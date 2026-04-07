"""
workload.py — VQE Workload, QuantumFuture, and Background Traffic (Extended)
=============================================================================
Supports all four architectural modes:

  MODE_BASELINE           (SBQ)  — iterative loop with random queue delay
  MODE_PURE_FAAS          (PF)   — stateless: drops session each iteration
  MODE_STATIC_RESERVATION (SR)   — QPU locked for full job duration
  MODE_PILOT_QUANTUM      (PQ)   — Session-based Pilot abstraction
  MODE_ENTANGLED          (EFaaS)— Quantum Future + session-aware scheduling
"""

from __future__ import annotations

import random
import math
import re
from typing import Optional, TYPE_CHECKING

import numpy as np
import simpy

from qiskit.circuit.library import RealAmplitudes
from qiskit.circuit.library import EfficientSU2
from qiskit.circuit.library import TwoLocal
from qiskit.quantum_info import SparsePauliOp
from qiskit.quantum_info import Statevector
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit_aer.primitives import Estimator as AerEstimator
import qiskit.qasm2 as qasm2
import os

import config
from scheduler import EntangledFaaSScheduler, QuantumJob, ClassicalJob

try:
    from qiskit_ibm_runtime import QiskitRuntimeService, Session
    from qiskit_ibm_runtime import EstimatorV2 as IBMRuntimeEstimator
    from qiskit_ibm_runtime.fake_provider import FakeNighthawk, FakeSherbrooke, FakeTorontoV2, FakeWashingtonV2
except ImportError:
    QiskitRuntimeService = None
    Session = None
    IBMRuntimeEstimator = None
    FakeNighthawk = None
    FakeSherbrooke = None
    FakeTorontoV2 = None
    FakeWashingtonV2 = None

if TYPE_CHECKING:
    from sim_env import ClassicalCloud, QuantumCloud
    from tracker import MetricsTracker


# ─────────────────────────────────────────────────────────────────────────────
# LiH Hamiltonian (STO-3G, Jordan-Wigner, 4 qubits, frozen-core)
# ─────────────────────────────────────────────────────────────────────────────

LIH_HAMILTONIAN = SparsePauliOp.from_list([
    ("IIII", -7.499),
    ("IIIZ", +0.171),
    ("IIZI", -0.171),
    ("IZII", +0.222),
    ("ZIII", +0.222),
    ("IIZZ", +0.123),
    ("IZZZ", -0.045),
    ("ZZZZ", +0.012),
    ("XXXX", +0.044),
    ("YYYY", +0.044),
    ("XXYY", +0.044),
    ("YYXX", +0.044),
])


# ─────────────────────────────────────────────────────────────────────────────
# Noise model — drift-aware depolarising
# ─────────────────────────────────────────────────────────────────────────────

def build_noise_model(drift_factor: float) -> NoiseModel:
    """
    error_rate = base_depol_error × (1 + drift_factor)
    drift_factor = min(Δt_wait / τ_drift, max_drift_factor)
    """
    error_rate = config.base_depol_error * (1.0 + drift_factor)
    error_rate = min(error_rate, 0.25)
    noise_model = NoiseModel()
    dp_1q = depolarizing_error(error_rate, 1)
    dp_2q = depolarizing_error(min(error_rate * 10, 0.5), 2)
    noise_model.add_all_qubit_quantum_error(dp_1q, ["u", "u1", "u2", "u3"])
    noise_model.add_all_qubit_quantum_error(dp_2q, ["cx", "ecr"])
    return noise_model


def _backend_kind() -> str:
    return config.QUANTUM_BACKEND.strip().lower().replace("-", "_")


def _is_ibm_backend() -> bool:
    return _backend_kind() in {"ibm", "ibm_runtime", "runtime", "ibm_quantum"}


def _is_fake_backend() -> bool:
    return _backend_kind().startswith("fake_")


def _as_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (list, tuple)) and value:
        return _as_float(value[0])
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except Exception:
        return float(value)


def _create_ibm_service() -> "QiskitRuntimeService":
    if QiskitRuntimeService is None:
        raise RuntimeError(
            "IBM Runtime backend requested, but qiskit-ibm-runtime is not installed. "
            "Install it with `pip install qiskit-ibm-runtime` and configure an IBM account."
        )

    service_kwargs = {}
    if config.IBM_RUNTIME_CHANNEL:
        service_kwargs["channel"] = config.IBM_RUNTIME_CHANNEL
    return QiskitRuntimeService(**service_kwargs)


def _select_ibm_backend(service: "QiskitRuntimeService", min_qubits: int):
    backend_name = config.IBM_BACKEND_NAME
    if backend_name:
        backend = service.backend(backend_name)
    else:
        backend = service.least_busy(operational=True, simulator=False, min_num_qubits=min_qubits)

    if backend.num_qubits < min_qubits:
        raise RuntimeError(
            f"IBM backend {backend.name} only exposes {backend.num_qubits} qubits, "
            f"but the current circuit needs {min_qubits}."
        )
    return backend


def _create_fake_backend():
    if FakeNighthawk is None:
        raise RuntimeError(
            "Fake IBM backend requested, but qiskit-ibm-runtime is not installed. "
            "Install it with `pip install qiskit-ibm-runtime`."
        )

    name = (config.FAKE_BACKEND_NAME or _backend_kind()).strip().lower().replace("-", "_")
    fake_backends = {
        "fake_nighthawk": FakeNighthawk,
        "fake_sherbrooke": FakeSherbrooke,
        "fake_toronto": FakeTorontoV2,
        "fake_washington": FakeWashingtonV2,
    }
    if name not in fake_backends:
        raise ValueError(
            f"Unknown fake backend '{name}'. Choose one of: {', '.join(sorted(fake_backends))}."
        )
    return fake_backends[name]()


# ─────────────────────────────────────────────────────────────────────────────
# QuantumFuture — async promise abstraction (Section III-D / Eq. 5)
# ─────────────────────────────────────────────────────────────────────────────

class QuantumFuture:
    """
    Quantum Future programming primitive.
    Classical process does t_async speculative work, then yield future.
    Implements: L_ent = max(t_cpu − t_async, 0) + t_qpu + t_net
    """

    def __init__(self, env: simpy.Environment) -> None:
        self.env = env
        self._resolve_event = env.event()
    def resolve(self, energy: float, variance: float, metadata: dict) -> None:
        self.energy   = energy
        self.variance = variance
        self.metadata = metadata
        
        # Principled reconciliation check (Sect VI-D)
        if self.metadata.get("drift_factor", 0.0) > 1.5:
             # Just a log line to simulate that the speculative gradient 
             # deviated too much due to severe drift.
             self.metadata["reconciliation_failed"] = True
             
        # Resolve will be handled in separate record_reconcile call in _finish_iteration
             
        if not self._resolve_event.triggered:
            self._resolve_event.succeed()

    def await_result(self):
        yield self._resolve_event


# ─────────────────────────────────────────────────────────────────────────────
# VQEJob — full iterative VQE loop (all 4 modes)
# ─────────────────────────────────────────────────────────────────────────────

class VQEJob:
    """
    Simulates the VQE iterative loop for LiH (Section V).

    Mode-specific behaviour:
      SBQ  — standard loop; session flag set but scheduler ignores it
      PF   — session flag dropped each iteration (stateless FaaS)
      SR   — acquires QPU resource BEFORE t_cpu step and holds it throughout
              (exclusive reservation → zero queue wait, low QDC)
      EFaaS— submits circuit → t_async speculative work → await Quantum Future
    """

    JOB_PREFIX = "vqe_lih"

    def __init__(
        self,
        env:             simpy.Environment,
        scheduler:       EntangledFaaSScheduler,
        classical_cloud: "ClassicalCloud",
        quantum_cloud:   "QuantumCloud",
        tracker:         "MetricsTracker",
        mode:            str,
        rng:             random.Random,
        level:           str = config.LEVEL_SIMPLE,
    ) -> None:
        self.env             = env
        self.scheduler       = scheduler
        self.classical_cloud = classical_cloud
        self.quantum_cloud   = quantum_cloud
        self.tracker         = tracker
        self.mode            = mode
        self.rng             = rng
        self.level           = level

        self._is_entangled = (mode == config.MODE_ENTANGLED)
        self._is_sr        = (mode == config.MODE_STATIC_RESERVATION)
        self._is_pq        = (mode == config.MODE_PILOT_QUANTUM)
        self._is_pf        = (mode == config.MODE_PURE_FAAS)

        self.ansatz = self._build_realistic_circuit(level)
        self.observable = self._build_observable(self.ansatz.num_qubits)
        self._save_circuit_once()

        n_params = self.ansatz.num_parameters
        self.params = np.array(
            [rng.uniform(-0.1, 0.1) for _ in range(n_params)], dtype=float
        )

        # SPSA hyperparameters
        self._spsa_a     = 0.2
        self._spsa_c     = 0.1
        self._spsa_A     = 10.0
        self._spsa_alpha = 0.602
        self._spsa_gamma = 0.101

        self.iteration           = 0
        self.last_shot_sim_time  = 0.0
        self.prev_energy: Optional[float] = None

        # Static Reservation: pick one QPU for the whole job duration
        self._sr_qpu = None
        if self._is_sr:
            self._sr_qpu = self.quantum_cloud.qpus[0]

    def _build_realistic_circuit(self, level: str):
        """Builds a realistic circuit based on complexity level.

                Circuits sourced from standard Qiskit library / textbook VQA families:
                    Simple  : EfficientSU2 (4q, 2 reps, linear entanglement)
                    Medium  : EfficientSU2 (6q, 3 reps, linear entanglement)
                    Source: qiskit.circuit.library.EfficientSU2
          Complex : EfficientSU2 (8q, 5 reps, full entanglement)
                    Source: qiskit.circuit.library.EfficientSU2
                    Emulates deep ansatz circuits used in hardware-efficient VQE.
        """
        parsed = self._build_circuit_from_spec(level)
        if parsed is not None:
            return parsed

        if level == config.LEVEL_SIMPLE:
            return EfficientSU2(num_qubits=4, reps=2, entanglement="linear")
        elif level == config.LEVEL_MEDIUM:
            # EfficientSU2: 6 qubits, 3 reps, linear entanglement
            # Represents a medium-depth hardware-efficient VQE ansatz
            return EfficientSU2(num_qubits=6, reps=3, entanglement="linear")
        elif level == config.LEVEL_COMPLEX:
            # EfficientSU2: 8 qubits, 5 reps, full entanglement
            # Deep hardware-efficient ansatz as used in e.g. IBM Eagle experiments
            return EfficientSU2(num_qubits=8, reps=5, entanglement="full")
        elif level == config.LEVEL_COMPLEX_EFFSU2_10Q_R6_FULL:
            return EfficientSU2(num_qubits=10, reps=6, entanglement="full")
        elif level == config.LEVEL_COMPLEX_EFFSU2_12Q_R5_LINEAR:
            return EfficientSU2(num_qubits=12, reps=5, entanglement="linear")
        elif level == config.LEVEL_COMPLEX_REALAMP_10Q_R7:
            return RealAmplitudes(num_qubits=10, reps=7, entanglement="linear")
        elif level == config.LEVEL_COMPLEX_TWOLOCAL_10Q_R6_CZ:
            return TwoLocal(
                num_qubits=10,
                rotation_blocks=["ry", "rz"],
                entanglement_blocks="cz",
                entanglement="full",
                reps=6,
            )
        elif level == config.LEVEL_COMPLEX_TWOLOCAL_12Q_R5_CX:
            return TwoLocal(
                num_qubits=12,
                rotation_blocks=["rx", "rz"],
                entanglement_blocks="cx",
                entanglement="linear",
                reps=5,
            )
        return RealAmplitudes(num_qubits=4, reps=2)

    def _build_circuit_from_spec(self, level: str):
        """
        Parse standard circuit specs used by main experiment catalogs.

        Supported formats:
          - std_efficientsu2_<n>q_r<reps>_<entanglement>
          - std_realamplitudes_<n>q_r<reps>_<entanglement>
          - std_twolocal_<n>q_r<reps>_<ent_block>_<entanglement>
        """
        lvl = level.strip().lower()

        m = re.fullmatch(r"std_efficientsu2_(\d+)q_r(\d+)_([a-z_]+)", lvl)
        if m:
            n_qubits = int(m.group(1))
            reps = int(m.group(2))
            ent = m.group(3)
            return EfficientSU2(num_qubits=n_qubits, reps=reps, entanglement=ent)

        m = re.fullmatch(r"std_realamplitudes_(\d+)q_r(\d+)_([a-z_]+)", lvl)
        if m:
            n_qubits = int(m.group(1))
            reps = int(m.group(2))
            ent = m.group(3)
            return RealAmplitudes(num_qubits=n_qubits, reps=reps, entanglement=ent)

        m = re.fullmatch(r"std_twolocal_(\d+)q_r(\d+)_([a-z0-9_]+)_([a-z_]+)", lvl)
        if m:
            n_qubits = int(m.group(1))
            reps = int(m.group(2))
            ent_block = m.group(3)
            ent = m.group(4)
            return TwoLocal(
                num_qubits=n_qubits,
                rotation_blocks=["ry", "rz"],
                entanglement_blocks=ent_block,
                entanglement=ent,
                reps=reps,
            )

        return None

    def _build_observable(self, n_qubits: int) -> SparsePauliOp:
        """
        Realistic observable per circuit size.

        - 4 qubits: LiH Hamiltonian used in the original setup.
        - >4 qubits: transverse-field Ising chain (common VQA benchmark).
        """
        if n_qubits == 4:
            return LIH_HAMILTONIAN

        terms = []
        # ZZ nearest-neighbor interactions
        for i in range(n_qubits - 1):
            p = ["I"] * n_qubits
            p[i] = "Z"
            p[i + 1] = "Z"
            terms.append(("".join(p), -1.0))

        # Transverse field X terms
        for i in range(n_qubits):
            p = ["I"] * n_qubits
            p[i] = "X"
            terms.append(("".join(p), -0.5))

        return SparsePauliOp.from_list(terms)

    def _save_circuit_once(self):
        """Saves the circuit to QASM file for persistence."""
        os.makedirs(config.CIRCUITS_DIR, exist_ok=True)
        level_tag = re.sub(r"[^a-z0-9]+", "_", self.level.lower()).strip("_")
        mode_tag = re.sub(r"[^a-z0-9]+", "_", self.mode.lower()).strip("_")
        fname = f"circuit_{level_tag}_{mode_tag}.qasm"
        path = os.path.join(config.CIRCUITS_DIR, fname)
        try:
            circuit_to_dump = self.ansatz
            if circuit_to_dump.num_parameters > 0:
                # QASM2 export requires concrete values for all parameters.
                zero_params = [0.0] * circuit_to_dump.num_parameters
                circuit_to_dump = circuit_to_dump.assign_parameters(zero_params, inplace=False)
            with open(path, "w") as f:
                qasm2.dump(circuit_to_dump, f)
            print(f"  [workload] Saved circuit → {path} (Depth: {self.ansatz.decompose().depth()})")
        except Exception as e:
            print(f"  [workload] Failed to save circuit: {e}")

    # ── SimPy process ─────────────────────────────────────────────────────────

    def run(self):
        for iteration in range(config.max_iter):
            self.iteration = iteration
            iter_start     = self.env.now

            if self._is_sr:
                yield from self._run_static_reservation(iteration, iter_start)
            else:
                yield from self._run_standard_or_entangled(iteration, iter_start)

    # ── Static Reservation path ───────────────────────────────────────────────

    def _run_static_reservation(self, iteration: int, iter_start: float):
        """
        QPU is reserved exclusively:
          • Acquire QPU resource ONCE at top of iteration.
          • Run t_cpu while QPU is held (locked, idle → QDC penalty).
          • Execute t_qpu.
          • Release.
        """
        sr_qpu = self._sr_qpu

        with sr_qpu.resource.request() as qpu_req:
            yield qpu_req   # get exclusive access

            # Classical compute while QPU is locked (paid idleness)
            cjob = ClassicalJob(
                job_id = f"{self.JOB_PREFIX}_classical",
                arrival_time = self.env.now,
            )
            yield self.scheduler.submit(cjob)

            # QPU execution
            t_qpu_actual = config.t_qpu_base + self.rng.uniform(-0.3, 0.3)
            exec_start   = self.env.now
            yield self.env.timeout(t_qpu_actual)
            exec_dur     = self.env.now - exec_start

            sr_qpu.total_active_time += exec_dur
            sr_qpu.register_session(self.JOB_PREFIX)
            sr_qpu.touch_calibration()
            self.tracker.record_qpu_active(sr_qpu.qpu_id, exec_dur)

            drift_f = sr_qpu.drift_factor(self.JOB_PREFIX)
            qpu_meta = {
                "qpu_id":       sr_qpu.qpu_id,
                "had_recalib":  False,
                "drift_factor": drift_f,
                "exec_time":    exec_dur,
            }

        yield from self._finish_iteration(iteration, iter_start, qpu_meta)

    # ── SBQ / PF / EFaaS path ─────────────────────────────────────────────────

    def _run_standard_or_entangled(self, iteration: int, iter_start: float):
        # 1. Classical Job via Unified Scheduler Queue
        cjob = ClassicalJob(
            job_id = f"{self.JOB_PREFIX}_classical",
            arrival_time = self.env.now,
        )
        yield self.scheduler.submit(cjob)

        # 2. Submit quantum circuit
        #    PF: always drop session (stateless FaaS drops context)
        has_session = False if self._is_pf else True
        qjob = QuantumJob(
            job_id            = self.JOB_PREFIX,
            has_session       = has_session,
            arrival_time      = self.env.now,
            last_shot_time    = self.last_shot_sim_time,
            fair_share_weight = 1.0,
            t_qpu             = config.t_qpu_base + self.rng.uniform(-0.3, 0.3),
        )
        qpu_done = self.scheduler.submit(qjob)

        # 3. Speculative classical work (Quantum Future — EFaaS only)
        if self._is_entangled:
            t_spec = min(config.t_async, config.tau_drift - config.epsilon)
            yield self.env.timeout(t_spec)

        # 4. Await QPU result
        yield qpu_done
        qpu_meta: dict = qpu_done.value

        yield from self._finish_iteration(iteration, iter_start, qpu_meta)

    # ── Shared finish logic ───────────────────────────────────────────────────

    def _finish_iteration(self, iteration: int, iter_start: float, qpu_meta: dict):
        energy, variance = self._evaluate_energy(qpu_meta)
        self.params      = self._spsa_step(iteration, energy)

        shot_time    = self.env.now
        ttns         = shot_time - iter_start
        drift_f      = qpu_meta.get("drift_factor", 0.0)
        had_recalib  = qpu_meta.get("had_recalib", False)
        qpu_id       = qpu_meta.get("qpu_id", 0)

        # Reconcile Quantum Future (Sect VI-D)
        qf = QuantumFuture(self.env)
        qf.resolve(energy, variance, qpu_meta)
        
        failed = qf.metadata.get("reconciliation_failed", False)
        self.tracker.record_reconcile(failed=failed)
        
        if failed:
             # Mock penalty: if speculative derivation was too far off due
             # to drift, the classical node requires an extra adjustment step
             c_penalty = ClassicalJob(
                 job_id = f"{self.JOB_PREFIX}_reconcile",
                 arrival_time = self.env.now,
                 t_cpu = config.t_cpu * 0.5
             )
             yield self.scheduler.submit(c_penalty)

        self.tracker.record_shot(
            iteration=iteration, sim_time=shot_time, ttns=ttns,
            energy=energy, variance=variance, drift_penalty=had_recalib,
            qpu_id=qpu_id, wait_time=ttns - qpu_meta.get("exec_time", 0.0) - config.t_cpu - (config.t_calib if had_recalib else 0.0),
        )

        # Convergence check
        if self.prev_energy is not None:
            if abs(energy - self.prev_energy) < config.energy_convergence_threshold:
                self.tracker.record_convergence(shot_time, iteration)

        self.prev_energy       = energy
        self.last_shot_sim_time = shot_time
        if True:  # always yield at least t_net
            yield self.env.timeout(config.t_net)

    # ── Energy evaluation (real Qiskit Aer) ──────────────────────────────────

    def _evaluate_energy(self, qpu_meta: dict) -> tuple[float, float]:
        drift_factor = qpu_meta.get("drift_factor", 0.0)
        backend_kind = _backend_kind()

        if backend_kind == "statevector":
            return self._statevector_fallback()

        if _is_ibm_backend():
            return self._evaluate_energy_ibm()

        if _is_fake_backend():
            return self._evaluate_energy_fake()

        noise_model = build_noise_model(drift_factor)
        try:
            estimator = AerEstimator()
            estimator.set_options(shots=config.shots, noise_model=noise_model)
            job_result = estimator.run(
                [self.ansatz], [self.observable], [self.params]
            ).result()
            energy = float(job_result.values[0])
            variance = float(job_result.metadata[0].get("variance", 0.0))
            return energy, variance
        except Exception:
            return self._statevector_fallback()

    def _evaluate_energy_ibm(self) -> tuple[float, float]:
        service = _create_ibm_service()
        backend = _select_ibm_backend(service, self.ansatz.num_qubits)

        bound_circuit = self.ansatz.assign_parameters(self.params, inplace=False)
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(bound_circuit)
        isa_observable = self.observable.apply_layout(isa_circuit.layout)

        with Session(backend=backend) as session:
            estimator = IBMRuntimeEstimator(mode=session)
            estimator.options.resilience_level = config.IBM_RESILIENCE_LEVEL
            job = estimator.run(
                [(isa_circuit, isa_observable, [self.params.tolist()])],
                precision=config.IBM_PRECISION,
            )
            pub_result = job.result()[0]

        energy = _as_float(pub_result.data.evs)
        variance = 0.0
        stds = getattr(pub_result.data, "stds", None)
        if stds is not None:
            variance = _as_float(stds) ** 2
        return energy, variance

    def _evaluate_energy_fake(self) -> tuple[float, float]:
        backend = _create_fake_backend()

        bound_circuit = self.ansatz.assign_parameters(self.params, inplace=False)
        pm = generate_preset_pass_manager(backend=backend, optimization_level=1)
        isa_circuit = pm.run(bound_circuit)
        isa_observable = self.observable.apply_layout(isa_circuit.layout)

        with Session(backend=backend) as session:
            estimator = IBMRuntimeEstimator(mode=session)
            estimator.options.resilience_level = config.IBM_RESILIENCE_LEVEL
            job = estimator.run(
                [(isa_circuit, isa_observable, [self.params.tolist()])],
                precision=config.IBM_PRECISION,
            )
            pub_result = job.result()[0]

        energy = _as_float(pub_result.data.evs)
        variance = 0.0
        stds = getattr(pub_result.data, "stds", None)
        if stds is not None:
            variance = _as_float(stds) ** 2
        return energy, variance

    def _statevector_fallback(self) -> tuple[float, float]:
        """Physics-based fallback: exact expectation from statevector."""
        bound = self.ansatz.assign_parameters(self.params, inplace=False)
        psi = Statevector.from_instruction(bound)
        energy = float(np.real(psi.expectation_value(self.observable)))
        h2 = (self.observable @ self.observable).simplify()
        exp2 = float(np.real(psi.expectation_value(h2)))
        variance = max(exp2 - energy * energy, 0.0)
        return energy, variance

    def _spsa_step(self, k: int, energy: float) -> np.ndarray:
        k1    = k + 1
        a_k   = self._spsa_a / (k1 + self._spsa_A) ** self._spsa_alpha
        c_k   = self._spsa_c / (k1 ** self._spsa_gamma)
        delta = np.array([self.rng.choice([-1, 1]) for _ in self.params])
        grad  = delta * (energy / c_k)
        return np.clip(self.params - a_k * grad, -math.pi, math.pi)


# ─────────────────────────────────────────────────────────────────────────────
# BackgroundBatchJobGenerator
# ─────────────────────────────────────────────────────────────────────────────

class BackgroundBatchJobGenerator:
    """
    Generates Poisson-arrival background batch quantum jobs (E_s=0).
    Models real-world multi-tenant QPU contention.
    """

    def __init__(
        self,
        env:          simpy.Environment,
        scheduler:    EntangledFaaSScheduler,
        tracker:      "MetricsTracker",
        arrival_rate: float,
        rng:          random.Random,
    ) -> None:
        self.env          = env
        self.scheduler    = scheduler
        self.tracker      = tracker
        self.arrival_rate = arrival_rate
        self.rng          = rng
        self._counter     = 0

    def run(self):
        while True:
            iat = self.rng.expovariate(self.arrival_rate)
            yield self.env.timeout(iat)
            self._counter += 1
            t_qpu_bg = self.rng.expovariate(1.0 / config.bg_t_qpu_mean)
            arrival_time = self.env.now
            qjob = QuantumJob(
                job_id            = f"bg_{self._counter}",
                has_session       = False,
                arrival_time      = arrival_time,
                last_shot_time    = arrival_time,
                fair_share_weight = 0.5,
                t_qpu             = t_qpu_bg,
            )
            self.tracker.bg_jobs_submitted += 1
            done = self.scheduler.submit(qjob)
            self.env.process(self._await(done, arrival_time))

    def _await(self, event: simpy.Event, arrival_time: float):
        yield event
        qpu_meta = event.value
        exec_dur = qpu_meta.get("exec_time", 0.0)
        had_recalib = qpu_meta.get("had_recalib", False)
        wait_time = self.env.now - arrival_time - exec_dur - (config.t_calib if had_recalib else 0.0)
        self.tracker.record_bg_job(wait_time)

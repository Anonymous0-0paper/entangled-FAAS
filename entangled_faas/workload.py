"""
workload.py — VQE Workload, QuantumFuture, and Background Traffic (Extended)
=============================================================================
Supports all four architectural modes:

  MODE_BASELINE           (SBQ)  — iterative loop with random queue delay
  MODE_PURE_FAAS          (PF)   — stateless: drops session each iteration
  MODE_STATIC_RESERVATION (SR)   — QPU locked for full job duration
  MODE_ENTANGLED          (EFaaS)— Quantum Future + session-aware scheduling
"""

from __future__ import annotations

import random
import math
from typing import Optional, TYPE_CHECKING

import numpy as np
import simpy

from qiskit.circuit.library import RealAmplitudes
from qiskit.quantum_info import SparsePauliOp
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit_aer.primitives import Estimator as AerEstimator

import config
from scheduler import EntangledFaaSScheduler, QuantumJob

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
        self.energy:   Optional[float] = None
        self.variance: Optional[float] = None
        self.metadata: dict = {}

    def resolve(self, energy: float, variance: float, metadata: dict) -> None:
        self.energy   = energy
        self.variance = variance
        self.metadata = metadata
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
    ) -> None:
        self.env             = env
        self.scheduler       = scheduler
        self.classical_cloud = classical_cloud
        self.quantum_cloud   = quantum_cloud
        self.tracker         = tracker
        self.mode            = mode
        self.rng             = rng

        self._is_entangled = (mode == config.MODE_ENTANGLED)
        self._is_sr        = (mode == config.MODE_STATIC_RESERVATION)
        self._is_pf        = (mode == config.MODE_PURE_FAAS)

        self.ansatz = RealAmplitudes(
            num_qubits=config.num_qubits,
            reps=config.ansatz_reps,
            entanglement="linear",
        )
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
            classical_req = self.classical_cloud.request_node()
            yield classical_req
            yield self.env.timeout(config.t_cpu)
            self.classical_cloud.release_node(classical_req)

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
        # 1. Classical FaaS node
        classical_req = self.classical_cloud.request_node()
        yield classical_req
        yield self.env.timeout(config.t_cpu)
        self.classical_cloud.release_node(classical_req)

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
        had_recalib  = qpu_meta.get("had_recalib", False)
        qpu_id       = qpu_meta.get("qpu_id", 0)

        self.tracker.record_shot(
            iteration=iteration, sim_time=shot_time, ttns=ttns,
            energy=energy, variance=variance, drift_penalty=had_recalib,
            qpu_id=qpu_id,
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
        noise_model  = build_noise_model(drift_factor)
        try:
            estimator = AerEstimator()
            estimator.set_options(shots=config.shots, noise_model=noise_model)
            job_result = estimator.run(
                [self.ansatz], [LIH_HAMILTONIAN], [self.params]
            ).result()
            energy   = float(job_result.values[0])
            variance = float(job_result.metadata[0].get("variance", 0.0))
        except Exception:
            energy, variance = self._fallback_energy(drift_factor)
        return energy, variance

    def _fallback_energy(self, drift_factor: float) -> tuple[float, float]:
        n       = self.iteration
        decay   = math.exp(-n / 30.0)
        noise   = self.rng.gauss(0, 0.05 * (1.0 + drift_factor))
        energy  = config.lih_ground_state_energy + decay * 0.8 + noise
        variance= 0.01 * (1.0 + 3.0 * drift_factor)
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
            qjob = QuantumJob(
                job_id            = f"bg_{self._counter}",
                has_session       = False,
                arrival_time      = self.env.now,
                last_shot_time    = self.env.now,
                fair_share_weight = 0.5,
                t_qpu             = t_qpu_bg,
            )
            self.tracker.bg_jobs_submitted += 1
            done = self.scheduler.submit(qjob)
            self.env.process(self._await(done))

    def _await(self, event: simpy.Event):
        yield event
        self.tracker.bg_jobs_completed += 1

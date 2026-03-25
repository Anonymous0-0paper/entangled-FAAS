"""
sim_env.py — SimPy Simulation Environment
==========================================
Implements the physical infrastructure layer of the Entangled-FaaS
architecture (Section III):

  • QPU        — Quantum Processing Unit with session + calibration state
  • ClassicalCloud — Pool of classical FaaS compute nodes
  • QuantumCloud   — Collection of QPUs + helper look-up methods

All timing values are in *simulated seconds* as advanced by the
SimPy discrete-event clock (env.now).
"""

from __future__ import annotations

import simpy
from dataclasses import dataclass, field
from typing import Dict, Optional, List

import config


# ─────────────────────────────────────────────────────────────────────────────
# QPU — Quantum Processing Unit
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QPU:
    """
    Represents a single Quantum Processing Unit in the QuantumCloud.

    Attributes
    ----------
    qpu_id : int
        Unique numeric identifier for this QPU.
    env : simpy.Environment
        Reference to the shared simulation clock.
    resource : simpy.Resource
        SimPy resource with capacity=1 (one circuit at a time).
    last_calib : float
        Simulation time at which the QPU was last (re-)calibrated.
        Used to evaluate the drift condition: (now − last_calib) < τ_drift.
    sessions : dict[str, float]
        Maps job_id → simulation timestamp of the last QPU shot for
        that job.  This represents the Session State Cache (C_q) that
        the Entangled-FaaS middleware holds for active iterators
        (Section III-B).
    total_active_time : float
        Accumulated simulated seconds the QPU spent executing circuits
        (used to compute the Quantum Duty Cycle, QDC).
    recalib_count : int
        Number of cold-start / re-calibration events triggered on this QPU.
    """

    qpu_id: int
    env: simpy.Environment
    resource: simpy.Resource = field(init=False)
    last_calib: float = field(init=False)
    sessions: Dict[str, float] = field(default_factory=dict)
    total_active_time: float = 0.0
    recalib_count: int = 0
    expected_completion: float = 0.0

    def __post_init__(self) -> None:
        # One quantum circuit can run at a time on a physical QPU
        self.resource = simpy.PreemptiveResource(self.env, capacity=1)
        # Initialise calibration timestamp to the simulation start time
        self.last_calib = self.env.now

    # ── Session helpers ───────────────────────────────────────────────────────

    def register_session(self, job_id: str) -> None:
        """Record / refresh the session entry for *job_id*."""
        self.sessions[job_id] = self.env.now

    def is_session_warm(self, job_id: str) -> bool:
        """
        Return True if *job_id* has a live session AND the calibration
        is still within the drift window τ_drift.

        Implements the guard condition from Algorithm 1, Line 6:
            (t_now − u*.last_calib) < τ_drift
        """
        if job_id not in self.sessions:
            return False
        elapsed = self.env.now - self.last_calib
        return elapsed < config.tau_drift

    def touch_calibration(self) -> None:
        """Refresh the calibration timestamp to the current sim time."""
        self.last_calib = self.env.now

    # ── Drift factor helper ───────────────────────────────────────────────────

    def drift_factor(self, job_id: str) -> float:
        """
        Compute the drift amplification scalar for noise modelling
        (Section IV-C of the paper):

            drift_factor = min(Δt_wait / τ_drift,  max_drift_factor)

        where Δt_wait is the time since the last shot for *job_id*.
        Returns 0.0 if the job has never been seen (first shot).
        """
        if job_id not in self.sessions:
            return 0.0
        delta_t = self.env.now - self.sessions[job_id]
        return min(delta_t / config.tau_drift, config.max_drift_factor)

    def __repr__(self) -> str:
        return (f"QPU(id={self.qpu_id}, "
                f"last_calib={self.last_calib:.1f}s, "
                f"sessions={list(self.sessions.keys())})")


# ─────────────────────────────────────────────────────────────────────────────
# ClassicalCloud — Pool of classical FaaS nodes (AWS Lambda / Kubernetes pods)
# ─────────────────────────────────────────────────────────────────────────────

class ClassicalCloud:
    """
    Abstracts the classical compute tier: N_classical independent FaaS
    nodes, each capable of running a single optimiser step at a time.

    Uses a single SimPy Resource pool so multiple VQE iterations can
    share the available classical capacity (fair-share by default).

    Parameters
    ----------
    env : simpy.Environment
    n_nodes : int
        Number of classical FaaS nodes (N_classical in config).
    """

    def __init__(self, env: simpy.Environment, n_nodes: int) -> None:
        self.env = env
        self.n_nodes = n_nodes
        # Pool resource — represents the node-slot pool
        self.pool: simpy.Resource = simpy.Resource(env, capacity=n_nodes)
        self.total_busy_time: float = 0.0

    def request_node(self) -> simpy.resources.resource.Request:
        """Return a SimPy Request for one classical FaaS node slot."""
        return self.pool.request()

    def release_node(self, req: simpy.resources.resource.Request) -> None:
        """Release a classical node slot back to the pool."""
        self.pool.release(req)

    @property
    def utilisation(self) -> float:
        """Current fraction of classical nodes in use."""
        return self.pool.count / self.n_nodes if self.n_nodes else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# QuantumCloud — Registry of QPUs + placement helpers
# ─────────────────────────────────────────────────────────────────────────────

class QuantumCloud:
    """
    Manages the collection of QPU objects and exposes routing helpers
    required by the Calibration-Aware Placement Strategy (Section IV-A).

    Parameters
    ----------
    env : simpy.Environment
    n_qpus : int
        Number of QPUs to instantiate (N_QPU in config).
    """

    def __init__(self, env: simpy.Environment, n_qpus: int) -> None:
        self.env = env
        self.qpus: List[QPU] = [QPU(qpu_id=i, env=env) for i in range(n_qpus)]

    # ── Calibration-Aware look-up (Algorithm 1, Line 5) ──────────────────────

    def find_cached_qpu(self, job_id: str) -> Optional[QPU]:
        """
        Return the QPU that holds a *warm* session for *job_id*, or
        None if no QPU has valid calibration data for this job.

        A session is "warm" when:
          • The QPU's sessions dict contains job_id (previous shot recorded)
          • (env.now − qpu.last_calib) < τ_drift          (Eq. 3 guard)
        """
        for qpu in self.qpus:
            if qpu.is_session_warm(job_id):
                return qpu
        return None

    def find_any_available_qpu(self) -> Optional[QPU]:
        """
        Return the first QPU whose SimPy resource queue is empty (idle),
        for standard fair-queue scheduling of batch jobs (Algorithm 1, Line 15).
        """
        for qpu in self.qpus:
            if qpu.resource.count == 0:  # nobody holding the resource
                return qpu
        return None

    def least_loaded_qpu(self) -> QPU:
        """
        Return the QPU with the shortest expected completion time.
        """
        return min(self.qpus, key=lambda q: q.expected_completion)

    @property
    def total_active_time(self) -> float:
        """Sum of active execution time across all QPUs."""
        return sum(q.total_active_time for q in self.qpus)

    def __repr__(self) -> str:
        return f"QuantumCloud(n_qpus={len(self.qpus)})"

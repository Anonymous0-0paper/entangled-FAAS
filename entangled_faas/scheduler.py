"""
scheduler.py — Entangled-FaaS Co-Scheduler (Extended: all 4 modes)
====================================================================
Implements the scheduling logic for all four architectural modes:

  • MODE_BASELINE           (SBQ)  — α=β=0, FIFO + random queue delay
  • MODE_PURE_FAAS          (PF)   — stateless, FaaS cold-start + queue delay
  • MODE_STATIC_RESERVATION (SR)   — no queue wait, QPU exclusively locked
  • MODE_ENTANGLED          (EFaaS)— full co-scheduling, Algorithm 1

Priority score ρ_i (Eq. 4):
    ρ_i = α · 𝕀(E_s=1) + β · (τ_drift − Δt_wait)/τ_drift + γ · W_i
"""

from __future__ import annotations

import heapq
import random
import simpy
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

import config
from sim_env import QPU, QuantumCloud

if TYPE_CHECKING:
    from tracker import MetricsTracker


# ─────────────────────────────────────────────────────────────────────────────
# QuantumJob descriptor
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(order=False)
class QuantumJob:
    """Represents a single quantum circuit execution request."""
    job_id:            str
    has_session:       bool          # E_s ∈ {0, 1}
    arrival_time:      float
    last_shot_time:    float
    fair_share_weight: float = 1.0
    result_event:      Optional[simpy.Event] = field(default=None, compare=False)
    t_qpu:             float = config.t_qpu_base
    seq:               int   = 0

    def __lt__(self, other: "QuantumJob") -> bool:
        return self.seq < other.seq


# ─────────────────────────────────────────────────────────────────────────────
# Priority scoring — Equation (4)
# ─────────────────────────────────────────────────────────────────────────────

def compute_priority(
    job: QuantumJob,
    now: float,
    alpha: float,
    beta: float,
    gamma: float,
    tau_drift: float,
) -> float:
    """
    ρ_i = α · 𝕀(E_s=1) + β · (τ_drift − Δt_wait) / τ_drift + γ · W_i
    """
    indicator    = 1.0 if job.has_session else 0.0
    delta_t_wait = now - job.last_shot_time
    urgency      = max((tau_drift - delta_t_wait) / tau_drift, 0.0)
    return alpha * indicator + beta * urgency + gamma * job.fair_share_weight


# ─────────────────────────────────────────────────────────────────────────────
# EntangledFaaSScheduler — handles all 4 modes
# ─────────────────────────────────────────────────────────────────────────────

class EntangledFaaSScheduler:
    """
    Central co-scheduling controller.

    Mode-specific behaviour:
    ─────────────────────────
    SBQ  : α=β=0, random queue delay Uniform[10,60]+base before QPU access.
    PF   : Same as SBQ queue delay PLUS a FaaS container cold-start penalty
           Uniform[t_faas_coldstart_min, t_faas_coldstart_max]; session flag
           is suppressed (the stateless FaaS model drops context between calls).
    SR   : No queue delay (QPU is exclusively reserved), but the QPU resource
           is held (locked) for the entire t_cpu classical step, so it cannot
           serve other jobs → low QDC.
    EFaaS: Full calibration-aware routing per Algorithm 1.
    """

    def __init__(
        self,
        env:           simpy.Environment,
        quantum_cloud: QuantumCloud,
        tracker:       "MetricsTracker",
        mode:          str,
        rng:           random.Random,
        *,
        alpha:     float = config.alpha,
        beta:      float = config.beta,
        gamma:     float = config.gamma,
        tau_drift: float = config.tau_drift,
    ) -> None:
        self.env       = env
        self.qc        = quantum_cloud
        self.tracker   = tracker
        self.mode      = mode
        self.rng       = rng
        self.tau_drift = tau_drift

        self._is_entangled = (mode == config.MODE_ENTANGLED)
        self._is_sr        = (mode == config.MODE_STATIC_RESERVATION)
        self._is_pf        = (mode == config.MODE_PURE_FAAS)
        self._is_sbq       = (mode == config.MODE_BASELINE)

        # Scheduling weights (zeroed for non-Entangled modes)
        self._alpha = alpha if self._is_entangled else 0.0
        self._beta  = beta  if self._is_entangled else 0.0
        self._gamma = gamma

        # Min-heap of (-priority, seq, job)
        self._heap: list = []
        self._seq:  int  = 0

        self._job_arrived = env.event()
        self._process     = env.process(self._dispatch_loop())

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, job: QuantumJob) -> simpy.Event:
        """Enqueue job, return Quantum Future event."""
        job.result_event = self.env.event()
        job.seq          = self._seq
        self._seq       += 1

        priority = compute_priority(
            job, self.env.now, self._alpha, self._beta, self._gamma,
            self.tau_drift,
        )
        heapq.heappush(self._heap, (-priority, job.seq, job))

        if not self._job_arrived.triggered:
            self._job_arrived.succeed()

        return job.result_event

    # ── Dispatcher loop ───────────────────────────────────────────────────────

    def _dispatch_loop(self):
        while True:
            if not self._heap:
                self._job_arrived = self.env.event()
                yield self._job_arrived

            job = self._pop_best_job()
            if job is None:
                continue
            self.env.process(self._execute_job(job))

    def _pop_best_job(self) -> Optional[QuantumJob]:
        if not self._heap:
            return None
        # Re-score at current time
        rescored = []
        while self._heap:
            _, seq, job = heapq.heappop(self._heap)
            new_p = compute_priority(
                job, self.env.now, self._alpha, self._beta, self._gamma,
                self.tau_drift,
            )
            rescored.append((-new_p, seq, job))
        heapq.heapify(rescored)
        _, _, best = heapq.heappop(rescored)
        for item in rescored:
            heapq.heappush(self._heap, item)
        return best

    # ── Per-job execution process (Algorithm 1) ───────────────────────────────

    def _execute_job(self, job: QuantumJob):
        """Route and execute one quantum job, mode-aware."""
        had_recalib = False

        # ── Pre-QPU delays (mode-specific) ────────────────────────────────────

        if self._is_entangled:
            # Algorithm 1: calibration-aware placement
            cached = self.qc.find_cached_qpu(job.job_id)
            if cached is not None:
                target_qpu = cached
                # Cache hit — no extra delay
            else:
                # Cold start
                stale_qpu = next(
                    (q for q in self.qc.qpus if job.job_id in q.sessions), None
                )
                target_qpu = stale_qpu or self.qc.least_loaded_qpu()
                had_recalib = True
                yield self.env.timeout(config.t_calib)
                target_qpu.touch_calibration()
                target_qpu.recalib_count += 1

        elif self._is_sr:
            # Static Reservation: no queue wait, but QPU stays locked
            # (handled by holding the resource during t_cpu — see workload.py)
            target_qpu = self.qc.least_loaded_qpu()

        else:
            # SBQ / PF: random multi-tenant queue delay
            t_queue = self.rng.uniform(10.0, 60.0) + config.t_queue_base
            yield self.env.timeout(t_queue)

            # Pure FaaS: additional FaaS container cold-start
            if self._is_pf:
                t_cold = self.rng.uniform(
                    config.t_faas_coldstart_min,
                    config.t_faas_coldstart_max,
                )
                yield self.env.timeout(t_cold)

            target_qpu = self.qc.least_loaded_qpu()

        # ── Acquire QPU resource ──────────────────────────────────────────────
        with target_qpu.resource.request() as req:
            yield req

            exec_start = self.env.now
            yield self.env.timeout(job.t_qpu)
            exec_dur = self.env.now - exec_start

            target_qpu.total_active_time += exec_dur
            target_qpu.register_session(job.job_id)
            target_qpu.touch_calibration()

            self.tracker.record_qpu_active(target_qpu.qpu_id, exec_dur)

            drift_f = target_qpu.drift_factor(job.job_id)
            job.result_event.succeed({
                "qpu_id":       target_qpu.qpu_id,
                "had_recalib":  had_recalib,
                "drift_factor": drift_f,
                "exec_time":    exec_dur,
            })

"""
scheduler.py — Entangled-FaaS Co-Scheduler (Extended: all 4 modes)
====================================================================
Implements the scheduling logic for all four architectural modes:

  • MODE_BASELINE           (SBQ)  — α=β=0, FIFO + random queue delay
  • MODE_PURE_FAAS          (PF)   — stateless, FaaS cold-start + queue delay
  • MODE_STATIC_RESERVATION (SR)   — no queue wait, QPU exclusively locked
  • MODE_PILOT_QUANTUM      (PQ)   — Pilot-Job: cold startup + warm session hits
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

    def __lt__(self, other) -> bool:
        return self.seq < other.seq

@dataclass(order=False)
class ClassicalJob:
    """Represents a single classical computation request."""
    job_id:            str
    arrival_time:      float
    fair_share_weight: float = 1.0
    result_event:      Optional[simpy.Event] = field(default=None, compare=False)
    t_cpu:             float = config.t_cpu
    seq:               int   = 0

    def __lt__(self, other) -> bool:
        return self.seq < other.seq


# ─────────────────────────────────────────────────────────────────────────────
# Priority scoring — Equation (4)
# ─────────────────────────────────────────────────────────────────────────────

def compute_priority(
    job,
    now: float,
    alpha: float,
    beta: float,
    gamma: float,
    tau_drift: float,
) -> float:
    """
    ρ_i = α · 𝕀(E_s=1) + β · (τ_drift − Δt_wait) / τ_drift + γ · W_i
    """
    if isinstance(job, ClassicalJob):
        # Classical jobs get standard fair share
        return gamma * job.fair_share_weight
        
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
    PQ   : Pilot-Job model. First task pays t_queue + t_pilot_init. Subsequent
           tasks in the same session bypass t_queue and pay t_pilot_overhead.
    EFaaS: Full calibration-aware routing per Algorithm 1.
    """

    def __init__(
        self,
        env:           simpy.Environment,
        quantum_cloud: QuantumCloud,
        classical_cloud: "ClassicalCloud",
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
        self.cc        = classical_cloud
        self.tracker   = tracker
        self.mode      = mode
        self.rng       = rng
        self.tau_drift = tau_drift

        self._is_entangled = (mode == config.MODE_ENTANGLED)
        self._is_sr        = (mode == config.MODE_STATIC_RESERVATION)
        self._is_pq        = (mode == config.MODE_PILOT_QUANTUM)
        self._is_pf        = (mode == config.MODE_PURE_FAAS)
        self._is_sbq       = (mode == config.MODE_BASELINE)

        # Scheduling weights (zeroed for non-Entangled modes)
        self._alpha = alpha if self._is_entangled else 0.0
        self._beta  = beta  if self._is_entangled else 0.0
        self._gamma = gamma
        self._base_beta = self._beta
        self._base_gamma = self._gamma
        
        # Track Pilot-Quantum active sessions
        self._pilot_ready: bool = False

        # Min-heap of (-priority, seq, job)
        self._heap: list = []
        self._seq:  int  = 0

        self._job_arrived = env.event()
        self._process     = env.process(self._dispatch_loop())

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, job) -> simpy.Event:
        """Enqueue job (Quantum or Classical), return result event."""
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
            
            # Record queue wait time
            self.tracker.record_queue_wait(self.env.now - job.arrival_time)
            
            self.env.process(self._execute_job(job))

    def _pop_best_job(self):
        if not self._heap:
            return None
            
        # Rescore only periodically to avoid O(N log N) every pop
        if getattr(self, '_last_rescore_time', -1) < self.env.now - 1.0:
            rescored = []
            while self._heap:
                _, seq, job = heapq.heappop(self._heap)
                new_p = compute_priority(
                    job, self.env.now, self._alpha, self._beta, self._gamma,
                    self.tau_drift,
                )
                rescored.append((-new_p, seq, job))
            heapq.heapify(rescored)
            self._heap = rescored
            self._last_rescore_time = self.env.now
            
        _, _, best = heapq.heappop(self._heap)
        return best

    # ── Per-job execution process (Algorithm 1) ───────────────────────────────

    def _execute_job(self, job):
        """Route and execute job (Quantum or Classical), mode-aware."""
        
        if isinstance(job, ClassicalJob):
            # Algorithm 1: assign_classical_node
            req = self.cc.request_node()
            yield req
            t_start = self.env.now
            yield self.env.timeout(job.t_cpu)
            self.tracker.record_classical_active(self.env.now - t_start)
            self.cc.release_node(req)
            job.result_event.succeed({})
            return

        had_recalib = False
        needs_calib = False

        # ── Pre-QPU delays (mode-specific) ────────────────────────────────────

        if self._is_entangled:
            # Algorithm 1: calibration-aware placement
            if job.has_session:
                # Stateful iterations (VQE path) use calibration-aware cache lookup.
                u_star = self.qc.find_cached_qpu(job.job_id)
                if u_star:
                    target_qpu = u_star
                    session_age = self.env.now - u_star.sessions[job.job_id]
                    is_session_warm = session_age < self.tau_drift
                    self.tracker.record_session_request(hit=is_session_warm)
                else:
                    # Cache miss: reuse stale location if known, else place by load.
                    for q in self.qc.qpus:
                        if job.job_id in q.sessions:
                            target_qpu = q
                            break
                    else:
                        target_qpu = self.qc.least_loaded_qpu()
                    self.tracker.record_session_request(hit=False)

                # Recalibrate only if this QPU has actually drifted past threshold.
                if (self.env.now - target_qpu.last_calib) > self.tau_drift:
                    needs_calib = True
                    target_qpu.expected_completion += config.t_calib

                target_qpu.expected_completion += job.t_qpu
                req_priority = -2  # Keep stateful VQE ahead of best-effort background jobs.
            else:
                # Best-effort background quantum jobs should not force a cold recalibration.
                # They run on the least-loaded QPU without forcing calibration.
                # This preserves QPU throughput while keeping stateful iterations responsive.
                target_qpu = self.qc.least_loaded_qpu()

                target_qpu.expected_completion += job.t_qpu
                req_priority = 2

        elif self._is_pq:
            # Pilot-Quantum: one pilot startup, then all tasks use warm pilot path.
            if self._pilot_ready:
                yield self.env.timeout(config.t_pilot_overhead)
            else:
                t_queue = self.rng.lognormvariate(config.t_queue_mu, config.t_queue_sigma)
                yield self.env.timeout(t_queue)
                yield self.env.timeout(config.t_pilot_init)
                self._pilot_ready = True

            target_qpu = self.qc.least_loaded_qpu()

            target_qpu.expected_completion += job.t_qpu
            req_priority = 5 # Medium priority

            # PQ still checks for drift (Eq. 1 indicator)
            if (self.env.now - target_qpu.last_calib) > self.tau_drift:
                needs_calib = True
                target_qpu.expected_completion += config.t_calib

        elif self._is_sr:
            # Static Reservation: no queue wait, but QPU stays locked
            # (handled by holding the resource during t_cpu — see workload.py)
            target_qpu = self.qc.least_loaded_qpu()
            target_qpu.expected_completion += job.t_qpu
            req_priority = 0
            
            # SR: Still subject to drift if the reservation is long (Eq. 1)
            if (self.env.now - target_qpu.last_calib) > self.tau_drift:
                needs_calib = True
                target_qpu.expected_completion += config.t_calib

        else:
            # SBQ / PF: Lognormal multi-tenant queue delay (simulates 'Eagle r3' trace)
            t_queue = self.rng.lognormvariate(config.t_queue_mu, config.t_queue_sigma)
            yield self.env.timeout(t_queue)

            # Pure FaaS: additional FaaS container cold-start
            if self._is_pf:
                t_cold = self.rng.uniform(
                    config.t_faas_coldstart_min,
                    config.t_faas_coldstart_max,
                )
                yield self.env.timeout(t_cold)

            target_qpu = self.qc.least_loaded_qpu()
            target_qpu.expected_completion += job.t_qpu
            req_priority = 10 # Lower priority for background/baseline jobs
            
            # Baseline Drift Check (Eq. 1 indicator)
            if (self.env.now - target_qpu.last_calib) > self.tau_drift:
                needs_calib = True
                target_qpu.expected_completion += config.t_calib

        # ── Acquire QPU resource ──────────────────────────────────────────────
        while True:
            with target_qpu.resource.request(priority=req_priority, preempt=True) as req:
                yield req
                
                try:
                    if needs_calib:
                        t_cal_start = self.env.now
                        yield self.env.timeout(config.t_calib)
                        self.tracker.record_calib_time(self.env.now - t_cal_start)
                        had_recalib = True
                        target_qpu.touch_calibration()
                        target_qpu.recalib_count += 1
                        needs_calib = False # Done calibrating

                    exec_start = self.env.now
                    yield self.env.timeout(job.t_qpu)
                    exec_dur = self.env.now - exec_start

                    target_qpu.total_active_time += exec_dur
                    target_qpu.register_session(job.job_id)
                    target_qpu.touch_calibration()
                    target_qpu.expected_completion -= (job.t_qpu + (config.t_calib if had_recalib else 0))
                    target_qpu.expected_completion = max(0, target_qpu.expected_completion)

                    self.tracker.record_qpu_active(target_qpu.qpu_id, exec_dur)

                    drift_f = target_qpu.drift_factor(job.job_id)
                    job.result_event.succeed({
                        "qpu_id":       target_qpu.qpu_id,
                        "had_recalib":  had_recalib,
                        "drift_factor": drift_f,
                        "exec_time":    exec_dur,
                    })
                    break # Success, exit loop
                except simpy.Interrupt:
                    # Job was preempted
                    self.tracker.record_preemption()
                    job.t_qpu -= (self.env.now - exec_start) # Deduct elapsed time
                    if job.t_qpu <= 0:
                         # Finished right when preempted
                         job.result_event.succeed({
                            "qpu_id":       target_qpu.qpu_id,
                            "had_recalib":  had_recalib,
                            "drift_factor": target_qpu.drift_factor(job.job_id),
                            "exec_time":    job.t_qpu + (self.env.now - exec_start),
                         })
                         target_qpu.expected_completion -= (job.t_qpu + (config.t_calib if had_recalib else 0))
                         target_qpu.expected_completion = max(0, target_qpu.expected_completion)
                         break
                    # Will loop and re-request

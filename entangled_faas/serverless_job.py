"""
serverless_job.py
=================
Minimal Qiskit Serverless entrypoint for one Entangled-FaaS simulation task.

This script supports two execution modes:
1) Local CLI run (for testing)
2) Qiskit Serverless job run (through get_arguments/save_result)
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from typing import Any, Dict

import config
from main import run_simulation

try:
    from qiskit_serverless import get_arguments, save_result
except Exception:
    get_arguments = None
    save_result = None


_MODE_ALIASES = {
    "SBQ": config.MODE_BASELINE,
    "PF": config.MODE_PURE_FAAS,
    "SR": config.MODE_STATIC_RESERVATION,
    "PQ": config.MODE_PILOT_QUANTUM,
    "EFAAS": config.MODE_ENTANGLED,
}


def _resolve_mode(mode: str) -> str:
    m = mode.strip()
    return _MODE_ALIASES.get(m.upper(), m)


@contextlib.contextmanager
def _temporary_config(overrides: Dict[str, Any]):
    original = {}
    try:
        for key, value in overrides.items():
            if hasattr(config, key):
                original[key] = getattr(config, key)
                setattr(config, key, value)
        yield
    finally:
        for key, value in original.items():
            setattr(config, key, value)


def run_one(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = _resolve_mode(payload.get("mode", config.MODE_ENTANGLED))
    level = payload.get("level", config.LEVEL_SIMPLE)
    seed_offset = int(payload.get("seed_offset", 0))
    verbose = bool(payload.get("verbose", False))

    alpha = float(payload.get("alpha", config.alpha))
    beta = float(payload.get("beta", config.beta))
    gamma = float(payload.get("gamma", config.gamma))
    tau_drift = float(payload.get("tau_drift", config.tau_drift))

    cfg_overrides = dict(payload.get("config_overrides", {}))

    with _temporary_config(cfg_overrides):
        summary = run_simulation(
            mode=mode,
            seed_offset=seed_offset,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            tau_drift=tau_drift,
            level=level,
            verbose=verbose,
        )

    result = {
        "input": {
            "mode": mode,
            "level": level,
            "seed_offset": seed_offset,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "tau_drift": tau_drift,
            "config_overrides": cfg_overrides,
        },
        "summary": summary,
    }

    output_filename = payload.get("output_filename")
    if output_filename:
        output_path = os.path.join(config.OUTPUT_DIR, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

    return result


def run_serverless_entry() -> Dict[str, Any]:
    if get_arguments is None or save_result is None:
        raise RuntimeError(
            "qiskit-serverless is not available in this environment. "
            "Install dependencies and run on a configured serverless runtime."
        )

    payload = get_arguments() or {}
    result = run_one(payload)
    save_result(result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one Entangled-FaaS serverless-style task.")
    parser.add_argument("--payload", type=str, default=None, help="Inline JSON payload string")
    parser.add_argument("--payload-file", type=str, default=None, help="Path to JSON payload file")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.payload or args.payload_file:
        if args.payload_file:
            with open(args.payload_file, "r") as f:
                payload = json.load(f)
        else:
            payload = json.loads(args.payload)
        result = run_one(payload)
        print(json.dumps(result, indent=2))
        return

    run_serverless_entry()


if __name__ == "__main__":
    main()

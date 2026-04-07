"""
serverless_submit.py
====================
Submit helper for Qiskit Serverless.

This script is intentionally API-flexible: it tries commonly used submit APIs
so the project can work across minor qiskit-serverless API revisions.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict


def _load_payload(payload_file: str) -> Dict[str, Any]:
    with open(payload_file, "r") as f:
        return json.load(f)


def _submit_with_current_api(script_path: str, payload: Dict[str, Any]):
    """
    Try known qiskit-serverless submission shapes.
    """
    try:
        from qiskit_serverless import QiskitServerless, QiskitFunction

        serverless = QiskitServerless()
        function = QiskitFunction(
            title="entangled-faas-single-run",
            entrypoint=script_path,
            working_dir=str(Path(script_path).resolve().parents[1]),
        )
        job = serverless.run(function=function, arguments=payload)
        return job
    except Exception as first_exc:
        try:
            from qiskit_serverless import run

            job = run(
                entrypoint=script_path,
                arguments=payload,
                working_dir=str(Path(script_path).resolve().parents[1]),
            )
            return job
        except Exception as second_exc:
            raise RuntimeError(
                "Unable to submit using detected qiskit-serverless APIs. "
                "Check your qiskit-serverless version and configured provider. "
                f"First error: {first_exc}; Second error: {second_exc}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit one Entangled-FaaS serverless task")
    parser.add_argument(
        "--payload-file",
        type=str,
        default="serverless_payload_example.json",
        help="JSON payload path relative to entangled_faas/",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    payload_path = (base / args.payload_file).resolve()
    script_path = str((base / "serverless_job.py").resolve())

    payload = _load_payload(str(payload_path))
    job = _submit_with_current_api(script_path, payload)

    print("Submitted Qiskit Serverless job")
    print(f"payload: {payload_path}")
    print(f"entrypoint: {script_path}")
    print(f"job: {job}")


if __name__ == "__main__":
    main()

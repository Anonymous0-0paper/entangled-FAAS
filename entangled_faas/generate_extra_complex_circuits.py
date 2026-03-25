"""
generate_extra_complex_circuits.py
=================================
Create 5 additional complex circuits, save them to circuits/,
and print a summary table with circuit name and depth.
"""

from __future__ import annotations

import os
from typing import Callable, List, Tuple

from qiskit import QuantumCircuit
from qiskit.circuit.library import EfficientSU2, RealAmplitudes, TwoLocal
import qiskit.qasm2 as qasm2

import config


def _bind_if_parameterized(circuit: QuantumCircuit) -> QuantumCircuit:
    """Return a parameter-bound copy when the circuit has free parameters."""
    if circuit.num_parameters == 0:
        return circuit
    values = [0.0] * circuit.num_parameters
    return circuit.assign_parameters(values, inplace=False)


def build_complex_suite() -> List[Tuple[str, Callable[[], QuantumCircuit]]]:
    """Define five additional complex circuits."""
    return [
        (
            "complex_efficientsu2_10q_r6_full",
            lambda: EfficientSU2(num_qubits=10, reps=6, entanglement="full"),
        ),
        (
            "complex_efficientsu2_12q_r5_linear",
            lambda: EfficientSU2(num_qubits=12, reps=5, entanglement="linear"),
        ),
        (
            "complex_realamplitudes_10q_r7_linear",
            lambda: RealAmplitudes(num_qubits=10, reps=7, entanglement="linear"),
        ),
        (
            "complex_twolocal_10q_r6_cz",
            lambda: TwoLocal(
                num_qubits=10,
                rotation_blocks=["ry", "rz"],
                entanglement_blocks="cz",
                entanglement="full",
                reps=6,
            ),
        ),
        (
            "complex_twolocal_12q_r5_cx",
            lambda: TwoLocal(
                num_qubits=12,
                rotation_blocks=["rx", "rz"],
                entanglement_blocks="cx",
                entanglement="linear",
                reps=5,
            ),
        ),
    ]


def main() -> None:
    os.makedirs(config.CIRCUITS_DIR, exist_ok=True)

    rows = []
    for name, builder in build_complex_suite():
        circuit = builder()
        bound = _bind_if_parameterized(circuit)
        depth = bound.decompose().depth()

        qasm_path = os.path.join(config.CIRCUITS_DIR, f"{name}.qasm")
        with open(qasm_path, "w") as f:
            qasm2.dump(bound, f)

        rows.append((name, depth, qasm_path))

    print("\nGenerated 5 additional complex circuits:\n")
    print(f"{'Circuit Name':45} {'Depth':>8}")
    print("-" * 56)
    for name, depth, _ in rows:
        print(f"{name:45} {depth:8d}")

    print("\nSaved QASM files:")
    for _, _, path in rows:
        print(f"  - {path}")


if __name__ == "__main__":
    main()

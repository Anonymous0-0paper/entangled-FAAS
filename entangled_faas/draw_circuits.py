"""
draw_circuits.py - Export benchmark circuit diagrams for the paper
==================================================================

Generates diagrams for all standard catalog circuits used by main.py.
Outputs:
  - PNG diagrams (matplotlib drawer)
  - UTF-8 text diagrams
  - JSON manifest with metadata
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

import matplotlib.pyplot as plt
from qiskit.circuit.library import EfficientSU2, RealAmplitudes, TwoLocal

from main import _select_circuit_levels


def _build_from_level_spec(level: str):
    lvl = level.strip().lower()

    m = re.fullmatch(r"std_efficientsu2_(\d+)q_r(\d+)_([a-z_]+)", lvl)
    if m:
        return EfficientSU2(
            num_qubits=int(m.group(1)),
            reps=int(m.group(2)),
            entanglement=m.group(3),
        )

    m = re.fullmatch(r"std_realamplitudes_(\d+)q_r(\d+)_([a-z_]+)", lvl)
    if m:
        return RealAmplitudes(
            num_qubits=int(m.group(1)),
            reps=int(m.group(2)),
            entanglement=m.group(3),
        )

    m = re.fullmatch(r"std_twolocal_(\d+)q_r(\d+)_([a-z0-9_]+)_([a-z_]+)", lvl)
    if m:
        return TwoLocal(
            num_qubits=int(m.group(1)),
            rotation_blocks=["ry", "rz"],
            entanglement_blocks=m.group(3),
            entanglement=m.group(4),
            reps=int(m.group(2)),
        )

    raise ValueError(f"Unsupported level spec: {level}")


def draw_all(circuits_per_level: int = 10) -> Dict[str, str]:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    out_dir = os.path.join(root, "figures", "circuits")
    os.makedirs(out_dir, exist_ok=True)

    selected = _select_circuit_levels(circuits_per_level)
    manifest: Dict[str, List[dict]] = {"simple": [], "medium": [], "complex": []}

    for band in ["simple", "medium", "complex"]:
        for row in selected.get(band, []):
            level = row["level"]
            citation = row.get("citation", "")
            circuit = _build_from_level_spec(level)
            decomp = circuit.decompose()

            stem = f"{band}_{level}"
            png_path = os.path.join(out_dir, f"{stem}.png")
            txt_path = os.path.join(out_dir, f"{stem}.txt")

            # PNG plot (adaptive layout for very deep/wide circuits)
            png_ok = False
            draw_configs = [
                {"fold": 80, "scale": 0.55, "dpi": 160},
                {"fold": 120, "scale": 0.45, "dpi": 140},
                {"fold": 180, "scale": 0.35, "dpi": 120},
                {"fold": -1, "scale": 0.25, "dpi": 100},
            ]
            last_err = None
            for cfg in draw_configs:
                try:
                    fig = decomp.draw(output="mpl", fold=cfg["fold"], scale=cfg["scale"])
                    fig.savefig(png_path, dpi=cfg["dpi"], bbox_inches="tight")
                    plt.close(fig)
                    png_ok = True
                    break
                except Exception as exc:
                    last_err = exc
                    try:
                        plt.close(fig)
                    except Exception:
                        pass

            # Text drawer backup/useful for diffs
            text_art = str(decomp.draw(output="text", fold=120))
            with open(txt_path, "w") as f:
                f.write(text_art + "\n")

            if not png_ok:
                # Ensure there is still a visual artifact path for bookkeeping.
                with open(png_path + ".error.txt", "w") as f:
                    f.write(f"PNG rendering failed for {level}: {last_err}\n")

            manifest[band].append(
                {
                    "level": level,
                    "citation": citation,
                    "num_qubits": decomp.num_qubits,
                    "depth": decomp.depth(),
                    "png": png_path if png_ok else None,
                    "text": txt_path,
                    "png_ok": png_ok,
                }
            )
            print(f"[draw] {level} -> depth={decomp.depth()} qubits={decomp.num_qubits}")

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[draw] wrote manifest -> {manifest_path}")
    return {
        "output_dir": out_dir,
        "manifest": manifest_path,
    }


if __name__ == "__main__":
    draw_all(circuits_per_level=10)

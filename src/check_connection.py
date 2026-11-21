"""CoppeliaSim との接続確認。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation import Simulation  # noqa: E402


def main():
    simu = Simulation()
    sim = simu.sim
    v = sim.getInt32Param(sim.intparam_program_full_version)
    ver = f"{v // 1000000}.{v // 10000 % 100}.{v // 100 % 100}"
    print(f"OK: connected to CoppeliaSim {ver} at {simu.host}:{simu.port}")
    if v < 4100000:
        print("WARNING: この教材は CoppeliaSim 4.10 以降で動作確認しています。")


if __name__ == "__main__":
    main()

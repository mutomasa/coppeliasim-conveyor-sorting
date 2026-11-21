"""ZeroMQ Remote API 接続、ステップ実行、終了処理。"""
from __future__ import annotations

import os
import time

from coppeliasim_zmqremoteapi_client import RemoteAPIClient


class Simulation:
    def __init__(self, host: str | None = None, port: int | None = None):
        # Docker 内からは COPPELIASIM_HOST=host.docker.internal でホストの CoppeliaSim に接続する
        host = os.environ.get("COPPELIASIM_HOST", host or "localhost")
        port = int(os.environ.get("COPPELIASIM_PORT", port or 23000))
        self.host, self.port = host, port
        self.client = RemoteAPIClient(host, port)
        self.sim = self.client.require("sim")
        self.simIK = self.client.require("simIK")

    def start(self) -> None:
        self.sim.setStepping(True)
        self.sim.startSimulation()

    def step(self, n: int = 1) -> None:
        for _ in range(n):
            self.sim.step()

    @property
    def time(self) -> float:
        return self.sim.getSimulationTime()

    @property
    def dt(self) -> float:
        return self.sim.getSimulationTimeStep()

    def stop(self) -> None:
        sim = self.sim
        if sim.getSimulationState() != sim.simulation_stopped:
            sim.stopSimulation()
            while sim.getSimulationState() != sim.simulation_stopped:
                time.sleep(0.05)
        sim.setStepping(False)

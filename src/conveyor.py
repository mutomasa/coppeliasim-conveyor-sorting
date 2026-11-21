"""Generic conveyor (belt) の速度・停止・再開。"""
from __future__ import annotations


class Conveyor:
    def __init__(self, sim, path: str = "/conveyor", speed: float = 0.08):
        self.sim = sim
        self.handle = sim.getObject(path)
        self.speed = speed

    def set_velocity(self, vel: float) -> None:
        # モデル付属スクリプト（conveyor_customization-3）が __ctrl__ の vel を読む
        self.sim.writeCustomTableData(self.handle, "__ctrl__", {"vel": vel})

    def start(self) -> None:
        self.set_velocity(self.speed)

    def stop(self) -> None:
        self.set_velocity(0.0)

    def state(self) -> dict:
        return self.sim.readCustomTableData(self.handle, "__state__")

    def is_stopped(self, tol: float = 1e-4) -> bool:
        return abs(self.state().get("vel", 0.0)) < tol

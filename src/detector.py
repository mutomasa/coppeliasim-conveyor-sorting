"""Proximity Sensor の読み取りと、検出した箱ハンドルの取得。"""
from __future__ import annotations


class Detector:
    def __init__(self, sim, path: str = "/pickSensor"):
        self.sim = sim
        self.handle = sim.getObject(path)

    def read(self) -> int | None:
        """箱を検出していればそのハンドル、なければ None。"""
        res, dist, point, obj, normal = self.sim.readProximitySensor(self.handle)
        if res > 0 and obj != -1:
            alias = self.sim.getObjectAlias(obj)
            if "_box_" in alias:
                return obj
        return None

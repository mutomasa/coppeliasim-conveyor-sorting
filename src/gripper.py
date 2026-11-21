"""簡易吸着グリッパー：箱を attachPoint の子にして保持する（論理吸着）。"""
from __future__ import annotations


class Gripper:
    def __init__(self, sim, attach_path: str = "/UR5/connection/toolTip/attachPoint"):
        self.sim = sim
        self.attach_point = sim.getObject(attach_path)
        self.held: int | None = None

    def attach(self, box: int) -> None:
        sim = self.sim
        sim.setObjectInt32Param(box, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(box, sim.shapeintparam_respondable, 0)
        sim.resetDynamicObject(box)
        sim.setObjectParent(box, self.attach_point, True)
        self.held = box

    def release(self) -> int | None:
        sim = self.sim
        box = self.held
        if box is None:
            return None
        sim.setObjectParent(box, -1, True)
        sim.setObjectInt32Param(box, sim.shapeintparam_static, 0)
        sim.setObjectInt32Param(box, sim.shapeintparam_respondable, 1)
        sim.resetDynamicObject(box)
        self.held = None
        return box

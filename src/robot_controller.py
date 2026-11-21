"""UR5 の手先制御：simIK による逆運動学と、直線補間軌道。"""
from __future__ import annotations

import math


class RobotController:
    def __init__(self, sim, simIK, step_fn, speed: float = 0.5,
                 base="/UR5", tip="/UR5/connection/toolTip", target="/ikTarget"):
        self.sim = sim
        self.simIK = simIK
        self.step_fn = step_fn  # 1 ステップ進める関数（他の処理も一緒に回すため外から渡す）
        self.speed = speed
        self.base = sim.getObject(base)
        self.tip = sim.getObject(tip)
        self.target = sim.getObject(target)

        # IK 環境：ベース〜手先〜目標を登録（位置＋姿勢の拘束）
        self.env = simIK.createEnvironment()
        self.group = simIK.createGroup(self.env)
        simIK.setGroupCalculation(self.env, self.group, simIK.method_damped_least_squares, 0.02, 50)
        simIK.addElementFromScene(self.env, self.group, self.base, self.tip, self.target,
                                  simIK.constraint_pose)
        # 目標を現在の手先に重ね、手先が真下を向く姿勢を保持する
        sim.setObjectPose(self.target, sim.getObjectPose(self.tip, -1), -1)

    def tip_position(self) -> list[float]:
        return self.sim.getObjectPosition(self.tip, -1)

    def tip_error(self) -> float:
        a = self.sim.getObjectPosition(self.tip, -1)
        b = self.sim.getObjectPosition(self.target, -1)
        return math.dist(a, b)

    def _solve(self) -> None:
        self.simIK.handleGroup(self.env, self.group, {"syncWorlds": True, "allowError": True})

    def move_to(self, goal, speed: float | None = None) -> float:
        """ikTarget を goal まで滑らかに動かし、毎ステップ IK を解く。到達後の誤差 [m] を返す。"""
        sim = self.sim
        speed = speed or self.speed
        start = sim.getObjectPosition(self.target, -1)
        dist = math.dist(start, goal)
        dt = sim.getSimulationTimeStep()
        n = max(1, math.ceil(dist / (speed * dt)))
        for i in range(1, n + 1):
            s = i / n
            s = 0.5 - 0.5 * math.cos(math.pi * s)  # 加減速を付けた補間
            p = [a + (b - a) * s for a, b in zip(start, goal)]
            sim.setObjectPosition(self.target, p, -1)
            self._solve()
            self.step_fn()
        for _ in range(3):  # 収束のための追加反復
            self._solve()
        self.step_fn()
        return self.tip_error()

    def move_via_safe(self, goal, safe_z: float) -> float:
        """一旦 safe_z まで上がり、水平移動してから goal へ下りる。"""
        cur = self.sim.getObjectPosition(self.target, -1)
        if cur[2] < safe_z - 1e-3:
            self.move_to([cur[0], cur[1], safe_z])
        self.move_to([goal[0], goal[1], safe_z])
        return self.move_to(goal)

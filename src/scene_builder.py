"""CoppeliaSim のシーンを Python から自動で組み立てる。

main.py は実行のたびにこのモジュールでシーンを作り直すので、.ttt ファイルは配布しない。
シーンだけを作って画面で確認したいときは、CoppeliaSim を起動した状態で:
    python src/scene_builder.py
    python src/scene_builder.py --save /path/on/host/conveyor_sorting.ttt   # 保存も行う
（--save のパスは CoppeliaSim が動いているマシン側のパス）

作成するもの:
    /conveyor     Generic conveyor (belt)
    /pickSensor   仕分け位置の Proximity Sensor（下向きの Ray）
    /pickCamera   色認識用の Vision Sensor（下向き）
    /UR5          UR5（関節は kinematic、付属のデモスクリプトは削除）
    toolTip / attachPoint   UR5 手先（connection）の子 Dummy
    /ikTarget     IK の目標 Dummy（ワールド直下）
    /redTray /blueTray      受け皿
    /redPlace /bluePlace    受け皿中央上の Dummy
"""
from __future__ import annotations

import math
import argparse
import os
import sys

# レイアウト（ワールド座標 [m]）
BELT_TOP_Z = 0.70
PICK_X = 0.25
ROBOT_BASE = [0.25, -0.45, 0.65]
TRAY_TOP_Z = 0.65
TRAYS = {
    "red": {"center": [-0.10, -0.50], "color": [0.9, 0.3, 0.3]},
    "blue": {"center": [0.60, -0.50], "color": [0.3, 0.4, 0.9]},
}
TRAY_SIZE = [0.32, 0.26]
UR5_READY_CONFIG = [0.0, 0.0, math.pi / 2, 0.0, -math.pi / 2, 0.0]  # 手先が真下を向く姿勢


def model_path(sim, *parts) -> str:
    """CoppeliaSim 側のマシンでのモデルファイルのパス。

    Python が Docker コンテナ内で動いていても、パスは CoppeliaSim が動くホスト側で解決させる。
    """
    app = sim.getStringParam(sim.stringparam_application_path).replace("\\", "/")
    if sim.getInt32Param(sim.intparam_platform) == 1:  # macOS: .app/Contents/MacOS
        app = app + "/../Resources"
    return "/".join([app, "models", *parts])


def make_static_box(sim, size, pos, color, alias, respondable=True, parent=-1):
    h = sim.createPrimitiveShape(sim.primitiveshape_cuboid, size, 0)
    sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
    sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 1 if respondable else 0)
    sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse, color)
    sim.setObjectPosition(h, pos, -1)
    sim.setObjectAlias(h, alias)
    if parent != -1:
        sim.setObjectParent(h, parent, True)
    return h


def make_dummy(sim, alias, pos, size=0.02, color=None, parent=-1):
    d = sim.createDummy(size)
    sim.setObjectAlias(d, alias)
    sim.setObjectPosition(d, pos, -1)
    if parent != -1:
        sim.setObjectParent(d, parent, True)
    if color:
        sim.setObjectColor(d, 0, sim.colorcomponent_ambient_diffuse, color)
    return d


def build(sim):
    if sim.getSimulationState() != sim.simulation_stopped:
        sim.stopSimulation()
        while sim.getSimulationState() != sim.simulation_stopped:
            pass
    sim.closeScene()  # 床と照明だけの新規シーン

    # --- Step 1: コンベア -------------------------------------------------
    conveyor = sim.loadModel(model_path(sim, "equipment", "conveyors", "generic conveyor (belt).ttm"))
    sim.setObjectAlias(conveyor, "conveyor")
    sim.setObjectPosition(conveyor, [0.0, 0.0, BELT_TOP_Z], -1)
    # 架台（見た目用・非 respondable）
    make_static_box(sim, [1.0, 0.18, 0.48], [0.0, 0.0, 0.24], [0.45, 0.45, 0.5],
                    "conveyorStand", respondable=False, parent=conveyor)
    # 箱が始端から落ちないように後ろに当て板を置く
    make_static_box(sim, [0.01, 0.2, 0.06], [-0.50, 0.0, BELT_TOP_Z + 0.03], [0.6, 0.6, 0.6],
                    "backStop", respondable=True, parent=conveyor)

    # --- Step 3: Proximity Sensor（下向き Ray） ----------------------------
    int_params = [0, 0, 0, 0, 0, 0, 0, 0]
    # [offset, range, xSize, ySize, xFar, yFar, insideGap, radius, farRadius, angle, thresholdAngle,
    #  smallestDist, sensingPointSize, 0, 0]
    float_params = [0.0, 0.10, 0.01, 0.01, 0.01, 0.01, 0.0, 0.01, 0.01, 0.0, 0.0, 0.0, 0.005, 0.0, 0.0]
    sensor = sim.createProximitySensor(sim.proximitysensor_ray, 16, 16, int_params, float_params)
    sim.setObjectAlias(sensor, "pickSensor")
    sim.setObjectPosition(sensor, [PICK_X, 0.0, BELT_TOP_Z + 0.12], -1)
    sim.setObjectOrientation(sensor, [math.pi, 0.0, 0.0], -1)  # +Z を下へ

    # --- Step 8: Vision Sensor（下向き） -----------------------------------
    cam = sim.createVisionSensor(2, [64, 64, 0, 0],
                                 [0.01, 0.4, math.radians(40), 0.05, 0, 0, 0, 0, 0, 0, 0])
    sim.setObjectAlias(cam, "pickCamera")
    sim.setObjectPosition(cam, [PICK_X, 0.0, BELT_TOP_Z + 0.20], -1)
    sim.setObjectOrientation(cam, [math.pi, 0.0, 0.0], -1)

    # --- Step 4: UR5 + 吸着パッド ------------------------------------------
    make_static_box(sim, [0.18, 0.18, ROBOT_BASE[2]], [ROBOT_BASE[0], ROBOT_BASE[1], ROBOT_BASE[2] / 2],
                    [0.3, 0.3, 0.35], "robotPedestal")
    ur5 = sim.loadModel(model_path(sim, "robots", "non-mobile", "UR5.ttm"))
    sim.setObjectPosition(ur5, ROBOT_BASE, -1)
    # 付属のデモ用スクリプトは Python 制御と競合するので削除
    for obj in sim.getObjectsInTree(ur5, sim.sceneobject_script):
        sim.removeObjects([obj])
    # 関節を kinematic にして IK で直接角度を与える。リンクは静的・非 respondable
    joints = [sim.getObject("/UR5/joint", {"index": i}) for i in range(6)]
    for j, q in zip(joints, UR5_READY_CONFIG):
        sim.setJointMode(j, sim.jointmode_kinematic, 0)
        sim.setJointPosition(j, q)
    for s in sim.getObjectsInTree(ur5, sim.sceneobject_shape):
        sim.setObjectInt32Param(s, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(s, sim.shapeintparam_respondable, 0)

    connection = sim.getObject("/UR5/connection")  # +Z が工具方向
    cup_len = 0.05
    cup = sim.createPrimitiveShape(sim.primitiveshape_cylinder, [0.035, 0.035, cup_len], 0)
    sim.setObjectInt32Param(cup, sim.shapeintparam_static, 1)
    sim.setObjectInt32Param(cup, sim.shapeintparam_respondable, 0)
    sim.setShapeColor(cup, None, sim.colorcomponent_ambient_diffuse, [0.15, 0.15, 0.15])
    sim.setObjectAlias(cup, "suctionCup")
    sim.setObjectParent(cup, connection, False)
    sim.setObjectPose(cup, [0, 0, cup_len / 2, 0, 0, 0, 1], connection)

    tool_tip = sim.createDummy(0.015)
    sim.setObjectAlias(tool_tip, "toolTip")
    sim.setObjectParent(tool_tip, connection, False)
    sim.setObjectPose(tool_tip, [0, 0, cup_len, 0, 0, 0, 1], connection)

    attach = sim.createDummy(0.01)
    sim.setObjectAlias(attach, "attachPoint")
    sim.setObjectParent(attach, tool_tip, False)
    sim.setObjectPose(attach, [0, 0, 0, 0, 0, 0, 1], tool_tip)

    ik_target = sim.createDummy(0.02)
    sim.setObjectAlias(ik_target, "ikTarget")
    sim.setObjectColor(ik_target, 0, sim.colorcomponent_ambient_diffuse, [0.0, 1.0, 0.0])
    sim.setObjectPose(ik_target, sim.getObjectPose(tool_tip, -1), -1)

    # --- Step 6: 受け皿と置き場所 ------------------------------------------
    for name, t in TRAYS.items():
        cx, cy = t["center"]
        tray = make_static_box(sim, [TRAY_SIZE[0], TRAY_SIZE[1], 0.02],
                               [cx, cy, TRAY_TOP_Z - 0.01], t["color"], f"{name}Tray")
        make_static_box(sim, [0.12, 0.12, TRAY_TOP_Z - 0.02], [cx, cy, (TRAY_TOP_Z - 0.02) / 2],
                        [0.4, 0.4, 0.4], f"{name}TrayStand", parent=tray)
        # 縁
        wx, wy, wh = TRAY_SIZE[0], TRAY_SIZE[1], 0.03
        for dx, dy, sx, sy in ((0, wy / 2, wx, 0.01), (0, -wy / 2, wx, 0.01),
                               (wx / 2, 0, 0.01, wy), (-wx / 2, 0, 0.01, wy)):
            make_static_box(sim, [sx, sy, wh], [cx + dx, cy + dy, TRAY_TOP_Z + wh / 2],
                            t["color"], f"{name}TrayWall", parent=tray)
        make_dummy(sim, f"{name}Place", [cx, cy, TRAY_TOP_Z], 0.03, t["color"])

    print("Scene built.")


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from simulation import Simulation

    ap = argparse.ArgumentParser()
    ap.add_argument("--save", help="CoppeliaSim 側のマシンでの保存先 .ttt パス")
    args = ap.parse_args()
    sim = Simulation().sim
    build(sim)
    if args.save:
        sim.saveScene(args.save)
        print(f"Scene saved: {args.save}")


if __name__ == "__main__":
    main()

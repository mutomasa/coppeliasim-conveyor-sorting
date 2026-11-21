"""ベルトコンベア色別仕分けデモ：状態遷移による連続自動運転。

CoppeliaSim を起動し、空のシーンを開いた状態（シミュレーション停止中）で実行する:
    docker compose run --rm lab python src/main.py [--boxes 12] [--classifier vision|label]
    （Docker を使わない場合: python src/main.py ...）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import math
import os
import sys
from enum import Enum, auto

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scene_builder  # noqa: E402
from box_spawner import BoxSpawner  # noqa: E402
from conveyor import Conveyor  # noqa: E402
from detector import Detector  # noqa: E402
from gripper import Gripper  # noqa: E402
from logger import ResultLogger, SortRecord  # noqa: E402
from robot_controller import RobotController  # noqa: E402
from simulation import Simulation  # noqa: E402
from sorter import VisionClassifier, classify_by_label, get_destination  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAFE_Z = 0.90
TRAY_HALF = (0.16, 0.13)


class State(Enum):
    WAIT = auto()
    DETECT = auto()
    PICK = auto()
    SORT = auto()
    PLACE = auto()


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


class SortingApp:
    def __init__(self, cfg, args):
        self.cfg = cfg
        s = cfg["simulation"]
        self.simu = Simulation(s["host"], s["port"])
        self.sim = self.simu.sim
        print(f"Connected to CoppeliaSim at {self.simu.host}:{self.simu.port}")
        scene_builder.build(self.sim)  # 毎回シーンを組み立て直す（.ttt を配布しない）
        self.total = args.boxes or s["total_boxes"]
        self.classifier_name = args.classifier or cfg["classifier"]["method"]
        self.max_time = s["max_sim_time"]
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log = ResultLogger(os.path.join(ROOT, "results", f"sorting_{stamp}.csv"))

        sim = self.sim
        self.conveyor = Conveyor(sim, speed=cfg["conveyor"]["speed"])
        b = cfg["box"]
        self.box_h = b["size"][2]
        self.spawner = BoxSpawner(sim, b["size"], b["mass"], b["spawn_pos"], b["colors"], s["seed"])
        self.spawn_interval = b["spawn_interval"]
        self.detector = Detector(sim)
        self.gripper = Gripper(sim)
        self.vision = VisionClassifier(sim)
        r = cfg["robot"]
        self.home = r["home"]
        self.approach = r["approach_height"]
        self.place_gap = r["place_height"]
        self.settle = r["settle_steps"]
        self.robot_speed = r["speed"]
        t = cfg["trays"]
        self.grid = t["grid"]
        self.pitch = t["pitch"]
        self.slot_used = {"red": 0, "blue": 0}

        self.belt_time = 0.0       # ベルトが動いていた時間（箱の生成タイミングに使う）
        self.next_spawn = 0.0
        self.processed = 0

    # ------------------------------------------------------------------
    def step(self, n=1):
        self.simu.step(n)

    def classify(self, box):
        if self.classifier_name == "vision":
            return self.vision.classify(box)
        return classify_by_label(self.sim, box)

    def slot_position(self, color):
        """受け皿の上に箱を並べる位置（グリッド。埋まったら2段目）。"""
        place = self.sim.getObjectPosition(self.sim.getObject(get_destination(color)), -1)
        rows, cols = self.grid
        k = self.slot_used[color]
        self.slot_used[color] += 1
        layer, idx = divmod(k, rows * cols)
        r, c = divmod(idx, cols)
        x = place[0] + (c - (cols - 1) / 2) * self.pitch
        y = place[1] + (r - (rows - 1) / 2) * self.pitch
        z = place[2] + self.box_h * (layer + 1)  # 置いたときの箱の上面
        return [x, y, z]

    def evaluate(self, box, color):
        place = self.sim.getObjectPosition(self.sim.getObject(get_destination(color)), -1)
        p = self.sim.getObjectPosition(box, -1)
        inside = abs(p[0] - place[0]) < TRAY_HALF[0] and abs(p[1] - place[1]) < TRAY_HALF[1] \
            and p[2] > place[2] - 0.01
        return inside, p

    # ------------------------------------------------------------------
    def run(self):
        sim = self.sim
        self.simu.start()
        self.robot = RobotController(sim, self.simu.simIK, self.step, self.robot_speed)
        self.conveyor.stop()
        print(f"Classifier: {self.classifier_name}, boxes: {self.total}")
        self.robot.move_to(self.home)
        self.conveyor.start()

        state = State.WAIT
        box = None
        detect_t = 0.0
        try:
            while self.processed < self.total and self.simu.time < self.max_time:
                if state == State.WAIT:
                    if self.spawner.count < self.total and self.belt_time >= self.next_spawn:
                        b, c = self.spawner.spawn()
                        print(f"  spawn {sim.getObjectAlias(b)} at t={self.simu.time:.1f}s")
                        self.next_spawn += self.spawn_interval
                    box = self.detector.read()
                    if box is not None:
                        detect_t = self.simu.time
                        state = State.DETECT
                        continue
                    self.step()
                    self.belt_time += self.simu.dt

                elif state == State.DETECT:
                    self.conveyor.stop()
                    for _ in range(400):  # 減速して停止するまで待つ
                        self.step()
                        if self.conveyor.is_stopped():
                            break
                    self.step(5)
                    predicted = self.classify(box)
                    bp = sim.getObjectPosition(box, -1)
                    print(f"  detected {sim.getObjectAlias(box)} at x={bp[0]:.3f} z={bp[2]:.3f} -> {predicted}")
                    state = State.PICK

                elif state == State.PICK:
                    bp = sim.getObjectPosition(box, -1)
                    top = [bp[0], bp[1], bp[2] + self.box_h / 2]
                    self.robot.move_via_safe([top[0], top[1], top[2] + self.approach], SAFE_Z)
                    tip_err = self.robot.move_to(top, speed=0.2)
                    self.gripper.attach(box)
                    self.robot.move_to([top[0], top[1], SAFE_Z])
                    state = State.SORT

                elif state == State.SORT:
                    if predicted == "unknown":
                        print("  色を判定できませんでした。ラベルで代用します。")
                        predicted = classify_by_label(sim, box)
                    slot = self.slot_position(predicted)
                    state = State.PLACE

                elif state == State.PLACE:
                    above = [slot[0], slot[1], slot[2] + self.place_gap]
                    self.robot.move_via_safe([above[0], above[1], above[2] + 0.08], SAFE_Z)
                    self.robot.move_to(above, speed=0.2)
                    self.gripper.release()
                    self.step(self.settle)
                    self.robot.move_to([above[0], above[1], SAFE_Z])
                    self.robot.move_to(self.home)
                    self.step(self.settle)

                    true_color = self.spawner.boxes[box]
                    inside, fp = self.evaluate(box, true_color)
                    success = inside and predicted == true_color
                    failure = ""
                    if predicted != true_color:
                        failure = "misclassified"
                    elif not inside:
                        failure = "dropped/outside tray"
                    done_t = self.simu.time
                    self.log.add(SortRecord(
                        index=self.processed, box=sim.getObjectAlias(box), true_color=true_color,
                        predicted_color=predicted, destination=get_destination(predicted),
                        detect_time=round(detect_t, 3), done_time=round(done_t, 3),
                        cycle_time=round(done_t - detect_t, 3), tip_error_mm=round(tip_err * 1000, 2),
                        final_x=round(fp[0], 4), final_y=round(fp[1], 4),
                        success=success, failure=failure))
                    self.processed += 1
                    self.conveyor.start()
                    state = State.WAIT
            elapsed = self.simu.time
        finally:
            try:
                self.conveyor.stop()
                self.log.save()
            finally:
                self.simu.stop()
        print(self.log.summary(elapsed))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--boxes", type=int)
    ap.add_argument("--classifier", choices=["label", "vision"])
    args = ap.parse_args()
    SortingApp(load_config(args.config), args).run()


if __name__ == "__main__":
    main()

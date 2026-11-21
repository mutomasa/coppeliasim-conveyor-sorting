"""赤・青の箱のランダム生成。箱は dynamic にしてベルトとの摩擦で運ばせる。"""
from __future__ import annotations

import random


class BoxSpawner:
    def __init__(self, sim, size, mass, spawn_pos, colors: dict, seed=None):
        self.sim = sim
        self.size = list(size)
        self.mass = mass
        self.spawn_pos = list(spawn_pos)
        self.colors = colors
        self.rng = random.Random(seed)
        self.count = 0
        self.boxes: dict[int, str] = {}  # handle -> 正解の色ラベル

    def spawn(self, color: str | None = None) -> tuple[int, str]:
        sim = self.sim
        color = color or self.rng.choice(sorted(self.colors))
        box = sim.createPrimitiveShape(sim.primitiveshape_cuboid, self.size, 0)
        sim.setObjectAlias(box, f"{color}_box_{self.count}")
        sim.setShapeColor(box, None, sim.colorcomponent_ambient_diffuse, self.colors[color])
        sim.setObjectPosition(box, self.spawn_pos, sim.handle_world)
        # 物理設定：dynamic / respondable / detectable / collidable
        sim.setObjectInt32Param(box, sim.shapeintparam_static, 0)
        sim.setObjectInt32Param(box, sim.shapeintparam_respondable, 1)
        sim.setObjectSpecialProperty(
            box,
            sim.objectspecialproperty_collidable
            | sim.objectspecialproperty_measurable
            | sim.objectspecialproperty_detectable
            | sim.objectspecialproperty_renderable,
        )
        sim.setShapeMass(box, self.mass)
        sim.resetDynamicObject(box)
        self.boxes[box] = color
        self.count += 1
        return box, color

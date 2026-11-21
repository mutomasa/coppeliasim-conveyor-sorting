"""色の判定と置き場所の選択。"""
from __future__ import annotations

import numpy as np

DESTINATIONS = {"red": "/redPlace", "blue": "/bluePlace"}


def classify_by_label(sim, box: int) -> str:
    """Step 6：生成時の Alias で判定する簡易版。"""
    alias = sim.getObjectAlias(box)
    if alias.startswith("red_box_"):
        return "red"
    if alias.startswith("blue_box_"):
        return "blue"
    return "unknown"


def classify_image(img: np.ndarray, min_pixels: int = 30) -> str:
    """Step 8：RGB 画像（H×W×3, uint8）を HSV で見て赤・青を判定する。"""
    rgb = img.astype(np.float32) / 255.0
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    diff = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == r, ((g - b) / diff) % 6,
                   np.where(mx == g, (b - r) / diff + 2, (r - g) / diff + 4)) * 60.0
    colored = (sat > 0.5) & (mx > 0.3)
    red = int(np.count_nonzero(colored & ((hue < 20) | (hue > 340))))
    blue = int(np.count_nonzero(colored & (hue > 200) & (hue < 260)))
    if max(red, blue) < min_pixels:
        return "unknown"
    return "red" if red > blue else "blue"


class VisionClassifier:
    def __init__(self, sim, path: str = "/pickCamera"):
        self.sim = sim
        self.handle = sim.getObject(path)

    def capture(self) -> np.ndarray:
        buf, (w, h) = self.sim.getVisionSensorImg(self.handle)
        img = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
        return np.flipud(img)

    def classify(self, box: int | None = None) -> str:
        return classify_image(self.capture())


def get_destination(color: str) -> str:
    if color not in DESTINATIONS:
        raise ValueError(f"Unknown color: {color}")
    return DESTINATIONS[color]

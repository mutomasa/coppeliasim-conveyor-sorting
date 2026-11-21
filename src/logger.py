"""試行結果の CSV 出力と評価指標の集計。"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, fields


@dataclass
class SortRecord:
    index: int
    box: str
    true_color: str
    predicted_color: str
    destination: str
    detect_time: float
    done_time: float
    cycle_time: float
    tip_error_mm: float
    final_x: float
    final_y: float
    success: bool
    failure: str


class ResultLogger:
    def __init__(self, path: str):
        self.path = path
        self.records: list[SortRecord] = []
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def add(self, rec: SortRecord) -> None:
        self.records.append(rec)
        mark = "OK " if rec.success else "NG "
        print(f"[{mark}] #{rec.index:02d} {rec.box:<12} true={rec.true_color:<4} "
              f"pred={rec.predicted_color:<7} cycle={rec.cycle_time:5.2f}s "
              f"tipErr={rec.tip_error_mm:4.1f}mm {rec.failure}")

    def save(self) -> None:
        with open(self.path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(SortRecord)])
            w.writeheader()
            for r in self.records:
                w.writerow(asdict(r))

    def summary(self, elapsed: float) -> str:
        n = len(self.records)
        if n == 0:
            return "No boxes processed."
        ok = sum(r.success for r in self.records)
        cyc = sum(r.cycle_time for r in self.records) / n
        err = sum(r.tip_error_mm for r in self.records) / n
        fails = [r.failure for r in self.records if r.failure]
        thr = ok / elapsed * 60.0 if elapsed > 0 else 0.0
        return (
            "\n===== 評価結果 =====\n"
            f"処理した箱       : {n}\n"
            f"仕分け成功率     : {ok}/{n} = {ok / n * 100:.1f}%\n"
            f"平均サイクルタイム: {cyc:.2f} s\n"
            f"処理能力         : {thr:.2f} 個/分（シミュレーション時間 {elapsed:.1f} s）\n"
            f"平均手先位置誤差 : {err:.2f} mm\n"
            f"搬送失敗         : {len(fails)} 件 {fails if fails else ''}\n"
            f"CSV              : {os.path.relpath(self.path)}"
        )

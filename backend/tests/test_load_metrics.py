# -*- coding: utf-8 -*-
"""load_metrics 单元测试（冰衡模块）。运行：python -m unittest tests.test_load_metrics -v"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import load_metrics as lm  # noqa: E402


class TestSessionLoad(unittest.TestCase):
    def test_zero_when_invalid(self):
        self.assertEqual(lm.session_load(None), 0.0)
        self.assertEqual(lm.session_load(0), 0.0)

    def test_hrr_fallback(self):
        # 60 分钟，平均 140，最高 200，静息 60 → HRR=0.571 → 34.3
        v = lm.session_load(60, 140, 200)
        self.assertAlmostEqual(v, 34.3, places=1)

    def test_zone_weighted(self):
        # 全部在 Z4（权重 4）→ 60 分钟 × 4 = 240
        v = lm.session_load(60, zones={1: 0, 2: 0, 3: 0, 4: 100, 5: 0})
        self.assertAlmostEqual(v, 240.0, places=1)

    def test_zone_partial(self):
        # 一半 Z1 一半 Z3 → 权重 (1+3)/2 = 2 → 120
        v = lm.session_load(60, zones={1: 50, 3: 50})
        self.assertAlmostEqual(v, 120.0, places=1)


class TestSeries(unittest.TestCase):
    def _series(self, days: int, load: float, start: date):
        return {start + timedelta(days=i): load for i in range(days)}

    def test_acwr_stable(self):
        start = date(2026, 7, 1)
        series = self._series(35, 100.0, start)
        metrics = lm.compute_series(series, end=start + timedelta(days=34))
        last = metrics[-1]
        self.assertAlmostEqual(last.acwr, 1.0, places=2)
        self.assertEqual(last.level, "green")

    def test_acwr_spike_red(self):
        start = date(2026, 7, 1)
        series = self._series(28, 50.0, start)
        # 最后两天暴增
        for i in (27, 28):
            series[start + timedelta(days=i)] = 400.0
        metrics = lm.compute_series(series, end=start + timedelta(days=28))
        last = metrics[-1]
        self.assertGreaterEqual(last.acwr or 0, 1.5)
        self.assertEqual(last.level, "red")
        self.assertEqual(last.suggested_pct, 0)

    def test_insufficient_history_unknown(self):
        start = date(2026, 7, 1)
        series = self._series(5, 100.0, start)
        metrics = lm.compute_series(series, end=start + timedelta(days=4))
        self.assertEqual(metrics[-1].level, "unknown")

    def test_monotony_detected(self):
        start = date(2026, 7, 1)
        series = {}
        d = start
        while d <= start + timedelta(days=27):
            series[d] = 100.0
            d += timedelta(days=1)
        # 制造单调性：7 天里有 6 天 0、1 天 700
        for i in range(21, 28):
            series[start + timedelta(days=i)] = 0.0
        series[start + timedelta(days=27)] = 700.0
        metrics = lm.compute_series(series, end=start + timedelta(days=27))
        self.assertIsNotNone(metrics[-1].monotony)

    def test_summary_fields(self):
        start = date(2026, 7, 1)
        series = self._series(35, 100.0, start)
        s = lm.summarize(lm.compute_series(series, end=start + timedelta(days=34)))
        for key in ("date", "acwr", "level", "level_text", "reason", "suggested_pct", "week_load"):
            self.assertIn(key, s)
        self.assertEqual(s["level_text"], "正常训练")


if __name__ == "__main__":
    unittest.main(verbosity=2)

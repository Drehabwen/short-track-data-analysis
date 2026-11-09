# -*- coding: utf-8 -*-
"""训练负荷与疲劳指标（冰衡模块 · 与 PRD 第 5/6 节一致）。

指标定义
--------
负荷指数 LOAD：优先用心率区间（z1..z5 时长占比）加权；缺失时用 HRR 线性法
    LOAD = 时长(min) × Σ(区间权重 × 区间占比)
    区间权重 1..5（Z1..Z5），无区间时 LOAD = 时长 × HRR，HRR=(avg-rest)/(max-rest)
急性负荷 ACUTE：近 7 天日均负荷
慢性负荷 CHRONIC：近 28 天日均负荷（历史不足时按已有天数计算，并标记 coverage）
ACWR = ACUTE / CHRONIC（甜蜜区 0.8–1.3）
单调性 MONOTONY = 近 7 天负荷均值 / 标准差（越大越单一）
应变 STRAIN = 近 7 天负荷总和 × 单调性
决策：
  红（停训观察）ACWR≥1.5，或 ACWR≥1.3 且主观疲劳≥8
  黄（建议减量）ACWR≥1.3，或单调性≥2.0，或主观疲劳≥7
  绿（正常训练）其余
历史不足（慢性负荷覆盖 <10 天）→ 输出 unknown，不给红黄绿，避免误判。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean, pstdev

REST_HR = 60.0
ZONE_WEIGHTS = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}
ACUTE_DAYS = 7
CHRONIC_DAYS = 28
MIN_COVERAGE_DAYS = 10

LEVEL_TEXT = {
    "green": "正常训练",
    "yellow": "建议减量",
    "red": "停训观察",
    "under": "负荷偏低",
    "unknown": "数据不足",
}


def session_load(
    duration_min: float | None,
    avg_hr: float | None = None,
    max_hr: float | None = None,
    zones: dict[int, float] | None = None,
    rest_hr: float = REST_HR,
) -> float:
    """单次训练负荷。zones 为 {1..5: 该区间时长占比(0-100)}。"""
    if not duration_min or duration_min <= 0:
        return 0.0
    if zones:
        total_pct = sum(v for v in zones.values() if v)
        if total_pct > 0:
            weight = sum(ZONE_WEIGHTS[z] * (zones.get(z) or 0) for z in ZONE_WEIGHTS) / total_pct
            return round(duration_min * weight, 1)
    if avg_hr and max_hr and max_hr > rest_hr:
        hrr = max(0.0, min(1.0, (avg_hr - rest_hr) / (max_hr - rest_hr)))
        return round(duration_min * hrr, 1)
    return 0.0


@dataclass
class DayMetrics:
    day: date
    load: float
    acute: float | None
    chronic: float | None
    acwr: float | None
    monotony: float | None
    strain: float | None
    level: str
    reason: str
    suggested_pct: int
    coverage_days: int
    extras: dict = field(default_factory=dict)


def _window(series: list[float], end_idx: int, days: int) -> list[float]:
    start = max(0, end_idx - days + 1)
    return series[start:end_idx + 1]


def decide(
    acwr: float | None,
    monotony: float | None,
    fatigue: int | None = None,
    coverage_days: int = CHRONIC_DAYS,
) -> tuple[str, str, int]:
    """返回 (level, reason, suggested_pct)。"""
    if coverage_days < MIN_COVERAGE_DAYS or acwr is None:
        return "unknown", f"慢性负荷历史仅 {coverage_days} 天（<{MIN_COVERAGE_DAYS}），暂不判定", 100
    if acwr >= 1.5:
        return "red", f"ACWR {acwr:.2f} ≥ 1.5，负荷急增", 0
    if acwr >= 1.3 and (fatigue or 0) >= 8:
        return "red", f"ACWR {acwr:.2f} ≥ 1.3 且主观疲劳 {fatigue}/10", 0
    if acwr >= 1.3:
        return "yellow", f"ACWR {acwr:.2f} 进入超阈区（1.3–1.5）", 60
    if monotony is not None and monotony >= 2.0:
        return "yellow", f"单调性 {monotony:.1f} ≥ 2.0，训练结构单一", 70
    if (fatigue or 0) >= 7:
        return "yellow", f"主观疲劳 {fatigue}/10 偏高", 70
    if 0.8 <= acwr <= 1.3:
        return "green", f"ACWR {acwr:.2f} 在安全区 0.8–1.3", 100
    return "under", f"ACWR {acwr:.2f} 低于 0.8，负荷偏低，可适度加量", 110


def compute_series(
    daily_loads: dict[date, float],
    fatigue_by_day: dict[date, int] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[DayMetrics]:
    """把「按天负荷」计算成逐日指标序列（含缺失日补 0）。"""
    fatigue_by_day = fatigue_by_day or {}
    if not daily_loads:
        return []
    lo = start or min(daily_loads)
    hi = end or max(daily_loads)
    if lo > hi:
        lo, hi = hi, lo
    days: list[date] = []
    d = lo
    while d <= hi:
        days.append(d)
        d += timedelta(days=1)
    series = [float(daily_loads.get(d, 0.0)) for d in days]

    out: list[DayMetrics] = []
    for i, d in enumerate(days):
        acute = mean(_window(series, i, ACUTE_DAYS))
        cov = min(i + 1, CHRONIC_DAYS)
        chronic_window = _window(series, i, CHRONIC_DAYS)
        chronic = mean(chronic_window)
        acwr = round(acute / chronic, 2) if chronic > 0 else None
        w7 = _window(series, i, ACUTE_DAYS)
        sd = pstdev(w7) if len(w7) > 1 else 0.0
        monotony = round(mean(w7) / sd, 2) if sd > 0 else None
        strain = round(sum(w7) * monotony, 1) if monotony is not None else None
        level, reason, pct = decide(acwr, monotony, fatigue_by_day.get(d), cov)
        out.append(DayMetrics(
            day=d, load=round(series[i], 1), acute=round(acute, 1), chronic=round(chronic, 1),
            acwr=acwr, monotony=monotony, strain=strain, level=level, reason=reason,
            suggested_pct=pct, coverage_days=cov,
        ))
    return out


def summarize(metrics: list[DayMetrics]) -> dict:
    """把序列压成今日卡需要的摘要。"""
    if not metrics:
        return {}
    last = metrics[-1]
    week = metrics[-7:]
    return {
        "date": last.day.isoformat(),
        "load": last.load,
        "acute": last.acute,
        "chronic": last.chronic,
        "acwr": last.acwr,
        "monotony": last.monotony,
        "strain": last.strain,
        "level": last.level,
        "level_text": LEVEL_TEXT.get(last.level, last.level),
        "reason": last.reason,
        "suggested_pct": last.suggested_pct,
        "coverage_days": last.coverage_days,
        "week_load": round(sum(m.load for m in week), 1),
        "week_days": len([m for m in week if m.load > 0]),
    }

# -*- coding: utf-8 -*-
"""统计计算服务：描述统计、Friedman、Wilcoxon、Kruskal-Wallis、Spearman。

与 Academic/outputs/clean_analysis_2026-07-21 的分析口径保持一致。
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from ..config import ANALYTES, TIMEPOINTS

# 参与统计的数值列（睾酮使用非 censored 值）
STAT_COLS = {
    "cortisol_ug_dL": "皮质醇",
    "urea_mmol_L": "尿素",
    "creatine_kinase_U_L": "肌酸激酶",
    "ldh_U_L": "乳酸脱氢酶",
}
# 睾酮单独处理（censored）
TESTOSTERONE_COL = "testosterone_value"


def _num_series(samples: list[dict], col: str) -> pd.Series:
    """提取数值列，过滤 NaN。"""
    values = [s.get(col) for s in samples]
    return pd.Series(values, dtype="float64").dropna()


def _pivot(samples: list[dict], col: str) -> pd.DataFrame:
    """透视：行=受试者，列=时间点。"""
    df = pd.DataFrame(
        [
            {"participant": s["participant_id"], "timepoint": s["timepoint"], "value": s.get(col)}
            for s in samples
        ]
    )
    pivot = df.pivot_table(index="participant", columns="timepoint", values="value", aggfunc="first")
    return pivot.reindex(columns=TIMEPOINTS)


def descriptive(values: pd.Series) -> dict:
    if values.empty:
        return {"n": 0, "mean": None, "sd": None, "median": None, "q1": None, "q3": None,
                "min": None, "max": None}
    return {
        "n": int(len(values)),
        "mean": round(float(values.mean()), 4),
        "sd": round(float(values.std(ddof=1)), 4) if len(values) > 1 else None,
        "median": round(float(values.median()), 4),
        "q1": round(float(values.quantile(0.25)), 4),
        "q3": round(float(values.quantile(0.75)), 4),
        "min": round(float(values.min()), 4),
        "max": round(float(values.max()), 4),
    }


def friedman(samples: list[dict], col: str) -> dict:
    pivot = _pivot(samples, col)
    complete = pivot.dropna(subset=TIMEPOINTS)
    n = len(complete)
    if n < 3:
        return {"complete_n": n, "statistic": None, "p": None}
    try:
        stat, p = stats.friedmanchisquare(*[complete[t] for t in TIMEPOINTS])
    except ValueError:
        stat, p = None, None
    return {
        "complete_n": n,
        "statistic": round(float(stat), 4) if stat is not None else None,
        "p": round(float(p), 6) if p is not None else None,
    }


def wilcoxon_pairs(samples: list[dict], col: str, pairs=None) -> list[dict]:
    if pairs is None:
        pairs = [("BL", "24H"), ("BL", "72H"), ("24H", "72H")]
    pivot = _pivot(samples, col)
    raw_ps = []
    rows = []
    for t1, t2 in pairs:
        paired = pivot[[t1, t2]].dropna()
        n = len(paired)
        diff = paired[t2] - paired[t1]
        if n < 2:
            stat, p = None, None
        elif np.allclose(diff.to_numpy(), 0):
            stat, p = 0.0, 1.0
        else:
            stat, p = stats.wilcoxon(paired[t2], paired[t1], alternative="two-sided")
        raw_ps.append(1.0 if p is None or not math.isfinite(p) else float(p))
        rows.append({
            "comparison": f"{t1} vs {t2}",
            "paired_n": n,
            "mean_change": round(float(diff.mean()), 4) if n else None,
            "median_change": round(float(diff.median()), 4) if n else None,
            "statistic": round(float(stat), 4) if stat is not None else None,
            "p_raw": round(float(p), 6) if p is not None else None,
        })
    # Holm 校正
    order = np.argsort(raw_ps)
    adjusted = np.empty(len(raw_ps), dtype=float)
    running = 0.0
    m = len(raw_ps)
    for rank, idx in enumerate(order):
        candidate = (m - rank) * raw_ps[idx]
        running = max(running, candidate)
        adjusted[idx] = min(running, 1.0)
    for row, p_adj in zip(rows, adjusted):
        row["p_holm"] = round(float(p_adj), 6)
    return rows


def kruskal_groups(samples: list[dict], col: str, groups: list[str]) -> dict:
    """组间差异检验（Kruskal-Wallis），按时间点分层。"""
    result = {}
    for tp in TIMEPOINTS:
        group_vals = []
        group_names = []
        for g in groups:
            vals = _num_series(
                [s for s in samples if s["timepoint"] == tp and s.get("group_name") == g], col
            )
            if not vals.empty:
                group_vals.append(vals.to_numpy())
                group_names.append(g)
        if len(group_vals) >= 2:
            stat, p = stats.kruskal(*group_vals)
            result[tp] = {
                "groups": group_names,
                "n_per_group": [int(len(v)) for v in group_vals],
                "statistic": round(float(stat), 4),
                "p": round(float(p), 6),
            }
        else:
            result[tp] = {
                "groups": group_names,
                "n_per_group": [int(len(v)) for v in group_vals],
                "statistic": None,
                "p": None,
            }
    return result


def spearman_correlation(samples: list[dict]) -> list[dict]:
    """指标间 Spearman 相关矩阵。"""
    cols = [TESTOSTERONE_COL] + list(STAT_COLS.keys())
    df = pd.DataFrame([{c: s.get(c) for c in cols} for s in samples])
    labels = ["睾酮"] + list(STAT_COLS.values())
    result = []
    for i, (rc, rl) in enumerate(zip(cols, labels)):
        for j, (cc, cl) in enumerate(zip(cols, labels)):
            pair = df[[rc, cc]].dropna()
            n = len(pair)
            if n < 3:
                rho, p = None, None
            elif i == j:
                rho, p = 1.0, 0.0
            else:
                rho, p = stats.spearmanr(pair[rc], pair[cc])
            result.append({
                "row": rl,
                "column": cl,
                "n": n,
                "rho": round(float(rho), 4) if rho is not None else None,
                "p": round(float(p), 6) if p is not None else None,
            })
    return result


def spearman_pair(x: list[float], y: list[float]) -> tuple[float | None, float | None]:
    """计算一对已配对数值的 Spearman ρ 与 p 值。"""
    if len(x) < 3 or len(y) < 3 or len(x) != len(y):
        return None, None
    try:
        rho, p = stats.spearmanr(x, y)
    except (ValueError, TypeError):
        return None, None
    if not (math.isfinite(float(rho)) and math.isfinite(float(p))):
        return None, None
    return round(float(rho), 4), round(float(p), 6)


def summary_by(samples: list[dict], col: str, key: str) -> list[dict]:
    """按 key（timepoint/group_name/sex）分组描述统计。"""
    result = []
    for k in sorted({s.get(key) for s in samples if s.get(key)}):
        group = [s for s in samples if s.get(key) == k]
        result.append({"key": k, **descriptive(_num_series(group, col))})
    return result


def tc_ratio(sample: dict) -> float | None:
    """T/C 比值 = 睾酮/皮质醇 × 100%。"""
    t = sample.get("testosterone_value")
    c = sample.get("cortisol_ug_dL")
    if t is None or c is None or c == 0:
        return None
    return round(t / c * 100.0, 4)

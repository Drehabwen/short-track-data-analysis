# -*- coding: utf-8 -*-
"""Modality ablation for the RehabID-Fatigue v0.1 pilot.

All models use the same leave-one-subject-out evaluation and Ridge pipeline.
Only variables available before the 24/72-hour CMJ outcome are included.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(r"D:\DEV\blood")
UNIFIED = ROOT / "统一数据集"
MAIN = UNIFIED / "统一数据集_受试者主表.csv"
CPET = ROOT / "最大摄氧量" / "最大摄氧量数据" / "cpet_enriched.csv"
OUT = UNIFIED / "RehabID-Fatigue_v0.1_ablation_metrics.csv"
OUT_JSON = UNIFIED / "RehabID-Fatigue_v0.1_ablation_summary.json"
OUT_README = UNIFIED / "RehabID-Fatigue_v0.1_ablation_README.md"


def clean(v):
    return "" if v is None else str(v).strip()


def date_from_file(text):
    m = re.search(r"(20\d{2})[._-](\d{2})[._-](\d{2})", clean(text))
    return tuple(map(int, m.groups())) if m else (9999, 99, 99)


def cpet_baseline(main):
    """Select the earliest CPET event per linked subject for a sensitivity block."""
    if not CPET.exists():
        return pd.DataFrame(index=main.index)
    cpet = pd.read_csv(CPET, encoding="utf-8-sig")
    aliases = {}
    for _, row in main.iterrows():
        sid = clean(row.subject_id)
        aliases[clean(row["name"])] = sid
        for alias in clean(row.get("name_aliases", "")).split(";"):
            if alias:
                aliases[alias] = sid
    cpet["subject_id"] = cpet["name"].map(aliases)
    cpet = cpet[cpet["subject_id"].notna()].copy()
    cpet["date_key"] = cpet["file"].map(date_from_file)
    cpet = cpet.sort_values(["subject_id", "date_key"]).drop_duplicates("subject_id", keep="first")
    cpet = cpet.set_index("subject_id")
    out = pd.DataFrame(index=main.index)
    for col, new in [("meas_max_vo2", "cpet_vo2_max"),
                     ("meas_max_vo2kg", "cpet_vo2kg_max"),
                     ("peak_wr", "cpet_peak_work_rate"),
                     ("exercise_dur_s", "cpet_exercise_duration")]:
        if col in cpet:
            out[new] = pd.to_numeric(main.subject_id.map(cpet[col]), errors="coerce").to_numpy()
    return out


def build_blocks(df):
    groups = {
        "demographic": ["age", "height_cm", "weight_kg"],
        "exercise_load": ["load_pct"] + [f"{x}_p{i}" for x in ("avg_power", "peak_power") for i in range(1, 6)],
        "subjective": ["vas_rest", "vas_post", "vas_interv", "rpe_rest", "rpe_post", "rpe_interv"],
        "heart_hrv": ["hr_rest_avg", "hr_rest_max", "hr_post_avg", "hr_post_max",
                      "hrv_sdnn", "hrv_rmssd", "hrv_lf_hf", "hrv_total_power"],
        "performance": ["cmj_pre"] + [c for c in df.columns if c.startswith("pt_")],
        "lactate": ["lactate_rest", "lactate_post", "lactate_interv"],
        "blood_baseline": [c for c in df.columns if c.startswith("blood_") and c.endswith("_BL")],
    }
    numeric = pd.DataFrame(index=df.index)
    for block, cols in groups.items():
        for col in cols:
            if col in df.columns:
                numeric[col] = pd.to_numeric(df[col], errors="coerce")
    cpet = cpet_baseline(df)
    for col in cpet.columns:
        numeric[col] = cpet[col]
    groups["cpet_sensitivity"] = list(cpet.columns)
    # Keep only columns with at least 10 observations in the full cohort.
    for block in list(groups):
        groups[block] = [c for c in groups[block] if c in numeric and numeric[c].notna().sum() >= 10]
    return numeric, groups


def evaluate(df, target, feature_names, X):
    mask = pd.to_numeric(df[target], errors="coerce").notna()
    y = pd.to_numeric(df.loc[mask, target], errors="coerce").to_numpy(dtype=float)
    x = X.loc[mask, feature_names]
    x = x.loc[:, x.notna().any(axis=0)]
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=10.0)),
    ])
    pred = cross_val_predict(pipe, x, y, cv=LeaveOneOut(), n_jobs=None)
    return {
        "n": int(len(y)),
        "feature_count": int(x.shape[1]),
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(math.sqrt(mean_squared_error(y, pred))),
        "r2": float(r2_score(y, pred)),
    }


def main():
    df = pd.read_csv(MAIN, encoding="utf-8-sig")
    X, groups = build_blocks(df)
    order = ["demographic", "exercise_load", "subjective", "heart_hrv",
             "performance", "lactate", "blood_baseline", "cpet_sensitivity"]
    rows = []
    for target in ("cmj_24h", "cmj_72h"):
        cumulative = []
        previous = None
        for block in order:
            cumulative += groups.get(block, [])
            if not cumulative:
                continue
            result = evaluate(df, target, cumulative, X)
            result.update({"target": target, "feature_block": block,
                           "cumulative_features": len(set(cumulative))})
            result["mae_change_vs_previous"] = "" if previous is None else round(result["mae"] - previous, 6)
            rows.append(result)
            previous = result["mae"]
    metrics = pd.DataFrame(rows)
    metrics = metrics[["target", "feature_block", "n", "cumulative_features",
                       "feature_count", "mae", "rmse", "r2", "mae_change_vs_previous"]]
    metrics.to_csv(OUT, index=False, encoding="utf-8-sig")
    summary = {
        "dataset_version": "RehabID-Fatigue v0.1",
        "validation": "same leave-one-subject-out Ridge pipeline for every cumulative feature block",
        "targets": ["cmj_24h", "cmj_72h"],
        "feature_blocks": {k: v for k, v in groups.items()},
        "cpet_note": "CPET block uses the earliest linked CPET event per subject and is a sensitivity analysis because the current export lacks a confirmed alignment date to the fatigue episode.",
        "metrics_rows": int(len(metrics)),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_README.write_text(build_readme(summary, metrics), encoding="utf-8")
    print(metrics.to_string(index=False))


def build_readme(summary, metrics):
    return "\n".join([
        "# RehabID-Fatigue v0.1 modality ablation",
        "",
        "固定同一留一受试者岭回归管道，逐层加入模态，预测 CMJ 24/72 小时结果。所有目标时间点变量均排除；缺失值只在训练折内用中位数处理，并加入缺失指示器。",
        "",
        "## 加入顺序",
        "",
        "demographic → exercise_load → subjective → heart_hrv → performance → lactate → blood_baseline → cpet_sensitivity",
        "",
        "## 解释边界",
        "",
        "这项实验衡量的是模态增量和跨受试者预测表现，不等同于因果效应，也不等同于真正的个人专属模型。当前每名受试者只有一次主要疲劳事件。CPET 与疲劳实验的时间对齐尚未完全确认，因此单独作为敏感性分析。",
        "",
        "输出：`RehabID-Fatigue_v0.1_ablation_metrics.csv`、`RehabID-Fatigue_v0.1_ablation_summary.json`。",
        "",
    ])


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""First leakage-controlled benchmark for RehabID-Fatigue v0.1.

This is an exploratory benchmark, not a clinical validation. It predicts
24/72-hour CMJ recovery using only baseline and immediate-response variables.
Leave-one-subject-out predictions are saved for auditability.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.dummy import DummyRegressor


ROOT = Path(r"D:\DEV\blood")
UNIFIED = ROOT / "统一数据集"
INPUT = UNIFIED / "统一数据集_受试者主表.csv"
OUT_METRICS = UNIFIED / "RehabID-Fatigue_v0.1_benchmark_metrics.csv"
OUT_PREDS = UNIFIED / "RehabID-Fatigue_v0.1_benchmark_predictions.csv"
OUT_SUMMARY = UNIFIED / "RehabID-Fatigue_v0.1_benchmark_summary.json"
OUT_README = UNIFIED / "RehabID-Fatigue_v0.1_benchmark_README.md"

SEED = 20260906


def to_numeric_frame(df, columns):
    out = pd.DataFrame(index=df.index)
    for col in columns:
        out[col] = pd.to_numeric(df[col], errors="coerce")
    return out


def build_feature_sets(df):
    # These variables are known before the 24/72-hour outcome. All future
    # timepoint variables are intentionally excluded to prevent leakage.
    blocked = {
        "cmj_24h", "cmj_72h", "vas_24h", "vas_72h", "rpe_24h", "rpe_72h",
        "hr_24h_avg", "hr_24h_max", "hr_72h_avg", "hr_72h_max",
        # These aggregates cover a broader date range than one fatigue episode
        # in the current export, so they are excluded from the early-response
        # benchmark until session windows are aligned by subject and date.
        "hr_sessions", "hr_minutes", "hr_avg", "hr_max", "hr_trimp_sum",
        "hr_rel_mean", "hr_zero_rate_mean", "hr_ice_sessions", "hr_land_sessions",
    }
    id_and_text = {"subject_id", "name", "name_aliases", "class", "coach", "gender", "intervention"}
    candidate = []
    for col in df.columns:
        if col in blocked or col in id_and_text or col.startswith("blood_"):
            continue
        if col.startswith(("avg_power_", "peak_power_", "cmj_", "vas_", "rpe_", "lactate_",
                           "hr_", "hrv_", "pt_")) or col in {"age", "height_cm", "weight_kg", "load_pct"}:
            candidate.append(col)
    raw = to_numeric_frame(df, candidate)
    # Do not let almost-empty columns dominate a tiny pilot. This threshold is
    # a feature availability rule, not value-based selection.
    raw = raw.loc[:, raw.notna().sum() >= 10]

    delta = raw.copy()
    pairs = [
        ("vas_post", "vas_rest", "vas_delta_post"),
        ("vas_interv", "vas_rest", "vas_delta_intervention"),
        ("rpe_post", "rpe_rest", "rpe_delta_post"),
        ("rpe_interv", "rpe_rest", "rpe_delta_intervention"),
        ("lactate_post", "lactate_rest", "lactate_delta_post"),
        ("lactate_interv", "lactate_rest", "lactate_delta_intervention"),
        ("hr_post_avg", "hr_rest_avg", "heart_rate_delta_post"),
        ("hr_post_max", "hr_rest_max", "heart_rate_max_delta_post"),
    ]
    for post, base, new in pairs:
        if post in raw.columns and base in raw.columns:
            delta[new] = raw[post] - raw[base]
    return {"raw_absolute": raw, "baseline_aware": delta}


def make_pipeline(model):
    return Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
        ("model", model),
    ])


def evaluate(df, target, feature_set_name, X, model_name, model):
    mask = pd.to_numeric(df[target], errors="coerce").notna()
    y = pd.to_numeric(df.loc[mask, target], errors="coerce").to_numpy(dtype=float)
    X_target = X.loc[mask]
    # Drop columns that are entirely absent in this target's training frame.
    X_target = X_target.loc[:, X_target.notna().any(axis=0)]
    if len(y) < 10:
        return None, None
    estimator = make_pipeline(model)
    cv = LeaveOneOut()
    pred = cross_val_predict(estimator, X_target, y, cv=cv, n_jobs=None)
    metrics = {
        "target": target,
        "feature_set": feature_set_name,
        "model": model_name,
        "n": int(len(y)),
        "feature_count": int(X_target.shape[1]),
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(math.sqrt(mean_squared_error(y, pred))),
        "r2": float(r2_score(y, pred)),
    }
    predictions = pd.DataFrame({
        "subject_id": df.loc[mask, "subject_id"].to_numpy(),
        "name": df.loc[mask, "name"].to_numpy(),
        "target": target,
        "feature_set": feature_set_name,
        "model": model_name,
        "y_true": y,
        "y_pred": pred,
        "residual": y - pred,
    })
    return metrics, predictions


def main():
    df = pd.read_csv(INPUT, encoding="utf-8-sig")
    feature_sets = build_feature_sets(df)
    models = {
        "median_baseline": DummyRegressor(strategy="median"),
        "ridge": Ridge(alpha=10.0),
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=4, max_features=0.7,
            random_state=SEED, n_jobs=1,
        ),
    }
    metrics, predictions = [], []
    for target in ("cmj_24h", "cmj_72h"):
        for feature_set_name, X in feature_sets.items():
            for model_name, model in models.items():
                result, pred = evaluate(df, target, feature_set_name, X, model_name, model)
                if result:
                    metrics.append(result)
                    predictions.append(pred)

    metrics_df = pd.DataFrame(metrics).sort_values(["target", "mae", "model"])
    preds_df = pd.concat(predictions, ignore_index=True)
    metrics_df.to_csv(OUT_METRICS, index=False, encoding="utf-8-sig")
    preds_df.to_csv(OUT_PREDS, index=False, encoding="utf-8-sig")

    summary = {
        "dataset_version": "RehabID-Fatigue v0.1",
        "input": str(INPUT),
        "seed": SEED,
        "validation": "leave-one-subject-out cross-validation",
        "targets": ["cmj_24h", "cmj_72h"],
        "feature_sets": {name: int(X.shape[1]) for name, X in feature_sets.items()},
        "metrics_rows": int(len(metrics_df)),
        "note": "This benchmark estimates out-of-subject performance. It does not train a true per-person model because the current cohort has one primary fatigue episode per subject.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_README.write_text(build_readme(summary, metrics_df), encoding="utf-8")
    print(metrics_df.to_string(index=False))


def build_readme(summary, metrics_df):
    lines = [
        "# RehabID-Fatigue v0.1 benchmark",
        "",
        "本轮实验只使用运动前、运动后即刻和干预后变量，预测 CMJ 24 h/72 h 结果。评价采用留一受试者交叉验证，每次测试受试者的全部记录均不进入训练。",
        "",
        "## 模型",
        "",
        "- `median_baseline`：中位数基线，用于判断模型是否真正超过简单基线。",
        "- `ridge`：带中位数插补和缺失指示器的岭回归。",
        "- `random_forest`：固定随机种子的随机森林，用于探索非线性关系。",
        "- `raw_absolute`：原始绝对值特征。",
        "- `baseline_aware`：原始特征加上运动后/干预后相对静息值的变化量。",
        "",
        "## 输出",
        "",
        "- `RehabID-Fatigue_v0.1_benchmark_metrics.csv`：MAE、RMSE、R² 和特征数量。",
        "- `RehabID-Fatigue_v0.1_benchmark_predictions.csv`：每个测试受试者的真实值、预测值和残差。",
        "- `RehabID-Fatigue_v0.1_benchmark_summary.json`：数据切分与实验配置。",
        "",
        "## 解释边界",
        "",
        "当前每名受试者只有一次完整疲劳实验，因此这不是训练个人专属模型的结果。它只能回答：基线和即时反应变量在新受试者上的预测表现如何。真正的个体化模型需要同一受试者的多次疲劳事件或连续训练周期。",
        "",
        f"随机种子：{summary['seed']}；特征数：" + ", ".join(f"{k}={v}" for k, v in summary["feature_sets"].items()) + "。",
        "",
        "所有输入的缺失值只在训练管道内用训练折中位数处理，并保留缺失指示器；原始数据文件不变。",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

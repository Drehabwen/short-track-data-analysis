# -*- coding: utf-8 -*-
"""基于 chart-visualization skill 的论文图生成脚本

数据源（D:\DEV\blood 内既有 CSV）：
  1. CPET:  最大摄氧量/最大摄氧量数据/cpet_enriched.csv
  2. 心率:  心率/hr_sessions.csv
  3. 血液:  统一数据集/血液明细表_链接后.csv

输出：论文图/ 目录下的 240dpi PNG（打印质量）+ 数据说明。
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\DEV\blood"
OUT = os.path.join(ROOT, "论文图")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 240,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": ["Microsoft YaHei", "SimHei", "sans-serif"],
    "axes.unicode_minus": False,
})

PALETTE = ["#3f7fb8", "#e58f4f", "#5fb06e", "#d05555", "#e0c34e", "#8a94a0"]
sns.set_palette(PALETTE)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"已生成: {path}")
    return path


# ============ 图1：CPET 相对摄氧量分布（按性别 + 有效性） ============
def fig_cpet():
    df = pd.read_csv(os.path.join(ROOT, "最大摄氧量", "最大摄氧量数据",
                                  "cpet_enriched.csv"), encoding="utf-8-sig")
    df = df.dropna(subset=["V'O2/kg_peak"])
    df["性别"] = df["gender"].map({"男性": "男", "女性": "女"})
    # 有效性分级简化
    def cls(r):
        if pd.isna(r["V'O2/kg_peak"]):
            return "无效"
        if pd.notna(r["meas_max_rer"]) and r["meas_max_rer"] >= 1.05:
            return "有效"
        return "亚极量"
    df["有效性"] = df.apply(cls, axis=1)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), constrained_layout=True)
    # 左：总体分布直方图
    ax = axes[0]
    sns.histplot(df["V'O2/kg_peak"], bins=12, kde=True, color=PALETTE[0], ax=ax)
    med = df["V'O2/kg_peak"].median()
    ax.axvline(med, color=PALETTE[1], linestyle="--", linewidth=1.4)
    ax.text(med + 1, ax.get_ylim()[1] * 0.92, f"中位 {med:.0f} ml/kg/min",
            color=PALETTE[1], fontsize=10)
    ax.set_title(f"相对摄氧量分布（n={len(df)}）", fontsize=12)
    ax.set_xlabel("相对摄氧量 (ml/kg/min)")
    ax.set_ylabel("人数")
    # 右：性别箱线图
    ax = axes[1]
    sns.boxplot(data=df, x="性别", y="V'O2/kg_peak", palette=[PALETTE[0], PALETTE[2]], ax=ax)
    sns.stripplot(data=df, x="性别", y="V'O2/kg_peak",
                  color="0.35", alpha=0.55, size=3, jitter=0.12, ax=ax)
    for g in df["性别"].dropna().unique():
        sub = df[df["性别"] == g]
        vo2_mean = sub["V'O2/kg_peak"].mean()
        ax.text(g, ax.get_ylim()[1] * 0.95,
                f"n={len(sub)} · 均值 {vo2_mean:.1f}",
                ha="center", fontsize=9, color="#555")
    ax.set_title("男女相对摄氧量对比", fontsize=12)
    ax.set_ylabel("相对摄氧量 (ml/kg/min)")
    fig.suptitle("图1  全队心肺运动试验（CPET）相对摄氧量", fontsize=13, y=1.02)
    return save(fig, "图1_CPET相对摄氧量分布.png")


# ============ 图2：心率负荷——教练分组对比（近两周） ============
def fig_hr():
    inv = pd.read_csv(os.path.join(ROOT, "心率", "心率场次清单_全量.csv"),
                      encoding="utf-8-sig")
    inv["dt"] = pd.to_datetime(inv["datetime"])
    inv["week"] = np.where(inv["dt"].dt.date.astype(str) >= "2026-08-04", "本周", "上周")
    inv = inv[(inv["dt"].dt.date.astype(str) >= "2026-07-28") &
              (inv["dt"].dt.date.astype(str) <= "2026-08-07")]

    hr = pd.read_csv(os.path.join(ROOT, "心率", "hr_sessions.csv"), encoding="utf-8-sig")
    hr["dt"] = pd.to_datetime(hr["datetime"])
    hr = hr[(hr["dt"].dt.date.astype(str) >= "2026-07-28") &
            (hr["dt"].dt.date.astype(str) <= "2026-08-07")]
    hr = hr.merge(inv[["datetime", "session"]], on="datetime", how="left")

    def coach_of(n):
        n = str(n)
        if "教练D" in n or "教练F" in n:
            return "教练D组(教练F)"
        for c in ["教练C", "教练B", "教练A", "教练E"]:
            if c in n:
                return c
        return "其他"
    hr["教练"] = hr["session"].map(coach_of)
    hr["周"] = np.where(hr["dt"].dt.date.astype(str) >= "2026-08-04", "本周", "上周")
    g = hr.groupby(["教练", "周"]).agg(
        均心=("avg_hr", "mean"), 人数=("athlete", "nunique")).round(1).reset_index()
    # 两周对比条形图
    pivot = g.pivot(index="教练", columns="周", values="均心").reindex(
        ["教练B", "教练A", "教练D组(教练F)", "教练E", "教练C"])
    pivot = pivot.dropna(how="all")
    fig, ax = plt.subplots(figsize=(9.5, 4.6), constrained_layout=True)
    x = np.arange(len(pivot))
    w = 0.36
    for i, wk in enumerate(["上周", "本周"]):
        vals = pivot[wk].values if wk in pivot.columns else np.full(len(pivot), np.nan)
        b = ax.bar(x + (i - 0.5) * w, vals, w, label=wk,
                   color=[PALETTE[4], PALETTE[0]][i],
                   alpha=0.92 if wk == "本周" else 0.65)
        for rect, v in zip(b, vals):
            if not np.isnan(v):
                ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1,
                        f"{v:.0f}", ha="center", fontsize=9, color="#333")
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, fontsize=11)
    ax.set_ylabel("平均心率 (bpm)")
    ax.set_ylim(0, 170)
    ax.legend(frameon=False, fontsize=10)
    ax.set_title("图2  各教练组平均心率：上周 (07-28~30) vs 本周 (08-04~07)",
                 fontsize=12, pad=10)
    return save(fig, "图2_教练组心率两周对比.png")


# ============ 图3：血液恢复指标随干预时间变化 ============
def fig_blood():
    df = pd.read_csv(os.path.join(ROOT, "统一数据集", "血液明细表_链接后.csv"),
                     encoding="utf-8-sig")
    order = {"BL": 0, "24H": 1, "72H": 2}
    df["t"] = df["timepoint"].map(order)
    df = df[df["t"].notna() & df["result_value"].notna()]
    g = df.groupby(["analyte", "t"]).agg(
        m=("result_value", "mean"), n=("result_value", "count")).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), constrained_layout=True)
    titles = {"ck": "肌酸激酶 CK (U/L)", "cortisol": "皮质醇 Cortisol (μg/dL)"}
    for ax, (k, ttl) in zip(axes, titles.items()):
        sub = g[g["analyte"] == k].sort_values("t")
        if sub.empty:
            ax.text(0.5, 0.5, "无数据", ha="center", transform=ax.transAxes)
            continue
        ax.plot(sub["t"], sub["m"], marker="o", linewidth=2.2,
                color=PALETTE[1], markersize=7)
        for _, r in sub.iterrows():
            ax.annotate(f"{r['m']:.0f}\n(n={int(r['n'])})",
                        (r["t"], r["m"]), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=9, color="#444")
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["基线 BL", "24H", "72H"], fontsize=10)
        ax.set_title(ttl, fontsize=12)
        ax.set_ylabel("均值")
    fig.suptitle("图3  急性疲劳干预前后血液恢复指标变化（全队均值）",
                 fontsize=13, y=1.02)
    return save(fig, "图3_血液恢复指标趋势.png")


if __name__ == "__main__":
    paths = [fig_cpet(), fig_hr(), fig_blood()]
    print("\n输出目录:", OUT)
    for p in paths:
        print(" ", os.path.basename(p), f"({os.path.getsize(p)/1024:.0f} KB)")

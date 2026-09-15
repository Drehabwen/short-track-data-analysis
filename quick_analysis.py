# -*- coding: utf-8 -*-
"""新数据小分析：干预恢复对比 / 造模反应 / 前测素质×有氧能力。"""
import math

import numpy as np
import pandas as pd

U = r"D:\DEV\blood\统一数据集"
master = pd.read_csv(U + r"\统一数据集_受试者主表.csv", encoding="utf-8-sig")
pre = pd.read_csv(U + r"\前测明细表.csv", encoding="utf-8-sig")
blood = pd.read_csv(U + r"\血液明细表_链接后.csv", encoding="utf-8-sig")
cpet = pd.read_csv(r"D:\DEV\blood\最大摄氧量\最大摄氧量数据\cpet_enriched.csv",
                   encoding="utf-8-sig")

# ---------- 1. 干预三组恢复对比 ----------
print("=" * 70)
print("1) 干预三组恢复效果（均值±SD, n）")
master["interv"] = master["intervention"]
for metric, cols in [("CK", ["blood_ck_BL", "blood_ck_24H", "blood_ck_72H"]),
                     ("CMJ", ["cmj_pre", "cmj_24h", "cmj_72h"]),
                     ("晨脉HR", ["hr_rest_avg", "hr_24h_avg", "hr_72h_avg"])]:
    print(f"\n--- {metric} ---")
    for g in ["拔罐+推拿", "艾灸+推拿", "常规恢复"]:
        sub = master[master["interv"] == g]
        vals = []
        for c in cols:
            v = pd.to_numeric(sub[c], errors="coerce").dropna()
            vals.append(f"{v.mean():.1f}±{v.std(ddof=1):.1f} (n={len(v)})" if len(v) else "-")
        print(f"{g:6s} | " + " | ".join(vals))

# 24h 变化评分（CK、CMJ）
print("\n--- 变化评分（24h - 基线）---")
for metric, base, t24 in [("CK", "blood_ck_BL", "blood_ck_24H"),
                          ("CMJ", "cmj_pre", "cmj_24h")]:
    for g in ["拔罐+推拿", "艾灸+推拿", "常规恢复"]:
        sub = master[master["interv"] == g]
        a = pd.to_numeric(sub[base], errors="coerce")
        b = pd.to_numeric(sub[t24], errors="coerce")
        d = (b - a).dropna()
        print(f"{metric} {g:6s} Δ={d.mean():+.1f}±{d.std(ddof=1):.1f} (n={len(d)})" if len(d)
              else f"{metric} {g}: -")

# ---------- 2. 造模强度与恢复反应 ----------
print("\n" + "=" * 70)
print("2) 造模强度与恢复反应相关")


def pearson(x, y):
    m = x.notna() & y.notna()
    x, y = x[m], y[m]
    if len(x) < 8 or x.std() == 0 or y.std() == 0:
        return None
    r = float(x.corr(y))
    t = r * math.sqrt((len(x) - 2) / (1 - r * r))
    p = 2 * (1 - 0.5 * math.erfc(abs(t) / math.sqrt(2)))
    return f"n={len(x)} r={r:.2f} p={p:.3f}"


for name, x, y in [
    ("乳酸即刻 vs 心率即刻", "lactate_post", "hr_post_avg"),
    ("造模负荷% vs CK24hΔ", "load_pct", None),
    ("平均功率 vs 乳酸即刻", "avg_power_p1", "lactate_post"),
    ("乳酸即刻 vs CMJ24hΔ", "lactate_post", None),
]:
    if y is None:
        continue
    print(f"{name}: {pearson(pd.to_numeric(master[x], errors='coerce'),
                              pd.to_numeric(master[y], errors='coerce'))}")

master["ck24_delta"] = pd.to_numeric(master["blood_ck_24H"], errors="coerce") - \
    pd.to_numeric(master["blood_ck_BL"], errors="coerce")
master["cmj24_delta"] = pd.to_numeric(master["cmj_24h"], errors="coerce") - \
    pd.to_numeric(master["cmj_pre"], errors="coerce")
print(f"造模负荷% vs CK24hΔ: {pearson(pd.to_numeric(master['load_pct'], errors='coerce'), master['ck24_delta'])}")
print(f"乳酸即刻 vs CMJ24hΔ: {pearson(pd.to_numeric(master['lactate_post'], errors='coerce'), master['cmj24_delta'])}")

# ---------- 3. 前测素质 × 有氧能力 ----------
print("\n" + "=" * 70)
print("3) 前测素质 × CPET 有氧能力（姓名匹配）")


def cls(r):
    if pd.isna(r["V'O2/kg_peak"]) or not r.get("has_exercise", False):
        return "无效"
    if pd.notna(r.get("exercise_dur_s", None)) and r["exercise_dur_s"] < 180:
        return "无效"
    if pd.notna(r["meas_max_rer"]):
        if r["meas_max_rer"] >= 1.05:
            return "有效"
        if r["meas_max_rer"] >= 1.00:
            return "亚极量"
    return "亚极量"


cpet["cls"] = cpet.apply(cls, axis=1)
order = {"有效": 0, "亚极量": 1, "无效": 2}
cpet["_k"] = cpet.apply(
    lambda r: (order[r["cls"]], -r["V'O2/kg_peak"] if pd.notna(r["V'O2/kg_peak"]) else 1e9),
    axis=1)
best = cpet.sort_values("_k").drop_duplicates("name", keep="first")
best = best[best["cls"] != "无效"]

m = best.merge(pre[["name", "fms_total", "ybt_left_ant", "ybt_right_ant",
                    "rom_strength_ankle_dorsi_l", "profile_time_500m_s"]],
               on="name", how="left")
print(f"匹配人数: {m['fms_total'].notna().sum()}/{len(m)}")
for label, col in [("FMS总分", "fms_total"), ("YBT左前", "ybt_left_ant"),
                   ("500m(s)", "profile_time_500m_s")]:
    r = pearson(pd.to_numeric(m["V'O2/kg_peak"], errors="coerce"),
                pd.to_numeric(m[col], errors="coerce"))
    print(f"VO2/kg vs {label}: {r}")

# CMJ 前测（master 表）匹配
m2 = best.merge(master[["name", "cmj_pre"]], on="name", how="left")
print(f"VO2/kg vs CMJ前测: {pearson(pd.to_numeric(m2['V\'O2/kg_peak'], errors='coerce'),
                                    pd.to_numeric(m2['cmj_pre'], errors='coerce'))}")

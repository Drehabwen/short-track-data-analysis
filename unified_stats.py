# -*- coding: utf-8 -*-
"""Compute summary stats for the unified research dataset (weekly report)."""
import json

import numpy as np
import pandas as pd

U = r"D:\DEV\blood\统一数据集"

master = pd.read_csv(U + r"\统一数据集_受试者主表.csv", encoding="utf-8-sig")
pre = pd.read_csv(U + r"\前测明细表.csv", encoding="utf-8-sig")
hr = pd.read_csv(U + r"\心率明细表.csv", encoding="utf-8-sig")
blood = pd.read_csv(U + r"\血液明细表_链接后.csv", encoding="utf-8-sig")
matrix = pd.read_csv(U + r"\数据完整性矩阵.csv", encoding="utf-8-sig")

s = {}
s["n_subjects"] = len(master)
s["n_pre"] = len(pre)
s["n_blood"] = len(blood)
s["n_blood_subjects"] = blood["participant_id"].nunique()
s["n_hr_rows"] = len(hr)
s["interventions"] = master["intervention"].value_counts(dropna=False).to_dict()
s["groups"] = master["class"].value_counts().to_dict()
s["genders"] = master["gender"].value_counts().to_dict()


def avg(series):
    v = pd.to_numeric(series, errors="coerce").dropna()
    return {"n": int(len(v)), "mean": round(float(v.mean()), 2),
            "sd": round(float(v.std(ddof=1)), 2)} if len(v) else None


for col in ["cmj_pre", "cmj_24h", "cmj_72h"]:
    s[col] = avg(master[col])
for col in ["hr_rest_avg", "hr_post_avg", "hr_24h_avg", "hr_72h_avg"]:
    s[col] = avg(master[col])
for col in ["lactate_rest", "lactate_post", "lactate_interv"]:
    s[col] = avg(master[col])
for col in ["vas_rest", "vas_post", "vas_24h", "vas_72h"]:
    s[col] = avg(master[col])
for col in ["rpe_rest", "rpe_post", "rpe_24h", "rpe_72h"]:
    s[col] = avg(master[col])
s["fms_total"] = avg(pre["fms_total"])
s["cmj_pre_fms"] = avg(pre["cmj_pre"]) if "cmj_pre" in pre.columns else None

# blood per analyte per timepoint
bl = blood.copy()
bl["result_value"] = pd.to_numeric(bl["result_value"], errors="coerce")
s["blood_analytes"] = {}
for analyte, g in bl.groupby("analyte"):
    s["blood_analytes"][analyte] = {}
    for tp, gg in g.groupby("timepoint"):
        v = gg["result_value"].dropna()
        if len(v):
            s["blood_analytes"][analyte][tp] = {
                "n": int(len(v)), "mean": round(float(v.mean()), 2)}
s["blood_timepoints"] = bl["timepoint"].value_counts().to_dict()
s["completeness"] = {
    "基础": float(matrix["完整度%"].mean()),
    "前测": float(matrix["前测_FMS"].mean() * 100),
    "血液BL": float(matrix["血液_BL"].mean() * 100),
    "血液24H": float(matrix["血液_24H"].mean() * 100),
    "血液72H": float(matrix["血液_72H"].mean() * 100),
    "心率任一": float(matrix["心率_任一"].mean() * 100),
}

print(json.dumps(s, ensure_ascii=False, indent=1))
with open(r"D:\DEV\blood\unified_stats.json", "w", encoding="utf-8") as f:
    json.dump(s, f, ensure_ascii=False, indent=1, default=str)

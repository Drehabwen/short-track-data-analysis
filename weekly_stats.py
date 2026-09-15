# -*- coding: utf-8 -*-
"""Aggregate stats for the weekly report."""
import glob
import json
import os
import re

import numpy as np
import openpyxl
import pandas as pd

HR_DIR = r"D:\DEV\blood\心率"
CPET_DIR = r"D:\DEV\blood\最大摄氧量\最大摄氧量数据"


def hhmmss(s):
    p = str(s).split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    return None


stats = {}

# ---------- CPET ----------
cpet = pd.read_csv(os.path.join(CPET_DIR, "cpet_enriched.csv"), encoding="utf-8-sig")
stats["cpet_tests"] = len(cpet)
stats["cpet_subjects"] = cpet["name"].nunique()
stats["cpet_male"] = int(cpet[cpet["gender"] == "男性"]["name"].nunique())
stats["cpet_female"] = int(cpet[cpet["gender"] == "女性"]["name"].nunique())
stats["cpet_date_range"] = f"{pd.to_datetime(cpet['start']).min():%m-%d} ~ {pd.to_datetime(cpet['start']).max():%m-%d}"
stats["cpet_breaths"] = int(cpet["n_breaths"].sum())

# ---------- HR sessions ----------
hr_files = sorted(glob.glob(os.path.join(HR_DIR, "*.xlsx")))
n_sessions = 0
total_points = 0
athletes = set()
by_coach = {}
by_type = {"冰上": 0, "陆地": 0, "晨脉/恢复": 0, "其他": 0}
rest_sessions = []
for fn in hr_files:
    name = os.path.basename(fn)
    try:
        wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
    except Exception:
        continue
    ws = wb["团队综合报告"] if "团队综合报告" in wb.sheetnames else wb.worksheets[0]
    meta = None
    for row in ws.iter_rows(values_only=True):
        if row and row[0] and str(row[0]).startswith("训练名称"):
            meta = str(row[0])
            break
    sname = ""
    if meta:
        m = re.search(r"训练名称:\s*(.*?)\s+训练日期:", meta)
        sname = m.group(1).strip() if m else ""
    n_sessions += 1
    # points
    for sn in wb.sheetnames:
        if sn in ("团队综合报告", "阶段报告"):
            continue
        athletes.add(sn)
        s = wb[sn]
        cnt = 0
        for row in s.iter_rows(values_only=True):
            if row and row[0] is not None and re.match(r"^\d+:\d{2}:\d{2}", str(row[0])):
                cnt += 1
        total_points += cnt
    # classify
    if any(k in sname for k in ("24", "48", "72", "24h", "48h", "72h", "晨脉")):
        by_type["晨脉/恢复"] += 1
        rest_sessions.append(name)
    elif "冰" in sname:
        by_type["冰上"] += 1
    elif "陆" in sname or "陆地" in sname:
        by_type["陆地"] += 1
    else:
        by_type["其他"] += 1
    coach = None
    for c in ("教练D", "教练C", "教练B", "教练A", "教练E", "教练F"):
        if c in sname:
            coach = c
            break
    if coach:
        by_coach[coach] = by_coach.get(coach, 0) + 1
    wb.close()

stats["hr_sessions"] = n_sessions
stats["hr_points"] = total_points
stats["hr_athletes"] = len(athletes)
stats["hr_by_type"] = by_type
stats["hr_by_coach"] = by_coach
stats["rest_sessions"] = len(rest_sessions)

# ---------- overlap ----------
hr_names = set()
for fn in hr_files:
    try:
        wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
        for sn in wb.sheetnames:
            if sn not in ("团队综合报告", "阶段报告") and not sn.startswith("访客"):
                hr_names.add(sn)
        wb.close()
    except Exception:
        pass
cpet_names = set(cpet["name"])
stats["both"] = len(hr_names & cpet_names)
stats["hr_only"] = len(hr_names - cpet_names)
stats["cpet_only"] = len(cpet_names - hr_names)

print(json.dumps(stats, ensure_ascii=False, indent=1))
with open(r"D:\DEV\blood\weekly_stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=1)

# -*- coding: utf-8 -*-
"""教练C 7.28 复合场次拆分（前段陆地 + 后段冰上，按 15:22 / 录制后 6193 秒）。

TRIMP 口径: Edward's (区间1-5 权重 1-5)，区间边界用每人整场心率分布校准，
并乘以 k=Z_total/100 使整场 TRIMP 与设备区间计算的旧值完全一致。
"""
import os

import numpy as np
import openpyxl

FILE = r"D:\DEV\blood\心率\2026-07-28_教练C陆上.xlsx"
CUT_SEC = 6193  # 13:38:53 + 103分13秒 = 15:22


def to_sec(v):
    s = str(v).strip()
    p = s.split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    return None


def load():
    wb = openpyxl.load_workbook(FILE, read_only=True, data_only=True)
    ws = wb["团队综合报告"]
    zones_file = {}
    for row in ws.iter_rows(values_only=True):
        if row and row[0] and row[0] not in ("姓名", "七台河短道速滑队"):
            try:
                if row[2] is not None and all(row[i] is not None for i in range(6, 11)):
                    zones_file[row[0]] = [float(str(row[i]).replace("%", ""))
                                          for i in range(6, 11)]
            except (ValueError, IndexError, TypeError):
                pass

    athletes = []
    for sn in wb.sheetnames:
        if sn in ("团队综合报告", "阶段报告"):
            continue
        s = wb[sn]
        rows = list(s.iter_rows(values_only=True))
        body = [r for r in rows[1:] if r[0] is not None]
        if not body:
            continue
        hdr = rows[0]
        df_rows = []
        for r in body:
            t = to_sec(r[0])
            if t is not None:
                try:
                    hr = float(r[1])
                except (TypeError, ValueError):
                    hr = np.nan
                df_rows.append((t, hr))
        if not df_rows:
            continue
        arr = np.array(df_rows, dtype=float)
        sec, hr = arr[:, 0], arr[:, 1]
        athletes.append({"name": sn, "sec": sec, "hr": hr,
                         "zones_file": zones_file.get(sn)})
    wb.close()
    return athletes


def segment_metrics(sec, hr, t0, t1):
    m = (sec >= t0) & (sec < t1) & (hr > 0)
    v = hr[m]
    if len(v) == 0:
        return None
    step = float(np.median(np.diff(sec[m]))) if len(sec[m]) > 1 else 1.0
    return {
        "secs": len(v),
        "min": len(v) * step / 60.0,
        "avg": float(v.mean()),
        "max": float(v.max()),
        "g160": float(np.sum(v >= 160)) * step / 60.0,
        "g170": float(np.sum(v >= 170)) * step / 60.0,
        "g180": float(np.sum(v >= 180)) * step / 60.0,
    }


def zones_for_segment(sec, hr, t0, t1, b):
    m = (sec >= t0) & (sec < t1) & (hr > 0)
    v = hr[m]
    if len(v) == 0:
        return None
    frac = []
    for i in range(5):
        lo = -np.inf if i == 0 else b[i - 1]
        hi = b[i]
        frac.append(float(np.mean((v >= lo) & (v < hi))))
    return frac


def split():
    athletes = load()
    out = []
    for a in athletes:
        z = a["zones_file"]
        if z is None:
            out.append({"name": a["name"], "ok": False})
            continue
        sec, hr = a["sec"], a["hr"]
        valid = hr[hr > 0]
        if len(valid) == 0:
            out.append({"name": a["name"], "ok": False})
            continue
        Z = sum(z)
        if Z <= 0:
            out.append({"name": a["name"], "ok": False})
            continue
        # 区间边界 = 整场有效心率分布的累计分位数（占区间总质量的比例）
        cums = np.cumsum(z)
        b = [float(np.quantile(valid, cums[i] / Z)) for i in range(4)] + [np.inf]
        full_frac = zones_for_segment(sec, hr, sec.min(), sec.max() + 1, b)
        land = segment_metrics(sec, hr, sec.min(), CUT_SEC)
        ice = segment_metrics(sec, hr, CUT_SEC, sec.max() + 1)
        land_frac = zones_for_segment(sec, hr, sec.min(), CUT_SEC, b)
        ice_frac = zones_for_segment(sec, hr, CUT_SEC, sec.max() + 1, b)
        k = Z / 100.0  # 使整场 TRIMP = 设备区间口径

        def trimp(fracs, minutes):
            if fracs is None or minutes is None:
                return np.nan
            return minutes * sum(f * (i + 1) for i, f in enumerate(fracs)) * k

        out.append({
            "name": a["name"], "ok": True,
            "land": land, "ice": ice,
            "land_frac": land_frac, "ice_frac": ice_frac,
            "land_trimp": trimp(land_frac, land["min"] if land else None),
            "ice_trimp": trimp(ice_frac, ice["min"] if ice else None),
        })
    return out


if __name__ == "__main__":
    import pandas as pd
    rows = []
    for r in split():
        if not r["ok"]:
            rows.append({"name": r["name"], "land_avg": None, "ice_avg": None,
                         "land_trimp": None, "ice_trimp": None})
            continue
        if r["land"] is None or r["ice"] is None:
            rows.append({"name": r["name"], "land_avg": None, "ice_avg": None,
                         "land_trimp": None, "ice_trimp": None})
            continue
        rows.append({
            "name": r["name"],
            "land_min": round(r["land"]["min"]),
            "land_avg": round(r["land"]["avg"]), "ice_avg": round(r["ice"]["avg"]),
            "ice_max": round(r["ice"]["max"]),
            "ice_160": round(r["ice"]["g160"], 1),
            "land_trimp": round(r["land_trimp"]), "ice_trimp": round(r["ice_trimp"]),
        })
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    print("总TRIMP:", round(df["land_trimp"].sum() + df["ice_trimp"].sum(), 1))

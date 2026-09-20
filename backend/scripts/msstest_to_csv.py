# -*- coding: utf-8 -*-
"""将 MetaMax .msstest 测试文件转换为 CSV（摘要 + 逐呼吸）。

用法：python scripts/msstest_to_csv.py
输出：
  最大摄氧量_msstest_摘要.csv   每份测试一行（峰值指标）
  最大摄氧量_msstest_逐呼吸.csv 每份测试逐呼吸数据
"""
import base64
import glob
import gzip
import os
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = r"D:\DEV\blood\最大摄氧量\最大摄氧量数据\新的最大摄氧量数据\最大"
OUT_DIR = r"D:\DEV\blood\最大摄氧量"

# MetaMax 变量编号 → 含义（推断）
VAR_NAMES = {
    "2001": "VO2_Lmin",
    "2002": "VCO2_Lmin",
    "2003": "VE_Lmin",
    "2004": "vo2kg?",
    "2007": "vco2kg?",
    "2008": "?",
    "2010": "?",
    "2011": "?",
    "2012": "?",
    "2013": "?",
    "2014": "?",
    "2015": "?",
    "2016": "HR",
    "2017": "HR2?",
}


def read_msstest(path):
    """返回 (TestGen根, 摘要dict)。"""
    raw = open(path, "rb").read().replace(b'encoding="utf-16"', b'encoding="utf-8"')
    root = ET.fromstring(raw)
    data_b64 = ""
    for el in root.iter():
        if el.tag.split("}")[-1] == "Data":
            data_b64 = (el.text or "").strip()
    blob = base64.b64decode(data_b64)
    inner = gzip.decompress(blob[4:]).replace(b'encoding="utf-16"', b'encoding="utf-8"')
    r2 = ET.fromstring(inner)
    return r2


def el_text(root, tag):
    for el in root.iter():
        if el.tag.split("}")[-1] == tag and (el.text or "").strip():
            return el.text.strip()
    return ""


def summary_of(r2):
    name = el_text(r2, "Name") + el_text(r2, "FirstName")
    sex = el_text(r2, "Sex")
    birth = el_text(r2, "BirthDate")
    start = el_text(r2, "TestBegin")
    dur_ms = el_text(r2, "TestDurationMeasured")
    weight = el_text(r2, "PersonInitialWeightForWattWeightWLP")
    wlp = el_text(r2, "WLPName")
    return {
        "name": name,
        "sex": "男" if sex == "MALE" else ("女" if sex == "FEMALE" else sex),
        "birth": birth[:10] if birth else "",
        "test_start": start[:19] if start else "",
        "duration_sec": round(int(dur_ms) / 1000, 1) if dur_ms and dur_ms.isdigit() else "",
        "weight_kg": weight,
        "protocol": wlp,
    }


def variables_of(r2):
    """返回 {var_nr: [values]} + 时间序列。"""
    vars_data = {}
    time_seq = {}
    for vd in r2.iter():
        tag = vd.tag.split("}")[-1]
        if tag == "VariableData":
            nr_el = vd.find(".//{*}VariableNr")
            vals_el = vd.find(".//{*}Values")
            nr = nr_el.text.strip() if nr_el is not None and nr_el.text else ""
            nums = []
            if vals_el is not None:
                for d in list(vals_el):
                    t = (d.text or "").strip()
                    if t and t != "NaN":
                        try:
                            nums.append(float(t))
                        except ValueError:
                            nums.append(None)
                    else:
                        nums.append(None)
            if nr:
                vars_data[nr] = nums
        elif tag == "TimeSequence":
            nr_el = vd.find(".//{*}Nr")
            vals_el = vd.find(".//{*}Values")
            nr = nr_el.text.strip() if nr_el is not None and nr_el.text else ""
            vals = [float(d.text) for d in list(vals_el) if d.text]
            if nr:
                time_seq[nr] = vals
    return vars_data, time_seq


def main():
    files = sorted(glob.glob(os.path.join(SRC_DIR, "*.msstest")))
    print(f"找到 {len(files)} 个 .msstest 文件")

    summaries = []
    breath_rows = []
    for f in files:
        base = os.path.basename(f)
        try:
            r2 = read_msstest(f)
            s = summary_of(r2)
            vars_data, time_seq = variables_of(r2)
            s["file"] = base

            # 峰值指标
            vo2 = vars_data.get("2001", [])
            vco2 = vars_data.get("2002", [])
            ve = vars_data.get("2003", [])
            hr = vars_data.get("2016", [])
            vo2_peak = max((v for v in vo2 if v is not None), default=None)
            vco2_peak = max((v for v in vco2 if v is not None), default=None)
            ve_peak = max((v for v in ve if v is not None), default=None)
            hr_peak = max((v for v in hr if v is not None), default=None)
            # RER = VCO2/VO2 逐点，取 max（<1.5 合理范围）
            rers = [b / a for a, b in zip(vo2, vco2) if a and b and 0 < b / a < 1.5]
            rer_peak = max(rers) if rers else None
            # VO2/kg
            weight = float(s["weight_kg"]) if s["weight_kg"] else None
            vo2kg_peak = (vo2_peak / weight * 1000) if (vo2_peak and weight) else None
            # VE/VCO2 斜率（线性回归）
            slope = None
            pairs = [(a, b) for a, b in zip(vco2, ve) if a and b]
            if len(pairs) > 10:
                xs = [p[0] for p in pairs]
                ys = [p[1] for p in pairs]
                n = len(xs)
                mx = sum(xs) / n
                my = sum(ys) / n
                sxx = sum((x - mx) ** 2 for x in xs)
                sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                slope = sxy / sxx if sxx else None

            s.update({
                "vo2_peak_Lmin": round(vo2_peak, 3) if vo2_peak else "",
                "vo2kg_peak": round(vo2kg_peak, 1) if vo2kg_peak else "",
                "vco2_peak_Lmin": round(vco2_peak, 3) if vco2_peak else "",
                "rer_peak": round(rer_peak, 2) if rer_peak else "",
                "ve_peak_Lmin": round(ve_peak, 1) if ve_peak else "",
                "hr_peak": round(hr_peak) if hr_peak else "",
                "ve_vco2_slope": round(slope, 2) if slope else "",
                "n_breaths": len(vo2),
            })
            summaries.append(s)

            # 逐呼吸行（取 VO2/VCO2/VE/HR）
            n = max(len(vo2), len(vco2), len(ve), len(hr))
            for i in range(n):
                breath_rows.append({
                    "file": base,
                    "name": s["name"],
                    "test_start": s["test_start"],
                    "breath_n": i + 1,
                    "VO2_Lmin": vo2[i] if i < len(vo2) else "",
                    "VCO2_Lmin": vco2[i] if i < len(vco2) else "",
                    "VE_Lmin": ve[i] if i < len(ve) else "",
                    "HR": hr[i] if i < len(hr) else "",
                    "RER": (vco2[i] / vo2[i]) if (i < len(vo2) and i < len(vco2) and vo2[i] and 0 < vco2[i] / vo2[i] < 1.5) else "",
                })
            print(f"  ✓ {base}: {s['name']} {s['test_start'][:10]} | VO2/kg={s['vo2kg_peak']} RER={s['rer_peak']} HR={s['hr_peak']}")
        except Exception as e:
            print(f"  ✗ {base}: {e}")
            summaries.append({"file": base, "error": str(e)})

    # 写 CSV
    import csv
    sum_csv = os.path.join(OUT_DIR, "最大摄氧量_msstest_摘要.csv")
    with open(sum_csv, "w", newline="", encoding="utf-8-sig") as f:
        cols = ["file", "name", "sex", "birth", "test_start", "duration_sec", "weight_kg",
                "protocol", "vo2_peak_Lmin", "vo2kg_peak", "vco2_peak_Lmin", "rer_peak",
                "ve_peak_Lmin", "hr_peak", "ve_vco2_slope", "n_breaths"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)

    br_csv = os.path.join(OUT_DIR, "最大摄氧量_msstest_逐呼吸.csv")
    with open(br_csv, "w", newline="", encoding="utf-8-sig") as f:
        cols = ["file", "name", "test_start", "breath_n", "VO2_Lmin", "VCO2_Lmin", "VE_Lmin", "HR", "RER"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(breath_rows)

    print(f"\n摘要 CSV: {sum_csv}（{len(summaries)} 行）")
    print(f"逐呼吸 CSV: {br_csv}（{len(breath_rows)} 行）")


if __name__ == "__main__":
    main()

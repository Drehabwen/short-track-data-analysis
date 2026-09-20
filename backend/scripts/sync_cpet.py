# -*- coding: utf-8 -*-
"""将 .msstest 解析的 CPET 测试同步到平台 cpet_tests。

用法：python -m scripts.sync_cpet
"""
import base64
import glob
import gzip
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import CpetTest, Participant  # noqa: E402

MSTEST_DIR = r"D:\DEV\blood\最大摄氧量\最大摄氧量数据\新的最大摄氧量数据\最大"


def parse_msstest(path):
    raw = open(path, "rb").read().replace(b'encoding="utf-16"', b'encoding="utf-8"')
    root = ET.fromstring(raw)
    data_b64 = ""
    for el in root.iter():
        if el.tag.split("}")[-1] == "Data":
            data_b64 = (el.text or "").strip()
    blob = base64.b64decode(data_b64)
    inner = gzip.decompress(blob[4:]).replace(b'encoding="utf-16"', b'encoding="utf-8"')
    r2 = ET.fromstring(inner)

    def txt(tag):
        for el in r2.iter():
            if el.tag.split("}")[-1] == tag and (el.text or "").strip():
                return el.text.strip()
        return ""

    vars_data = {}
    for vd in r2.iter():
        if vd.tag.split("}")[-1] != "VariableData":
            continue
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

    name = txt("Name") + txt("FirstName")
    sex_raw = txt("Sex")
    sex = "男" if sex_raw == "MALE" else ("女" if sex_raw == "FEMALE" else sex_raw)
    birth = txt("BirthDate")[:10]
    start = txt("TestBegin")[:19]
    dur_ms = txt("TestDurationMeasured")
    dur_sec = int(round(int(dur_ms) / 1000)) if dur_ms.isdigit() else None
    weight = float(txt("PersonInitialWeightForWattWeightWLP")) if txt("PersonInitialWeightForWattWeightWLP") else None

    vo2 = vars_data.get("2001", [])
    vco2 = vars_data.get("2002", [])
    ve = vars_data.get("2003", [])
    hr = vars_data.get("2016", [])

    vo2_peak = max((v for v in vo2 if v), default=None)
    ve_peak = max((v for v in ve if v), default=None)
    hr_peak = max((v for v in hr if v), default=None)
    rers = [b / a for a, b in zip(vo2, vco2) if a and b and 0.7 < b / a < 1.5]
    rer_max = max(rers) if rers else None
    vo2kg_peak = (vo2_peak / weight * 1000) if (vo2_peak and weight) else None

    slope = None
    pairs = [(a, b) for a, b in zip(vco2, ve) if a and b]
    if len(pairs) > 10:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        slope = sxy / sxx if sxx else None

    # 有效性分级（与报告口径一致）
    if not vo2kg_peak:
        vc = "无效"
    elif dur_sec and dur_sec < 180:
        vc = "无效"
    elif rer_max is not None and rer_max >= 1.05:
        vc = "有效"
    elif rer_max is not None and rer_max >= 1.0:
        vc = "亚极量"
    else:
        vc = "亚极量"

    return {
        "name": name, "sex": sex, "birth": birth, "start": start,
        "duration_s": dur_sec, "weight_kg": weight,
        "vo2kg_peak": vo2kg_peak, "vo2_peak": vo2_peak,
        "hr_peak": hr_peak, "rer_peak": rer_max, "ve_peak": ve_peak,
        "slope_ve_vco2": slope, "valid_class": vc,
        "device": "MetaMax 3B", "file": os.path.basename(path),
    }


def sync():
    files = sorted(glob.glob(os.path.join(MSTEST_DIR, "*.msstest")))
    print(f"扫描到 {len(files)} 个 .msstest")

    db = SessionLocal()
    try:
        name2id = {p.name: p.participant_id for p in db.query(Participant).all() if p.name}
        created = skipped = 0
        for f in files:
            rec = parse_msstest(f)
            # 幂等：同 姓名+开始时间 已存在则跳过
            start_dt = datetime.fromisoformat(rec["start"]) if rec["start"] else None
            exists = db.query(CpetTest).filter(
                CpetTest.name == rec["name"], CpetTest.test_start == start_dt
            ).first()
            if exists:
                skipped += 1
                print(f"  跳过(已存在): {rec['name']} {rec['start'][:10]}")
                continue
            db.add(CpetTest(
                file=rec["file"],
                name=rec["name"],
                subject_id=name2id.get(rec["name"]),
                gender=rec["sex"],
                age_years=None,
                weight_kg=rec["weight_kg"],
                test_start=datetime.fromisoformat(rec["start"]) if rec["start"] else None,
                device=rec["device"],
                duration_s=rec["duration_s"],
                valid_class=rec["valid_class"],
                vo2kg_peak=rec["vo2kg_peak"],
                vo2_peak=rec["vo2_peak"],
                hr_peak=rec["hr_peak"],
                rer_peak=rec["rer_peak"],
                ve_peak=rec["ve_peak"],
                slope_ve_vco2=rec["slope_ve_vco2"],
                exercise_dur_s=rec["duration_s"],
                meas_max_vo2kg=rec["vo2kg_peak"],
                meas_max_rer=rec["rer_peak"],
                meas_max_hr=rec["hr_peak"],
            ))
            created += 1
            print(f"  [新增] {rec['name']} {rec['start'][:10]} | VO2/kg={rec['vo2kg_peak']} | {rec['valid_class']}")
        db.commit()
        total = db.query(CpetTest).count()
        print(f"\n新增 {created}，跳过 {skipped}，平台 cpet_tests 现有 {total} 条")
    finally:
        db.close()


if __name__ == "__main__":
    sync()

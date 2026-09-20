# -*- coding: utf-8 -*-
"""将最新心率数据（心率/hr_sessions.csv）同步到平台 PostgreSQL。

数据源为心率管线产物（inventory_hr → hr_profile），含最新场次、
8/13 访客真实姓名映射与滕雨桐时间切片修正。
用法：python -m scripts.sync_hr
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import HrSession, Participant  # noqa: E402

SRC = r"D:\DEV\blood\心率\hr_sessions.csv"


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def coach_of(session_name):
    """从场次名解析教练（与 hr_2wk_stats.py 同一口径）。"""
    s = str(session_name or "")
    if "姚教练" in s or "尹教练" in s:
        return "姚教练组(尹教练)"
    for c, full in [("张", "张教练"), ("李", "李教练"), ("陈", "陈教练"), ("于", "于教练")]:
        if c in s:
            return full
    return None


def sync():
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    print(f"读取 {SRC}: {len(df)} 行")
    # 场次名 merge（与 hr_2wk_stats.py 同一数据源），用于教练归属
    try:
        inv = pd.read_csv(r"D:\DEV\blood\心率\心率场次清单_全量.csv", encoding="utf-8-sig")
        inv["dt"] = pd.to_datetime(inv["datetime"])
        inv = inv.drop_duplicates(subset=["dt"], keep="first")
        df["dt"] = pd.to_datetime(df["datetime"])
        df = df.merge(inv[["dt", "session"]], on="dt", how="left")
    except Exception as e:
        print("场次清单 merge 失败:", e)
        df["session"] = None

    db = SessionLocal()
    try:
        # 姓名 → 运动员编号映射（用于 subject_id 关联）
        name2id = {p.name: p.participant_id for p in db.query(Participant).all() if p.name}
        db.query(HrSession).delete()
        created = 0
        for _, r in df.iterrows():
            athlete = r.get("athlete")
            db.add(HrSession(
                athlete=athlete,
                subject_id=name2id.get(athlete),
                datetime=parse_dt(r.get("datetime")),
                session_name=r.get("session") if "session" in df.columns else None,
                coach=coach_of(r.get("session") if "session" in df.columns else None),
                session_type=None,                duration_min=to_f(r.get("duration_min")),
                avg_hr=to_f(r.get("avg_hr")),
                max_hr=to_f(r.get("max_hr")),
                cal=to_f(r.get("cal")),
                z1=to_f(r.get("z1")), z2=to_f(r.get("z2")), z3=to_f(r.get("z3")),
                z4=to_f(r.get("z4")), z5=to_f(r.get("z5")),
            ))
            created += 1
        db.commit()
        linked = db.query(HrSession).filter(HrSession.subject_id.isnot(None)).count()
        total = db.query(HrSession).count()
        print(f"已同步 {created} 条，平台 hr_sessions 现有 {total} 条（{linked} 条已关联运动员）")
    finally:
        db.close()


def to_f(v):
    try:
        return float(v) if v is not None and str(v).strip() not in ("", "nan", "None") else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sync()

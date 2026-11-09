# -*- coding: utf-8 -*-
"""把训练心率 CSV 导入 hr_sessions（冰衡模块数据准备）。

用法：
    python scripts/import_hr_sessions.py "C:\\path\\qitaihe_group_sessions.csv"

CSV 期望列：name/date/hr_mean/hr_max/dur（dur 为秒）
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import HrSession  # noqa: E402

Base.metadata.create_all(bind=engine)


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main(path: str) -> None:
    db = SessionLocal()
    inserted = 0
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("name") or "").strip()
                date_s = (row.get("date") or "").strip()
                if not name or not date_s:
                    continue
                try:
                    dt = datetime.fromisoformat(date_s)
                except ValueError:
                    continue
                dur_s = to_float(row.get("dur"))
                sess = HrSession(
                    athlete=name,
                    subject_id=name,
                    datetime=dt,
                    session_name=(row.get("session_id") or "").strip()[:50] or None,
                    coach=(row.get("coach") or "").strip()[:20] or None,
                    session_type=(row.get("group") or "").strip()[:20] or None,
                    duration_min=round(dur_s / 60.0, 1) if dur_s else None,
                    avg_hr=to_float(row.get("hr_mean")),
                    max_hr=to_float(row.get("hr_max")),
                )
                db.add(sess)
                inserted += 1
        db.commit()
    finally:
        db.close()
    print(f"导入完成：{inserted} 条 -> {engine.url}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])

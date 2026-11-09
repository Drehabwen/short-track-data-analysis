# -*- coding: utf-8 -*-
"""冰衡：每日状态录入、赛前减量、训练单导出。

POST /api/decision/status     录入/更新当日状态（睡眠、主观疲劳、晨脉）
GET  /api/decision/taper      赛前减量计划（倒计时 + 每日目标负荷）
GET  /api/decision/export.csv 今日训练单导出
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyStatus
from ..services import load_metrics as lm
from .decision import WINDOW_DAYS, _anchor, _collect, _fatigue, _status

router = APIRouter(prefix="/api/decision", tags=["decision"])


class StatusIn(BaseModel):
    athlete_name: str
    day: str | None = None
    sleep_hours: float | None = None
    fatigue: int | None = None          # 1-10 主观疲劳
    morning_hr: int | None = None
    muscle_soreness: int | None = None
    weight_kg: float | None = None
    note: str | None = None


@router.post("/status")
def upsert_status(payload: StatusIn, db: Session = Depends(get_db)):
    day = date.fromisoformat(payload.day) if payload.day else _anchor(db)
    row = db.execute(
        select(DailyStatus).where(
            DailyStatus.athlete_id == payload.athlete_name,
            DailyStatus.status_date == day,
        )
    ).scalar_one_or_none()
    if row is None:
        row = DailyStatus(athlete_id=payload.athlete_name, status_date=day)
        db.add(row)
    row.sleep_hours = payload.sleep_hours
    row.fatigue = payload.fatigue
    row.morning_hr = payload.morning_hr
    row.muscle_soreness = payload.muscle_soreness
    row.weight_kg = payload.weight_kg
    row.note = payload.note
    db.commit()
    return {"ok": True, "day": day.isoformat()}


@router.get("/taper")
def taper(event: str | None = None, db: Session = Depends(get_db)):
    """赛前减量：从当前基准日到比赛日，给出每日目标负荷与阶段建议。"""
    anchor = _anchor(db)
    event_day = date.fromisoformat(event) if event else anchor + timedelta(days=10)
    total = max((event_day - anchor).days, 1)
    plan = []
    for i in range(total + 1):
        d = anchor + timedelta(days=i)
        left = total - i
        pct = max(30, round(100 - 70 * (i / total)))
        if left >= 7:
            phase, tip = "维持期", "保持训练量，不做额外加量"
        elif left >= 4:
            phase, tip = "减量期", "总量降到 60–70%，保留强度课"
        elif left >= 1:
            phase, tip = "赛前期", "短促刺激，避免疲劳堆积"
        else:
            phase, tip = "比赛日", "全力比赛"
        plan.append({"date": d.isoformat(), "d_minus": left, "target_pct": pct,
                     "phase": phase, "tip": tip})
    return {"anchor": anchor.isoformat(), "event": event_day.isoformat(),
            "days_to_event": total, "plan": plan}


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    """导出今日训练单（CSV，Excel 直接打开）。"""
    anchor = _anchor(db)
    since = anchor - timedelta(days=WINDOW_DAYS)
    daily = _collect(db, since)
    fat = _fatigue(db, since)
    stat = _status(db, since)
    rows = []
    for who, series in daily.items():
        metrics = lm.compute_series(series, fat.get(who), end=anchor, status_by_day=stat.get(who))
        sm = lm.summarize(metrics)
        if not sm:
            continue
        rows.append([who, sm["level_text"], sm["suggested_pct"], sm["acwr"], sm["monotony"],
                     sm.get("fatigue_index"), sm["week_load"], sm["reason"]])
    rows.sort(key=lambda r: (r[1], -(r[3] or 0)))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["运动员", "建议", "建议负荷%", "ACWR", "单调性", "疲劳指数", "本周负荷", "依据"])
    w.writerows(rows)
    data = "\ufeff" + buf.getvalue()
    filename = f"training_sheet_{anchor.isoformat()}.csv"
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

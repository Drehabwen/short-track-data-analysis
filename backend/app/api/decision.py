# -*- coding: utf-8 -*-
"""训练决策 API（冰衡模块）。

GET  /api/decision/today            今日全队决策卡（默认以最近一次训练日为基准）
GET  /api/decision/athlete/{name}   单人负荷-恢复序列
POST /api/decision/log              教练决策留痕
GET  /api/decision/logs             最近决策记录
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyStatus, DecisionLog, HrSession
from ..services import load_metrics as lm

router = APIRouter(prefix="/api/decision", tags=["decision"])

WINDOW_DAYS = 45


def _session_load(row: HrSession) -> float:
    zones = None
    if any(getattr(row, f"z{i}", None) is not None for i in range(1, 6)):
        zones = {i: (getattr(row, f"z{i}", None) or 0) for i in range(1, 6)}
    return lm.session_load(row.duration_min, row.avg_hr, row.max_hr, zones)


def _anchor(db: Session) -> date:
    """以库中最近一次训练日期为“今天”，避免历史数据过期后全部为空。"""
    m = db.execute(select(func.max(HrSession.datetime))).scalar()
    return m.date() if m else date.today()


def _collect(db: Session, since: date) -> dict[str, dict[date, float]]:
    stmt = select(HrSession).where(HrSession.datetime >= datetime.combine(since, datetime.min.time()))
    rows = db.execute(stmt).scalars().all()
    daily: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if not r.datetime:
            continue
        who = (r.athlete or "").strip()
        if not who:
            continue
        daily[who][r.datetime.date()] += _session_load(r)
    return daily


def _fatigue(db: Session, since: date) -> dict[str, dict[date, int]]:
    stmt = select(DailyStatus).where(DailyStatus.status_date >= since)
    out: dict[str, dict[date, int]] = defaultdict(dict)
    for r in db.execute(stmt).scalars().all():
        if r.athlete_id and r.status_date and r.fatigue is not None:
            out[r.athlete_id][r.status_date] = int(r.fatigue)
    return out


def _status(db: Session, since: date) -> dict[str, dict[date, dict]]:
    stmt = select(DailyStatus).where(DailyStatus.status_date >= since)
    out: dict[str, dict[date, dict]] = defaultdict(dict)
    for r in db.execute(stmt).scalars().all():
        if not r.athlete_id or not r.status_date:
            continue
        out[r.athlete_id][r.status_date] = {
            "fatigue": r.fatigue, "morning_hr": r.morning_hr,
            "sleep_hours": r.sleep_hours, "muscle_soreness": r.muscle_soreness,
        }
    return out


@router.get("/today")
def today(
    day: str | None = Query(None, description="基准日期 YYYY-MM-DD，默认取最近一次训练日"),
    db: Session = Depends(get_db),
):
    anchor = date.fromisoformat(day) if day else _anchor(db)
    since = anchor - timedelta(days=WINDOW_DAYS)
    daily = _collect(db, since)
    counts = {"green": 0, "yellow": 0, "red": 0, "under": 0, "unknown": 0}
    if not daily:
        return {"date": anchor.isoformat(), "anchor": anchor.isoformat(), "cards": counts,
                "athletes": [], "note": "该时间段暂无训练心率数据，请先导入 hr_sessions"}

    fat = _fatigue(db, since)
    stat = _status(db, since)
    items = []
    for who, series in daily.items():
        metrics = lm.compute_series(series, fat.get(who), end=anchor, status_by_day=stat.get(who))
        s = lm.summarize(metrics)
        if not s:
            continue
        s["athlete"] = who
        counts[s["level"]] = counts.get(s["level"], 0) + 1
        items.append(s)
    order = {"red": 0, "yellow": 1, "under": 2, "unknown": 3, "green": 4}
    items.sort(key=lambda x: (order.get(x["level"], 9), -(x.get("acwr") or 0)))
    return {"date": anchor.isoformat(), "anchor": anchor.isoformat(), "cards": counts, "athletes": items}


@router.get("/athlete/{name}")
def athlete(name: str, days: int = 28, db: Session = Depends(get_db)):
    anchor = _anchor(db)
    since = anchor - timedelta(days=max(days, 40))
    daily = _collect(db, since)
    series = daily.get(name)
    if not series:
        raise HTTPException(404, f"未找到运动员 {name} 的训练心率数据")
    metrics = lm.compute_series(series, _fatigue(db, since).get(name), end=anchor,
                                status_by_day=_status(db, since).get(name))
    return {
        "athlete": name,
        "anchor": anchor.isoformat(),
        "summary": lm.summarize(metrics),
        "series": [
            {"date": m.day.isoformat(), "load": m.load, "acute": m.acute, "chronic": m.chronic,
             "acwr": m.acwr, "monotony": m.monotony, "strain": m.strain,
             "level": m.level, "reason": m.reason}
            for m in metrics
        ],
    }


class DecisionIn(BaseModel):
    athlete_name: str
    level: str
    suggested_pct: int | None = None
    reason: str | None = None
    acwr: float | None = None
    monotony: float | None = None
    decided_by: str = "coach"
    note: str | None = None


@router.post("/log")
def log_decision(payload: DecisionIn, db: Session = Depends(get_db)):
    row = DecisionLog(
        athlete_name=payload.athlete_name,
        athlete_id=payload.athlete_name,
        log_date=_anchor(db),
        level=payload.level,
        suggested_pct=payload.suggested_pct,
        reason=payload.reason,
        acwr=payload.acwr,
        monotony=payload.monotony,
        decided_by=payload.decided_by,
        note=payload.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.get("/logs")
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    stmt = select(DecisionLog).order_by(DecisionLog.id.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return {"items": [
        {"id": r.id, "athlete": r.athlete_name, "date": r.log_date.isoformat() if r.log_date else None,
         "level": r.level, "suggested_pct": r.suggested_pct, "reason": r.reason,
         "decided_by": r.decided_by}
        for r in rows
    ]}

@router.get("/weekly")
def weekly(days: int = 14, db: Session = Depends(get_db)):
    """近 N 天全队负荷曲线 + 超阈名单。"""
    anchor = _anchor(db)
    span = max(7, min(days, 42))
    since = anchor - timedelta(days=WINDOW_DAYS)   # 计算窗口固定 45 天，保证与今日卡口径一致
    daily = _collect(db, since)
    chart_from = anchor - timedelta(days=span - 1)
    d = chart_from
    day_list, team = [], []
    while d <= anchor:
        day_list.append(d.isoformat())
        team.append(round(sum(series.get(d, 0.0) for series in daily.values()), 1))
        d += timedelta(days=1)
    fat = _fatigue(db, since)
    stat = _status(db, since)
    alerts = []
    for who, series in daily.items():
        metrics = lm.compute_series(series, fat.get(who), end=anchor, status_by_day=stat.get(who))
        s = lm.summarize(metrics)
        if s and s["level"] in ("red", "yellow"):
            s["athlete"] = who
            alerts.append(s)
    alerts.sort(key=lambda x: (0 if x["level"] == "red" else 1, -(x.get("acwr") or 0)))
    return {"anchor": anchor.isoformat(), "days": day_list, "team_load": team, "alerts": alerts}

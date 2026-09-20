# -*- coding: utf-8 -*-
"""参赛记录 API：短道速滑比赛成绩的增删改查。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CompetitionResult, Participant

router = APIRouter(prefix="/api/competitions", tags=["competitions"])

# 赛事项目字典（可在此维护，前端动态获取，不硬编码）
COMPETITION_EVENTS = [
    {"name": "500m", "label": "500米"},
    {"name": "1000m", "label": "1000米"},
    {"name": "1500m", "label": "1500米"},
    {"name": "3000m", "label": "3000米"},
    {"name": "relay", "label": "接力"},
    {"name": "other", "label": "其他"},
]


@router.get("/events")
def competition_events():
    """参赛项目字典（动态配置，前端不硬编码）。"""
    return COMPETITION_EVENTS


class CompetitionIn(BaseModel):
    participant_id: str
    competition_name: str | None = None
    competition_date: date | None = None
    venue: str | None = None
    event: str | None = None
    time_result: str | None = None
    time_seconds: float | None = None
    rank: int | None = None
    note: str | None = None


def _parse_seconds(t: str | None) -> float | None:
    """解析成绩文本 '1:23.45' 或 '83.45' → 秒"""
    if not t:
        return None
    t = t.strip()
    try:
        if ':' in t:
            m, s = t.split(':')
            return round(int(m) * 60 + float(s), 2)
        return round(float(t), 2)
    except ValueError:
        return None


@router.get("")
def list_competitions(
    participant_id: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(CompetitionResult)
    if participant_id:
        q = q.filter(CompetitionResult.participant_id == participant_id)
    rows = q.order_by(CompetitionResult.competition_date.desc(), CompetitionResult.id.desc()).all()
    return [
        {
            "id": c.id, "participant_id": c.participant_id,
            "name": c.participant_id and _athlete_name(db, c.participant_id),
            "competition_name": c.competition_name,
            "competition_date": c.competition_date.isoformat() if c.competition_date else None,
            "venue": c.venue, "event": c.event,
            "time_result": c.time_result, "time_seconds": c.time_seconds,
            "rank": c.rank, "note": c.note,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


@router.post("")
def create_competition(payload: CompetitionIn, db: Session = Depends(get_db)):
    if not db.query(Participant).filter(Participant.participant_id == payload.participant_id).first():
        raise HTTPException(status_code=404, detail="运动员不存在")
    c = CompetitionResult(
        participant_id=payload.participant_id,
        competition_name=payload.competition_name,
        competition_date=payload.competition_date,
        venue=payload.venue,
        event=payload.event,
        time_result=payload.time_result,
        time_seconds=payload.time_seconds if payload.time_seconds is not None else _parse_seconds(payload.time_result),
        rank=payload.rank,
        note=payload.note,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"ok": True, "id": c.id}


@router.patch("/{cid}")
def update_competition(cid: int, payload: CompetitionIn, db: Session = Depends(get_db)):
    c = db.get(CompetitionResult, cid)
    if not c:
        raise HTTPException(status_code=404, detail="记录不存在")
    data = payload.model_dump(exclude_unset=True)
    if "participant_id" in data and data["participant_id"]:
        if not db.query(Participant).filter(Participant.participant_id == data["participant_id"]).first():
            raise HTTPException(status_code=404, detail="运动员不存在")
    if data.get("time_result") is not None and data.get("time_seconds") is None:
        data["time_seconds"] = _parse_seconds(data["time_result"])
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{cid}")
def delete_competition(cid: int, db: Session = Depends(get_db)):
    c = db.get(CompetitionResult, cid)
    if not c:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(c)
    db.commit()
    return {"ok": True}


def _athlete_name(db: Session, pid: str) -> str | None:
    p = db.query(Participant).filter(Participant.participant_id == pid).first()
    return p.name if p else None

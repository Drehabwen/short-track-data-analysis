# -*- coding: utf-8 -*-
"""运动员管理 API：CRUD（管理员/教练）。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Participant
from ..schemas import ParticipantCreate, ParticipantOut, ParticipantUpdate

router = APIRouter(prefix="/api/participants", tags=["participants"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("", response_model=list[ParticipantOut])
def list_participants(
    q: str | None = Query(None),
    group: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Participant)
    if group:
        query = query.filter(Participant.group_name == group)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Participant.participant_id.ilike(like))
            | (Participant.name.ilike(like))
            | (Participant.id_card.ilike(like))
        )
    return query.order_by(Participant.participant_id).all()


@router.post("", response_model=ParticipantOut)
def create_participant(
    payload: ParticipantCreate,
    db: Session = Depends(get_db),
):
    if db.query(Participant).filter(Participant.participant_id == payload.participant_id).first():
        raise HTTPException(status_code=400, detail="运动员编号已存在")
    participant = Participant(
        participant_id=payload.participant_id,
        batch_id=payload.batch_id,
        name=payload.name,
        sex=payload.sex,
        age_years=payload.age_years,
        birth_date=_parse_dt(payload.birth_date),
        join_date=_parse_dt(payload.join_date),
        group_name=payload.group_name,
        id_card=payload.id_card,
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


@router.patch("/{participant_id}", response_model=ParticipantOut)
def update_participant(
    participant_id: str,
    payload: ParticipantUpdate,
    db: Session = Depends(get_db),
):
    participant = (
        db.query(Participant).filter(Participant.participant_id == participant_id).first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="运动员不存在")
    data = payload.model_dump(exclude_unset=True)
    if "birth_date" in data:
        data["birth_date"] = _parse_dt(data.get("birth_date"))
    if "join_date" in data:
        data["join_date"] = _parse_dt(data.get("join_date"))
    for field, value in data.items():
        setattr(participant, field, value)
    db.commit()
    db.refresh(participant)
    return participant


@router.delete("/{participant_id}")
def delete_participant(
    participant_id: str,
    db: Session = Depends(get_db),
):
    participant = (
        db.query(Participant).filter(Participant.participant_id == participant_id).first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="运动员不存在")
    if participant.samples:
        raise HTTPException(status_code=400, detail="该运动员存在血样记录，不能删除")
    db.delete(participant)
    db.commit()
    return {"ok": True}


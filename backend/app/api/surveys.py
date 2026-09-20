# -*- coding: utf-8 -*-
"""心理问卷 API（简易版）：教练发放与查看回收，运动员填写。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Participant, Survey, SurveyAnswer, SurveyItem

router = APIRouter(prefix="/api/surveys", tags=["surveys"])

DEFAULT_SURVEY_ITEMS = [
    {"text": "你今天的心情如何？（1=非常差，5=非常好）", "type": "scale", "min": 1, "max": 5},
    {"text": "你感到的压力水平？（1=非常低，5=非常高）", "type": "scale", "min": 1, "max": 5},
    {"text": "昨晚的睡眠质量如何？（1=很差，5=很好）", "type": "scale", "min": 1, "max": 5},
    {"text": "身体的疲劳感？（1=完全不累，5=非常累）", "type": "scale", "min": 1, "max": 5},
    {"text": "对今天训练的想法或备注（可选）", "type": "text"},
]


def _participant_ids(db: Session, target_type: str, target_value: str | None) -> list[str]:
    q = db.query(Participant)
    if target_type == "group" and target_value:
        q = q.filter(Participant.group_name == target_value)
    elif target_type == "participant" and target_value:
        q = q.filter(Participant.participant_id == target_value)
    return [p.participant_id for p in q.all()]


@router.get("/templates")
def survey_templates():
    """内置问卷模板（简易版）。"""
    return {"code": "daily_psych", "title": "每日心理状态", "items": DEFAULT_SURVEY_ITEMS}


@router.post("")
def create_survey(payload: dict, db: Session = Depends(get_db)):
    """教练发放问卷。"""
    title = (payload.get("title") or "每日心理状态").strip()
    target_type = payload.get("target_type") or "all"
    target_value = payload.get("target_value")
    deadline = payload.get("deadline")
    survey = Survey(
        title=title,
        description=payload.get("description"),
        target_type=target_type,
        target_value=target_value,
        assign_date=date.today(),
        deadline=datetime.fromisoformat(deadline) if deadline else None,
    )
    db.add(survey)
    db.flush()
    for i, item in enumerate(DEFAULT_SURVEY_ITEMS):
        db.add(
            SurveyItem(
                survey_id=survey.id,
                sort_order=i,
                question_text=item["text"],
                question_type=item["type"],
                min_value=item.get("min"),
                max_value=item.get("max"),
            )
        )
    db.commit()
    return {"id": survey.id, "title": survey.title, "created": True}


@router.get("")
def list_surveys(db: Session = Depends(get_db)):
    """教练端：发放列表（含回收进度与未填名单）。"""
    rows = db.query(Survey).order_by(Survey.created_at.desc()).all()
    result = []
    for s in rows:
        question_count = (
            db.query(SurveyItem).filter(SurveyItem.survey_id == s.id).count()
        )
        answered_ids = {
            a[0]
            for a in db.query(SurveyAnswer.athlete_id)
            .filter(SurveyAnswer.survey_id == s.id)
            .distinct()
            .all()
        }
        target_ids = _participant_ids(db, s.target_type, s.target_value)
        result.append(
            {
                "id": s.id,
                "title": s.title,
                "target_type": s.target_type,
                "target_value": s.target_value,
                "assign_date": s.assign_date.isoformat() if s.assign_date else None,
                "deadline": s.deadline.isoformat() if s.deadline else None,
                "status": s.status,
                "question_count": question_count,
                "answered": len(answered_ids),
                "total": len(target_ids),
                "pending_ids": [pid for pid in target_ids if pid not in answered_ids],
            }
        )
    return result


@router.get("/mine")
def my_surveys(athlete_id: str = Query(...), db: Session = Depends(get_db)):
    """运动员端：待填/已填问卷。"""
    rows = (
        db.query(Survey)
        .filter(Survey.status == "active")
        .order_by(Survey.created_at.desc())
        .all()
    )
    result = []
    for s in rows:
        target_ids = _participant_ids(db, s.target_type, s.target_value)
        if athlete_id not in target_ids:
            continue
        answered = (
            db.query(SurveyAnswer)
            .filter(
                SurveyAnswer.survey_id == s.id,
                SurveyAnswer.athlete_id == athlete_id,
            )
            .first()
        )
        result.append(
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "deadline": s.deadline.isoformat() if s.deadline else None,
                "answered": bool(answered),
            }
        )
    return result


@router.get("/{survey_id}")
def survey_detail(survey_id: int, db: Session = Depends(get_db)):
    """教练端：回收详情（题目 + 每人答案 + 未填名单）。"""
    survey = db.get(Survey, survey_id)
    if not survey:
        return {"detail": "问卷不存在"}
    items = (
        db.query(SurveyItem)
        .filter(SurveyItem.survey_id == survey_id)
        .order_by(SurveyItem.sort_order)
        .all()
    )
    answers = (
        db.query(SurveyAnswer).filter(SurveyAnswer.survey_id == survey_id).all()
    )
    by_athlete: dict[str, dict] = {}
    for a in answers:
        by_athlete.setdefault(a.athlete_id, {})[a.item_id] = {
            "value": a.answer_value,
            "text": a.answer_text,
        }
    target_ids = _participant_ids(db, survey.target_type, survey.target_value)
    names = {p.participant_id: p.name for p in db.query(Participant).all()}
    respondents = [
        {
            "athlete_id": pid,
            "name": names.get(pid),
            "answers": by_athlete.get(pid, {}),
        }
        for pid in target_ids
    ]
    return {
        "id": survey.id,
        "title": survey.title,
        "target_type": survey.target_type,
        "target_value": survey.target_value,
        "status": survey.status,
        "items": [
            {
                "id": it.id,
                "sort_order": it.sort_order,
                "text": it.question_text,
                "type": it.question_type,
                "min": it.min_value,
                "max": it.max_value,
            }
            for it in items
        ],
        "respondents": respondents,
    }


@router.post("/{survey_id}/respond")
def respond(survey_id: int, payload: dict, db: Session = Depends(get_db)):
    """运动员提交问卷答案（重复提交=覆盖）。"""
    athlete_id = payload.get("athlete_id")
    if not athlete_id:
        return {"detail": "缺少 athlete_id"}
    survey = db.get(Survey, survey_id)
    if not survey or survey.status != "active":
        return {"detail": "问卷不存在或已关闭"}
    db.query(SurveyAnswer).filter(
        SurveyAnswer.survey_id == survey_id,
        SurveyAnswer.athlete_id == athlete_id,
    ).delete()
    for a in payload.get("answers") or []:
        db.add(
            SurveyAnswer(
                survey_id=survey_id,
                item_id=a.get("item_id"),
                athlete_id=athlete_id,
                answer_value=a.get("value"),
                answer_text=a.get("text"),
                answered_at=datetime.now(),
            )
        )
    db.commit()
    return {"ok": True, "submitted": len(payload.get("answers") or [])}

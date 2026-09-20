# -*- coding: utf-8 -*-
"""个体追踪 API：单运动员五指标三时间点趋势 + 恢复评估。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import ANALYTES, TIMEPOINTS, TIMEPOINT_LABELS
from ..database import get_db
from ..models import Participant, Sample
from ..services.stats import tc_ratio

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


def _recovery_assessment(samples: dict[str, Sample]) -> dict:
    """恢复评估：基于 CK 的 BL→24H→72H 变化。"""
    ck = {tp: samples[tp].creatine_kinase_U_L for tp in TIMEPOINTS if tp in samples}
    result = {"level": "信息不足", "message": "", "detail": {}}
    bl = ck.get("BL")
    h24 = ck.get("24H")
    h72 = ck.get("72H")
    if bl is not None and h24 is not None and bl > 0:
        rise = (h24 - bl) / bl * 100.0
        result["detail"]["bl_to_24h_pct"] = round(rise, 1)
    if bl is not None and h72 is not None and bl > 0:
        back = (h72 - bl) / bl * 100.0
        result["detail"]["bl_to_72h_pct"] = round(back, 1)
    if bl is None or h24 is None or h72 is None:
        result["message"] = "缺少完整三时间点数据，无法评估恢复状态。"
        return result

    rise = (h24 - bl) / bl * 100.0 if bl else 0.0
    back = (h72 - bl) / bl * 100.0 if bl else 0.0
    if h24 > bl * 1.2 and h72 <= bl * 1.1:
        level, msg = "恢复良好", "训练后 24h CK 明显升高（肌肉负荷反应），72h 已回落至接近基线，恢复良好。"
    elif h24 > bl * 1.2 and h72 > bl * 1.1 and h72 < h24:
        level, msg = "恢复中", "72h 时 CK 较 24h 有所回落，但仍高于基线，恢复尚未完全。"
    elif h24 > bl * 1.2 and h72 >= h24:
        level, msg = "恢复缓慢", "72h 时 CK 仍处于高位，未见明显回落，建议关注并延长恢复时间。"
    elif h24 <= bl * 1.2 and h72 <= bl * 1.2:
        level, msg = "平稳", "训练后 CK 变化幅度小，肌肉负荷反应轻微。"
    else:
        level, msg = "需关注", "CK 时间模式不典型，建议人工复核。"
    result["level"] = level
    result["message"] = msg
    return result


@router.get("/{participant_id}")
def track(participant_id: str, db: Session = Depends(get_db)):
    participant = (
        db.query(Participant).filter(Participant.participant_id == participant_id).first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="运动员不存在")

    samples = (
        db.query(Sample)
        .filter(Sample.participant_id == participant_id)
        .order_by(Sample.time_order)
        .all()
    )
    if not samples:
        raise HTTPException(status_code=404, detail="该运动员暂无血样记录")

    by_tp = {s.timepoint: s for s in samples}

    series = {}
    for col, (label, unit) in ANALYTES.items():
        series[col] = {
            "label": label,
            "unit": unit,
            "points": [
                {
                    "timepoint": tp,
                    "timepoint_label": TIMEPOINT_LABELS.get(tp, tp),
                    "value": getattr(s, col) if (s := by_tp.get(tp)) else None,
                    "raw": s.testosterone_raw if col == "testosterone_value" and s else None,
                }
                for tp in TIMEPOINTS
            ],
        }

    # T/C 比值
    tc_points = []
    for tp in TIMEPOINTS:
        s = by_tp.get(tp)
        tc_points.append(
            {
                "timepoint": tp,
                "timepoint_label": TIMEPOINT_LABELS.get(tp, tp),
                "value": tc_ratio(s.__dict__) if s else None,
            }
        )

    return {
        "participant": {
            "participant_id": participant.participant_id,
            "name": participant.name,
            "batch_id": participant.batch_id,
            "sex": participant.sex,
            "age_years": participant.age_years,
            "group_name": participant.group_name,
            "coach": participant.coach,
            "height_cm": participant.height_cm,
            "weight_kg": participant.weight_kg,
            "intervention": participant.intervention,
        },
        "series": series,
        "tc_ratio": tc_points,
        "recovery": _recovery_assessment(by_tp),
        "samples": [
            {
                "visit_id": s.visit_id,
                "timepoint": s.timepoint,
                "collection_time": s.collection_time.isoformat() if s.collection_time else None,
                "review_status": s.review_status,
                "review_note": s.review_note,
            }
            for s in samples
        ],
    }

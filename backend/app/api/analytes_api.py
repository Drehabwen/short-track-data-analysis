# -*- coding: utf-8 -*-
"""指标配置与超标统计 API。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import TIMEPOINTS
from ..database import get_db
from ..models import Analyte, Sample

router = APIRouter(prefix="/api/analytes", tags=["analytes"])


class AnalyteOut(BaseModel):
    id: int
    code: str
    name: str
    unit: str | None = None
    sample_column: str
    lower_male: float | None = None
    upper_male: float | None = None
    lower_female: float | None = None
    upper_female: float | None = None
    censored_is_normal: bool
    enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AnalyteOut])
def list_analytes(db: Session = Depends(get_db)):
    return db.query(Analyte).order_by(Analyte.sort_order).all()


def _evaluate(analyte: Analyte, value: float, sex: str | None, censored: bool = False) -> str | None:
    """返回 正常/偏高/偏低/正常(低于检测限)，None 表示无法判断。"""
    if value is None:
        return None
    if censored and analyte.censored_is_normal:
        return "正常（低于检测限）"
    lo = analyte.lower_male if sex == "男" else analyte.lower_female
    hi = analyte.upper_male if sex == "男" else analyte.upper_female
    if lo is None and hi is None:
        return None
    if lo is not None and value < lo:
        return "偏低"
    if hi is not None and value > hi:
        return "偏高"
    return "正常"


@router.get("/exceedance")
def exceedance_summary(db: Session = Depends(get_db)):
    """超标统计：按指标、时间点、组别汇总。"""
    analytes = db.query(Analyte).filter(Analyte.enabled == True).order_by(Analyte.sort_order).all()  # noqa: E712
    samples = db.query(Sample).all()

    result = []
    for a in analytes:
        high = low = normal = total = 0
        by_timepoint = {tp: {"high": 0, "low": 0, "total": 0} for tp in TIMEPOINTS}
        by_group: dict[str, dict] = {}
        for s in samples:
            value = getattr(s, a.sample_column, None)
            sex = s.participant.sex if s.participant else None
            censored = bool(
                s.testosterone_below_lod and a.sample_column == "testosterone_value"
            )
            verdict = _evaluate(a, value, sex, censored)
            if verdict is None:
                continue
            total += 1
            if verdict == "偏高":
                high += 1
            elif verdict == "偏低":
                low += 1
            else:
                normal += 1
            if s.timepoint in by_timepoint:
                by_timepoint[s.timepoint]["total"] += 1
                if verdict == "偏高":
                    by_timepoint[s.timepoint]["high"] += 1
                elif verdict == "偏低":
                    by_timepoint[s.timepoint]["low"] += 1
            g = s.participant.group_name if s.participant else None
            if g:
                bg = by_group.setdefault(g, {"high": 0, "low": 0, "total": 0})
                bg["total"] += 1
                if verdict == "偏高":
                    bg["high"] += 1
                elif verdict == "偏低":
                    bg["low"] += 1
        result.append(
            {
                "code": a.code,
                "name": a.name,
                "unit": a.unit,
                "total": total,
                "high": high,
                "low": low,
                "normal": normal,
                "high_rate": round(high / total, 4) if total else None,
                "low_rate": round(low / total, 4) if total else None,
                "by_timepoint": by_timepoint,
                "by_group": by_group,
            }
        )
    return result


@router.get("/reference")
def reference_ranges(db: Session = Depends(get_db)):
    """参考区间配置（供前端展示/管理）。"""
    analytes = db.query(Analyte).order_by(Analyte.sort_order).all()
    return [
        {
            "code": a.code,
            "name": a.name,
            "unit": a.unit,
            "male": [a.lower_male, a.upper_male],
            "female": [a.lower_female, a.upper_female],
            "enabled": a.enabled,
            "censored_is_normal": a.censored_is_normal,
        }
        for a in analytes
    ]


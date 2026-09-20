# -*- coding: utf-8 -*-
"""总览仪表盘 API：全队状态、异常预警。"""
import statistics
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import TIMEPOINTS
from ..database import get_db
from ..models import Participant, Sample

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _alert_flags(sample: Sample) -> list[str]:
    """异常预警规则（教练端）。"""
    flags = []
    ck = sample.creatine_kinase_U_L
    if ck is not None and ck > 500:
        flags.append(f"CK 偏高({ck:.0f} U/L)")
    t = sample.testosterone_value
    c = sample.cortisol_ug_dL
    if t is not None and c is not None and c > 0:
        ratio = t / c * 100.0
        if ratio < 2.0:
            flags.append(f"T/C 比值偏低({ratio:.1f}%)")
    if sample.review_status and "需复核" in sample.review_status:
        flags.append("待复核")
    return flags


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    participants = db.query(Participant).all()
    samples = db.query(Sample).all()

    timepoint_counts = {tp: 0 for tp in TIMEPOINTS}
    for s in samples:
        if s.timepoint in timepoint_counts:
            timepoint_counts[s.timepoint] += 1

    group_counts = {}
    sex_counts = {}
    for p in participants:
        g = p.group_name or "未分组"
        group_counts[g] = group_counts.get(g, 0) + 1
        sx = p.sex or "未知"
        sex_counts[sx] = sex_counts.get(sx, 0) + 1

    # 完整三时间点运动员
    complete = 0
    for p in participants:
        tps = {s.timepoint for s in p.samples}
        if set(TIMEPOINTS).issubset(tps):
            complete += 1

    return {
        "participant_count": len(participants),
        "sample_count": len(samples),
        "complete_three_timepoint_count": complete,
        "timepoint_counts": timepoint_counts,
        "group_counts": group_counts,
        "sex_counts": sex_counts,
        "review_pending_count": sum(
            1 for s in samples if s.review_status and "复核" in s.review_status
        ),
    }


@router.get("/alerts")
def alerts(db: Session = Depends(get_db)):
    result = []
    for s in db.query(Sample).all():
        flags = _alert_flags(s)
        if flags:
            result.append(
                {
                    "sample_id": s.id,
                    "visit_id": s.visit_id,
                    "participant_id": s.participant_id,
                    "timepoint": s.timepoint,
                    "timepoint_label": {"BL": "训练前", "24H": "24小时后", "72H": "72小时后"}.get(
                        s.timepoint, s.timepoint
                    ),
                    "group": s.participant.group_name if s.participant else None,
                    "collection_time": s.collection_time.isoformat() if s.collection_time else None,
                    "alerts": flags,
                }
            )
    result.sort(key=lambda x: x["participant_id"])
    return result


METRIC_DEFS = [
    ("creatine_kinase_U_L", "肌酸激酶CK", "U/L", "high"),
    ("ldh_U_L", "LDH", "U/L", "high"),
    ("urea_mmol_L", "尿素", "mmol/L", "high"),
    ("cortisol_ug_dL", "皮质醇", "μg/dL", "high"),
    ("testosterone_value", "睾酮", "nmol/L", "low"),
]

TP_LABEL_MAP = {"BL": "训练前", "24H": "24小时后", "72H": "72小时后"}


def _episode_value(ep_samples: list[Sample], timepoint: str, column: str):
    vals = [
        getattr(s, column)
        for s in ep_samples
        if s.timepoint == timepoint and getattr(s, column) is not None
    ]
    return vals[-1] if vals else None


def _episode_tc_ratio(ep_samples: list[Sample], timepoint: str):
    for s in reversed(ep_samples):
        if s.timepoint != timepoint:
            continue
        t = s.testosterone_value
        c = s.cortisol_ug_dL
        if t is not None and c is not None and c > 0:
            return t / c * 100.0
    return None


def _severity_order(level: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(level, 2)


@router.get("/personalized_alerts")
def personalized_alerts(db: Session = Depends(get_db)):
    """趋势与个人基线预警。

    当前数据支持：周期内恢复趋势（BL→24H→72H）。
    数据积累后：跨周期同时间点趋势 + 个人历史基线偏离。
    """
    result = []
    for p in db.query(Participant).all():
        # 每个时间点取最新样本（按采集时间、id 排序）
        latest: dict[str, Sample] = {}
        for s in sorted(p.samples, key=lambda s: (s.collection_time or datetime.min, s.id)):
            latest[s.timepoint] = s

        def _ck(tp: str):
            s = latest.get(tp)
            return s.creatine_kinase_U_L if s else None

        def _tc(tp: str):
            s = latest.get(tp)
            if (
                s
                and s.testosterone_value is not None
                and s.cortisol_ug_dL
                and s.cortisol_ug_dL > 0
            ):
                return s.testosterone_value / s.cortisol_ug_dL * 100.0
            return None

        # 1) CK 恢复趋势：24H 应高于 BL，72H 应回落
        bl, h24, h72 = _ck("BL"), _ck("24H"), _ck("72H")
        if bl and h24 and h72:
            if h24 > bl and h72 > h24:
                rise = (h72 - h24) / h24 * 100.0
                if rise >= 5:
                    result.append(
                        {
                            "participant_id": p.participant_id,
                            "name": p.name,
                            "group": p.group_name,
                            "severity": "high" if rise >= 10 else "medium",
                            "metric": "肌酸激酶CK",
                            "timepoint": "72H",
                            "timepoint_label": "72小时后",
                            "current": round(h72, 2),
                            "previous": round(h24, 2),
                            "change_pct": round(rise, 1),
                            "kind": "ck_no_recovery",
                            "message": f"CK 24小时→72小时未回落，继续上升 {rise:.1f}%",
                        }
                    )
            if h72 > bl * 1.5:
                ratio = (h72 / bl - 1.0) * 100.0
                result.append(
                    {
                        "participant_id": p.participant_id,
                        "name": p.name,
                        "group": p.group_name,
                        "severity": "high" if ratio >= 100 else "medium",
                        "metric": "肌酸激酶CK",
                        "timepoint": "72H",
                        "timepoint_label": "72小时后",
                        "current": round(h72, 2),
                        "previous": round(bl, 2),
                        "change_pct": round(ratio, 1),
                        "kind": "ck_elevated_at_72h",
                        "message": f"CK 72小时仍高于训练前 {ratio:.1f}%",
                    }
                )

        # 2) T/C 持续下降
        bl_tc, h24_tc, h72_tc = _tc("BL"), _tc("24H"), _tc("72H")
        if bl_tc and h24_tc and h72_tc and bl_tc > h24_tc > h72_tc:
            decline = (bl_tc - h72_tc) / bl_tc * 100.0
            if decline >= 20:
                result.append(
                    {
                        "participant_id": p.participant_id,
                        "name": p.name,
                        "group": p.group_name,
                        "severity": "high" if decline >= 40 else "medium",
                        "metric": "T/C 比值",
                        "timepoint": "72H",
                        "timepoint_label": "72小时后",
                        "current": round(h72_tc, 2),
                        "previous": round(bl_tc, 2),
                        "change_pct": round(decline, 1),
                        "kind": "tc_decline",
                        "message": f"T/C 比值持续下降 {decline:.1f}%",
                    }
                )

        episodes: dict[str, list[Sample]] = {}
        for s in p.samples:
            episodes.setdefault(s.episode_id or "?", []).append(s)
        if len(episodes) < 2:
            continue

        def episode_time(ep: str):
            times = [s.collection_time for s in episodes[ep] if s.collection_time]
            return min(times) if times else datetime.max

        ep_order = sorted(episodes.keys(), key=episode_time)
        current = ep_order[-1]
        previous = ep_order[-2]

        for tp in TIMEPOINTS:
            # 1) CK 跨周期上升
            cur_ck = _episode_value(episodes[current], tp, "creatine_kinase_U_L")
            prev_ck = _episode_value(episodes[previous], tp, "creatine_kinase_U_L")
            if cur_ck is not None and prev_ck is not None and prev_ck > 0:
                chg = (cur_ck - prev_ck) / prev_ck * 100.0
                if chg >= 20:
                    sev = "high" if chg >= 40 else "medium"
                    result.append(
                        {
                            "participant_id": p.participant_id,
                            "name": p.name,
                            "group": p.group_name,
                            "severity": sev,
                            "metric": "肌酸激酶CK",
                            "timepoint": tp,
                            "timepoint_label": TP_LABEL_MAP.get(tp, tp),
                            "current": round(cur_ck, 2),
                            "previous": round(prev_ck, 2),
                            "change_pct": round(chg, 1),
                            "kind": "ck_rise",
                            "message": f"CK {TP_LABEL_MAP.get(tp, tp)}较上一周期上升 {chg:.1f}%",
                        }
                    )

            # 2) T/C 跨周期下降
            cur_tc = _episode_tc_ratio(episodes[current], tp)
            prev_tc = _episode_tc_ratio(episodes[previous], tp)
            if cur_tc is not None and prev_tc is not None and prev_tc > 0:
                chg = (cur_tc - prev_tc) / prev_tc * 100.0
                if chg <= -20:
                    sev = "high" if chg <= -40 else "medium"
                    result.append(
                        {
                            "participant_id": p.participant_id,
                            "name": p.name,
                            "group": p.group_name,
                            "severity": sev,
                            "metric": "T/C 比值",
                            "timepoint": tp,
                            "timepoint_label": TP_LABEL_MAP.get(tp, tp),
                            "current": round(cur_tc, 2),
                            "previous": round(prev_tc, 2),
                            "change_pct": round(chg, 1),
                            "kind": "tc_decline",
                            "message": f"T/C {TP_LABEL_MAP.get(tp, tp)}较上一周期下降 {abs(chg):.1f}%",
                        }
                    )

        # 3) 个人基线偏离（至少 3 个历史同时间点值才可靠）
        for col, label, unit, direction in METRIC_DEFS:
            for tp in TIMEPOINTS:
                hist = [
                    getattr(s, col)
                    for ep in ep_order[:-1]
                    for s in episodes[ep]
                    if s.timepoint == tp and getattr(s, col) is not None
                ]
                cur = _episode_value(episodes[current], tp, col)
                if cur is None or len(hist) < 3:
                    continue
                mu = statistics.mean(hist)
                sd = statistics.stdev(hist) if len(hist) > 1 else 0.0
                if sd <= 0:
                    continue
                z = (cur - mu) / sd
                trigger = (direction == "high" and z > 1.5) or (
                    direction == "low" and z < -1.5
                )
                if not trigger:
                    continue
                sev = "high" if abs(z) >= 2.5 else "medium"
                result.append(
                    {
                        "participant_id": p.participant_id,
                        "name": p.name,
                        "group": p.group_name,
                        "severity": sev,
                        "metric": label,
                        "timepoint": tp,
                        "timepoint_label": TP_LABEL_MAP.get(tp, tp),
                        "current": round(cur, 2),
                        "baseline_mean": round(mu, 2),
                        "baseline_sd": round(sd, 2),
                        "z_score": round(z, 2),
                        "kind": "baseline_high" if z > 0 else "baseline_low",
                        "message": f"{label} {TP_LABEL_MAP.get(tp, tp)}偏离个人基线 {z:+.1f} SD",
                    }
                )

    result.sort(key=lambda x: (_severity_order(x["severity"]), x["participant_id"]))
    return result

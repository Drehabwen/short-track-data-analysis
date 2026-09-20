# -*- coding: utf-8 -*-
"""综合数据 API：心率、CPET、前测、疲劳监测、运动员全景。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AcuteFatigue,
    CpetTest,
    DailyStatus,
    HrSession,
    InjuryRecord,
    Participant,
    Pretest,
    Sample,
    TrainingEntry,
    TrainingPlan,
    TrainingSession,
)

router = APIRouter(prefix="/api", tags=["datahub"])


def _p(db, sid):
    return db.query(Participant).filter(Participant.participant_id == sid).first()


# ══════════ 心率 ══════════
@router.get("/hr/overview")
def hr_overview(db: Session = Depends(get_db)):
    rows = db.query(HrSession).all()
    n = len(rows)
    if not n:
        return {"sessions": 0, "rows": 0}
    athletes = {r.subject_id for r in rows if r.subject_id}
    avg_hrs = [r.avg_hr for r in rows if r.avg_hr is not None]
    max_hrs = [r.max_hr for r in rows if r.max_hr is not None]
    z45 = sum((r.z4 or 0) + (r.z5 or 0) for r in rows)
    total_z = sum((r.z1 or 0) + (r.z2 or 0) + (r.z3 or 0) + (r.z4 or 0) + (r.z5 or 0) for r in rows)
    by_type = {}
    for r in rows:
        t = r.session_type or "未知"
        by_type[t] = by_type.get(t, 0) + 1
    by_coach = {}
    for r in rows:
        c = r.coach or "未分配"
        d = by_coach.setdefault(c, {"rows": 0, "hrs": [], "z45": 0.0, "zsum": 0.0})
        d["rows"] += 1
        if r.avg_hr is not None:
            d["hrs"].append(r.avg_hr)
        d["z45"] += (r.z4 or 0) + (r.z5 or 0)
        d["zsum"] += (r.z1 or 0) + (r.z2 or 0) + (r.z3 or 0) + (r.z4 or 0) + (r.z5 or 0)
    by_coach = {
        c: {
            "rows": d["rows"],
            "avg_hr": round(sum(d["hrs"]) / len(d["hrs"]), 1) if d["hrs"] else None,
            "z45_pct": round(d["z45"] / d["zsum"] * 100, 1) if d["zsum"] else None,
        }
        for c, d in sorted(by_coach.items(), key=lambda kv: -kv[1]["rows"])
    }
    return {
        "rows": n,
        "athletes": len(athletes),
        "avg_hr": round(sum(avg_hrs) / len(avg_hrs), 1) if avg_hrs else None,
        "max_hr": max(max_hrs) if max_hrs else None,
        "z45_pct": round(z45 / total_z * 100, 1) if total_z else None,
        "by_type": by_type,
        "by_coach": by_coach,
    }


@router.get("/hr/athlete/{subject_id}")
def hr_athlete(subject_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(HrSession)
        .filter(HrSession.subject_id == subject_id)
        .order_by(HrSession.datetime)
        .all()
    )
    return [
        {
            "id": r.id,
            "datetime": r.datetime.isoformat() if r.datetime else None,
            "session_name": r.session_name,
            "coach": r.coach,
            "session_type": r.session_type,
            "duration_min": r.duration_min,
            "avg_hr": r.avg_hr,
            "max_hr": r.max_hr,
            "z1": r.z1, "z2": r.z2, "z3": r.z3, "z4": r.z4, "z5": r.z5,
        }
        for r in rows
    ]


@router.get("/hr/sessions")
def hr_sessions(
    coach: str | None = None,
    session_type: str | None = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
):
    q = db.query(HrSession)
    if coach:
        q = q.filter(HrSession.coach == coach)
    if session_type:
        q = q.filter(HrSession.session_type == session_type)
    # 教练端需要覆盖合并后的历史数据；限制上限仅用于避免误请求超大结果集。
    rows = q.order_by(HrSession.datetime.desc()).limit(min(max(limit, 1), 5000)).all()
    return [
        {
            "id": r.id,
            "athlete": r.athlete,
            "subject_id": r.subject_id,
            "datetime": r.datetime.isoformat() if r.datetime else None,
            "session_name": r.session_name,
            "coach": r.coach,
            "session_type": r.session_type,
            "duration_min": r.duration_min,
            "avg_hr": r.avg_hr,
            "max_hr": r.max_hr,
        }
        for r in rows
    ]


# ══════════ CPET ══════════
@router.get("/cpet/tests")
def cpet_tests(db: Session = Depends(get_db)):
    rows = db.query(CpetTest).order_by(CpetTest.test_id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "subject_id": r.subject_id,
            "gender": r.gender,
            "age_years": r.age_years,
            "height_cm": r.height_cm,
            "weight_kg": r.weight_kg,
            "bmi": r.bmi,
            "test_start": r.test_start.isoformat() if r.test_start else None,
            "duration_s": r.duration_s,
            "valid_class": r.valid_class,
            "vo2kg_peak": r.vo2kg_peak,
            "vo2kg_pctnorm": r.vo2kg_pctnorm,
            "vo2_peak": r.vo2_peak,
            "hr_peak": r.hr_peak,
            "rer_peak": r.rer_peak,
            "slope_ve_vco2": r.slope_ve_vco2,
            "vo2kg_vt1": r.vo2kg_vt1,
            "peak_wr": r.peak_wr,
        }
        for r in rows
    ]


@router.get("/cpet/ranking")
def cpet_ranking(db: Session = Depends(get_db)):
    """每人最优 VO2 排名（有效测试优先）。"""
    rows = db.query(CpetTest).all()
    best = {}
    for r in rows:
        if r.vo2kg_peak is None:
            continue
        sid = r.subject_id or r.name
        valid = "有效" in (r.valid_class or "")
        cur = best.get(sid)
        if cur is None or (valid and not cur["valid"]) or (
            valid == cur["valid"] and (r.vo2kg_peak or 0) > (cur["vo2kg_peak"] or 0)
        ):
            best[sid] = {
                "subject_id": r.subject_id,
                "name": r.name,
                "valid": valid,
                "valid_class": r.valid_class,
                "vo2kg_peak": r.vo2kg_peak,
                "vo2kg_pctnorm": r.vo2kg_pctnorm,
                "hr_peak": r.hr_peak,
                "test_start": r.test_start.isoformat() if r.test_start else None,
            }
    ranked = sorted(best.values(), key=lambda x: -(x["vo2kg_peak"] or 0))
    for i, item in enumerate(ranked, 1):
        item["rank"] = i
    return ranked


@router.get("/cpet/athlete/{subject_id}")
def cpet_athlete(subject_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(CpetTest)
        .filter(CpetTest.subject_id == subject_id)
        .order_by(CpetTest.test_start)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="该运动员无 CPET 测试")
    return [
        {
            "id": r.id,
            "test_start": r.test_start.isoformat() if r.test_start else None,
            "valid_class": r.valid_class,
            "duration_s": r.duration_s,
            "vo2kg_peak": r.vo2kg_peak,
            "vo2kg_pctnorm": r.vo2kg_pctnorm,
            "vo2_peak": r.vo2_peak,
            "hr_peak": r.hr_peak,
            "rer_peak": r.rer_peak,
            "slope_ve_vco2": r.slope_ve_vco2,
            "vo2kg_vt1": r.vo2kg_vt1,
            "vo2kg_vt1_pctmax": r.vo2kg_vt1_pctmax,
            "peak_wr": r.peak_wr,
            "exercise_dur_s": r.exercise_dur_s,
            "plateau_delta": r.plateau_delta,
        }
        for r in rows
    ]


@router.get("/cpet/trends")
def cpet_trends(db: Session = Depends(get_db)):
    """复测趋势：每人多次测试的 VO2 变化（首次 vs 末次）。"""
    rows = db.query(CpetTest).all()
    by_person = {}
    for r in rows:
        if r.vo2kg_peak is None or not r.name:
            continue
        by_person.setdefault(r.name, []).append(r)
    trends = []
    for name, vs in by_person.items():
        if len(vs) < 2:
            continue
        vs.sort(key=lambda x: x.test_start or datetime.min)
        first, last = vs[0], vs[-1]
        delta = round((last.vo2kg_peak or 0) - (first.vo2kg_peak or 0), 1)
        trends.append({
            "name": name,
            "first": round(first.vo2kg_peak, 1),
            "last": round(last.vo2kg_peak, 1),
            "delta": delta,
            "n": len(vs),
            "first_date": first.test_start.date().isoformat() if first.test_start else None,
            "last_date": last.test_start.date().isoformat() if last.test_start else None,
            "cls": last.valid_class,
        })
    trends.sort(key=lambda x: -x["delta"])
    return {"trends": trends, "n_multi": len(trends),
            "n_progress": sum(1 for t in trends if t["delta"] > 2)}


@router.get("/cpet/group_compare")
def cpet_group_compare(db: Session = Depends(get_db)):
    """干预组 VO2 对比（按每人最优测试 + Kruskal-Wallis）。"""
    rows = db.query(CpetTest).all()
    parts = {p.name: p.intervention for p in db.query(Participant).all() if p.name}
    best = {}
    for r in rows:
        if r.vo2kg_peak is None or not r.name:
            continue
        g = parts.get(r.name, "")
        cur = best.get(r.name)
        if cur is None or (r.vo2kg_peak or 0) > (cur.get("vo2kg") or 0):
            best[r.name] = {"name": r.name, "group": g, "vo2kg": r.vo2kg_peak}
    order = ["常规恢复", "艾灸+推拿", "拔罐+推拿"]
    groups = {g: [] for g in order}
    for v in best.values():
        if v["group"] in groups:
            groups[v["group"]].append(v["vo2kg"])
    out = []
    for g in order:
        vals = sorted(groups[g])
        if vals:
            out.append({
                "group": g, "n": len(vals),
                "median": round(vals[len(vals) // 2], 1),
                "mean": round(sum(vals) / len(vals), 1),
                "min": vals[0], "max": vals[-1],
                "q1": vals[len(vals) // 4], "q3": vals[3 * len(vals) // 4],
            })
    kw = None
    valid_groups = [groups[g] for g in order if len(groups[g]) >= 3]
    if len(valid_groups) >= 2:
        try:
            from scipy import stats as _st
            kw = float(_st.kruskal(*valid_groups).pvalue)
        except Exception:
            kw = None
    return {"groups": out, "kruskal_p": kw}


@router.get("/cpet/quality")
def cpet_quality(db: Session = Depends(get_db)):
    """数据质量筛查：z-score 离群 + 无效测试清单。"""
    rows = db.query(CpetTest).all()
    best = {}
    no_vo2 = set()
    has_any = set()
    for r in rows:
        if not r.name:
            continue
        has_any.add(r.name)
        if r.vo2kg_peak is None:
            continue
        cur = best.get(r.name)
        if cur is None or (r.vo2kg_peak or 0) > (cur.get("vo2kg") or 0):
            best[r.name] = {"name": r.name, "vo2kg": r.vo2kg_peak, "cls": r.valid_class,
                            "age": r.age_years}
    invalid = sorted(has_any - set(best))
    vals = [v["vo2kg"] for v in best.values()]
    mean = sum(vals) / len(vals) if vals else 0
    sd = (sum((x - mean) ** 2 for x in vals) / max(len(vals) - 1, 1)) ** 0.5 or 1
    high, low = [], []
    for v in best.values():
        z = (v["vo2kg"] - mean) / sd
        if z > 1.5:
            high.append({"name": v["name"], "vo2kg": round(v["vo2kg"], 1), "z": round(z, 2), "age": v["age"]})
        elif z < -1.5:
            low.append({"name": v["name"], "vo2kg": round(v["vo2kg"], 1), "z": round(z, 2)})
    return {"high": high, "low": low, "invalid": invalid,
            "n_total": len(best), "median": round(sorted(vals)[len(vals) // 2], 1) if vals else None}


# ══════════ HRV 分析（hrvanalysis 引擎）══════════
@router.get("/hrv/overview")
def hrv_overview(db: Session = Depends(get_db)):
    """全队 HRV 恢复状态总览（来自急性疲劳监测）。"""
    rows = [r for r in db.query(AcuteFatigue).all() if r.hrv_sdnn is not None or r.hrv_rmssd is not None]
    from ..services.hrv import recovery_level
    levels = {}
    for r in rows:
        lv = recovery_level(r.hrv_sdnn, r.hrv_rmssd)
        levels[lv] = levels.get(lv, 0) + 1
    stats = {}
    for key, vals in [("sdnn", [r.hrv_sdnn for r in rows if r.hrv_sdnn is not None]),
                      ("rmssd", [r.hrv_rmssd for r in rows if r.hrv_rmssd is not None]),
                      ("lfhf", [r.hrv_lf_hf for r in rows if r.hrv_lf_hf is not None])]:
        if vals:
            v = sorted(vals)
            stats[key] = {"n": len(v), "mean": round(sum(v) / len(v), 1),
                          "median": round(v[len(v) // 2], 1), "min": v[0], "max": v[-1]}
    return {"n_measured": len(rows), "levels": levels, "stats": stats,
            "athletes": [{"subject_id": r.subject_id, "name": r.name,
                          "sdnn": r.hrv_sdnn, "rmssd": r.hrv_rmssd,
                          "lf_hf": r.hrv_lf_hf, "total_power": r.hrv_total_power,
                          "level": recovery_level(r.hrv_sdnn, r.hrv_rmssd)}
                         for r in rows]}


@router.get("/hrv/athlete/{subject_id}")
def hrv_athlete(subject_id: str, db: Session = Depends(get_db)):
    """个体 HRV 记录。"""
    from ..services.hrv import recovery_level
    rows = db.query(AcuteFatigue).filter(AcuteFatigue.subject_id == subject_id).all()
    return [{"subject_id": r.subject_id, "name": r.name, "sdnn": r.hrv_sdnn,
             "rmssd": r.hrv_rmssd, "lf_hf": r.hrv_lf_hf,
             "total_power": r.hrv_total_power,
             "level": recovery_level(r.hrv_sdnn, r.hrv_rmssd)} for r in rows]


@router.post("/hrv/analyze")
def hrv_analyze(payload: dict):
    """POST {'rr_intervals': [ms...]} → HRV 全套指标（时域+频域）。"""
    rri = payload.get("rr_intervals") or payload.get("rri") or []
    if not isinstance(rri, list) or not rri:
        raise HTTPException(status_code=400, detail="请提供 rr_intervals 列表")
    from ..services.hrv import compute_hrv
    return compute_hrv(rri)


# ══════════ 训练成绩录入（日常训练/体能）══════════
# 三级分类：成绩（训练成绩）/ 体能（体能测试）
TEST_TYPES = [
    # 成绩类（训练成绩，计时/速度）
    ("500m计时", "s", "成绩"), ("7圈计时", "s", "成绩"), ("1000m计时", "s", "成绩"), ("1500m计时", "s", "成绩"),
    ("30m冲刺", "s", "成绩"), ("折返跑", "s", "成绩"),
    # 体能类（体能测试/身体成分）
    ("CMJ纵跳", "cm", "体能"), ("立定跳远", "cm", "体能"),
    ("FMS总分", "分", "体能"), ("YBT总分", "cm", "体能"),
    ("深蹲1RM", "kg", "体能"), ("卧推1RM", "kg", "体能"),
    ("引体向上", "次", "体能"), ("平板支撑", "s", "体能"),
    ("体重", "kg", "体能"), ("体脂率", "%", "体能"),
    ("出勤", "1", "成绩"), ("伤病", "0", "伤病"),
]


@router.get("/training/types")
def training_types():
    """训练成绩项目类型字典（前端表单用）。"""
    return [{"name": n, "unit": u, "category": c} for n, u, c in TEST_TYPES]


@router.post("/training/entries")
def training_entry_create(payload: dict, db: Session = Depends(get_db)):
    """录入训练成绩（单条或批量）。
    POST {"entries": [{"athlete_id","entry_date","session_name","test_type","value","unit","note"}, ...]}
    """
    entries = payload.get("entries") or [payload]
    from datetime import datetime as _dt
    created = []
    for e in entries:
        if not e.get("athlete_id") or not e.get("test_type"):
            continue
        val = e.get("value")
        if val is None:
            continue
        row = TrainingEntry(
            athlete_id=e["athlete_id"],
            entry_date=_dt.fromisoformat(e["entry_date"]) if e.get("entry_date") else _dt.now(),
            session_name=e.get("session_name"),
            test_type=e["test_type"],
            value=float(val),
            unit=e.get("unit"),
            note=e.get("note"),
            source="manual",
        )
        db.add(row)
        created.append({"athlete_id": row.athlete_id, "test_type": row.test_type, "value": row.value})
    db.commit()
    return {"created": len(created)}


@router.get("/training/entries")
def training_entries(athlete_id: str | None = None, test_type: str | None = None,
                     limit: int = 200, db: Session = Depends(get_db)):
    """查询训练成绩（可按运动员/项目筛选）。"""
    q = db.query(TrainingEntry)
    if athlete_id:
        q = q.filter(TrainingEntry.athlete_id == athlete_id)
    if test_type:
        q = q.filter(TrainingEntry.test_type == test_type)
    rows = q.order_by(TrainingEntry.entry_date.desc().nullslast()).limit(limit).all()
    names = {p.participant_id: p.name for p in db.query(Participant).all()}
    return [
        {
            "id": r.id, "athlete_id": r.athlete_id, "athlete_name": names.get(r.athlete_id),
            "entry_date": r.entry_date.strftime("%Y-%m-%d %H:%M") if r.entry_date else None,
            "session_name": r.session_name, "test_type": r.test_type,
            "value": r.value, "unit": r.unit, "note": r.note,
        }
        for r in rows
    ]


@router.get("/training/entries/athlete/{athlete_id}")
def training_entries_athlete(athlete_id: str, db: Session = Depends(get_db)):
    """个人成绩：按项目分组的历史（用于趋势图）。"""
    rows = db.query(TrainingEntry).filter(TrainingEntry.athlete_id == athlete_id)\
        .order_by(TrainingEntry.entry_date).all()
    by_type = {}
    for r in rows:
        by_type.setdefault(r.test_type, []).append({
            "date": r.entry_date.strftime("%m-%d") if r.entry_date else None,
            "value": r.value, "unit": r.unit, "note": r.note,
        })
    return {"athlete_id": athlete_id, "by_type": by_type}


# ══════════ 训练计划（排课）══════════
@router.get("/plans")
def plans_get(week_start: str | None = None, db: Session = Depends(get_db)):
    """训练计划：按周查询（week_start=周一日期 YYYY-MM-DD），默认本周。"""
    from datetime import date, timedelta
    if week_start:
        start = date.fromisoformat(week_start)
    else:
        today = date.today()
        start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    rows = db.query(TrainingPlan).filter(TrainingPlan.plan_date >= start,
                                         TrainingPlan.plan_date <= end)\
        .order_by(TrainingPlan.plan_date, TrainingPlan.coach).all()
    return {
        "week_start": start.isoformat(),
        "plans": [
            {"id": r.id, "plan_date": r.plan_date.strftime("%Y-%m-%d"), "coach": r.coach,
             "session_type": r.session_type, "content": r.content,
             "duration_min": r.duration_min, "intensity": r.intensity, "status": r.status}
            for r in rows
        ],
    }


@router.post("/plans")
def plan_create(payload: dict, db: Session = Depends(get_db)):
    """排课：POST {plan_date, coach, session_type, content, duration_min, intensity}"""
    row = TrainingPlan(
        plan_date=datetime.strptime(payload["plan_date"], "%Y-%m-%d").date(),
        coach=payload.get("coach"),
        session_type=payload.get("session_type"),
        content=payload.get("content"),
        duration_min=payload.get("duration_min"),
        intensity=payload.get("intensity"),
        status=payload.get("status", "计划"),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "created": True}


@router.patch("/plans/{plan_id}")
def plan_update(plan_id: int, payload: dict, db: Session = Depends(get_db)):
    """修改计划（含标记已执行/取消）。"""
    row = db.query(TrainingPlan).get(plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    for k in ("coach", "session_type", "content", "duration_min", "intensity", "status"):
        if k in payload:
            setattr(row, k, payload[k])
    db.commit()
    return {"id": row.id, "updated": True}


@router.delete("/plans/{plan_id}")
def plan_delete(plan_id: int, db: Session = Depends(get_db)):
    row = db.query(TrainingPlan).get(plan_id)
    if row:
        db.delete(row)
        db.commit()
    return {"deleted": True}


# ══════════ 每日状态上报 ══════════
@router.post("/status/report")
def status_report(payload: dict, db: Session = Depends(get_db)):
    """运动员每日上报：POST {athlete_id, status_date, sleep_hours, fatigue, morning_hr, weight_kg, muscle_soreness, injury, self_rating, note}
    同人同日重复上报 = 覆盖更新。"""
    from datetime import date
    sid = payload["athlete_id"]
    sdate = date.fromisoformat(payload.get("status_date") or date.today().isoformat())
    row = db.query(DailyStatus).filter(DailyStatus.athlete_id == sid,
                                       DailyStatus.status_date == sdate).first()
    if not row:
        row = DailyStatus(athlete_id=sid, status_date=sdate)
        db.add(row)
    for k in ("sleep_hours", "fatigue", "morning_hr", "weight_kg",
              "muscle_soreness", "injury", "self_rating", "note"):
        if k in payload:
            setattr(row, k, payload[k])
    db.commit()
    return {"athlete_id": sid, "status_date": sdate.isoformat(), "saved": True}


@router.get("/status/team")
def status_team(status_date: str | None = None, db: Session = Depends(get_db)):
    """全队当日状态汇总（教练看板）。"""
    from datetime import date
    sdate = date.fromisoformat(status_date) if status_date else date.today()
    rows = db.query(DailyStatus).filter(DailyStatus.status_date == sdate).all()
    names = {p.participant_id: p.name for p in db.query(Participant).all()}
    coaches = {p.participant_id: p.coach for p in db.query(Participant).all()}
    out = []
    for r in rows:
        flag = None
        if r.fatigue is not None and r.fatigue >= 7:
            flag = "疲劳高"
        elif r.muscle_soreness is not None and r.muscle_soreness >= 7:
            flag = "酸痛重"
        elif r.injury and r.injury != "无":
            flag = "伤病:" + r.injury
        out.append({
            "athlete_id": r.athlete_id, "name": names.get(r.athlete_id, r.athlete_id),
            "coach": coaches.get(r.athlete_id),
            "sleep_hours": r.sleep_hours, "fatigue": r.fatigue,
            "morning_hr": r.morning_hr, "weight_kg": r.weight_kg,
            "muscle_soreness": r.muscle_soreness, "injury": r.injury,
            "self_rating": r.self_rating, "note": r.note, "flag": flag,
        })
    n = len(out)
    n_flag = sum(1 for x in out if x["flag"])
    return {"date": sdate.isoformat(), "reported": n, "flagged": n_flag, "rows": out}


@router.get("/status/athlete/{athlete_id}")
def status_athlete(athlete_id: str, db: Session = Depends(get_db)):
    """个人状态历史（趋势图用）。"""
    rows = db.query(DailyStatus).filter(DailyStatus.athlete_id == athlete_id)\
        .order_by(DailyStatus.status_date).all()
    return [
        {"date": r.status_date.strftime("%m-%d"), "sleep_hours": r.sleep_hours,
         "fatigue": r.fatigue, "morning_hr": r.morning_hr, "weight_kg": r.weight_kg,
         "muscle_soreness": r.muscle_soreness, "self_rating": r.self_rating,
         "injury": r.injury, "note": r.note}
        for r in rows
    ]


# ══════════ 伤病记录（第三级）══════════
@router.get("/injuries")
def injuries_get(athlete_id: str | None = None, status: str | None = None,
                 limit: int = 100, db: Session = Depends(get_db)):
    """伤病记录查询。"""
    q = db.query(InjuryRecord)
    if athlete_id:
        q = q.filter(InjuryRecord.athlete_id == athlete_id)
    if status:
        q = q.filter(InjuryRecord.status == status)
    rows = q.order_by(InjuryRecord.injury_date.desc()).limit(limit).all()
    names = {p.participant_id: p.name for p in db.query(Participant).all()}
    return [
        {"id": r.id, "athlete_id": r.athlete_id, "athlete_name": names.get(r.athlete_id),
         "injury_date": r.injury_date.strftime("%Y-%m-%d") if r.injury_date else None,
         "part": r.part, "injury_level": r.injury_level, "diagnosis": r.diagnosis,
         "status": r.status, "note": r.note}
        for r in rows
    ]


@router.post("/injuries")
def injury_create(payload: dict, db: Session = Depends(get_db)):
    """伤病录入：POST {athlete_id, injury_date, part, injury_level, diagnosis, status, note}"""
    from datetime import date
    row = InjuryRecord(
        athlete_id=payload["athlete_id"],
        injury_date=date.fromisoformat(payload.get("injury_date") or date.today().isoformat()),
        part=payload.get("part"), injury_level=payload.get("injury_level", "轻"),
        diagnosis=payload.get("diagnosis"), status=payload.get("status", "治疗中"),
        note=payload.get("note"),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "created": True}


@router.patch("/injuries/{injury_id}")
def injury_update(injury_id: int, payload: dict, db: Session = Depends(get_db)):
    """伤病更新（如状态：治疗中→已恢复）。"""
    row = db.query(InjuryRecord).get(injury_id)
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    for k in ("part", "injury_level", "diagnosis", "status", "note"):
        if k in payload:
            setattr(row, k, payload[k])
    db.commit()
    return {"id": row.id, "updated": True}


# ══════════ 前测 / 疲劳 / 训练课 ══════════
@router.get("/pretest")
def pretest_list(db: Session = Depends(get_db)):
    rows = db.query(Pretest).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "subject_id": r.subject_id,
            "profile_class": r.profile_class,
            "profile_gender": r.profile_gender,
            "profile_coach": r.profile_coach,
            "profile_age": r.profile_age,
            "fms_total": r.fms_total,
            "ybt_left_ant": r.ybt_left_ant,
            "ybt_right_ant": r.ybt_right_ant,
            "jump_single_r": r.jump_single_r,
            "jump_triple_r": r.jump_triple_r,
            "cmj_height_cm": r.cmj_height_cm,
            "lactate_pre": r.lactate_pre,
            "lactate_post5": r.lactate_post5,
            "cop_left_ellipse_area": r.cop_left_ellipse_area,
        }
        for r in rows
    ]


@router.get("/fatigue")
def fatigue_list(db: Session = Depends(get_db)):
    rows = db.query(AcuteFatigue).all()
    return [
        {
            "id": r.id,
            "subject_id": r.subject_id,
            "name": r.name,
            "load_pct": r.load_pct,
            "intervention": r.intervention,
            "avg_power_w": r.avg_power_w,
            "peak_power_w": r.peak_power_w,
            "cmj_pre": r.cmj_pre,
            "cmj_24h": r.cmj_24h,
            "cmj_72h": r.cmj_72h,
            "vas_rest": r.vas_rest,
            "vas_24h": r.vas_24h,
            "rpe_rest": r.rpe_rest,
            "rpe_24h": r.rpe_24h,
            "hrv_sdnn": r.hrv_sdnn,
            "hrv_rmssd": r.hrv_rmssd,
        }
        for r in rows
    ]


@router.get("/training/sessions")
def training_list(db: Session = Depends(get_db)):
    rows = db.query(TrainingSession).order_by(TrainingSession.datetime.desc()).all()
    return [
        {
            "id": r.id,
            "session_name": r.session_name,
            "datetime": r.datetime.isoformat() if r.datetime else None,
            "duration_min": r.duration_min,
            "n_athletes": r.n_athletes,
            "coach": r.coach,
        }
        for r in rows
    ]


# ══════════ 运动员全景 ══════════
@router.get("/athlete/panorama/{subject_id}")
def panorama(subject_id: str, db: Session = Depends(get_db)):
    p = _p(db, subject_id)
    if not p:
        raise HTTPException(status_code=404, detail="运动员不存在")
    from ..services.hrv import recovery_level
    samples = db.query(Sample).filter(Sample.participant_id == subject_id).all()
    hr = db.query(HrSession).filter(HrSession.subject_id == subject_id).all()
    cpet = db.query(CpetTest).filter(CpetTest.subject_id == subject_id).all()
    pretest = db.query(Pretest).filter(Pretest.subject_id == subject_id).first()
    fatigue = db.query(AcuteFatigue).filter(AcuteFatigue.subject_id == subject_id).first()

    # CPET 最优 + 历史
    cpet_ok = [c for c in cpet if c.vo2kg_peak]
    best_cpet = max(cpet_ok, key=lambda c: c.vo2kg_peak) if cpet_ok else None
    # HRV
    hrv = None
    if fatigue and (fatigue.hrv_sdnn is not None or fatigue.hrv_rmssd is not None):
        hrv = {
            "sdnn": fatigue.hrv_sdnn, "rmssd": fatigue.hrv_rmssd,
            "lf_hf": fatigue.hrv_lf_hf, "total_power": fatigue.hrv_total_power,
            "level": recovery_level(fatigue.hrv_sdnn, fatigue.hrv_rmssd),
        }
    # 心率统计
    hrs = [h.avg_hr for h in hr if h.avg_hr]
    z45 = sum((h.z4 or 0) + (h.z5 or 0) for h in hr)
    zsum = sum((h.z1 or 0) + (h.z2 or 0) + (h.z3 or 0) + (h.z4 or 0) + (h.z5 or 0) for h in hr)
    # 血液最新（最后一条 72H，否则最近）
    bl = {}
    if samples:
        latest = max(samples, key=lambda s: (s.collection_time or datetime.min, s.id))
        bl = {
            "testosterone": latest.testosterone_value,
            "cortisol": latest.cortisol_ug_dL,
            "urea": latest.urea_mmol_L,
            "ck": latest.creatine_kinase_U_L,
            "ldh": latest.ldh_U_L,
            "collection_time": latest.collection_time.strftime("%m-%d") if latest.collection_time else None,
        }
    # 训练成绩（日常录入）：最近记录 + 各项目最新值
    tents = db.query(TrainingEntry).filter(TrainingEntry.athlete_id == subject_id)\
        .order_by(TrainingEntry.entry_date.desc()).all()
    latest_by_type = {}
    for te in tents:
        if te.test_type not in latest_by_type:
            latest_by_type[te.test_type] = {"value": te.value, "unit": te.unit,
                                            "date": te.entry_date.strftime("%m-%d") if te.entry_date else None}
    training = {
        "count": len(tents),
        "latest_by_type": latest_by_type,
        "recent": [
            {"date": te.entry_date.strftime("%m-%d") if te.entry_date else None,
             "test_type": te.test_type, "value": te.value, "unit": te.unit,
             "session_name": te.session_name, "note": te.note}
            for te in tents[:8]
        ],
    }
    # 雷达五维（相对全队归一，0-100）
    radar = _radar_profile(db, subject_id, best_cpet, hrv, hr, pretest)
    return {
        "participant": {
            "participant_id": p.participant_id,
            "name": p.name,
            "sex": p.sex,
            "age_years": p.age_years,
            "group_name": p.group_name,
            "athlete_class": p.athlete_class,
            "coach": p.coach,
            "height_cm": p.height_cm,
            "weight_kg": p.weight_kg,
            "intervention": p.intervention,
        },
        "radar": radar,
        "cpet": {
            "count": len(cpet),
            "best_vo2kg": round(best_cpet.vo2kg_peak, 1) if best_cpet else None,
            "best_pctnorm": round(best_cpet.vo2kg_pctnorm, 1) if best_cpet and best_cpet.vo2kg_pctnorm else None,
            "ve_slope": round(best_cpet.slope_ve_vco2, 1) if best_cpet and best_cpet.slope_ve_vco2 else None,
            "vt1_pct": round(best_cpet.vo2kg_vt1_pctmax, 1) if best_cpet and best_cpet.vo2kg_vt1_pctmax else None,
            "vt1_vo2kg": round(best_cpet.vo2kg_vt1, 1) if best_cpet and best_cpet.vo2kg_vt1 else None,
            "rer": best_cpet.rer_peak if best_cpet else None,
            "hr_peak": best_cpet.hr_peak if best_cpet else None,
            "ve_peak": round(best_cpet.ve_peak, 1) if best_cpet and best_cpet.ve_peak else None,
            "vo2_abs": round(best_cpet.vo2_peak, 2) if best_cpet and best_cpet.vo2_peak else None,
            "duration_s": round(best_cpet.exercise_dur_s or best_cpet.duration_s, 0) if best_cpet else None,
            "peak_wr": best_cpet.peak_wr if best_cpet else None,
            "valid_class": best_cpet.valid_class if best_cpet else None,
            "ranks": _cpet_ranks(db, best_cpet),
            "history": [
                {"date": c.test_start.strftime("%m-%d") if c.test_start else None,
                 "vo2kg": c.vo2kg_peak, "cls": c.valid_class,
                 "vo2kg_norm": c.vo2kg_norm}
                for c in sorted(cpet, key=lambda x: x.test_start or datetime.min)
            ],
        },
        "hrv": hrv,
        "hr": {
            "sessions": len(hr),
            "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
            "max_hr": max((h.max_hr for h in hr if h.max_hr), default=None),
            "z45_pct": round(z45 / zsum * 100, 1) if zsum else None,
        },
        "blood": bl,
        "blood_samples": len(samples),
        "training": training,
        "pretest": {
            "fms_total": pretest.fms_total if pretest else None,
            "cmj_height_cm": pretest.cmj_height_cm if pretest else None,
            "lactate_pre": pretest.lactate_pre if pretest else None,
            "ybt_score": pretest.ybt_total if hasattr(pretest, "ybt_total") and pretest.ybt_total else None,
        } if pretest else None,
        "fatigue": {
            "load_pct": fatigue.load_pct if fatigue else None,
            "cmj_pre": fatigue.cmj_pre if fatigue else None,
            "cmj_24h": fatigue.cmj_24h if fatigue else None,
            "cmj_72h": fatigue.cmj_72h if fatigue else None,
        } if fatigue else None,
    }


def _radar_profile(db, subject_id, best_cpet, hrv, hr_objs, pretest):
    """雷达五维画像（相对全队百分位，0-100）。
    hr_objs: HrSession 对象列表（用于算负荷百分位）。
    """
    from app.models import CpetTest as _C, HrSession as _H
    dims = {"有氧能力": None, "耐力储备": None, "恢复状态": None, "训练负荷": None, "体能基础": None}
    # 有氧：全队 VO2 百分位
    if best_cpet and best_cpet.vo2kg_peak:
        allv = [c.vo2kg_peak for c in db.query(_C).all() if c.vo2kg_peak]
        allv.sort()
        dims["有氧能力"] = round(_pct(allv, best_cpet.vo2kg_peak))
    # 耐力：VT1%
    if best_cpet and best_cpet.vo2kg_vt1_pctmax:
        allv = [c.vo2kg_vt1_pctmax for c in db.query(_C).all() if c.vo2kg_vt1_pctmax]
        allv.sort()
        dims["耐力储备"] = round(_pct(allv, best_cpet.vo2kg_vt1_pctmax))
    # 恢复：RMSSD 百分位
    if hrv and hrv["rmssd"] is not None:
        from app.models import AcuteFatigue as _AF
        allv = sorted(x.hrv_rmssd for x in db.query(_AF).all() if x.hrv_rmssd is not None)
        dims["恢复状态"] = round(_pct(allv, hrv["rmssd"]))
    # 训练负荷：高强度% 百分位（越高负荷越大）
    if hr_objs:
        all_hr = db.query(_H).all()
        vals = []
        for h in all_hr:
            zs = (h.z1 or 0) + (h.z2 or 0) + (h.z3 or 0) + (h.z4 or 0) + (h.z5 or 0)
            if zs:
                vals.append(((h.z4 or 0) + (h.z5 or 0)) / zs * 100)
        zs_mine = sum((h.z1 or 0) + (h.z2 or 0) + (h.z3 or 0) + (h.z4 or 0) + (h.z5 or 0) for h in hr_objs)
        mine = sum((h.z4 or 0) + (h.z5 or 0) for h in hr_objs) / max(1, zs_mine) * 100
        dims["训练负荷"] = round(_pct(sorted(vals), mine))
    # 体能：FMS 百分位
    if pretest and pretest.fms_total:
        from app.models import Pretest as _PT
        allv = sorted(x.fms_total for x in db.query(_PT).all() if x.fms_total is not None)
        dims["体能基础"] = round(_pct(allv, pretest.fms_total))
    return {"indicators": list(dims.keys()), "values": list(dims.values())}


def _pct(sorted_list, v):
    """值在排序列表中的百分位（0-100）。"""
    if not sorted_list:
        return 0
    if v <= sorted_list[0]:
        return 1
    if v >= sorted_list[-1]:
        return 100
    import bisect
    i = bisect.bisect_left(sorted_list, v)
    return round(i / len(sorted_list) * 100)


def _cpet_ranks(db, best):
    """该运动员各 CPET 指标在全队（每人最优）的排名。"""
    from app.models import CpetTest as _C
    if not best:
        return {}
    rows = db.query(_C).all()
    best_by_person = {}
    for r in rows:
        if not r.name or r.vo2kg_peak is None:
            continue
        cur = best_by_person.get(r.name)
        if cur is None or (r.vo2kg_peak or 0) > (cur.get("vo2kg") or 0):
            best_by_person[r.name] = {
                "vo2kg": r.vo2kg_peak, "pctnorm": r.vo2kg_pctnorm,
                "slope": r.slope_ve_vco2, "vt1": r.vo2kg_vt1_pctmax,
                "rer": r.rer_peak,
            }
    total = len(best_by_person)
    if not total:
        return {}

    def _rank(field, desc, mine):
        if mine is None:
            return None
        vals = [v[field] for v in best_by_person.values() if v.get(field) is not None]
        if not vals:
            return None
        if desc:
            rank = 1 + sum(1 for x in vals if x > mine)
        else:
            rank = 1 + sum(1 for x in vals if x < mine)
        return {"rank": rank, "total": len(vals),
                "pct": round(rank / len(vals) * 100)}

    return {
        "vo2kg": _rank("vo2kg", True, best.vo2kg_peak),
        "pctnorm": _rank("pctnorm", True, best.vo2kg_pctnorm),
        "slope": _rank("slope", False, best.slope_ve_vco2),
        "vt1": _rank("vt1", True, best.vo2kg_vt1_pctmax),
        "rer": _rank("rer", True, best.rer_peak),
        "total": total,
    }

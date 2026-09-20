# -*- coding: utf-8 -*-
"""统计/科研 API：描述统计、纵向检验、组间比较、相关分析。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import ANALYTES, GROUPS
from ..database import get_db
from ..models import AcuteFatigue, CompetitionResult, CpetTest, Pretest, Sample, TrainingEntry, Participant
from ..services import stats as svc

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _samples_as_dicts(db: Session):
    return [
        {
            "participant_id": s.participant_id,
            "timepoint": s.timepoint,
            "group_name": s.participant.group_name if s.participant else None,
            "sex": s.participant.sex if s.participant else None,
            "testosterone_value": s.testosterone_value,
            "cortisol_ug_dL": s.cortisol_ug_dL,
            "urea_mmol_L": s.urea_mmol_L,
            "creatine_kinase_U_L": s.creatine_kinase_U_L,
            "ldh_U_L": s.ldh_U_L,
        }
        for s in db.query(Sample).all()
    ]


@router.get("/descriptive")
def descriptive(
    by: str = "timepoint",  # timepoint | group | sex
    analyte: str | None = None,
    db: Session = Depends(get_db),
):
    samples = _samples_as_dicts(db)
    cols = {"testosterone_value": "睾酮"} | {k: v[0] for k, v in ANALYTES.items()}
    if analyte:
        cols = {analyte: cols.get(analyte, analyte)}
    result = {}
    for col, label in cols.items():
        result[label] = svc.summary_by(samples, col, by)
    return result


@router.get("/longitudinal")
def longitudinal(db: Session = Depends(get_db)):
    """每指标 Friedman + Wilcoxon 配对（含 Holm 校正）。"""
    samples = _samples_as_dicts(db)
    result = {}
    for col, (label, unit) in ANALYTES.items():
        result[label] = {
            "unit": unit,
            "friedman": svc.friedman(samples, col),
            "pairwise": svc.wilcoxon_pairs(samples, col),
        }
    return result


@router.get("/group_comparison")
def group_comparison(db: Session = Depends(get_db)):
    """按时间点分层，组间 Kruskal-Wallis。"""
    samples = _samples_as_dicts(db)
    result = {}
    for col, (label, unit) in ANALYTES.items():
        result[label] = {
            "unit": unit,
            "kruskal": svc.kruskal_groups(samples, col, GROUPS),
        }
    return result


@router.get("/correlation")
def correlation(db: Session = Depends(get_db)):
    samples = _samples_as_dicts(db)
    return {"matrix": svc.spearman_correlation(samples)}


@router.get("/performance_correlation")
def performance_correlation(db: Session = Depends(get_db)):
    """成绩与体能指标的运动员层级 Spearman 相关分析。

    每名运动员先聚合为一个值：比赛取该项目最好成绩（用时最短），
    体能取最好一次测试；再按相同运动员配对计算相关，避免同一人多次
    记录把样本量人为放大。结果用于训练决策参考，不代表因果关系。
    """
    participants = {
        p.participant_id: (p.name or p.participant_id)
        for p in db.query(Participant).all()
        if p.participant_id
    }
    competitions = [
        {"athlete_id": r.participant_id, "event": r.event or "未分类", "value": r.time_seconds}
        for r in db.query(CompetitionResult).all()
        if r.participant_id and r.time_seconds is not None
    ]
    performance = {}
    for row in competitions:
        performance.setdefault(row["event"], {})
        current = performance[row["event"]].get(row["athlete_id"])
        if current is None or row["value"] < current:
            performance[row["event"]][row["athlete_id"]] = row["value"]

    metric_values = {}
    metric_meta = {}

    # 日常体能记录：按运动员取最好一次；计时项目取最小值，其余取最大值。
    fitness_types = {
        "CMJ纵跳": ("CMJ纵跳", "cm", "max"),
        "立定跳远": ("立定跳远", "cm", "max"),
        "FMS总分": ("FMS总分", "分", "max"),
        "YBT总分": ("YBT总分", "cm", "max"),
        "深蹲1RM": ("深蹲1RM", "kg", "max"),
        "卧推1RM": ("卧推1RM", "kg", "max"),
        "引体向上": ("引体向上", "次", "max"),
        "平板支撑": ("平板支撑", "s", "max"),
        "体重": ("体重", "kg", "max"),
        "体脂率": ("体脂率", "%", "min"),
    }
    training_rows = {}
    for row in db.query(TrainingEntry).all():
        meta = fitness_types.get(row.test_type)
        if not meta or row.athlete_id is None or row.value is None:
            continue
        key = f"training:{row.test_type}"
        metric_meta[key] = {"key": key, "label": meta[0], "unit": meta[1], "source": "日常训练体能", "higher_is_better": meta[2] == "max"}
        training_rows.setdefault(key, {}).setdefault(row.athlete_id, []).append(float(row.value))
    for key, by_athlete in training_rows.items():
        meta = metric_meta[key]
        metric_values[key] = {
            athlete_id: (max(vals) if meta["higher_is_better"] else min(vals))
            for athlete_id, vals in by_athlete.items()
        }

    # CPET：每人取有效测试中的最高 VO₂/kg 与峰值功率。
    cpet_metrics = {
        "cpet:vo2kg_peak": ("VO₂/kg峰值", "ml/kg/min"),
        "cpet:peak_wr": ("CPET峰值功率", "W"),
    }
    cpet_rows = {key: {} for key in cpet_metrics}
    for row in db.query(CpetTest).all():
        if not row.subject_id:
            continue
        for key, (label, unit) in cpet_metrics.items():
            value = getattr(row, key.split(":", 1)[1])
            if value is None:
                continue
            metric_meta[key] = {"key": key, "label": label, "unit": unit, "source": "CPET", "higher_is_better": True}
            previous = cpet_rows[key].get(row.subject_id)
            cpet_rows[key][row.subject_id] = max(previous, float(value)) if previous is not None else float(value)
    metric_values.update(cpet_rows)

    # 前测与急性疲劳：取数据库中的标准化记录（每人一条时直接使用）。
    pretest_metrics = {
        "pretest:cmj_height_cm": ("前测 CMJ", "cm", True),
        "pretest:fms_total": ("前测 FMS", "分", True),
        "pretest:ybt_total": ("前测 YBT", "cm", True),
        "pretest:jump_single_r": ("单跳（右）", "cm", True),
        "pretest:jump_triple_r": ("三级跳（右）", "cm", True),
    }
    pretest_rows = {key: {} for key in pretest_metrics}
    for row in db.query(Pretest).all():
        if not row.subject_id:
            continue
        for key, (label, unit, higher) in pretest_metrics.items():
            attr = key.split(":", 1)[1]
            value = getattr(row, attr, None)
            if value is None:
                continue
            metric_meta[key] = {"key": key, "label": label, "unit": unit, "source": "基础体能前测", "higher_is_better": higher}
            previous = pretest_rows[key].get(row.subject_id)
            pretest_rows[key][row.subject_id] = max(previous, float(value)) if previous is not None else float(value)
    metric_values.update(pretest_rows)

    # CMJ 24h 恢复值作为可选指标，帮助教练观察成绩与恢复状态的关系。
    fatigue_rows = {}
    for row in db.query(AcuteFatigue).all():
        if row.subject_id and row.cmj_24h is not None:
            fatigue_rows[row.subject_id] = max(fatigue_rows.get(row.subject_id, float("-inf")), float(row.cmj_24h))
    metric_values["fatigue:cmj_24h"] = fatigue_rows
    metric_meta["fatigue:cmj_24h"] = {"key": "fatigue:cmj_24h", "label": "CMJ 24小时", "unit": "cm", "source": "急性疲劳", "higher_is_better": True}

    result = []
    for event, by_athlete in performance.items():
        for key, fitness in metric_values.items():
            points = []
            for athlete_id, performance_value in by_athlete.items():
                fitness_value = fitness.get(athlete_id)
                if fitness_value is None:
                    continue
                points.append({
                    "athlete_id": athlete_id,
                    "name": participants.get(athlete_id, athlete_id),
                    "performance": round(float(performance_value), 3),
                    "fitness": round(float(fitness_value), 3),
                })
            if len(points) < 3:
                continue
            x = [p["fitness"] for p in points]
            y = [p["performance"] for p in points]
            rho, p_value = svc.spearman_pair(x, y)
            if rho is None:
                continue
            result.append({
                "event": event,
                "metric": metric_meta[key],
                "n": len(points),
                "rho": rho,
                "p": p_value,
                "points": points,
            })

    result.sort(key=lambda row: (row["event"], -row["n"], row["metric"]["label"]))
    return {
        "events": sorted(performance.keys()),
        "metrics": list(metric_meta.values()),
        "pairs": result,
        "method": "按运动员聚合：比赛取最好用时，体能取最好测试；Spearman ρ；相关不等于因果。",
    }


@router.get("/by_timepoint")
def by_timepoint(db: Session = Depends(get_db)):
    """各时间点描述统计（科研表格用）。"""
    samples = _samples_as_dicts(db)
    result = {}
    for col, (label, unit) in ANALYTES.items():
        rows = []
        for tp in ["BL", "24H", "72H"]:
            sub = [s for s in samples if s["timepoint"] == tp]
            rows.append({"timepoint": tp, **svc.descriptive(svc._num_series(sub, col))})
        result[label] = {"unit": unit, "rows": rows}
    return result

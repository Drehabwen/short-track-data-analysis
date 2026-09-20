# -*- coding: utf-8 -*-
"""修复并接入统一数据集的运动员、疲劳、训练指标和心率记录。

幂等执行：急性疲劳按统一主表重建；训练指标按来源键去重追加；
心率按运动员/日期/课名/核心数值去重追加，不覆盖其他来源的历史记录。
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import AcuteFatigue, HrSession, Participant, TrainingEntry  # noqa: E402


ROOT = Path(r"D:\DEV\blood\统一数据集")
MASTER = ROOT / "统一数据集_受试者主表.csv"
HR_SOURCE = ROOT / "心率明细表.csv"


FATIGUE_FIELDS = {
    "load_pct": "load_pct",
    "avg_power_p1": "avg_power_w",
    "peak_power_p1": "peak_power_w",
    "cmj_pre": "cmj_pre",
    "cmj_24h": "cmj_24h",
    "cmj_72h": "cmj_72h",
    "vas_rest": "vas_rest",
    "vas_post": "vas_post",
    "vas_interv": "vas_interv",
    "vas_24h": "vas_24h",
    "vas_72h": "vas_72h",
    "rpe_rest": "rpe_rest",
    "rpe_post": "rpe_post",
    "rpe_interv": "rpe_interv",
    "rpe_24h": "rpe_24h",
    "rpe_72h": "rpe_72h",
    "lactate_rest": "lactate_rest",
    "lactate_post": "lactate_post",
    "lactate_interv": "lactate_interv",
    "hr_rest_avg": "hr_rest_avg",
    "hr_rest_max": "hr_rest_max",
    "hr_post_avg": "hr_post_avg",
    "hr_post_max": "hr_post_max",
    "hr_24h_avg": "hr_24h_avg",
    "hr_72h_avg": "hr_72h_avg",
    "hrv_sdnn": "hrv_sdnn",
    "hrv_rmssd": "hrv_rmssd",
    "hrv_lf_hf": "hrv_lf_hf",
    "hrv_total_power": "hrv_total_power",
}


def to_float(value):
    if value is None or str(value).strip() in {"", "NA", "nan", "None"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def rebuild_fatigue(db, master_rows):
    """以统一主表重建可按运动员查询的急性疲劳数据。"""
    db.query(AcuteFatigue).delete(synchronize_session=False)
    for source in master_rows:
        values = {
            dest: to_float(source.get(src)) for src, dest in FATIGUE_FIELDS.items()
        }
        db.add(
            AcuteFatigue(
                subject_id=source["subject_id"],
                name=source.get("name") or None,
                intervention=source.get("intervention") or None,
                **values,
            )
        )
    return len(master_rows)


def import_baseline_entries(db, master_rows):
    """把明确的前测成绩接入训练数据入口，并保留日期缺失事实。"""
    metric_map = [
        ("pt_500m_s", "500m计时", "s"),
        ("pt_7lap_s", "7圈计时", "s"),
        ("pt_cmj", "CMJ纵跳", "cm"),
        ("pt_fms_total", "FMS总分", "分"),
    ]
    created = 0
    skipped = 0
    source_label = "统一数据集前测"
    note = "来源：统一数据集_受试者主表.csv；原表未提供测量日期"
    for source in master_rows:
        for field, test_type, unit in metric_map:
            value = to_float(source.get(field))
            if value is None:
                continue
            exists = (
                db.query(TrainingEntry)
                .filter(
                    TrainingEntry.athlete_id == source["subject_id"],
                    TrainingEntry.session_name == source_label,
                    TrainingEntry.test_type == test_type,
                    TrainingEntry.value == value,
                    TrainingEntry.source == "unified",
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            db.add(
                TrainingEntry(
                    athlete_id=source["subject_id"],
                    entry_date=None,
                    session_name=source_label,
                    test_type=test_type,
                    value=value,
                    unit=unit,
                    note=note,
                    source="unified",
                )
            )
            created += 1
    return created, skipped


def import_hr(db, hr_rows, participants):
    """追加统一数据集心率；已存在的同课记录只补来源标记。"""
    by_name = {p.name: p.participant_id for p in participants if p.name}
    # 原始文件中的姓名变体；访客记录保留姓名但不虚构运动员编号。
    aliases = {"王慧霖": "C13"}
    existing = db.query(HrSession).all()
    created = 0
    deduped = 0
    unresolved = 0

    def number(value):
        result = to_float(value)
        return round(result, 3) if result is not None else None

    for source in hr_rows:
        name = (source.get("姓名") or "").strip() or None
        sid = aliases.get(name) or by_name.get(name)
        if not sid:
            unresolved += 1
        date = datetime.strptime(source["日期"], "%Y-%m-%d")
        session_name = (source.get("场次") or "").strip() or None
        duration = number(source.get("时长min"))
        avg_hr = number(source.get("平均心率"))
        max_hr = number(source.get("最大心率"))
        candidates = [
            x
            for x in existing
            if x.subject_id == sid
            and (x.datetime.date() if x.datetime else None) == date.date()
            and x.session_name == session_name
        ]
        duplicate = next(
            (
                x
                for x in candidates
                if all(
                    a is not None and b is not None and abs(a - b) <= tolerance
                    for a, b, tolerance in (
                        (duration, x.duration_min, 0.7),
                        (avg_hr, x.avg_hr, 1.1),
                        (max_hr, x.max_hr, 1.1),
                    )
                )
            ),
            None,
        )
        if duplicate:
            deduped += 1
            source_tag = "统一数据集/心率明细表.csv"
            if duplicate.source_file:
                if source_tag not in duplicate.source_file:
                    duplicate.source_file = f"{duplicate.source_file};{source_tag}"
            else:
                duplicate.source_file = source_tag
            continue

        row = HrSession(
            athlete=name,
            subject_id=sid,
            datetime=date,
            session_name=session_name,
            coach=(source.get("教练") or "").strip() or None,
            session_type=(source.get("类型") or "").strip() or None,
            duration_min=duration,
            avg_hr=avg_hr,
            max_hr=max_hr,
            source_file="统一数据集/心率明细表.csv",
        )
        db.add(row)
        existing.append(row)
        created += 1
    return created, deduped, unresolved


def repair():
    if not MASTER.is_file() or not HR_SOURCE.is_file():
        raise FileNotFoundError("统一数据集源文件不存在")
    master_rows = read_csv(MASTER)
    hr_rows = read_csv(HR_SOURCE)
    db = SessionLocal()
    try:
        participants = db.query(Participant).all()
        fatigue_rows = rebuild_fatigue(db, master_rows)
        training_created, training_skipped = import_baseline_entries(db, master_rows)
        hr_created, hr_deduped, hr_unresolved = import_hr(db, hr_rows, participants)
        db.commit()
        print(f"统一主表：{len(master_rows)} 行")
        print(f"急性疲劳：重建 {fatigue_rows} 行，已补齐运动员编号")
        print(f"前测训练指标：新增 {training_created} 条，跳过重复 {training_skipped} 条")
        print(f"统一数据集心率：新增 {hr_created} 条，去重 {hr_deduped} 条，未关联姓名 {hr_unresolved} 条")
        print(f"当前总计：急性疲劳 {db.query(AcuteFatigue).count()} 行，训练记录 {db.query(TrainingEntry).count()} 条，心率 {db.query(HrSession).count()} 条")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    repair()

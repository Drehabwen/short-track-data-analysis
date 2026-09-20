# -*- coding: utf-8 -*-
"""将 D:\\DEV\\blood\\blood.db（SQLite 科研库）迁移到平台 PostgreSQL。

幂等：participants 按 subject_id upsert 合并档案；其余表清空后全量导入。
用法：python -m scripts.migrate_blooddb
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AcuteFatigue,
    CpetTest,
    HrSession,
    Participant,
    Pretest,
    TrainingSession,
)
from app.models import Base  # noqa: E402

SRC = r"D:\DEV\blood\blood.db"


def sex_map(g: str | None) -> str | None:
    if not g:
        return None
    if "男" in g or g == "M":
        return "男"
    if "女" in g or g == "F":
        return "女"
    return g


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def to_float(v):
    """数值容错：中文占位符/空值 → None。"""
    if v is None or isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def migrate():
    print(f"读取 {SRC} ...")
    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ── 1. participants upsert（86 人档案合并）──
    athletes = src.execute("SELECT * FROM athletes").fetchall()
    updated, created = 0, 0
    for a in athletes:
        sid = a["subject_id"]
        p = db.query(Participant).filter(Participant.participant_id == sid).first()
        data = dict(
            name=a["name"],
            sex=sex_map(a["gender"]),
            age_years=a["age"],
            birth_date=parse_dt(a["dob"]),
            group_name=a["intervention"],
            athlete_class=a["class"],
            coach=a["coach"],
            height_cm=a["height_cm"],
            weight_kg=a["weight_kg"],
            intervention=a["intervention"],
            unregistered=bool(a["unregistered"]),
        )
        if p:
            for k, v in data.items():
                if v is not None:
                    setattr(p, k, v)
            updated += 1
        else:
            db.add(Participant(participant_id=sid, **data))
            created += 1
    print(f"participants: 更新 {updated}，新增 {created}")
    db.commit()

    # ── 2. hr_sessions ──
    db.query(HrSession).delete()
    rows = [dict(r) for r in src.execute("SELECT * FROM hr_sessions")]
    for r in rows:
        db.add(HrSession(**{k: r[k] for k in [
            "athlete", "subject_id", "session_name", "coach", "session_type",
            "duration_min", "avg_hr", "max_hr", "cal", "z1", "z2", "z3", "z4", "z5",
            "source_file"]} | {"datetime": parse_dt(r["datetime"])}))
    db.commit()
    print(f"hr_sessions: 导入 {len(rows)} 条")

    # ── 3. training_sessions ──
    db.query(TrainingSession).delete()
    rows = [dict(r) for r in src.execute("SELECT * FROM training_sessions")]
    for r in rows:
        db.add(TrainingSession(**{k: r[k] for k in [
            "session_name", "duration_min", "n_athletes", "coach", "source_file"]} | {"datetime": parse_dt(r["datetime"])}))
    db.commit()
    print(f"training_sessions: 导入 {len(rows)} 条")

    # ── 4. cpet_tests ──
    db.query(CpetTest).delete()
    rows = [dict(r) for r in src.execute("SELECT * FROM cpet_tests")]
    cpet_cols = [
        "test_id", "file", "name", "subject_id", "gender", "age_years", "height_cm",
        "weight_kg", "bmi", "device", "duration_s", "valid_class", "vo2kg_peak",
        "vo2kg_norm", "vo2kg_pctnorm", "vo2_peak", "vo2_maxabs", "hr_peak", "rer_peak",
        "ve_peak", "slope_ve_vco2", "vo2kg_vt1", "vo2kg_vt1_pctmax", "peak_wr",
        "exercise_dur_s", "meas_max_vo2kg", "meas_max_rer", "meas_max_hr", "plateau_delta",
    ]
    for r in rows:
        db.add(CpetTest(**{k: r[k] for k in cpet_cols} | {"test_start": parse_dt(r["test_start"])}))
    db.commit()
    print(f"cpet_tests: 导入 {len(rows)} 条")

    # ── 5. pretest ──
    db.query(Pretest).delete()
    rows = [dict(r) for r in src.execute("SELECT * FROM pretest")]
    pretest_cols = [
        "name", "subject_id", "profile_class", "profile_gender", "profile_coach",
        "profile_age", "profile_height_cm", "profile_weight_kg", "profile_bmi",
        "fms_total", "ybt_left_ant", "ybt_left_post_med", "ybt_left_post_lat",
        "ybt_right_ant", "ybt_right_post_med", "ybt_right_post_lat",
        "ybt_heel_raise_l", "ybt_heel_raise_r", "ybt_eyes_closed_l", "ybt_eyes_closed_r",
        "rom_ankle_dorsi_l", "rom_ankle_dorsi_r", "jump_single_r", "jump_single_l",
        "jump_triple_r", "jump_triple_l", "cmj_height_cm",
        "lactate_pre", "lactate_post0", "lactate_post3", "lactate_post5", "lactate_post10",
        "cop_left_ellipse_area", "cop_right_ellipse_area",
    ]
    pretest_str_cols = {"name", "subject_id", "profile_class", "profile_gender", "profile_coach"}
    for r in rows:
        data = {
            k: (r[k] if k in pretest_str_cols else to_float(r[k]))
            for k in pretest_cols
        }
        db.add(Pretest(**data))
    db.commit()
    print(f"pretest: 导入 {len(rows)} 条")

    # ── 6. acute_fatigue ──
    db.query(AcuteFatigue).delete()
    rows = [dict(r) for r in src.execute("SELECT * FROM acute_fatigue")]
    fatigue_cols = [
        "subject_id", "name", "load_pct", "intervention", "avg_power_w", "peak_power_w",
        "cmj_pre", "cmj_24h", "cmj_72h", "vas_rest", "vas_post", "vas_interv",
        "vas_24h", "vas_72h", "rpe_rest", "rpe_post", "rpe_interv", "rpe_24h", "rpe_72h",
        "lactate_rest", "lactate_post", "lactate_interv",
        "hr_rest_avg", "hr_rest_max", "hr_post_avg", "hr_post_max", "hr_24h_avg", "hr_72h_avg",
        "hrv_sdnn", "hrv_rmssd", "hrv_lf_hf", "hrv_total_power",
    ]
    for r in rows:
        db.add(AcuteFatigue(**{k: to_float(r[k]) for k in fatigue_cols}))
    db.commit()
    print(f"acute_fatigue: 导入 {len(rows)} 条")

    src.close()
    db.close()

    # 汇总
    db = SessionLocal()
    print("\n=== 迁移后汇总 ===")
    print(f"participants: {db.query(Participant).count()}")
    print(f"hr_sessions: {db.query(HrSession).count()}")
    print(f"training_sessions: {db.query(TrainingSession).count()}")
    print(f"cpet_tests: {db.query(CpetTest).count()}")
    print(f"pretest: {db.query(Pretest).count()}")
    print(f"acute_fatigue: {db.query(AcuteFatigue).count()}")
    db.close()
    print("迁移完成 OK")


if __name__ == "__main__":
    migrate()

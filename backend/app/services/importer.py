# -*- coding: utf-8 -*-
"""CSV 导入服务：将校准后的 visit 级数据导入 PostgreSQL。"""
from __future__ import annotations

import csv
from datetime import datetime

import pandas as pd

from ..config import SEED_DIR, TESTOSTERONE_LOD
from ..database import SessionLocal
from ..models import Participant, Sample


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return pd.to_datetime(value)
    except Exception:
        return None


def import_visits_csv(path=None) -> dict:
    """导入 blood_visits_curated.csv。幂等：重复 visit_id 跳过。"""
    path = path or (SEED_DIR / "blood_visits_curated.csv")
    db = SessionLocal()
    created_participants = 0
    created_samples = 0
    skipped = 0
    errors = []
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                visit_id = (row.get("visit_id") or "").strip()
                if not visit_id:
                    errors.append(f"空 visit_id 行: {row.get('review_no')}")
                    continue
                if db.query(Sample).filter(Sample.visit_id == visit_id).first():
                    skipped += 1
                    continue

                participant_id = (row.get("participant_id") or "").strip()
                # 运动员（无则建）
                participant = None
                if participant_id:
                    participant = (
                        db.query(Participant)
                        .filter(Participant.participant_id == participant_id)
                        .first()
                    )
                if participant is None:
                    age = row.get("age_report") or ""
                    try:
                        age_f = float(age) if age else None
                    except ValueError:
                        age_f = None
                    participant = Participant(
                        participant_id=participant_id,
                        batch_id=(row.get("batch_id") or "").strip() or None,
                        sex=(row.get("sex_report") or "").strip() or None,
                        age_years=age_f,
                        group_name=(row.get("group") or "").strip() or None,
                    )
                    db.add(participant)
                    db.flush()
                    created_participants += 1

                t_raw = (row.get("testosterone_raw") or "").strip()
                t_qual = (row.get("testosterone_qualifier") or "").strip() or None
                t_below = t_qual == "<"
                t_val = None
                if t_raw and not t_below:
                    try:
                        t_val = float(t_raw)
                    except ValueError:
                        t_val = None

                def _num(key):
                    v = (row.get(key) or "").strip()
                    if not v:
                        return None
                    try:
                        return float(v)
                    except ValueError:
                        return None

                sample = Sample(
                    visit_id=visit_id,
                    participant_id=participant_id,
                    episode_id=(row.get("episode_id") or "").strip() or None,
                    timepoint=(row.get("timepoint") or "").strip().upper(),
                    time_order=int(row["time_order"]) if (row.get("time_order") or "").strip() else None,
                    collection_time=parse_time(row.get("collection_time") or ""),
                    review_status=(row.get("review_status") or "通过").strip(),
                    review_note=(row.get("review_note") or "").strip() or None,
                    source_file=(row.get("original_image") or "").strip() or None,
                    source_workbook=(row.get("source_workbook") or "").strip() or None,
                    duplicate_resolution=(row.get("duplicate_resolution") or "").strip() or None,
                    testosterone_raw=t_raw or None,
                    testosterone_value=t_val,
                    testosterone_qualifier=t_qual,
                    testosterone_below_lod=t_below,
                    cortisol_ug_dL=_num("cortisol"),
                    urea_mmol_L=_num("urea"),
                    creatine_kinase_U_L=_num("ck"),
                    ldh_U_L=_num("ldh"),
                )
                db.add(sample)
                created_samples += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise
    finally:
        db.close()
    return {
        "participants_created": created_participants,
        "samples_created": created_samples,
        "skipped": skipped,
        "errors": errors,
    }

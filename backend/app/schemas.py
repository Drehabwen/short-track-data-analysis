# -*- coding: utf-8 -*-
"""Pydantic 模型（API 出入参）。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_id: str
    batch_id: str | None = None
    name: str | None = None
    sex: str | None = None
    age_years: float | None = None
    birth_date: datetime | None = None
    group_name: str | None = None
    athlete_class: str | None = None
    coach: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    intervention: str | None = None
    unregistered: bool | None = None


class SampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: str
    participant_id: str
    episode_id: str | None = None
    timepoint: str
    time_order: int | None = None
    collection_time: datetime | None = None
    review_status: str
    review_note: str | None = None
    source_file: str | None = None
    duplicate_resolution: str | None = None
    testosterone_raw: str | None = None
    testosterone_value: float | None = None
    testosterone_qualifier: str | None = None
    testosterone_below_lod: bool
    cortisol_ug_dL: float | None = None
    urea_mmol_L: float | None = None
    creatine_kinase_U_L: float | None = None
    ldh_U_L: float | None = None


class SampleUpdate(BaseModel):
    """数据管理中允许人工修正的字段。"""

    review_status: str | None = None
    review_note: str | None = None
    cortisol_ug_dL: float | None = None
    urea_mmol_L: float | None = None
    creatine_kinase_U_L: float | None = None
    ldh_U_L: float | None = None
    testosterone_raw: str | None = None
    testosterone_value: float | None = None


class ImportResult(BaseModel):
    participants_created: int
    samples_created: int
    skipped: int
    errors: list[str] = []


class ParticipantCreate(BaseModel):
    participant_id: str
    batch_id: str | None = None
    name: str | None = None
    sex: str | None = None
    age_years: float | None = None
    birth_date: str | None = None
    join_date: str | None = None
    group_name: str | None = None
    id_card: str | None = None


class ParticipantUpdate(BaseModel):
    batch_id: str | None = None
    name: str | None = None
    sex: str | None = None
    age_years: float | None = None
    birth_date: str | None = None
    join_date: str | None = None
    group_name: str | None = None
    id_card: str | None = None

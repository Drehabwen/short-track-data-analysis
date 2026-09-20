# -*- coding: utf-8 -*-
"""ORM 模型：users（用户）、participants（运动员）、samples（血样）、analytes（指标配置）。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class CompetitionResult(Base):
    """参赛记录（短道速滑比赛成绩）。"""

    __tablename__ = "competition_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(20), index=True)
    competition_name: Mapped[str | None] = mapped_column(String(120))
    competition_date: Mapped[datetime | None] = mapped_column(Date)
    venue: Mapped[str | None] = mapped_column(String(80))
    event: Mapped[str | None] = mapped_column(String(40))  # 500m/1000m/1500m/接力等
    time_result: Mapped[str | None] = mapped_column(String(30))  # 成绩 mm:ss.xx
    time_seconds: Mapped[float | None] = mapped_column(Float)  # 秒（可排序）
    rank: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # admin | coach | athlete
    display_name: Mapped[str | None] = mapped_column(String(50))
    # 运动员角色关联的运动员编号（可选）
    athlete_id: Mapped[str | None] = mapped_column(String(20), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str | None] = mapped_column(String(50))
    sex: Mapped[str | None] = mapped_column(String(4))
    age_years: Mapped[float | None] = mapped_column(Float)
    birth_date: Mapped[datetime | None] = mapped_column(DateTime)
    join_date: Mapped[datetime | None] = mapped_column(DateTime)
    group_name: Mapped[str | None] = mapped_column(String(20))
    id_card: Mapped[str | None] = mapped_column(String(30))
    # blood.db 全量档案扩展字段
    athlete_class: Mapped[str | None] = mapped_column(String(20))  # 班级（张/李/陈...）
    coach: Mapped[str | None] = mapped_column(String(50))  # 教练姓名
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    intervention: Mapped[str | None] = mapped_column(String(30))  # 干预分组
    unregistered: Mapped[bool] = mapped_column(Boolean, default=False)  # 未注册新队员标记

    # Phase 1 科研项目归属（legacy 数据为 NULL；M2 起按项目隔离，同一编码可属于多个项目）
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("research_projects.id", name="fk_participants_project_id"),
        nullable=True, index=True,
    )
    project: Mapped["ResearchProject | None"] = relationship(back_populates="participants")

    samples: Mapped[list["Sample"]] = relationship(back_populates="participant")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    participant_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("participants.participant_id"), index=True
    )
    episode_id: Mapped[str | None] = mapped_column(String(40))
    timepoint: Mapped[str] = mapped_column(String(10), index=True)
    time_order: Mapped[int | None] = mapped_column(Integer)
    collection_time: Mapped[datetime | None] = mapped_column(DateTime)

    review_status: Mapped[str] = mapped_column(String(30), default="通过")
    review_note: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(String(255))
    source_workbook: Mapped[str | None] = mapped_column(String(255))
    duplicate_resolution: Mapped[str | None] = mapped_column(String(30))

    testosterone_raw: Mapped[str | None] = mapped_column(String(20))
    testosterone_value: Mapped[float | None] = mapped_column(Float)
    testosterone_qualifier: Mapped[str | None] = mapped_column(String(4))
    testosterone_below_lod: Mapped[bool] = mapped_column(Boolean, default=False)
    cortisol_ug_dL: Mapped[float | None] = mapped_column(Float)
    urea_mmol_L: Mapped[float | None] = mapped_column(Float)
    creatine_kinase_U_L: Mapped[float | None] = mapped_column(Float)
    ldh_U_L: Mapped[float | None] = mapped_column(Float)

    participant: Mapped["Participant"] = relationship(back_populates="samples")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Analyte(Base):
    """指标配置：名称、单位、参考区间（按性别分层）。"""

    __tablename__ = "analytes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # 如 creatine_kinase_U_L
    name: Mapped[str] = mapped_column(String(50))  # 如 肌酸激酶 CK
    unit: Mapped[str | None] = mapped_column(String(20))
    sample_column: Mapped[str] = mapped_column(String(40))  # samples 表对应列
    lower_male: Mapped[float | None] = mapped_column(Float)
    upper_male: Mapped[float | None] = mapped_column(Float)
    lower_female: Mapped[float | None] = mapped_column(Float)
    upper_female: Mapped[float | None] = mapped_column(Float)
    # 低于检测限是否按正常处理（如睾酮 <0.0868 视为正常低值）
    censored_is_normal: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class HrSession(Base):
    """训练心率逐人次记录（blood.db hr_sessions）。"""

    __tablename__ = "hr_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete: Mapped[str | None] = mapped_column(String(50))
    subject_id: Mapped[str | None] = mapped_column(String(20), index=True)
    datetime: Mapped[datetime | None] = mapped_column(DateTime)
    session_name: Mapped[str | None] = mapped_column(String(50))
    coach: Mapped[str | None] = mapped_column(String(20))
    session_type: Mapped[str | None] = mapped_column(String(20))
    duration_min: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[float | None] = mapped_column(Float)
    max_hr: Mapped[float | None] = mapped_column(Float)
    cal: Mapped[float | None] = mapped_column(Float)
    z1: Mapped[float | None] = mapped_column(Float)
    z2: Mapped[float | None] = mapped_column(Float)
    z3: Mapped[float | None] = mapped_column(Float)
    z4: Mapped[float | None] = mapped_column(Float)
    z5: Mapped[float | None] = mapped_column(Float)
    source_file: Mapped[str | None] = mapped_column(String(255))


class TrainingSession(Base):
    """训练课清单（blood.db training_sessions）。"""

    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_name: Mapped[str | None] = mapped_column(String(80))
    datetime: Mapped[datetime | None] = mapped_column(DateTime)
    duration_min: Mapped[float | None] = mapped_column(Float)
    n_athletes: Mapped[int | None] = mapped_column(Integer)
    coach: Mapped[str | None] = mapped_column(String(20))
    source_file: Mapped[str | None] = mapped_column(String(255))


class TrainingEntry(Base):
    """训练成绩记录（日常训练成绩/体能数据，手动录入）。"""

    __tablename__ = "training_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str | None] = mapped_column(String(20), index=True)
    entry_date: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    session_name: Mapped[str | None] = mapped_column(String(80))
    test_type: Mapped[str | None] = mapped_column(String(50), index=True)  # 项目：500m计时/CMJ/FMS...
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(20), default="manual")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


class TrainingPlan(Base):
    """训练计划（教练排课）。"""

    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_date: Mapped[datetime | None] = mapped_column(Date, index=True)
    coach: Mapped[str | None] = mapped_column(String(20))
    session_type: Mapped[str | None] = mapped_column(String(20))  # 冰上/陆地/力量/技术/恢复
    content: Mapped[str | None] = mapped_column(String(255))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    intensity: Mapped[str | None] = mapped_column(String(10))  # 低/中/高
    status: Mapped[str | None] = mapped_column(String(10), default="计划")  # 计划/已执行/取消
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


class DailyStatus(Base):
    """运动员每日状态上报。"""

    __tablename__ = "daily_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str | None] = mapped_column(String(20), index=True)
    status_date: Mapped[datetime | None] = mapped_column(Date, index=True)
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    fatigue: Mapped[int | None] = mapped_column(Integer)  # 1-10
    morning_hr: Mapped[int | None] = mapped_column(Integer)  # 晨脉
    weight_kg: Mapped[float | None] = mapped_column(Float)
    muscle_soreness: Mapped[int | None] = mapped_column(Integer)  # 1-10
    injury: Mapped[str | None] = mapped_column(String(50))  # 无/轻/中/重:部位
    self_rating: Mapped[int | None] = mapped_column(Integer)  # 1-10 训练自评
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


class InjuryRecord(Base):
    """伤病记录（第三级：伤病录入）。"""

    __tablename__ = "injury_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str | None] = mapped_column(String(20), index=True)
    injury_date: Mapped[datetime | None] = mapped_column(Date, index=True)
    part: Mapped[str | None] = mapped_column(String(50))  # 部位：膝/踝/腰/肩...
    injury_level: Mapped[str | None] = mapped_column(String(10))  # 轻/中/重
    diagnosis: Mapped[str | None] = mapped_column(String(100))  # 诊断/描述
    status: Mapped[str | None] = mapped_column(String(10), default="治疗中")  # 治疗中/康复中/已恢复
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)


class CpetTest(Base):
    """心肺运动试验 CPET（blood.db cpet_tests）。"""

    __tablename__ = "cpet_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[int | None] = mapped_column(Integer, index=True)
    file: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(50))
    subject_id: Mapped[str | None] = mapped_column(String(20), index=True)
    gender: Mapped[str | None] = mapped_column(String(10))
    age_years: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    test_start: Mapped[datetime | None] = mapped_column(DateTime)
    device: Mapped[str | None] = mapped_column(String(50))
    duration_s: Mapped[float | None] = mapped_column(Float)
    valid_class: Mapped[str | None] = mapped_column(String(50))
    vo2kg_peak: Mapped[float | None] = mapped_column(Float)
    vo2kg_norm: Mapped[float | None] = mapped_column(Float)
    vo2kg_pctnorm: Mapped[float | None] = mapped_column(Float)
    vo2_peak: Mapped[float | None] = mapped_column(Float)
    vo2_maxabs: Mapped[float | None] = mapped_column(Float)
    hr_peak: Mapped[float | None] = mapped_column(Float)
    rer_peak: Mapped[float | None] = mapped_column(Float)
    ve_peak: Mapped[float | None] = mapped_column(Float)
    slope_ve_vco2: Mapped[float | None] = mapped_column(Float)
    vo2kg_vt1: Mapped[float | None] = mapped_column(Float)
    vo2kg_vt1_pctmax: Mapped[float | None] = mapped_column(Float)
    peak_wr: Mapped[float | None] = mapped_column(Float)
    exercise_dur_s: Mapped[float | None] = mapped_column(Float)
    meas_max_vo2kg: Mapped[float | None] = mapped_column(Float)
    meas_max_rer: Mapped[float | None] = mapped_column(Float)
    meas_max_hr: Mapped[float | None] = mapped_column(Float)
    plateau_delta: Mapped[float | None] = mapped_column(Float)


class Pretest(Base):
    """前测体能（blood.db pretest）：FMS/YBT/CMJ/血乳酸/COP。"""

    __tablename__ = "pretest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(50))
    subject_id: Mapped[str | None] = mapped_column(String(20), index=True)
    profile_class: Mapped[str | None] = mapped_column(String(20))
    profile_gender: Mapped[str | None] = mapped_column(String(10))
    profile_coach: Mapped[str | None] = mapped_column(String(50))
    profile_age: Mapped[float | None] = mapped_column(Float)
    profile_height_cm: Mapped[float | None] = mapped_column(Float)
    profile_weight_kg: Mapped[float | None] = mapped_column(Float)
    profile_bmi: Mapped[float | None] = mapped_column(Float)
    fms_total: Mapped[float | None] = mapped_column(Float)
    ybt_left_ant: Mapped[float | None] = mapped_column(Float)
    ybt_left_post_med: Mapped[float | None] = mapped_column(Float)
    ybt_left_post_lat: Mapped[float | None] = mapped_column(Float)
    ybt_right_ant: Mapped[float | None] = mapped_column(Float)
    ybt_right_post_med: Mapped[float | None] = mapped_column(Float)
    ybt_right_post_lat: Mapped[float | None] = mapped_column(Float)
    ybt_heel_raise_l: Mapped[float | None] = mapped_column(Float)
    ybt_heel_raise_r: Mapped[float | None] = mapped_column(Float)
    ybt_eyes_closed_l: Mapped[float | None] = mapped_column(Float)
    ybt_eyes_closed_r: Mapped[float | None] = mapped_column(Float)
    rom_ankle_dorsi_l: Mapped[float | None] = mapped_column(Float)
    rom_ankle_dorsi_r: Mapped[float | None] = mapped_column(Float)
    jump_single_r: Mapped[float | None] = mapped_column(Float)
    jump_single_l: Mapped[float | None] = mapped_column(Float)
    jump_triple_r: Mapped[float | None] = mapped_column(Float)
    jump_triple_l: Mapped[float | None] = mapped_column(Float)
    cmj_height_cm: Mapped[float | None] = mapped_column(Float)
    lactate_pre: Mapped[float | None] = mapped_column(Float)
    lactate_post0: Mapped[float | None] = mapped_column(Float)
    lactate_post3: Mapped[float | None] = mapped_column(Float)
    lactate_post5: Mapped[float | None] = mapped_column(Float)
    lactate_post10: Mapped[float | None] = mapped_column(Float)
    cop_left_ellipse_area: Mapped[float | None] = mapped_column(Float)
    cop_right_ellipse_area: Mapped[float | None] = mapped_column(Float)


class AcuteFatigue(Base):
    """急性疲劳监测（blood.db acute_fatigue）。"""

    __tablename__ = "acute_fatigue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(50))
    load_pct: Mapped[float | None] = mapped_column(Float)
    intervention: Mapped[str | None] = mapped_column(String(30))
    avg_power_w: Mapped[float | None] = mapped_column(Float)
    peak_power_w: Mapped[float | None] = mapped_column(Float)
    cmj_pre: Mapped[float | None] = mapped_column(Float)
    cmj_24h: Mapped[float | None] = mapped_column(Float)
    cmj_72h: Mapped[float | None] = mapped_column(Float)
    vas_rest: Mapped[float | None] = mapped_column(Float)
    vas_post: Mapped[float | None] = mapped_column(Float)
    vas_interv: Mapped[float | None] = mapped_column(Float)
    vas_24h: Mapped[float | None] = mapped_column(Float)
    vas_72h: Mapped[float | None] = mapped_column(Float)
    rpe_rest: Mapped[float | None] = mapped_column(Float)
    rpe_post: Mapped[float | None] = mapped_column(Float)
    rpe_interv: Mapped[float | None] = mapped_column(Float)
    rpe_24h: Mapped[float | None] = mapped_column(Float)
    rpe_72h: Mapped[float | None] = mapped_column(Float)
    lactate_rest: Mapped[float | None] = mapped_column(Float)
    lactate_post: Mapped[float | None] = mapped_column(Float)
    lactate_interv: Mapped[float | None] = mapped_column(Float)
    hr_rest_avg: Mapped[float | None] = mapped_column(Float)
    hr_rest_max: Mapped[float | None] = mapped_column(Float)
    hr_post_avg: Mapped[float | None] = mapped_column(Float)
    hr_post_max: Mapped[float | None] = mapped_column(Float)
    hr_24h_avg: Mapped[float | None] = mapped_column(Float)
    hr_72h_avg: Mapped[float | None] = mapped_column(Float)
    hrv_sdnn: Mapped[float | None] = mapped_column(Float)
    hrv_rmssd: Mapped[float | None] = mapped_column(Float)
    hrv_lf_hf: Mapped[float | None] = mapped_column(Float)
    hrv_total_power: Mapped[float | None] = mapped_column(Float)


class Survey(Base):
    """心理问卷发放实例（教练发放，运动员填写）。"""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(20), default="all")  # all/group/participant
    target_value: Mapped[str | None] = mapped_column(String(50))
    assign_date: Mapped[datetime | None] = mapped_column(Date)
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SurveyItem(Base):
    """问卷题目（量表单选题或开放文本）。"""

    __tablename__ = "survey_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(Integer, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    question_text: Mapped[str] = mapped_column(String(200))
    question_type: Mapped[str] = mapped_column(String(20), default="scale")  # scale/text
    min_value: Mapped[int | None] = mapped_column(Integer)
    max_value: Mapped[int | None] = mapped_column(Integer)


class SurveyAnswer(Base):
    """问卷回答记录。"""

    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(Integer, index=True)
    item_id: Mapped[int] = mapped_column(Integer)
    athlete_id: Mapped[str] = mapped_column(String(20), index=True)
    answer_value: Mapped[float | None] = mapped_column(Float)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# =============================================================================
# Phase 1 科研数据模型（PRD_PHASE1_RESEARCH_DATA_FOUNDATION.md 第 7 节）
# 正式分析数据源为 Observation 长表；samples 宽表保留给 legacy 功能，不再扩展。
# =============================================================================


class ResearchProject(Base):
    """科研项目：数据隔离单元。归档后只读，不允许新增数据（FR-01）。"""

    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)  # 用于数据版本号 project-slug/...
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(50))
    study_design: Mapped[str | None] = mapped_column(String(50))  # 如 pre-post / parallel / crossover
    start_date: Mapped[datetime | None] = mapped_column(Date)
    end_date: Mapped[datetime | None] = mapped_column(Date)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    participants: Mapped[list["Participant"]] = relationship(back_populates="project")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class MeasureDefinition(Base):
    """数据字典（指标定义）：名称、单位、参考区间（含来源/适用人群/版本）、LOD 规则、换算。

    参考区间元数据（reference_source/reference_population/reference_version）为必填理念：
    区间数值必须可追溯到来源与版本日期（PRD 第 8 节）。
    """

    __tablename__ = "measure_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # 如 testosterone_nmol_L
    name_zh: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str | None] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(30), default="blood")  # blood / body_composition / performance
    canonical_unit: Mapped[str] = mapped_column(String(20))
    value_type: Mapped[str] = mapped_column(String(10), default="numeric")  # numeric / text
    decimal_places: Mapped[int] = mapped_column(Integer, default=2)

    # 合理范围（数据质量规则用）
    valid_min: Mapped[float | None] = mapped_column(Float)
    valid_max: Mapped[float | None] = mapped_column(Float)

    # 参考区间（按性别分层）
    reference_lower_male: Mapped[float | None] = mapped_column(Float)
    reference_upper_male: Mapped[float | None] = mapped_column(Float)
    reference_lower_female: Mapped[float | None] = mapped_column(Float)
    reference_upper_female: Mapped[float | None] = mapped_column(Float)
    reference_source: Mapped[str | None] = mapped_column(String(120))  # 来源，如"现有校准数据/教练组"
    reference_population: Mapped[str | None] = mapped_column(String(80))  # 适用人群
    reference_version: Mapped[str | None] = mapped_column(String(20))  # 版本日期 YYYY-MM-DD

    # 检测下限与规则（censored_is_normal：低于 LOD 视为正常低值，不参与数值统计）
    lod_value: Mapped[float | None] = mapped_column(Float)
    lod_rule: Mapped[str | None] = mapped_column(String(20))  # censored_is_normal / censored_exclude / none

    # 允许单位与换算系数（JSON：{"nmol/L": 1.0, "ng/dL": 0.288432}，基准为标准单位）
    unit_conversions: Mapped[dict | None] = mapped_column(JSON)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    definition_version: Mapped[str | None] = mapped_column(String(20))  # 字典版本号
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Observation(Base):
    """观测长表：正式分析数据源。每行 = (项目, 参与者, 指标, 时间点) 的一次观测。

    数据原则（PRD 7.2）：
    - 所有单位在写入前转换为标准单位（unit_canonical）；
    - 低于检测限的值保留 qualifier 与原始文本（value_text），不参与数值统计；
    - 每行可追溯到来源批次（source_batch_id）与源文件行（source_row）。
    """

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("research_projects.id", name="fk_observations_project_id"),
        nullable=True, index=True,
    )
    participant_code: Mapped[str] = mapped_column(String(20), index=True)  # 关联键用编码，非姓名
    measure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("measure_definitions.id", name="fk_observations_measure_id"), index=True
    )
    observed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    timepoint_code: Mapped[str | None] = mapped_column(String(10), index=True)  # BL / 24H / 72H ...

    value_numeric: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(40))  # 原始文本（如 "<0.0868"）
    qualifier: Mapped[str | None] = mapped_column(String(4))  # < / > / =（None 表示正常值）
    unit_original: Mapped[str | None] = mapped_column(String(20))
    unit_canonical: Mapped[str | None] = mapped_column(String(20))

    source_batch_id: Mapped[int | None] = mapped_column(Integer, index=True)  # 导入批次（ImportBatch，M2 建表）
    source_row: Mapped[int | None] = mapped_column(Integer)

    qc_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/validated/corrected/excluded
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

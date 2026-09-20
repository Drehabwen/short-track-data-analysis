# -*- coding: utf-8 -*-
"""数据字典种子：Phase 1 首批 11 项指标（血液 5 项 + 体成分 6 项占位）。

参考区间沿用现有校准数据（来源占位，见 docs/PRD_CONFIRMED_DECISIONS.md 决策 6）；
体成分指标只有字典定义（数值待设备样例灌入，决策 2）。

用法：
    cd backend
    .\\venv\\Scripts\\python -m scripts.seed_measures     # upsert，幂等可重复执行
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import MeasureDefinition  # noqa: E402

# 来源元数据（决策 6：沿用现有区间 + 来源占位；版本日期 = 录入日）
SOURCE = "现有校准数据/教练组"
POPULATION = "青少年短道速滑运动员"
REF_VERSION = "2026-08-17"
DEF_VERSION = "1.0"

# (code, name_zh, name_en, category, unit, decimals, valid_min, valid_max,
#  lo_m, hi_m, lo_f, hi_f, lod, lod_rule, unit_conversions)
MEASURES = [
    # ---- 血液指标（参考区间来自 init_db SEED_ANALYTES）----
    ("testosterone_nmol_L", "睾酮", "Testosterone", "blood", "nmol/L", 4,
     None, None, 0.5, 27.0, 0.1, 2.0,
     0.0868, "censored_is_normal", {"nmol/L": 1.0, "ng/dL": 0.03467}),
    ("cortisol_ug_dL", "皮质醇", "Cortisol", "blood", "μg/dL", 2,
     None, None, 5.0, 23.0, 5.0, 23.0,
     None, "none", {"μg/dL": 1.0}),
    ("urea_mmol_L", "尿素", "Urea", "blood", "mmol/L", 2,
     None, None, 2.5, 7.1, 2.5, 7.1,
     None, "none", {"mmol/L": 1.0}),
    ("creatine_kinase_U_L", "肌酸激酶 CK", "Creatine Kinase", "blood", "U/L", 2,
     None, None, 24.0, 200.0, 24.0, 170.0,
     None, "none", {"U/L": 1.0}),
    ("ldh_U_L", "乳酸脱氢酶 LDH", "Lactate Dehydrogenase", "blood", "U/L", 2,
     None, None, 120.0, 250.0, 120.0, 250.0,
     None, "none", {"U/L": 1.0}),
    # ---- 体成分指标（字典占位，无参考区间；数值待设备样例灌入）----
    ("height_cm", "身高", "Height", "body_composition", "cm", 1,
     100.0, 230.0, None, None, None, None,
     None, "none", {"cm": 1.0}),
    ("weight_kg", "体重", "Weight", "body_composition", "kg", 1,
     30.0, 200.0, None, None, None, None,
     None, "none", {"kg": 1.0}),
    ("bmi_kg_m2", "BMI", "Body Mass Index", "body_composition", "kg/m²", 1,
     10.0, 60.0, None, None, None, None,
     None, "none", {"kg/m²": 1.0}),
    ("body_fat_pct", "体脂率", "Body Fat Percentage", "body_composition", "%", 1,
     3.0, 60.0, None, None, None, None,
     None, "none", {"%": 1.0}),
    ("skeletal_muscle_kg", "骨骼肌量", "Skeletal Muscle Mass", "body_composition", "kg", 1,
     10.0, 100.0, None, None, None, None,
     None, "none", {"kg": 1.0}),
    ("fat_free_mass_kg", "去脂体重", "Fat-Free Mass", "body_composition", "kg", 1,
     20.0, 150.0, None, None, None, None,
     None, "none", {"kg": 1.0}),
]


def seed_measures(db) -> int:
    """按 code upsert 数据字典；返回新增条数。"""
    created = 0
    for (code, name_zh, name_en, category, unit, decimals,
         valid_min, valid_max, lo_m, hi_m, lo_f, hi_f,
         lod, lod_rule, conversions) in MEASURES:
        row = db.query(MeasureDefinition).filter(MeasureDefinition.code == code).first()
        fields = dict(
            name_zh=name_zh, name_en=name_en, category=category,
            canonical_unit=unit, value_type="numeric", decimal_places=decimals,
            valid_min=valid_min, valid_max=valid_max,
            reference_lower_male=lo_m, reference_upper_male=hi_m,
            reference_lower_female=lo_f, reference_upper_female=hi_f,
            reference_source=SOURCE, reference_population=POPULATION,
            reference_version=REF_VERSION,
            lod_value=lod, lod_rule=lod_rule,
            unit_conversions=conversions,
            enabled=True, definition_version=DEF_VERSION,
        )
        if row is None:
            db.add(MeasureDefinition(code=code, sort_order=len(MEASURES), **fields))
            created += 1
        else:
            for k, v in fields.items():
                setattr(row, k, v)
    db.commit()
    return created


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_measures(db)
        total = db.query(MeasureDefinition).count()
        print(f"数据字典种子完成：新增 {n} 条，当前共 {total} 条指标定义")
    finally:
        db.close()

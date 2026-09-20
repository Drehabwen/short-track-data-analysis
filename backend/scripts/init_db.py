# -*- coding: utf-8 -*-
"""数据库初始化：建表 + 导入种子数据（校准 CSV + 示例账号 + 指标参考区间）。
用法：python -m scripts.init_db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password  # noqa: E402
from app.config import ROOT_DIR  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Analyte, Participant, Sample, User  # noqa: F401, E402
from app.services.importer import import_visits_csv  # noqa: E402

# 指标参考区间（青少年运动员，按性别分层；可在系统管理中调整）
SEED_ANALYTES = [
    # code, name, unit, sample_column, lower_male, upper_male, lower_female, upper_female, censored_is_normal, enabled, sort
    ("testosterone_value", "睾酮", "nmol/L", "testosterone_value", 0.5, 27.0, 0.1, 2.0, True, True, 1),
    ("cortisol_ug_dL", "皮质醇", "μg/dL", "cortisol_ug_dL", 5.0, 23.0, 5.0, 23.0, False, True, 2),
    ("urea_mmol_L", "血尿素", "mmol/L", "urea_mmol_L", 2.5, 7.1, 2.5, 7.1, False, True, 3),
    ("creatine_kinase_U_L", "肌酸激酶 CK", "U/L", "creatine_kinase_U_L", 24.0, 200.0, 24.0, 170.0, False, True, 4),
    ("ldh_U_L", "乳酸脱氢酶 LDH", "U/L", "ldh_U_L", 120.0, 250.0, 120.0, 250.0, False, True, 5),
    # 预留指标（无数据，默认停用，后续录入数据后启用）
    ("rbc", "红细胞", "10^12/L", "rbc", 4.3, 5.9, 3.8, 5.1, False, False, 6),
    ("hemoglobin", "血红蛋白", "g/L", "hemoglobin", 130, 175, 115, 150, False, False, 7),
    ("hematocrit", "血细胞比容", "%", "hematocrit", 40, 50, 35, 45, False, False, 8),
    ("serum_iron", "血清铁", "μmol/L", "serum_iron", 11, 32, 9, 30, False, False, 9),
    ("ferritin", "铁蛋白", "μg/L", "ferritin", 30, 400, 12, 150, False, False, 10),
]

# 示例账号：admin / coach / athlete123
SEED_USERS = [
    ("admin", "admin123", "admin", "系统管理员", None),
    ("coach", "coach123", "coach", "主教练", None),
    ("athlete", "athlete123", "athlete", "运动员示例", "Z05"),
]


def seed_users(db):
    created = 0
    for username, password, role, display_name, athlete_id in SEED_USERS:
        if not db.query(User).filter(User.username == username).first():
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    display_name=display_name,
                    athlete_id=athlete_id,
                )
            )
            created += 1
    db.commit()
    return created


def seed_analytes(db):
    created = 0
    for code, name, unit, col, lm, um, lf, uf, censored, enabled, sort in SEED_ANALYTES:
        if not db.query(Analyte).filter(Analyte.code == code).first():
            db.add(
                Analyte(
                    code=code,
                    name=name,
                    unit=unit,
                    sample_column=col,
                    lower_male=lm,
                    upper_male=um,
                    lower_female=lf,
                    upper_female=uf,
                    censored_is_normal=censored,
                    enabled=enabled,
                    sort_order=sort,
                )
            )
            created += 1
    db.commit()
    return created


def main():
    print("创建数据表...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        u = seed_users(db)
        a = seed_analytes(db)
    finally:
        db.close()
    print(f"示例账号: 新建 {u}，指标配置: 新建 {a}")

    print("导入种子数据...")
    result = import_visits_csv()
    print(
        f"完成: 新建运动员 {result['participants_created']}, "
        f"新建血样 {result['samples_created']}, 跳过重复 {result['skipped']}"
    )
    if result["errors"]:
        print("警告:", result["errors"][:5])


if __name__ == "__main__":
    main()

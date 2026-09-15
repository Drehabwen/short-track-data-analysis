# -*- coding: utf-8 -*-
"""数据库查询层：常用科研/周报查询，返回 DataFrame。

用法：
    import db_queries as q
    df = q.athlete_card("示例运动员")      # 单个运动员全景
    df = q.week_summary("2026-08-04", "2026-08-07")   # 某周训练负荷
    df = q.coach_compare("2026-07-28", "2026-08-07")  # 两周教练对比
"""

import os
import sqlite3

import pandas as pd

DB = r"D:\DEV\blood\blood.db"


def _q(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def athlete_card(name):
    """单名运动员：档案 + 心率记录 + CPET 全部测试 + 血液指标 + 前测。"""
    sql = """
    SELECT a.subject_id, a.name, a.class, a.coach, a.gender, a.age,
           a.height_cm, a.weight_kg, a.intervention, a.unregistered
    FROM athletes a WHERE a.name = ?;
    """
    base = _q(sql, (name,))
    if base.empty:
        return None
    sid = base.iloc[0]["subject_id"]
    hr = _q("SELECT * FROM hr_sessions WHERE subject_id=? ORDER BY datetime",
            (sid,))
    cp = _q("SELECT * FROM cpet_tests WHERE subject_id=? ORDER BY test_start",
            (sid,))
    bl = _q("SELECT * FROM blood_markers WHERE subject_id=? ORDER BY timepoint",
            (sid,))
    pt = _q("SELECT * FROM pretest WHERE subject_id=?", (sid,))
    return {"profile": base, "hr": hr, "cpet": cp, "blood": bl, "pretest": pt}


def week_summary(d0, d1):
    """某时间段训练负荷汇总（人次、人数、均心、高强度占比、TRIMP 近似）。"""
    return _q(
        """
        SELECT date(datetime) AS date, session_name, coach, session_type,
               COUNT(*) AS n, ROUND(AVG(avg_hr),1) AS avg_hr,
               MAX(max_hr) AS max_hr, ROUND(AVG(z4+z5),1) AS z45_pct,
               ROUND(AVG(duration_min),1) AS dur_min
        FROM hr_sessions
        WHERE date(datetime) BETWEEN ? AND ?
        GROUP BY date(datetime), session_name
        ORDER BY date(datetime), datetime;
        """, (d0, d1))


def coach_compare(d0, d1):
    """按教练汇总某时间段监测场次与强度。"""
    return _q(
        """
        SELECT coach, COUNT(DISTINCT session_name) AS sessions,
               COUNT(*) AS rows, COUNT(DISTINCT athlete) AS athletes,
               ROUND(AVG(avg_hr),1) AS avg_hr,
               ROUND(AVG(z4+z5),1) AS z45_pct,
               ROUND(AVG(duration_min),1) AS avg_dur_min
        FROM hr_sessions
        WHERE date(datetime) BETWEEN ? AND ?
          AND coach IS NOT NULL
        GROUP BY coach ORDER BY avg_hr DESC;
        """, (d0, d1))


def cpet_best_per_athlete(valid_only=False):
    """每人最优 CPET（有效优先、其次亚极量，同效取 VO2/kg 最高）。"""
    cond = "WHERE valid_class LIKE '有效%'" if valid_only else ""
    return _q(
        f"""
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY name
            ORDER BY CASE WHEN valid_class LIKE '有效%' THEN 0
                          WHEN valid_class LIKE '亚极量%' THEN 1 ELSE 2 END,
                    vo2kg_peak DESC) AS rn
          FROM cpet_tests {cond}
        )
        SELECT name, gender, age_years, height_cm, weight_kg, test_start,
               valid_class, vo2kg_peak, vo2kg_pctnorm, slope_ve_vco2,
               rer_peak, hr_peak, vo2kg_vt1_pctmax, peak_wr
        FROM ranked WHERE rn=1
        ORDER BY vo2kg_peak DESC;
        """)


def blood_panel(analyte=None):
    """血液指标长表透视（可选按 analyte 过滤）。"""
    cond = "WHERE analyte=?" if analyte else ""
    params = (analyte,) if analyte else ()
    return _q(
        f"""
        SELECT b.athlete, b.timepoint, b.analyte, b.result_value, b.unit,
               a.coach, a.intervention, a.gender
        FROM blood_markers b LEFT JOIN athletes a ON a.subject_id=b.subject_id
        {cond}
        ORDER BY b.athlete, b.timepoint;
        """, params)


def data_coverage():
    """各表行数与关联情况一览。"""
    return _q(
        """
        SELECT 'athletes' AS tbl, COUNT(*) AS n FROM athletes
        UNION ALL SELECT 'hr_sessions', COUNT(*) FROM hr_sessions
        UNION ALL SELECT 'cpet_tests', COUNT(*) FROM cpet_tests
        UNION ALL SELECT 'blood_markers', COUNT(*) FROM blood_markers
        UNION ALL SELECT 'pretest', COUNT(*) FROM pretest
        UNION ALL SELECT 'training_sessions', COUNT(*) FROM training_sessions;
        """)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("== 数据覆盖 ==")
    print(data_coverage().to_string(index=False))
    print("\n== 本周(08-04~08-07)训练课 ==")
    print(week_summary("2026-08-04", "2026-08-07").to_string(index=False))
    print("\n== 每人最优 CPET TOP10 ==")
    print(cpet_best_per_athlete().head(10).to_string(index=False))
    print("\n== 示例运动员档案 ==")
    card = athlete_card("示例运动员")
    if card:
        print("CPET 测试:", len(card["cpet"]), "份 | HR 记录:", len(card["hr"]),
              "条 | 血液:", len(card["blood"]), "条")

# -*- coding: utf-8 -*-
"""七台河短道速滑训练基地 · 科研数据库构建脚本

数据源（均为清洗后的 CSV，作为数据库的单一事实来源）：
  1. 运动员主表      统一数据集/统一数据集_受试者主表.csv      (77 人)
  2. 心率逐人次记录   心率/hr_sessions.csv + 心率场次清单_全量.csv
  3. CPET 测试       最大摄氧量/最大摄氧量数据/cpet_enriched.csv (66 份)
  4. 血液指标(长表)  统一数据集/血液明细表_链接后.csv          (810 条)
  5. 前测/体能测量    统一数据集/前测明细表.csv                (89 行)
  6. 训练课清单      心率/心率场次清单_全量.csv
  7. 周报统计快照    最大摄氧量/hr_2wk.json

输出：blood.db（SQLite），表前缀见 SCHEMA。可用 sqlite3 / pandas / 任何 BI 工具读取。
"""

import json
import glob
import os
import sqlite3

import pandas as pd

ROOT = r"D:\DEV\blood"
DB_PATH = os.path.join(ROOT, "blood.db")

# HR 姓名 -> 主表规范名
HR_ALIAS = {}
SKIP_NAMES = {"七台河短道速滑队", "访客1", "访客2", "访客3", "访客4", "姓名"}
CPET_ALIAS = {}


def canon_hr(name):
    name = str(name).strip()
    return HR_ALIAS.get(name, name)


def canon_cpet(name):
    name = str(name).strip()
    return CPET_ALIAS.get(name, name)


def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def drop_all(con):
    cur = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    for (t,) in cur.fetchall():
        con.execute(f'DROP TABLE IF EXISTS "{t}"')
    con.commit()


def build_schema(con):
    con.executescript(
        """
        CREATE TABLE athletes (
            subject_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            name_aliases TEXT,
            class        TEXT,          -- 班级
            coach        TEXT,          -- 主管教练
            gender       TEXT,
            age          REAL,
            dob          TEXT,          -- 出生年月（来自 CPET 档案）
            height_cm    REAL,
            weight_kg    REAL,
            intervention TEXT,          -- 干预分组（艾灸+推拿/拔罐+推拿/常规恢复）
            unregistered INTEGER DEFAULT 0   -- 1=主表未收录、由 HR/CPET 数据自动补录
        );

        CREATE TABLE hr_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete      TEXT NOT NULL,
            subject_id   TEXT,
            datetime     TEXT NOT NULL,
            session_name TEXT,
            coach        TEXT,
            session_type TEXT,          -- 冰上/陆地/其他
            duration_min REAL,
            avg_hr       REAL,
            max_hr       REAL,
            cal          REAL,
            z1 REAL, z2 REAL, z3 REAL, z4 REAL, z5 REAL,
            source_file  TEXT,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );
        CREATE INDEX idx_hr_athlete ON hr_sessions(athlete);
        CREATE INDEX idx_hr_datetime ON hr_sessions(datetime);

        CREATE TABLE training_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            datetime     TEXT,
            duration_min REAL,
            n_athletes   INTEGER,
            coach        TEXT,
            source_file  TEXT
        );
        CREATE INDEX idx_ts_name ON training_sessions(session_name);

        CREATE TABLE cpet_tests (
            test_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            file            TEXT,
            name            TEXT NOT NULL,
            subject_id      TEXT,
            gender          TEXT,
            age_years       REAL,
            height_cm       REAL,
            weight_kg       REAL,
            bmi             REAL,
            test_start      TEXT,
            device          TEXT,
            duration_s      REAL,
            valid_class     TEXT,       -- 有效/亚极量/无效
            vo2kg_peak      REAL,
            vo2kg_norm      REAL,
            vo2kg_pctnorm   REAL,
            vo2_peak        REAL,
            vo2_maxabs      REAL,
            hr_peak         REAL,
            rer_peak        REAL,
            ve_peak         REAL,
            slope_ve_vco2   REAL,
            vo2kg_vt1       REAL,
            vo2kg_vt1_pctmax REAL,
            peak_wr         REAL,
            exercise_dur_s  REAL,
            meas_max_vo2kg  REAL,
            meas_max_rer    REAL,
            meas_max_hr     REAL,
            plateau_delta   REAL,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );
        CREATE INDEX idx_cpet_name ON cpet_tests(name);

        CREATE TABLE blood_markers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT,
            athlete      TEXT,
            subject_id   TEXT,
            timepoint    TEXT,          -- BL/24H/72H
            analyte      TEXT,
            result_value REAL,
            qualifier    TEXT,
            unit         TEXT,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );
        CREATE INDEX idx_blood_athlete ON blood_markers(athlete, timepoint);

        CREATE TABLE pretest (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            subject_id TEXT,
            profile_class TEXT,
            profile_gender TEXT,
            profile_coach TEXT,
            profile_age REAL,
            profile_height_cm REAL,
            profile_weight_kg REAL,
            profile_bmi REAL,
            fms_total REAL,
            ybt_left_ant REAL, ybt_left_post_med REAL, ybt_left_post_lat REAL,
            ybt_right_ant REAL, ybt_right_post_med REAL, ybt_right_post_lat REAL,
            ybt_heel_raise_l REAL, ybt_heel_raise_r REAL,
            ybt_eyes_closed_l REAL, ybt_eyes_closed_r REAL,
            rom_ankle_dorsi_l REAL, rom_ankle_dorsi_r REAL,
            jump_single_r REAL, jump_single_l REAL,
            jump_triple_r REAL, jump_triple_l REAL,
            cmj_height_cm REAL,
            lactate_pre REAL, lactate_post0 REAL, lactate_post3 REAL,
            lactate_post5 REAL, lactate_post10 REAL,
            cop_left_ellipse_area REAL, cop_right_ellipse_area REAL,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );

        CREATE TABLE acute_fatigue (
            subject_id   TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            load_pct     REAL,          -- 急性造模负荷(%)
            intervention TEXT,          -- 干预方式
            avg_power_w  REAL,          -- 5次平均功率均值
            peak_power_w REAL,          -- 5次峰值功率均值
            cmj_pre REAL, cmj_24h REAL, cmj_72h REAL,
            vas_rest REAL, vas_post REAL, vas_interv REAL, vas_24h REAL, vas_72h REAL,
            rpe_rest REAL, rpe_post REAL, rpe_interv REAL, rpe_24h REAL, rpe_72h REAL,
            lactate_rest REAL, lactate_post REAL, lactate_interv REAL,
            hr_rest_avg REAL, hr_rest_max REAL, hr_post_avg REAL, hr_post_max REAL,
            hr_24h_avg REAL, hr_72h_avg REAL,
            hrv_sdnn REAL, hrv_rmssd REAL, hrv_lf_hf REAL, hrv_total_power REAL,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );

        CREATE TABLE training_entries (
            id           TEXT PRIMARY KEY,
            entry_type   TEXT NOT NULL,   -- ice/physical/session/note
            athlete      TEXT NOT NULL,
            subject_id   TEXT,
            date         TEXT,
            coach        TEXT,
            project      TEXT,
            time_value   TEXT,
            split_text   TEXT,
            test_item    TEXT,
            value_num    REAL,
            unit         TEXT,
            contents     TEXT,            -- 逗号分隔的训练内容标签
            sets_num     INTEGER,
            rating       INTEGER,
            note         TEXT,
            created_ts   INTEGER,
            source       TEXT,
            FOREIGN KEY (subject_id) REFERENCES athletes(subject_id)
        );
        CREATE INDEX idx_te_athlete ON training_entries(athlete, date);

        CREATE TABLE meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    con.commit()


def load_athletes(con):
    df = pd.read_csv(os.path.join(ROOT, "统一数据集", "统一数据集_受试者主表.csv"),
                     encoding="utf-8-sig")
    keep = ["subject_id", "name", "name_aliases", "class", "coach", "gender",
            "age", "height_cm", "weight_kg", "intervention"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["unregistered"] = 0
    df.to_sql("athletes", con, if_exists="append", index=False)
    alias = {}
    for _, r in df.iterrows():
        alias[str(r["name"]).strip()] = str(r["subject_id"])
        if pd.notna(r.get("name_aliases")):
            for a in str(r["name_aliases"]).split(","):
                a = a.strip()
                if a:
                    alias[a] = str(r["subject_id"])
    return alias


def fill_dob(con, alias):
    """用 CPET 档案补出生日期。"""
    try:
        cpet = pd.read_csv(os.path.join(ROOT, "最大摄氧量", "最大摄氧量数据",
                                        "cpet_enriched.csv"), encoding="utf-8-sig")
        dob_map = {}
        for _, r in cpet.iterrows():
            nm = str(r.get("name", "")).strip()
            if nm and pd.notna(r.get("dob")):
                dob_map.setdefault(canon_cpet(nm), str(r["dob"])[:10])
        for nm, dob in dob_map.items():
            sid = alias.get(nm)
            if sid:
                con.execute("UPDATE athletes SET dob=? WHERE subject_id=?", (dob, sid))
        con.commit()
    except Exception as e:
        print("[警告] 出生日期补录失败:", e)


def register_missing(con, alias, names, gender_map=None):
    """把 HR/CPET 中出现但主表缺失的运动员补录进 athletes（unregistered=1）。"""
    cur = con.execute("SELECT MAX(subject_id) FROM athletes WHERE subject_id LIKE 'U%'")
    nxt = 1
    row = cur.fetchone()
    if row and row[0]:
        nxt = int(row[0][1:]) + 1
    for name in sorted(names):
        if name in alias:
            continue
        sid = f"U{nxt:03d}"
        nxt += 1
        gender = (gender_map or {}).get(name)
        con.execute(
            "INSERT INTO athletes(subject_id,name,gender,unregistered) VALUES(?,?,?,1)",
            (sid, name, gender))
        alias[name] = sid
    con.commit()
    return alias


def load_training_sessions(con):
    inv = pd.read_csv(os.path.join(ROOT, "心率", "心率场次清单_全量.csv"),
                      encoding="utf-8-sig")
    inv = inv.drop_duplicates("datetime", keep="first")
    df = pd.DataFrame({
        "session_name": inv["session"],
        "datetime": inv["datetime"],
        "duration_min": inv.get("duration"),
        "n_athletes": inv.get("n_athletes"),
        "coach": inv["session"].map(coach_of),
        "source_file": inv["file"],
    })
    # 时长字符串 mm:ss 转分钟
    def to_min(v):
        if pd.isna(v):
            return None
        p = str(v).split(":")
        try:
            return int(p[0]) + int(p[1]) / 60 if len(p) >= 2 else float(p[0])
        except (ValueError, IndexError):
            return None
    df["duration_min"] = df["duration_min"].map(to_min)
    df.to_sql("training_sessions", con, if_exists="append", index=False)
    return inv


def coach_of(name):
    name = str(name)
    if "教练D" in name or "教练F" in name:
        return "教练D组(教练F)"
    for c in ["教练C", "教练B", "教练A", "教练E"]:
        if c in name:
            return c
    return None


def load_hr(con, inv, alias):
    df = pd.read_csv(os.path.join(ROOT, "心率", "hr_sessions.csv"),
                     encoding="utf-8-sig")
    df["athlete"] = df["athlete"].map(canon_hr)
    df = df[~df["athlete"].isin(SKIP_NAMES)].copy()
    df = df.drop_duplicates(subset=["athlete", "datetime"], keep="first")
    inv2 = inv[["datetime", "session"]].drop_duplicates("datetime")
    df = df.merge(inv2, on="datetime", how="left")
    df["coach"] = df["session"].map(coach_of)
    df["subject_id"] = df["athlete"].map(alias)
    df = df.rename(columns={"session": "session_name"})
    cols = ["athlete", "subject_id", "datetime", "session_name", "coach",
            "duration_min", "avg_hr", "max_hr", "cal", "z1", "z2", "z3", "z4", "z5"]
    df = df[[c for c in cols if c in df.columns]]
    # 依据场次名推断冰上/陆地
    def stype(s):
        s = str(s)
        if "冰上" in s:
            return "冰上"
        if any(k in s for k in ("陆地", "陆上", "训练")):
            return "陆地"
        return "其他"
    df["session_type"] = df["session_name"].map(stype)
    df["source_file"] = None
    df.to_sql("hr_sessions", con, if_exists="append", index=False)


def load_cpet(con, alias):
    df = pd.read_csv(os.path.join(ROOT, "最大摄氧量", "最大摄氧量数据",
                                  "cpet_enriched.csv"), encoding="utf-8-sig")
    df["name"] = df["name"].map(canon_cpet)
    # 有效性分级（与 hr_profile.py 同一标准）
    def classify(r):
        if pd.isna(r["V'O2/kg_peak"]):
            return "无效测试(未完成运动)"
        if pd.notna(r["meas_max_rer"]) and r["meas_max_rer"] >= 1.05 \
                and pd.notna(r["exercise_dur_s"]) and r["exercise_dur_s"] >= 180:
            return "有效(达最大标准)"
        if pd.notna(r["meas_max_rer"]) and r["meas_max_rer"] >= 1.0:
            return "亚极量(接近最大)"
        if pd.notna(r["meas_max_rer"]):
            return "亚极量(RER<1.00)"
        return "无效测试(未完成运动)"
    df["valid_class"] = df.apply(classify, axis=1)
    df["subject_id"] = df["name"].map(alias)
    out = pd.DataFrame({
        "file": df.get("file"), "name": df["name"], "subject_id": df["subject_id"],
        "gender": df.get("gender"), "age_years": df.get("age_years"),
        "height_cm": df.get("height_cm"), "weight_kg": df.get("weight_kg"),
        "bmi": df.get("bmi"), "test_start": df.get("start"),
        "device": df.get("device"), "duration_s": df.get("duration_s"),
        "valid_class": df.get("valid_class"),
        "vo2kg_peak": df.get("V'O2/kg_peak"),
        "vo2kg_norm": df.get("V'O2/kg_norm"),
        "vo2kg_pctnorm": df.get("V'O2/kg_peak_pctnorm"),
        "vo2_peak": df.get("V'O2_peak"), "vo2_maxabs": df.get("V'O2_maxabs"),
        "hr_peak": df.get("HR_peak"), "rer_peak": df.get("RER_peak"),
        "ve_peak": df.get("V'E_peak"),
        "slope_ve_vco2": df.get("slope_ve_vco2"),
        "vo2kg_vt1": df.get("V'O2/kg_vt1"),
        "vo2kg_vt1_pctmax": df.get("V'O2/kg_vt1_pctmax"),
        "peak_wr": df.get("peak_wr"), "exercise_dur_s": df.get("exercise_dur_s"),
        "meas_max_vo2kg": df.get("meas_max_vo2kg"),
        "meas_max_rer": df.get("meas_max_rer"),
        "meas_max_hr": df.get("meas_max_hr"),
        "plateau_delta": df.get("plateau_delta"),
    })
    out.to_sql("cpet_tests", con, if_exists="append", index=False)


def load_blood(con, alias):
    df = pd.read_csv(os.path.join(ROOT, "统一数据集", "血液明细表_链接后.csv"),
                     encoding="utf-8-sig")
    df = df.rename(columns={"实验表姓名": "athlete"})
    df["athlete"] = df["athlete"].astype(str).str.strip()
    df["athlete"] = df["athlete"].map(canon_hr)
    df["subject_id"] = df["athlete"].map(alias)
    out = df[["participant_id", "athlete", "subject_id", "timepoint", "analyte",
              "result_value", "qualifier", "unit"]].copy()
    out["result_value"] = pd.to_numeric(out["result_value"], errors="coerce")
    out.to_sql("blood_markers", con, if_exists="append", index=False)


def load_pretest(con, alias):
    df = pd.read_csv(os.path.join(ROOT, "统一数据集", "前测明细表.csv"),
                     encoding="utf-8-sig")
    df = df.rename(columns={
        "profile_class": "profile_class", "profile_gender": "profile_gender",
        "profile_coach": "profile_coach", "profile_age": "profile_age",
        "profile_height_cm": "profile_height_cm",
        "profile_weight_kg": "profile_weight_kg", "profile_bmi": "profile_bmi",
    })
    df["subject_id"] = df["name"].map(alias)
    keep = ["name", "subject_id", "profile_class", "profile_gender",
            "profile_coach", "profile_age", "profile_height_cm",
            "profile_weight_kg", "profile_bmi", "fms_total",
            "ybt_left_ant", "ybt_left_post_med", "ybt_left_post_lat",
            "ybt_right_ant", "ybt_right_post_med", "ybt_right_post_lat",
            "ybt_heel_raise_l", "ybt_heel_raise_r",
            "ybt_eyes_closed_l", "ybt_eyes_closed_r",
            "rom_strength_ankle_dorsi_l", "rom_strength_ankle_dorsi_r",
            "jump_single_r1", "jump_single_l1",
            "jump_triple_r1", "jump_triple_l1",
            "cmj_height_cm", "lactate_pre", "lactate_post0", "lactate_post3",
            "lactate_post5", "lactate_post10",
            "cop_left_ellipse_area", "cop_right_ellipse_area"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df.rename(columns={
        "rom_strength_ankle_dorsi_l": "rom_ankle_dorsi_l",
        "rom_strength_ankle_dorsi_r": "rom_ankle_dorsi_r",
        "jump_single_r1": "jump_single_r", "jump_single_l1": "jump_single_l",
        "jump_triple_r1": "jump_triple_r", "jump_triple_l1": "jump_triple_l",
    })
    df.to_sql("pretest", con, if_exists="append", index=False)


def load_acute_fatigue(con, alias):
    """急性疲劳实验（造模+干预+恢复指标）——来自受试者主表。"""
    df = pd.read_csv(os.path.join(ROOT, "统一数据集", "统一数据集_受试者主表.csv"),
                     encoding="utf-8-sig")
    df["subject_id"] = df["subject_id"].astype(str).str.strip()
    pcols = [f"avg_power_p{i}" for i in range(1, 6)]
    pkcols = [f"peak_power_p{i}" for i in range(1, 6)]
    out = pd.DataFrame({
        "subject_id": df["subject_id"],
        "name": df["name"],
        "load_pct": pd.to_numeric(df.get("load_pct"), errors="coerce"),
        "intervention": df.get("intervention"),
        "avg_power_w": pd.to_numeric(df[pcols].apply(
            pd.to_numeric, errors="coerce").mean(axis=1), errors="coerce"),
        "peak_power_w": pd.to_numeric(df[pkcols].apply(
            pd.to_numeric, errors="coerce").mean(axis=1), errors="coerce"),
        "cmj_pre": pd.to_numeric(df.get("cmj_pre"), errors="coerce"),
        "cmj_24h": pd.to_numeric(df.get("cmj_24h"), errors="coerce"),
        "cmj_72h": pd.to_numeric(df.get("cmj_72h"), errors="coerce"),
        "vas_rest": pd.to_numeric(df.get("vas_rest"), errors="coerce"),
        "vas_post": pd.to_numeric(df.get("vas_post"), errors="coerce"),
        "vas_interv": pd.to_numeric(df.get("vas_interv"), errors="coerce"),
        "vas_24h": pd.to_numeric(df.get("vas_24h"), errors="coerce"),
        "vas_72h": pd.to_numeric(df.get("vas_72h"), errors="coerce"),
        "rpe_rest": pd.to_numeric(df.get("rpe_rest"), errors="coerce"),
        "rpe_post": pd.to_numeric(df.get("rpe_post"), errors="coerce"),
        "rpe_interv": pd.to_numeric(df.get("rpe_interv"), errors="coerce"),
        "rpe_24h": pd.to_numeric(df.get("rpe_24h"), errors="coerce"),
        "rpe_72h": pd.to_numeric(df.get("rpe_72h"), errors="coerce"),
        "lactate_rest": pd.to_numeric(df.get("lactate_rest"), errors="coerce"),
        "lactate_post": pd.to_numeric(df.get("lactate_post"), errors="coerce"),
        "lactate_interv": pd.to_numeric(df.get("lactate_interv"), errors="coerce"),
        "hr_rest_avg": pd.to_numeric(df.get("hr_rest_avg"), errors="coerce"),
        "hr_rest_max": pd.to_numeric(df.get("hr_rest_max"), errors="coerce"),
        "hr_post_avg": pd.to_numeric(df.get("hr_post_avg"), errors="coerce"),
        "hr_post_max": pd.to_numeric(df.get("hr_post_max"), errors="coerce"),
        "hr_24h_avg": pd.to_numeric(df.get("hr_24h_avg"), errors="coerce"),
        "hr_72h_avg": pd.to_numeric(df.get("hr_72h_avg"), errors="coerce"),
        "hrv_sdnn": pd.to_numeric(df.get("hrv_sdnn"), errors="coerce"),
        "hrv_rmssd": pd.to_numeric(df.get("hrv_rmssd"), errors="coerce"),
        "hrv_lf_hf": pd.to_numeric(df.get("hrv_lf_hf"), errors="coerce"),
        "hrv_total_power": pd.to_numeric(df.get("hrv_total_power"), errors="coerce"),
    })
    out = out.dropna(subset=["subject_id"]).drop_duplicates("subject_id")
    out.to_sql("acute_fatigue", con, if_exists="append", index=False)


def load_training_entries(con, alias):
    """合并训练数据录入（训练数据导出_*.json 或本地备份）。"""
    src_dir = os.path.join(ROOT, "训练数据导出")
    if not os.path.isdir(src_dir):
        return 0
    files = sorted(glob.glob(os.path.join(src_dir, "*.json")))
    n = 0
    for f in files:
        try:
            arr = json.load(open(f, encoding="utf-8-sig"))
        except Exception as e:
            print("跳过", f, e)
            continue
        for r in arr:
            if not isinstance(r, dict) or not r.get("id"):
                continue
            vals = {
                "id": str(r["id"]),
                "entry_type": r.get("type", ""),
                "athlete": str(r.get("athlete", "")).strip(),
                "subject_id": alias.get(str(r.get("athlete", "")).strip()),
                "date": r.get("date"),
                "coach": r.get("coach"),
                "project": r.get("project"),
                "time_value": r.get("time"),
                "split_text": r.get("split"),
                "test_item": r.get("test"),
                "value_num": pd.to_numeric(r.get("value"), errors="coerce") if r.get("value") not in (None, "") else None,
                "unit": r.get("unit"),
                "contents": ",".join(r.get("contents") or []),
                "sets_num": pd.to_numeric(r.get("sets"), errors="coerce") if r.get("sets") not in (None, "") else None,
                "rating": pd.to_numeric(r.get("rating"), errors="coerce") if r.get("rating") else None,
                "note": r.get("note"),
                "created_ts": r.get("ts"),
                "source": os.path.basename(f),
            }
            cur = con.execute("SELECT 1 FROM training_entries WHERE id=?", (vals["id"],))
            if cur.fetchone():
                continue
            con.execute(
                """INSERT INTO training_entries
                   (id, entry_type, athlete, subject_id, date, coach, project,
                    time_value, split_text, test_item, value_num, unit, contents,
                    sets_num, rating, note, created_ts, source)
                   VALUES (:id,:entry_type,:athlete,:subject_id,:date,:coach,:project,
                    :time_value,:split_text,:test_item,:value_num,:unit,:contents,
                    :sets_num,:rating,:note,:created_ts,:source)""", vals)
            n += 1
    con.commit()
    return n


def load_meta(con, alias):
    wk = json.load(open(os.path.join(ROOT, "最大摄氧量", "hr_2wk.json"),
                        encoding="utf-8"))
    meta = {
        "db_version": "1.0",
        "built_at": pd.Timestamp.now().isoformat(),
        "n_athletes": len(alias),
        "hr_this_week": json.dumps(wk["this"], ensure_ascii=False),
        "hr_last_week": json.dumps(wk["last"], ensure_ascii=False),
    }
    for k, v in meta.items():
        con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (k, str(v)))
    con.commit()


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = connect()
    build_schema(con)
    alias = load_athletes(con)
    fill_dob(con, alias)
    # 收集 HR/CPET/血液中出现但主表缺失的运动员，先补录（保证外键完整）
    hr = pd.read_csv(os.path.join(ROOT, "心率", "hr_sessions.csv"),
                     encoding="utf-8-sig")
    cpet = pd.read_csv(os.path.join(ROOT, "最大摄氧量", "最大摄氧量数据",
                                    "cpet_enriched.csv"), encoding="utf-8-sig")
    blood = pd.read_csv(os.path.join(ROOT, "统一数据集", "血液明细表_链接后.csv"),
                        encoding="utf-8-sig")
    missing = set(hr["athlete"].map(canon_hr)) | \
        set(cpet["name"].map(canon_cpet)) | \
        set(blood["实验表姓名"].astype(str).str.strip().map(canon_hr))
    missing.discard("nan")
    missing.discard("NaN")
    missing = {m for m in missing if isinstance(m, str) and m}
    missing -= set(alias) | SKIP_NAMES
    gender_map = {}
    if "gender" in cpet.columns:
        gender_map = {canon_cpet(r["name"]): r["gender"] for _, r in cpet.iterrows()}
    alias = register_missing(con, alias, missing, gender_map)
    inv = load_training_sessions(con)
    load_hr(con, inv, alias)
    load_cpet(con, alias)
    load_blood(con, alias)
    load_pretest(con, alias)
    load_acute_fatigue(con, alias)
    n_te = load_training_entries(con, alias)
    if n_te:
        print(f"训练数据录入合并: {n_te} 条")
    load_meta(con, alias)
    con.close()
    print("数据库已生成:", DB_PATH)
    con = connect()
    cur = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (t,) in cur.fetchall():
        cnt = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t}: {cnt} 行")
    con.close()


if __name__ == "__main__":
    main()

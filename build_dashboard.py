# -*- coding: utf-8 -*-
"""运动员画像 · 教练仪表盘（单文件 HTML）

数据源：blood.db（由 build_db.py 生成）。
产出：最大摄氧量/运动员画像仪表盘.html
"""

import json
import os
import sqlite3

import pandas as pd

from entry_component import ENTRY_HTML, ENTRY_JS

ROOT = r"D:\DEV\blood"
DB = os.path.join(ROOT, "blood.db")
OUT = os.path.join(ROOT, "最大摄氧量", "运动员画像仪表盘.html")
ECHARTS = r"D:\DEV\dashboard\echarts.min.js"

ZONE_COLORS = ["#5b8fc7", "#5fb06e", "#e0c34e", "#e58f4f", "#d05555"]


def query(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def percentile_rank(series, value, higher_better=True):
    """值在全队中的百分位（0-100）。"""
    if value is None or pd.isna(value):
        return None
    s = series.dropna()
    if s.empty:
        return None
    r = (s < value).mean() * 100
    return round(r if higher_better else 100 - r, 0)


def build_data():
    athletes = query(
        """SELECT subject_id, name, class, coach, gender, age, dob, height_cm, weight_kg,
                  intervention, unregistered
           FROM athletes ORDER BY unregistered, name""")
    hr = query(
        """SELECT subject_id, athlete, datetime, session_name, coach, session_type,
                  duration_min, avg_hr, max_hr, z1, z2, z3, z4, z5
           FROM hr_sessions ORDER BY datetime""")
    cpet = query(
        """SELECT subject_id, name, test_start, valid_class, vo2kg_peak,
                  vo2kg_pctnorm, slope_ve_vco2, vo2kg_vt1_pctmax, rer_peak, hr_peak,
                  peak_wr, exercise_dur_s
           FROM cpet_tests ORDER BY test_start""")
    blood = query(
        """SELECT subject_id, athlete, timepoint, analyte, result_value, unit
           FROM blood_markers ORDER BY timepoint""")
    pretest = query(
        """SELECT subject_id, name, profile_age, fms_total, cmj_height_cm,
                  lactate_pre, lactate_post3,
                  ybt_left_ant, ybt_left_post_med, ybt_left_post_lat,
                  ybt_right_ant, ybt_right_post_med, ybt_right_post_lat,
                  ybt_heel_raise_l, ybt_heel_raise_r,
                  ybt_eyes_closed_l, ybt_eyes_closed_r,
                  rom_ankle_dorsi_l, rom_ankle_dorsi_r,
                  jump_single_l, jump_triple_l,
                  cop_left_ellipse_area, cop_right_ellipse_area
           FROM pretest""")
    _num_cols = [c for c in pretest.columns if c not in ("subject_id", "name")]
    pretest[_num_cols] = pretest[_num_cols].apply(pd.to_numeric, errors="coerce")
    acute = query(
        """SELECT subject_id, name, load_pct, intervention,
                  avg_power_w, peak_power_w,
                  cmj_pre, cmj_24h, cmj_72h,
                  vas_rest, vas_post, vas_interv, vas_24h, vas_72h,
                  rpe_rest, rpe_post, rpe_interv, rpe_24h, rpe_72h,
                  lactate_rest, lactate_post, lactate_interv,
                  hr_rest_avg, hr_rest_max, hr_post_avg, hr_post_max,
                  hr_24h_avg, hr_72h_avg,
                  hrv_sdnn, hrv_rmssd, hrv_lf_hf, hrv_total_power
           FROM acute_fatigue""")
    train_rec = query(
        """SELECT subject_id, athlete, date, entry_type, project, time_value,
                  split_text, test_item, value_num, unit, contents, sets_num,
                  rating, note, created_ts
           FROM training_entries ORDER BY date DESC, created_ts DESC""")

    hr["date"] = pd.to_datetime(hr["datetime"]).dt.date.astype(str)
    hr["week"] = pd.to_datetime(hr["datetime"]).dt.to_period("W").astype(str)
    hr["month"] = pd.to_datetime(hr["datetime"]).dt.to_period("M").astype(str)
    # TRIMP 近似（Edwards）
    hr["trimp"] = hr.apply(
        lambda r: (r["duration_min"] or 0) * (r["z1"] * 1 + r["z2"] * 2 + r["z3"] * 3
                    + r["z4"] * 4 + r["z5"] * 5) / 100
        if pd.notna(r["duration_min"]) else None, axis=1)

    # ---- 每名运动员聚合画像 ----
    profiles = {}
    for _, a in athletes.iterrows():
        sid = a["subject_id"]
        h = hr[hr["subject_id"] == sid]
        c = cpet[cpet["subject_id"] == sid]
        b = blood[blood["subject_id"] == sid]
        pt = pretest[pretest["subject_id"] == sid]
        ac = acute[acute["subject_id"] == sid]
        tr = train_rec[train_rec["subject_id"] == sid]

        best = None
        if not c.empty:
            order = {"有效(达最大标准)": 0, "亚极量(接近最大)": 1,
                     "亚极量(RER<1.00)": 2, "无效测试(未完成运动)": 3}
            c2 = c.copy()
            c2["_o"] = c2["valid_class"].map(order).fillna(9)
            best = c2.sort_values(["_o", "vo2kg_peak"], ascending=[True, False]).iloc[0]

        # 最近 4 周周负荷
        wk = h.groupby("week").agg(
            n=("date", "count"), avg_hr=("avg_hr", "mean"),
            z45=("z4", "mean"), trimp=("trimp", "sum")).round(1).reset_index()
        wk = wk.sort_values("week")

        # 训练类型构成
        typecnt = h.groupby("session_type").size().to_dict()

        # 血液最近一次（72H 优先，其次 24H，最后 BL）
        bmark = {}
        if not b.empty:
            tp_rank = {"72H": 0, "24H": 1, "BL": 2}
            b2 = b.copy()
            b2["_o"] = b2["timepoint"].map(tp_rank).fillna(9)
            b2 = b2.sort_values("_o")
            for _, r in b2.iterrows():
                bmark.setdefault(r["analyte"], {
                    "value": None if pd.isna(r["result_value"]) else round(float(r["result_value"]), 1),
                    "unit": r["unit"], "timepoint": r["timepoint"]})

        profiles[sid] = {
            "name": a["name"], "coach": a["coach"], "class": a["class"],
            "gender": a["gender"], "age": a["age"], "height": a["height_cm"],
            "weight": a["weight_kg"], "intervention": a["intervention"],
            "unregistered": int(a["unregistered"] or 0),
            "dob": a["dob"],
            "hr": {
                "n_sessions": int(len(h)),
                "n_ice": int((h["session_type"] == "冰上").sum()),
                "n_land": int((h["session_type"] == "陆地").sum()),
                "avg_hr": round(float(h["avg_hr"].mean()), 1) if len(h) else None,
                "max_hr": int(h["max_hr"].max()) if len(h) else None,
                "z45": round(float(h["z4"].mean() + h["z5"].mean()), 1) if len(h) else None,
                "trimp_sum": round(float(h["trimp"].sum()), 1) if len(h) else None,
                "last_date": h["date"].max() if len(h) else None,
            },
            "weeks": wk.to_dict("records"),
            "sessions": h.sort_values("datetime")[["date", "session_name", "session_type",
                                                   "avg_hr", "max_hr", "z4", "z5",
                                                   "duration_min"]].to_dict("records"),
            "cpet": (None if best is None else {
                "date": best["test_start"], "valid_class": best["valid_class"],
                "vo2kg": best["vo2kg_peak"], "pctnorm": best["vo2kg_pctnorm"],
                "slope": best["slope_ve_vco2"], "vt1_pct": best["vo2kg_vt1_pctmax"],
                "rer": best["rer_peak"], "hr_peak": best["hr_peak"],
                "wr": best["peak_wr"],
                "n_tests": int(len(c)),
            }),
            "blood": bmark,
            "blood_all": ([] if b.empty else b[["timepoint", "analyte", "result_value", "unit"]]
                          .to_dict("records")),
            "pretest": (None if pt.empty else {
                "fms": pt.iloc[0]["fms_total"], "cmj": pt.iloc[0]["cmj_height_cm"],
                "lactate_pre": pt.iloc[0]["lactate_pre"],
                "lactate_post3": pt.iloc[0]["lactate_post3"],
                "ybt_ant": (pt.iloc[0]["ybt_left_ant"] + pt.iloc[0]["ybt_right_ant"]) / 2
                    if pd.notna(pt.iloc[0]["ybt_left_ant"]) else None,
                "ybt_l_ant": pt.iloc[0]["ybt_left_ant"],
                "ybt_r_ant": pt.iloc[0]["ybt_right_ant"],
                "ybt_post_med": (pt.iloc[0]["ybt_left_post_med"] + pt.iloc[0]["ybt_right_post_med"]) / 2
                    if pd.notna(pt.iloc[0]["ybt_left_post_med"]) else None,
                "ybt_post_lat": (pt.iloc[0]["ybt_left_post_lat"] + pt.iloc[0]["ybt_right_post_lat"]) / 2
                    if pd.notna(pt.iloc[0]["ybt_left_post_lat"]) else None,
                "heel_raise": (pt.iloc[0]["ybt_heel_raise_l"] + pt.iloc[0]["ybt_heel_raise_r"]) / 2
                    if pd.notna(pt.iloc[0]["ybt_heel_raise_l"]) else None,
                "eyes_closed": (pt.iloc[0]["ybt_eyes_closed_l"] + pt.iloc[0]["ybt_eyes_closed_r"]) / 2
                    if pd.notna(pt.iloc[0]["ybt_eyes_closed_l"]) else None,
                "rom_dorsi": (pt.iloc[0]["rom_ankle_dorsi_l"] + pt.iloc[0]["rom_ankle_dorsi_r"]) / 2
                    if pd.notna(pt.iloc[0]["rom_ankle_dorsi_l"]) else None,
                "jump_single": pt.iloc[0]["jump_single_l"],
                "jump_triple": pt.iloc[0]["jump_triple_l"],
                "cop": pt.iloc[0]["cop_left_ellipse_area"],
            }),
            "acute": (None if ac.empty else {
                "intervention": ac.iloc[0]["intervention"],
                **{k: (None if pd.isna(ac.iloc[0][k])
                       else round(float(ac.iloc[0][k]), 1))
                   for k in ["load_pct", "avg_power_w", "peak_power_w",
                             "cmj_pre", "cmj_24h", "cmj_72h",
                             "vas_rest", "vas_post", "vas_24h", "vas_72h",
                             "rpe_rest", "rpe_post", "rpe_24h", "rpe_72h",
                             "lactate_rest", "lactate_post", "lactate_interv",
                             "hr_rest_avg", "hr_post_avg", "hr_24h_avg", "hr_72h_avg",
                             "hrv_sdnn", "hrv_rmssd", "hrv_lf_hf", "hrv_total_power"]}
            }),
            "train_rec": tr.to_dict("records"),
            "train": {
                "week_type": h.groupby(["week", "session_type"])["duration_min"].sum().round(1)
                    .reset_index().rename(columns={"duration_min": "dur"}).to_dict("records"),
                "week_avg": h.groupby("week").agg(
                    avg_hr=("avg_hr", "mean"), z45=("z4", "mean"),
                    trimp=("trimp", "sum")).round(1).reset_index().to_dict("records"),
                "month_type": h.groupby(["month", "session_type"])["duration_min"].sum().round(1)
                    .reset_index().rename(columns={"duration_min": "dur"}).to_dict("records"),
                "month_avg": h.groupby("month").agg(
                    avg_hr=("avg_hr", "mean"), z45=("z4", "mean"),
                    trimp=("trimp", "sum")).round(1).reset_index().to_dict("records"),
                "daily": h.groupby("date").agg(
                    trimp=("trimp", "sum"), dur=("duration_min", "sum"),
                    avg_hr=("avg_hr", "mean"), n=("date", "count")).round(1)
                    .reset_index().to_dict("records"),
                "daily_type": h.groupby(["date", "session_type"])["duration_min"].sum().round(1)
                    .reset_index().rename(columns={"duration_min": "dur"}).to_dict("records"),
            },
        }

    # ---- 全队百分位（用于雷达图） ----
    def col(key, fn):
        vals = {}
        for sid, p in profiles.items():
            v = fn(p)
            if v is not None:
                vals[sid] = v
        return vals

    vo2 = col("vo2kg", lambda p: p["cpet"]["vo2kg"] if p["cpet"] else None)
    slope = col("slope", lambda p: p["cpet"]["slope"] if p["cpet"] else None)
    vt1 = col("vt1", lambda p: p["cpet"]["vt1_pct"] if p["cpet"] else None)
    trimp = col("trimp", lambda p: p["hr"]["trimp_sum"])
    z45 = col("z45", lambda p: p["hr"]["z45"])
    nses = col("n", lambda p: p["hr"]["n_sessions"])

    for sid, p in profiles.items():
        p["score"] = {
            "有氧能力": percentile_rank(pd.Series(vo2), vo2.get(sid), True),
            "通气效率": percentile_rank(pd.Series(slope), slope.get(sid), False),
            "耐力储备": percentile_rank(pd.Series(vt1), vt1.get(sid), True),
            "训练负荷": percentile_rank(pd.Series(trimp), trimp.get(sid), True),
            "高强度占比": percentile_rank(pd.Series(z45), z45.get(sid), True),
            "监测覆盖": percentile_rank(pd.Series(nses), nses.get(sid), True),
        }
        # 前测体能指标全队百分位
        p["pre_score"] = {}
        pre_vals = {
            "fms": {}, "cmj": {}, "ybt_ant": {}, "heel": {}, "rom": {},
            "jump3": {}, "cop": {},
        }
        for s2, p2 in profiles.items():
            pt2 = p2.get("pretest")
            if not pt2:
                continue
            pre_vals["fms"][s2] = pt2.get("fms")
            pre_vals["cmj"][s2] = pt2.get("cmj")
            pre_vals["ybt_ant"][s2] = pt2.get("ybt_ant")
            pre_vals["heel"][s2] = pt2.get("heel_raise")
            pre_vals["rom"][s2] = pt2.get("rom_dorsi")
            pre_vals["jump3"][s2] = pt2.get("jump_triple")
            pre_vals["cop"][s2] = pt2.get("cop")
        for m, vals in pre_vals.items():
            v = vals.get(sid)
            p["pre_score"][m] = percentile_rank(
                pd.Series(vals), v, higher_better=(m != "cop"))
        # 教练关注标签
        tags = []
        if p["cpet"] and p["cpet"]["valid_class"].startswith("无效"):
            tags.append("CPET需复测")
        elif p["cpet"] and p["cpet"]["valid_class"].startswith("亚极量"):
            tags.append("CPET亚极量")
        if p["hr"]["z45"] is not None and p["hr"]["z45"] >= 25:
            tags.append("高强度负荷大")
        if p["hr"]["n_sessions"] == 0:
            tags.append("暂无心率数据")
        if p["blood"].get("ck") and p["blood"]["ck"]["value"] and p["blood"]["ck"]["value"] >= 500:
            tags.append("CK偏高(恢复关注)")
        p["tags"] = tags

    return {
        "athletes": athletes.to_dict("records"),
        "profiles": profiles,
        "meta": {"built_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")},
    }


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>运动员画像 · 教练仪表盘</title>
<style>
:root{
  --ink:#0b1120;            /* 深冰蓝：底色 */
  --panel:#141c2e;          /* 面板 */
  --panel2:#101828;         /* 次级面板 */
  --ice:#eef3f8;            /* 冰白：主文字 */
  --frost:#8fa2b8;          /* 霜灰：次要文字 */
  --line:#24314a;           /* 分隔线 */
  --cyan:#d64541;           /* 冰面青：强调 */
  --amber:#e6a23c;          /* 计时橙：告警/高强度 */
  --red:#e2604f;            /* 警示红 */
  --ok:#46b985;             /* 冰绿：正常 */
  --mono:'Cascadia Mono','Consolas','Courier New',monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;background:var(--ink);color:var(--ice);
  background-image:radial-gradient(1200px 500px at 80% -10%,rgba(214,69,65,.08),transparent 60%),
                   radial-gradient(900px 400px at -10% 110%,rgba(214,69,65,.05),transparent 60%);
  background-attachment:fixed}
::selection{background:rgba(214,69,65,.35)}
.top{display:flex;align-items:center;gap:16px;padding:14px 22px;position:sticky;top:0;z-index:20;
  background:rgba(11,30,45,.88);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:baseline;gap:12px}
.brand h1{font-size:18px;letter-spacing:3px;font-weight:800;color:var(--ice)}
.brand h1 em{font-style:normal;background:linear-gradient(90deg,#d64541,#e6a23c);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.brand .sub{color:var(--frost);font-size:11.5px;letter-spacing:1px}
.top .sp{flex:1}
.top input,.top select{background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  padding:7px 12px;border-radius:8px;font-size:12.5px;font-family:inherit;outline:none}
.top input:focus,.top select:focus{border-color:var(--cyan)}
.top input::placeholder{color:#5d7889}
.top .btn{background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  font-size:12.5px;padding:8px 16px;border-radius:9px;font-family:inherit;cursor:pointer;letter-spacing:1px}
.top .btn.primary{background:linear-gradient(90deg,#d64541,#b83a34);color:#fff;border-color:transparent}
.top .btn:hover{border-color:var(--cyan)}
.wrap{display:flex;min-height:calc(100vh - 56px)}
/* ---- 左侧名单：赛道栏 ---- */
.side{width:312px;background:rgba(15,38,54,.72);border-right:1px solid var(--line);
  display:flex;flex-direction:column;max-height:calc(100vh - 56px);position:sticky;top:56px}
.side .h{padding:12px 16px 8px;font-size:11.5px;letter-spacing:2px;color:var(--frost);font-weight:700;
  display:flex;justify-content:space-between}
.side .h b{color:var(--cyan);font-family:var(--mono)}
.coach-filter{display:flex;gap:6px;flex-wrap:wrap;padding:8px 14px 10px;border-bottom:1px solid var(--line)}
.cf{font-size:11px;padding:4px 11px;border-radius:20px;cursor:pointer;color:var(--frost);
  border:1px solid var(--line);background:transparent;transition:all .15s}
.cf:hover{color:var(--ice);border-color:var(--cyan)}
.cf.on{background:rgba(214,69,65,.16);color:var(--cyan);border-color:rgba(214,69,65,.5)}
#list{overflow-y:auto;flex:1}
.ath{display:flex;align-items:center;gap:9px;padding:9px 14px;cursor:pointer;
  border-bottom:1px solid rgba(30,59,79,.45);transition:background .12s;position:relative}
.ath::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:transparent}
.ath:hover{background:rgba(214,69,65,.06)}
.ath.on{background:linear-gradient(90deg,rgba(214,69,65,.16),transparent 70%)}
.ath.on::before{background:var(--cyan)}
.ath .bw{font-size:9.5px;color:#10151f;border-radius:5px;padding:1px 5px;font-weight:700;letter-spacing:.5px;flex:none}
.bw.g{background:var(--ok)} .bw.o{background:var(--amber)} .bw.r{background:#5d7889} .bw.n{background:#2a4a60;color:var(--frost)}
.ath .nm{flex:1;font-size:13.5px;font-weight:600;letter-spacing:.5px}
.ath .meta{font-size:10.5px;color:#5d7889;font-family:var(--mono)}
.ath .form{width:64px;height:20px;flex:none;opacity:.9}
.ath .form svg{width:100%;height:100%;display:block}
.dot{width:7px;height:7px;border-radius:50%;flex:none}
.tag{font-size:9.5px;background:rgba(242,169,59,.15);color:var(--amber);border-radius:8px;padding:1px 6px;white-space:nowrap}
.tag.warn{background:rgba(224,91,79,.18);color:#ff8b7f}
/* ---- 右侧数据台 ---- */
.main{flex:1;padding:20px 24px;overflow-y:auto;max-height:calc(100vh - 56px)}
.empty{color:#5d7889;padding:80px 20px;text-align:center;font-size:14px;letter-spacing:2px}
/* ---- 内嵌录入视图 ---- */
#entryView{display:none;position:fixed;inset:0;z-index:100;background:var(--ink);overflow-y:auto}
#entryView.show{display:block}
.entry-top{display:flex;align-items:center;gap:12px;padding:14px 18px;position:sticky;top:0;z-index:10;
  background:rgba(11,30,45,.94);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.entry-top h2{font-size:16px;letter-spacing:2px;font-weight:800}
.entry-top h2 em{font-style:normal;color:var(--cyan)}
.entry-top .sp{flex:1}
.entry-top .btn{background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  font-size:12.5px;padding:9px 16px;border-radius:9px;font-family:inherit;cursor:pointer}
.entry-top .btn.primary{background:linear-gradient(90deg,#d64541,#b83a34);color:#fff;border-color:transparent}
.ewrap{max-width:860px;margin:0 auto;padding:16px 16px 60px}
.selbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.selbar .fld{flex:1;min-width:180px}
.fld label{display:block;font-size:11px;color:var(--frost);letter-spacing:1px;margin-bottom:5px}
.fld input,.fld select,.fld textarea{width:100%;background:var(--panel);border:1px solid var(--line);
  color:var(--ice);border-radius:10px;padding:12px 14px;font-size:15px;font-family:inherit;outline:none}
.fld input:focus,.fld select:focus,.fld textarea:focus{border-color:var(--cyan)}
.fld input[type="date"]{color-scheme:dark}
.tabs{display:flex;gap:6px;margin-bottom:16px;overflow-x:auto;padding-bottom:4px}
.tab{flex:1;min-width:130px;text-align:center;padding:13px 8px;border-radius:10px;cursor:pointer;
  background:var(--panel2);border:1px solid var(--line);color:var(--frost);font-size:13.5px;font-weight:600;letter-spacing:1px}
.tab.on{background:rgba(214,69,65,.16);color:var(--cyan);border-color:rgba(214,69,65,.5)}
.form{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.full{grid-column:1/-1}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:13px;padding:9px 15px;border-radius:20px;background:var(--panel2);border:1px solid var(--line);
  color:var(--frost);cursor:pointer;user-select:none}
.chip.on{background:rgba(214,69,65,.16);color:var(--cyan);border-color:rgba(214,69,65,.5)}
.stars{display:flex;gap:8px;font-size:26px;cursor:pointer}
.stars span{color:#2a4a60}
.stars span.on{color:var(--amber)}
.save{width:100%;background:linear-gradient(90deg,#d64541,#b83a34);color:#fff;border:none;border-radius:12px;
  font-size:17px;font-weight:800;letter-spacing:3px;padding:15px;cursor:pointer;font-family:inherit;margin-top:4px}
.sec-title{font-size:13px;color:var(--ice);letter-spacing:2px;margin:18px 0 8px;font-weight:700}
.sec-title b{color:var(--cyan);font-family:var(--mono)}
.list{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.row{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid rgba(30,59,79,.5);font-size:13px}
.row:last-child{border-bottom:none}
.row .bd{flex:1;min-width:0}
.row .bd .t{font-weight:700;color:var(--ice)}
.row .bd .s{font-size:11px;color:var(--frost);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .del{background:transparent;border:1px solid rgba(224,91,79,.5);color:#ff8b7f;border-radius:8px;
  padding:8px 12px;font-size:12px;cursor:pointer;flex:none}
.modal{position:fixed;inset:0;background:rgba(5,15,23,.9);z-index:150;display:none;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal .box{background:var(--panel);border:1px solid var(--line);border-radius:14px;width:100%;max-width:560px;padding:18px}
.modal h3{font-size:14px;margin-bottom:10px;color:var(--ice)}
.modal textarea{width:100%;height:180px;background:var(--panel2);border:1px solid var(--line);color:var(--ice);
  border-radius:10px;padding:12px;font-size:12px;font-family:var(--mono);resize:vertical;outline:none}
.modal .row2{display:flex;gap:10px;margin-top:12px}
.modal .btn{flex:1;text-align:center;padding:11px;border-radius:10px;cursor:pointer;font-size:13.5px;font-family:inherit}
.m-ok{background:var(--cyan);color:#10151f;font-weight:700;border:none}
.m-no{background:var(--panel2);color:var(--frost);border:1px solid var(--line)}
.toast{position:fixed;left:50%;bottom:40px;transform:translateX(-50%);background:var(--ice);color:var(--ink);
  padding:11px 22px;border-radius:20px;font-size:13.5px;font-weight:700;z-index:200;opacity:0;transition:opacity .2s;pointer-events:none}
@media (max-width:560px){ .grid2{grid-template-columns:1fr} }
/* ---- 画像分区 Tab ---- */
.tabs2{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 12px;border-bottom:1px solid var(--line);padding-bottom:10px}
.tabbtn{font-size:12.5px;padding:8px 18px;border-radius:8px;cursor:pointer;color:var(--frost);
  background:var(--panel2);border:1px solid var(--line);letter-spacing:1px;font-family:inherit}
.tabbtn.on{background:rgba(214,69,65,.16);color:var(--cyan);border-color:rgba(214,69,65,.5)}
.tabpane{display:none}
.tabpane.show{display:block}
.viewbar{display:flex;gap:6px;margin-bottom:10px}
.vbtn{font-size:11px;padding:4px 13px;border-radius:14px;cursor:pointer;color:var(--frost);
  background:transparent;border:1px solid var(--line);font-family:inherit}
.vbtn.on{background:rgba(214,69,65,.16);color:var(--cyan);border-color:rgba(214,69,65,.5)}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.info-cell{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px 13px}
.info-cell .l{font-size:10.5px;color:#5d7889;letter-spacing:.5px}
.info-cell .v{font-size:16px;font-weight:700;color:var(--ice);margin-top:2px}
.info-cell .d{font-size:10px;color:var(--frost);margin-top:1px}
.ath-head{display:flex;align-items:center;gap:18px;margin-bottom:16px;flex-wrap:wrap}
.ath-head .nm{font-size:26px;font-weight:800;letter-spacing:2px;color:var(--ice)}
.ath-head .meta-line{font-size:12.5px;color:var(--frost);margin-top:3px}
.ath-head .meta-line b{color:var(--ice);font-weight:600}
.head-form{flex:1;min-width:220px;max-width:360px;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:8px 12px}
.head-form .l{font-size:10px;color:var(--frost);letter-spacing:1px;margin-bottom:2px}
.head-form .spark{height:34px}
.head-form .spark svg{width:100%;height:100%}
.head-form .cap{font-size:10px;color:#5d7889;font-family:var(--mono)}
.kpi-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);
  border-radius:8px;padding:8px 14px;font-size:11.5px;color:var(--frost);min-width:150px;flex:1}
.kpi b{display:block;font-size:19px;font-weight:800;color:var(--ice);font-family:var(--mono);margin-top:2px;letter-spacing:.5px}
.kpi.hot{border-left-color:var(--amber)}
.alert{background:rgba(242,169,59,.08);border:1px solid rgba(242,169,59,.35);border-radius:10px;
  padding:12px 16px;font-size:12.5px;color:#f7d9a8;margin-bottom:16px}
.alert b{color:var(--amber);letter-spacing:1px}
.alert ul{margin:6px 0 0 18px}
.alert li{margin:3px 0}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.card{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;position:relative;overflow:hidden}
.card::after{content:"";position:absolute;right:-20px;top:-20px;width:60px;height:60px;border-radius:50%;
  background:radial-gradient(circle,rgba(87,176,232,.12),transparent 70%)}
.card .v{font-size:23px;font-weight:800;color:var(--ice);font-family:var(--mono);letter-spacing:.5px}
.card .l{font-size:11px;color:var(--frost);margin-top:3px}
.card .d{font-size:10px;color:#5d7889;margin-top:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.box h3{font-size:13px;color:var(--ice);letter-spacing:1px;margin-bottom:4px;font-weight:700}
.box h3 small{color:#5d7889;font-weight:400;margin-left:8px;font-size:10.5px}
.full{grid-column:1 / -1}
.legend{font-size:10.5px;color:#5d7889;margin-top:8px;line-height:1.7}
.insight{background:rgba(214,69,65,.07);border-left:3px solid var(--cyan);border-radius:4px;
  padding:7px 11px;font-size:12px;color:var(--frost);line-height:1.7}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:6px 8px;border-bottom:1px solid rgba(30,59,79,.6);text-align:left}
th{color:var(--frost);font-weight:600;font-size:10.5px;letter-spacing:.5px}
td b{color:var(--ice);font-family:var(--mono)}
tr:last-child td{border-bottom:none}
.ty{display:inline-block;font-size:10px;color:#10151f;border-radius:5px;padding:1px 7px;font-weight:700}
.ty.i{background:var(--cyan)} .ty.p{background:var(--ok)} .ty.s{background:var(--amber)} .ty.n{background:#8aa4b5}
.blood{display:flex;gap:10px;flex-wrap:wrap}
.bcell{min-width:118px;background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:8px 11px}
.bcell .tp{color:#5d7889;font-size:10px;letter-spacing:.5px}
.bcell .n{font-size:17px;font-weight:800;font-family:var(--mono);color:var(--ice);margin-top:2px}
.bcell .n.hi{color:var(--red)}
.bcell .n.ok{color:var(--ok)}
.bcell .u{font-size:10px;color:#5d7889}
/* 空状态 */
.emptybox{color:#5d7889;font-size:12px;padding:26px 0;text-align:center;letter-spacing:1px}
@media (max-width:960px){
  .wrap{flex-direction:column}
  .side{max-height:none;position:static;width:100%;border-right:none;border-bottom:1px solid var(--line)}
  .main{max-height:none}
  .grid{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){
  *{transition:none!important;animation:none!important}
}
</style>
<script>__ECHARTS__</script>
</head><body>
<div class="top">
  <div class="brand">
    <h1>运动员画像<em>·</em>教练仪表盘</h1>
    <span class="sub">七台河短道速滑训练基地 · __META__</span>
  </div>
  <span class="sp"></span>
  <button class="btn primary" id="btnEntry">＋ 录入训练数据</button>
  <input id="q" placeholder="搜索运动员…">
  <select id="coachSel"><option value="">全部教练</option></select>
</div>
<div class="wrap">
  <div class="side">
    <div class="h">名单 <b id="cnt">__N__</b></div>
    <div class="coach-filter" id="cf"></div>
    <div id="list"></div>
  </div>
  <div class="main" id="main">
    <div class="empty">← 选择左侧运动员，查看训练画像</div>
  </div>
</div>
<div id="entryView">
  <div class="entry-top">
    <h2>训练数据<em>录入</em></h2>
    <span class="sp"></span>
    <button class="btn" id="btnImport">导入</button>
    <button class="btn" id="btnCopy">复制</button>
    <button class="btn primary" id="btnExport">导出</button>
    <button class="btn primary" id="btnBack">返回仪表盘</button>
  </div>
  <div class="ewrap">
    <div class="selbar">
      <div class="fld" style="flex:2">
        <label>运动员</label>
        <input id="athSearch" placeholder="搜索姓名…" autocomplete="off">
      </div>
      <div class="fld" style="flex:2">
        <label>选择</label>
        <select id="athSel"></select>
      </div>
      <div class="fld" style="flex:1">
        <label>日期</label>
        <input type="date" id="recDate">
      </div>
    </div>
    __ENTRY_HTML__
  </div>
</div>
<div class="modal" id="modal">
  <div class="box">
    <h3 id="modalTitle">导出数据</h3>
    <textarea id="modalText" readonly></textarea>
    <div class="row2">
      <button class="btn m-no" id="modalNo">关闭</button>
      <button class="btn m-ok" id="modalCopy">复制</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
var DATA = __DATA__;
var CUR = null, coachFilter = "", kw = "", charts = [];
var C_OK="#46b985", C_ICE="#57b0e8", C_AMBER="#e6a23c", C_RED="#e2604f", C_FROST="#8fa2b8", C_LINE="#24314a";

function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];}); }
function fmt(v,d){ return (v==null||isNaN(v)) ? "-" : Number(v).toFixed(d==null?1:d); }
function pct(v){ return (v==null||isNaN(v)) ? "-" : v.toFixed(0)+"%"; }
function spark(vals, w, h, color){
  if(!vals || vals.length < 2) return '<svg viewBox="0 0 '+w+' '+h+'" xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="'+h/2+'" x2="'+w+'" y2="'+h/2+'" stroke="'+C_LINE+'" stroke-width="1" stroke-dasharray="2 2"/></svg>';
  var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), rng = (mx-mn)||1;
  var pts = vals.map(function(v,i){ return (i/(vals.length-1)*w).toFixed(1)+","+(h-2-((v-mn)/rng)*(h-4)).toFixed(1); });
  return '<svg viewBox="0 0 '+w+' '+h+'" xmlns="http://www.w3.org/2000/svg">'+
    '<polyline points="'+pts.join(" ")+'" fill="none" stroke="'+color+'" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
function formVals(p){
  var s = (p.sessions||[]).slice().reverse();
  return s.slice(0,12).map(function(x){ return x.avg_hr; });
}
function coachList(){ var m={}; DATA.athletes.forEach(function(a){ if(a.coach) m[a.coach]=1; }); return Object.keys(m).sort(); }
function renderCoachFilter(){
  var el = document.getElementById("cf");
  var html = '<span class="cf'+(coachFilter==""?" on":"")+'" data-c="">全部</span>';
  coachList().forEach(function(c){ html += '<span class="cf'+(coachFilter==c?" on":"")+'" data-c="'+esc(c)+'">'+esc(c)+'</span>'; });
  el.innerHTML = html;
}
function renderList(){
  var el = document.getElementById("list"), html = "", n = 0;
  DATA.athletes.forEach(function(a){
    if(coachFilter && a.coach != coachFilter) return;
    if(kw && a.name.indexOf(kw) < 0) return;
    n++;
    var p = DATA.profiles[a.subject_id] || {};
    var tags = (p.tags||[]).slice(0,1).map(function(t){ return '<span class="tag'+(t.indexOf("需复测")>=0||t.indexOf("偏高")>=0?" warn":"")+'">'+esc(t)+'</span>'; }).join("");
    var cls = "n";
    if(p.cpet){ cls = p.cpet.valid_class.indexOf("有效")==0 ? "g" : p.cpet.valid_class.indexOf("亚极量")==0 ? "o" : "r"; }
    var dcol = p.hr&&p.hr.z45!=null ? (p.hr.z45>=25?C_RED:(p.hr.z45>=10?C_AMBER:C_OK)) : "#2a4a60";
    html += '<div class="ath'+(CUR==a.subject_id?" on":"")+'" data-s="'+a.subject_id+'">'+
      '<span class="bw '+cls+'">'+(cls=="n"?"新":cls=="g"?"优":cls=="o"?"亚":"复")+'</span>'+
      '<span class="nm">'+esc(a.name)+'</span>'+
      '<span class="meta">'+(p.hr&&p.hr.n_sessions?p.hr.n_sessions+"场":"-")+'</span>'+
      '<span class="form">'+spark(formVals(p), 64, 20, p.hr&&p.hr.n_sessions?C_ICE:"#2a4a60")+'</span>'+
      '<span class="dot" style="background:'+dcol+'"></span>'+
      tags+'</div>';
  });
  document.getElementById("cnt").textContent = n;
  el.innerHTML = html || '<div class="emptybox">无匹配运动员</div>';
}
function initSidebar(){
  renderCoachFilter(); renderList();
  document.getElementById("coachSel").onchange = function(){ coachFilter=this.value; renderList(); };
  document.getElementById("q").oninput = function(){ kw=this.value.trim(); renderList(); };
  document.getElementById("cf").onclick = function(e){
    var t = e.target.closest(".cf"); if(!t) return;
    coachFilter = t.getAttribute("data-c");
    document.querySelectorAll(".cf").forEach(function(x){ x.classList.toggle("on", x==t); });
    document.getElementById("coachSel").value = coachFilter; renderList();
  };
  document.getElementById("list").onclick = function(e){
    var t = e.target.closest(".ath"); if(!t) return; selectAthlete(t.getAttribute("data-s"));
  };
}
var TABS = [["basic","基本信息"],["ability","能力评估"],["train","训练统计"],["recovery","恢复再生"],["perf","竞技表现"]];
var TRAIN_VIEW = "week", REC_VIEW = "week";
function selectAthlete(sid){
  CUR = sid; renderList(); TRAIN_VIEW = "week"; REC_VIEW = "week";
  var a = DATA.athletes.find(function(x){ return x.subject_id==sid; });
  var p = DATA.profiles[sid], main = document.getElementById("main");
  main.innerHTML = ""; main.scrollTop = 0;
  var tags = (p.tags||[]).map(function(t){ return '<span class="tag warn">'+esc(t)+'</span>'; }).join(" ");
  var clsTxt = p.cpet ? p.cpet.valid_class : "未测";
  var fv = formVals(p);
  main.innerHTML =
    '<div class="ath-head">'+
      '<div><div class="nm">'+esc(a.name)+' '+tags+'</div>'+
      '<div class="meta-line">'+[a.gender||"", a.age!=null?fmt(a.age,1)+"岁":"", a.class?esc(a.class)+"班":"", a.coach?esc(a.coach):""].filter(Boolean).join(" · ")+
      ' · <b>'+esc(clsTxt)+'</b></div></div>'+
      '<div class="head-form"><div class="l">训练状态线 · 近场次平均心率</div>'+
      '<div class="spark">'+spark(fv, 340, 34, C_ICE)+'</div>'+
      '<div class="cap">'+(p.hr.last_date?("最近训练 "+p.hr.last_date):"暂无训练记录")+'</div></div>'+
    '</div>'+
    '<div class="tabs2" id="tabs2">'+
      TABS.map(function(t){ return '<div class="tabbtn'+(t[0]=="basic"?" on":"")+'" data-t="'+t[0]+'">'+t[1]+'</div>'; }).join("")+
    '</div>'+
    TABS.map(function(t){ return '<div class="tabpane'+(t[0]=="basic"?" show":"")+'" id="tab_'+t[0]+'"></div>'; }).join("");
  document.getElementById("tabs2").onclick = function(e){
    var b = e.target.closest(".tabbtn"); if(!b) return;
    document.querySelectorAll(".tabbtn").forEach(function(x){ x.classList.toggle("on", x==b); });
    var t = b.getAttribute("data-t");
    document.querySelectorAll(".tabpane").forEach(function(x){ x.classList.remove("show"); });
    var pane = document.getElementById("tab_"+t);
    pane.classList.add("show");
    renderTab(t, pane, a, p);
  };
  charts = [];
  renderTab("basic", document.getElementById("tab_basic"), a, p);
}
function renderTab(t, pane, a, p){
  pane.innerHTML = "";
  if(t=="basic") renderBasic(pane, a, p);
  else if(t=="ability") renderAbility(pane, p);
  else if(t=="train") renderTrain(pane, p, TRAIN_VIEW);
  else if(t=="recovery") renderRecovery(pane, p, REC_VIEW);
  else if(t=="perf") renderPerf(pane, a, p);
}
function infoCell(l, v, d){
  return '<div class="info-cell"><div class="l">'+l+'</div><div class="v">'+v+'</div><div class="d">'+(d||"")+'</div></div>';
}
function renderBasic(pane, a, p){
  var bmi = (a.height && a.weight) ? (a.weight/(a.height/100)**2).toFixed(1) : "-";
  var dob = p.dob ? (p.dob.slice(0,4)+"年"+parseInt(p.dob.slice(5,7))+"月") : "-";
  var cells =
    infoCell("年龄", a.age!=null?fmt(a.age,1)+" 岁":"-","")+
    infoCell("出生年月", dob,"")+
    infoCell("组别", a.class?esc(a.class)+"班":"-","")+
    infoCell("教练", a.coach?esc(a.coach):"-","")+
    infoCell("性别", a.gender||"-","")+
    infoCell("干预分组", p.intervention?esc(p.intervention):"-","")+
    infoCell("身高 / 体重", (a.height?fmt(a.height)+"cm":"-")+" / "+(a.weight?fmt(a.weight)+"kg":"-"),"BMI "+bmi)+
    infoCell("训练监测", p.hr.n_sessions+" 场","冰上 "+p.hr.n_ice+" · 陆地 "+p.hr.n_land)+
    infoCell("最近训练", p.hr.last_date||"-","")+
    infoCell("累计负荷", p.hr.trimp_sum!=null?fmt(p.hr.trimp_sum,0):"-","TRIMP");
  var alert = (p.tags&&p.tags.length)?'<div class="alert"><b>教练关注</b><ul>'+p.tags.map(function(t){
      var why = { "CPET需复测":"测试无效，需重新安排最大摄氧量测试",
                  "CPET亚极量":"测试未达最大努力标准，数据仅作下限参考",
                  "高强度负荷大":"Z4+Z5 占比 ≥25%，注意恢复与疲劳监控",
                  "暂无心率数据":"无心率监测记录，建议补充",
                  "CK偏高(恢复关注)":"CK≥500 U/L，提示肌肉损伤/恢复不足"}[t]||"";
      return '<li>'+esc(t)+'<span style="color:#7a94a6"> — '+esc(why)+'</span></li>';
    }).join("")+'</ul></div>':"";
  pane.innerHTML = '<div class="info-grid">'+cells+'</div>'+alert+
    '<div class="kpi-row" style="margin-top:14px">'+
      '<div class="kpi">最大摄氧量<b>'+(p.cpet?p.cpet.vo2kg+" ml/kg/min":"暂无")+'</b><span>'+esc(p.cpet?p.cpet.valid_class+" · "+p.cpet.date.slice(0,10):"未测")+'</span></div>'+
      '<div class="kpi">FMS<b>'+(p.pretest&&p.pretest.fms!=null?p.pretest.fms:"-")+'</b><span>功能性筛查</span></div>'+
      '<div class="kpi">CMJ<b>'+(p.pretest&&p.pretest.cmj!=null?fmt(p.pretest.cmj)+"cm":"-")+'</b><span>纵跳</span></div>'+
      '<div class="kpi">高强度占比<b>'+(p.hr.z45!=null?pct(p.hr.z45):"-")+'</b><span>Z4+Z5 平均</span></div>'+
    '</div>';
}
function renderAbility(pane, p){
  pane.innerHTML =
    '<div class="grid">'+
      '<div class="box"><h3>能力画像<small>与全队比较 · 百分位</small></h3><div id="c_radar" style="height:300px"></div>'+
      '<div class="legend">有氧=相对摄氧量 · 耐力=VT1% · 通气=VE/VCO2斜率(低为好) · 做功=峰值功率 · 动作=FMS · 爆发=CMJ</div></div>'+
      '<div class="box"><h3>前测体能<small>FMS / CMJ / YBT / ROM / COP</small></h3><div id="c_pretest"></div></div>'+
      '<div class="box"><h3>CPET 测试<small>每次结果</small></h3><div id="c_cpet"></div></div>'+
      '<div class="box"><h3>左右对称性<small>平衡 / 活动度 / 单腿力量</small></h3><div id="c_asym" style="height:280px"></div></div>'+
    '</div>';
  drawRadar(p.score); drawPretest(p); drawCPET(p); drawAsym(p);
}
function viewBar(id, cur){
  return '<div class="viewbar">'+
    '<span class="vbtn'+(cur=="week"?" on":"")+'" data-v="week">周</span>'+
    '<span class="vbtn'+(cur=="month"?" on":"")+'" data-v="month">月</span></div>';
}
function renderTrain(pane, p, view){
  pane.innerHTML =
    '<div class="box">'+viewBar("tv", view)+
      '<h3>训练量构成<small>'+ (view=="week"?"按周":"按月") +' · 堆积=各类型时长(min) · 折线=平均心率</small></h3>'+
      '<div id="c_train" style="height:300px"></div></div>'+
    '<div class="box"><h3>每日训练负荷比例<small>各类型时长占比</small></h3><div id="c_daily" style="height:260px"></div></div>';
  var vbar = pane.querySelector(".viewbar");
  vbar.onclick = function(e){
    var b = e.target.closest(".vbtn"); if(!b) return;
    TRAIN_VIEW = b.getAttribute("data-v");
    renderTrain(pane, p, TRAIN_VIEW);
  };
  drawTrainChart(p, view);
  drawDailyLoad(p);
}
function renderRecovery(pane, p, view){
  pane.innerHTML =
    '<div class="box">'+viewBar("rv", view)+
      '<h3>恢复训练课统计<small>专项录入中含「放松恢复」的训练课</small></h3><div id="c_rec" style="height:220px"></div></div>'+
    '<div class="box"><h3>干预概况<small>急性疲劳实验</small></h3><div id="c_acute"></div></div>'+
    '<div class="grid2"><div class="box"><h3>血液恢复<small>BL / 24H / 72H</small></h3><div id="c_blood" style="height:240px"></div></div>'+
    '<div class="box"><h3>CMJ 恢复曲线<small>前测→24h→72h</small></h3><div id="c_cmj" style="height:240px"></div></div></div>';
  var vbar = pane.querySelector(".viewbar");
  vbar.onclick = function(e){
    var b = e.target.closest(".vbtn"); if(!b) return;
    REC_VIEW = b.getAttribute("data-v");
    renderRecovery(pane, p, REC_VIEW);
  };
  drawRecChart(p, view); drawAcute(p); drawBloodChart(p); drawCmjChart(p);
}
function renderPerf(pane, a, p){
  pane.innerHTML =
    '<div class="grid">'+
      '<div class="box"><h3>测试成绩<small>CPET</small></h3><div id="c_cpet2"></div></div>'+
      '<div class="box"><h3>计时成绩趋势<small>平板录入的冰上计时</small></h3><div id="c_ent_ice" style="height:260px"></div></div>'+
      '<div class="box full"><h3>专项训练记录<small>录入数据</small></h3><div id="train_rec"></div></div>'+
    '</div>';
  drawCPETInto("c_cpet2", p);
  drawIceTrend(entryAll(a.name));
  drawTrainRec(a.name);
}
function drawCPETInto(id, p){
  var el = document.getElementById(id);
  if(!p.cpet){ el.innerHTML = '<div class="emptybox">暂无 CPET 数据 · 建议安排测试</div>'; return; }
  var c = p.cpet;
  var rows = [
    ["相对摄氧量", fmt(c.vo2kg)+" ml/kg/min", "全队中位约 66", c.vo2kg>=70?"优":(c.vo2kg>=60?"中":"需关注")],
    ["预测达成率", pct(c.pctnorm), "≥100% 达到设备预测", c.pctnorm>=100?"达标":"未达标"],
    ["通气效率", fmt(c.slope)+" VE/VCO2", "<30 优秀 · 越低越好", c.slope<30?"优":(c.slope<35?"中":"需关注")],
    ["VT1 占峰值", pct(c.vt1_pct), "≥70% 耐力储备良好", c.vt1_pct>=70?"良好":"一般"],
    ["峰值功率", fmt(c.wr)+" W", "运动负荷能力", "-"],
    ["测试次数", c.n_tests+" 次", "含复测", "-"],
  ];
  el.innerHTML = '<table><thead><tr><th>指标</th><th>数值</th><th>参考</th><th>评价</th></tr></thead><tbody>'+
    rows.map(function(r){ return '<tr><td>'+r[0]+'</td><td><b>'+r[1]+'</b></td><td style="color:#5d7889">'+r[2]+'</td><td>'+r[3]+'</td></tr>'; }).join("")+'</tbody></table>';
}
function drawAsym(p){
  var el = document.getElementById("c_asym"); if(!el) return;
  var pt = p.pretest;
  if(!pt){
    el.innerHTML = '<div class="emptybox">暂无前测数据</div>';
    return;
  }
  var items = [
    ["YBT·左腿支撑", pt.ybt_r_ant, pt.ybt_l_ant],
    ["闭眼单脚站", pt.eyes_closed_l, pt.eyes_closed_r],
    ["踝背屈ROM", pt.rom_dorsi_l, pt.rom_dorsi_r],
    ["单腿跳", pt.jump_single_l, pt.jump_single_r],
    ["三连跳", pt.jump_triple_l, pt.jump_triple_r],
  ].filter(function(x){ return x[1]!=null || x[2]!=null; });
  var names = items.map(function(x){ return x[0]; });
  chart("c_asym", {
    textStyle:baseText(),
    tooltip:{trigger:"axis"},
    legend:{top:0,textStyle:{color:C_FROST},data:["左","右"]},
    grid:{left:100,right:24,top:28,bottom:22},
    xAxis:{type:"value",axisLabel:{color:C_FROST,fontSize:9}},
    yAxis:{type:"category",data:names,axisLabel:{color:C_FROST,fontSize:10}},
    series:[
      {name:"左",type:"bar",data:items.map(function(x){return x[1];}),
       itemStyle:{color:"rgba(87,176,232,.8)"},barMaxWidth:11},
      {name:"右",type:"bar",data:items.map(function(x){return x[2];}),
       itemStyle:{color:"rgba(242,169,59,.85)"},barMaxWidth:11,
       label:{show:true,position:"right",fontSize:9,color:C_FROST}}
    ]
  });
}
function drawTrainChart(p, view){
  var el = document.getElementById("c_train"); if(!el) return;
  var typeRows = view=="week" ? p.train.week_type : p.train.month_type;
  var avgRows = view=="week" ? p.train.week_avg : p.train.month_avg;
  var periods = avgRows.map(function(x){ return x.week||x.month; });
  var types = ["冰上","陆地","其他"];
  function durOf(period, t){
    var r = typeRows.filter(function(x){ return (x.week||x.month)==period && x.session_type==t; })[0];
    return r ? r.dur : 0;
  }
  chart("c_train", {
    textStyle:baseText(), tooltip:{trigger:"axis"},
    legend:{top:0,textStyle:{color:C_FROST},data:types.concat(["平均心率"])},
    grid:{left:44,right:44,top:34,bottom:26},
    xAxis:{type:"category",data:periods,axisLine:{lineStyle:{color:C_LINE}},axisLabel:{color:C_FROST,fontSize:10}},
    yAxis:[{type:"value",name:"分钟",nameTextStyle:{color:C_FROST,fontSize:9},axisLabel:{color:C_FROST,fontSize:9},
            splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
           {type:"value",name:"bpm",nameTextStyle:{color:C_FROST,fontSize:9},axisLabel:{color:C_FROST,fontSize:9},splitLine:{show:false}}],
    series:[
      {name:"冰上",type:"bar",stack:"d",data:periods.map(function(x){return durOf(x,"冰上");}),
       itemStyle:{color:"rgba(87,176,232,.85)"},barMaxWidth:28},
      {name:"陆地",type:"bar",stack:"d",data:periods.map(function(x){return durOf(x,"陆地");}),
       itemStyle:{color:"rgba(95,176,110,.85)"}},
      {name:"其他",type:"bar",stack:"d",data:periods.map(function(x){return durOf(x,"其他");}),
       itemStyle:{color:"rgba(143,148,160,.65)"}},
      {name:"平均心率",type:"line",yAxisIndex:1,data:avgRows.map(function(x){return x.avg_hr;}),
       itemStyle:{color:C_AMBER},lineStyle:{width:2.2},symbolSize:6,
       label:{show:true,position:"top",fontSize:9,color:C_AMBER}}
    ]
  });
}
function drawDailyLoad(p){
  var el = document.getElementById("c_daily"); if(!el) return;
  var dt = p.train.daily_type;
  var dates = p.train.daily.map(function(x){ return x.date.slice(5); });
  var types = ["冰上","陆地","其他"];
  function valOf(d, t){
    var full = "2026-"+d;
    var r = dt.filter(function(x){ return x.date==full && x.session_type==t; })[0];
    return r ? +r.dur.toFixed(1) : 0;
  }
  chart("c_daily", {
    textStyle:baseText(), tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},
    legend:{top:0,textStyle:{color:C_FROST},data:types},
    grid:{left:40,right:14,top:30,bottom:26},
    xAxis:{type:"category",data:dates,axisLine:{lineStyle:{color:C_LINE}},axisLabel:{color:C_FROST,fontSize:9,rotate:dates.length>8?35:0}},
    yAxis:{type:"value",axisLabel:{color:C_FROST,fontSize:9},splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:types.map(function(t,i){
      return {name:t,type:"bar",stack:"dl",data:dates.map(function(d){return valOf(d,t);}),
        itemStyle:{color:["rgba(87,176,232,.85)","rgba(95,176,110,.85)","rgba(143,148,160,.65)"][i]}};
    })
  });
}
function drawRecChart(p, view){
  var el = document.getElementById("c_rec"); if(!el) return;
  var rec = (p.train_rec||[]).filter(function(r){
    var cs = Array.isArray(r.contents) ? r.contents.join("/") : String(r.contents||"");
    return cs.indexOf("放松恢复")>=0;
  });
  var map = {};
  function isoWeek(dstr){
    var d = new Date(dstr+"T00:00:00");
    var day = (d.getDay()+6)%7;
    d.setDate(d.getDate()-day+3);
    var first = new Date(d.getFullYear(),0,1);
    return d.getFullYear()+"-W"+Math.ceil(((d-first)/86400000+first.getDay()+1)/7);
  }
  rec.forEach(function(r){
    var k = view=="week" ? isoWeek(r.date) : r.date.slice(0,7);
    map[k] = (map[k]||0) + (+(r.sets_num||r.sets)||1);
  });
  var keys = Object.keys(map).sort();
  if(!keys.length){
    el.innerHTML = '<div class="emptybox">暂无恢复训练课记录 · 可在「录入」中标记「放松恢复」</div>';
    return;
  }
  chart("c_rec", {
    textStyle:baseText(), tooltip:{},
    grid:{left:40,right:14,top:14,bottom:26},
    xAxis:{type:"category",data:keys,axisLine:{lineStyle:{color:C_LINE}},axisLabel:{color:C_FROST,fontSize:10}},
    yAxis:{type:"value",name:"组数",nameTextStyle:{color:C_FROST,fontSize:9},axisLabel:{color:C_FROST,fontSize:9},
      splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}},minInterval:1},
    series:[{type:"bar",data:keys.map(function(k){return map[k];}),
      itemStyle:{color:"rgba(78,197,139,.85)"},barMaxWidth:28,
      label:{show:true,position:"top",fontSize:9,color:C_FROST}}]
  });
}
function drawBloodChart(p){
  var el = document.getElementById("c_blood"); if(!el) return;
  var all = p.blood_all || [];
  if(!all.length){ el.innerHTML = '<div class="emptybox">暂无血液指标</div>'; return; }
  function seriesOf(key, color){
    return {name:key,type:"line",data:["BL","24H","72H"].map(function(tp){
      var r = all.filter(function(x){ return x.analyte==key && x.timepoint==tp; })[0];
      return r ? +r.result_value.toFixed(1) : null;
    }), itemStyle:{color:color},symbolSize:5,
      label:{show:true,position:"top",fontSize:9,color:C_FROST,
        formatter:function(pp){ return pp.value!=null?pp.value:""; }}};
  }
  chart("c_blood", {
    textStyle:baseText(), tooltip:{trigger:"axis"},
    legend:{top:0,textStyle:{color:C_FROST},data:["ck","cortisol","ldh"]},
    grid:{left:40,right:14,top:30,bottom:24},
    xAxis:{type:"category",data:["基线","24H","72H"],axisLine:{lineStyle:{color:C_LINE}},axisLabel:{color:C_FROST}},
    yAxis:{type:"value",axisLabel:{color:C_FROST,fontSize:9},splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:[seriesOf("ck",C_RED), seriesOf("cortisol",C_AMBER), seriesOf("ldh",C_ICE)]
  });
}
function drawCmjChart(p){
  var el = document.getElementById("c_cmj"); if(!el) return;
  var ac = p.acute;
  if(!ac || ac.cmj_pre==null){ el.innerHTML = '<div class="emptybox">暂无急性疲劳数据</div>'; return; }
  var pts = [["前测",ac.cmj_pre],["24h",ac.cmj_24h],["72h",ac.cmj_72h]].filter(function(x){return x[1]!=null;});
  chart("c_cmj", {
    textStyle:baseText(), tooltip:{trigger:"axis"},
    grid:{left:34,right:14,top:14,bottom:22},
    xAxis:{type:"category",data:pts.map(function(x){return x[0];}),axisLine:{lineStyle:{color:C_LINE}},axisLabel:{color:C_FROST}},
    yAxis:{type:"value",name:"cm",nameTextStyle:{color:C_FROST,fontSize:9},axisLabel:{color:C_FROST,fontSize:9},
      splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:[{type:"line",data:pts.map(function(x){return x[1];}),
      markLine:{silent:true,symbol:"none",data:ac.cmj_pre!=null?[{yAxis:ac.cmj_pre}]:[],
        lineStyle:{color:C_AMBER,type:"dashed",width:1},
        label:{show:true,formatter:"基线",color:C_AMBER,fontSize:9,position:"insideEndTop"}},
      symbolSize:7,itemStyle:{color:C_OK},lineStyle:{width:2.4},areaStyle:{color:"rgba(78,197,139,.12)"},
      label:{show:true,position:"top",fontSize:10,color:C_FROST,formatter:function(pp){return pp.value+" cm";}}}]
  });
}
function chart(id, opt){
  var el = document.getElementById(id); if(!el) return;
  var c = echarts.init(el, null, {renderer:"canvas"});
  c.setOption(opt); charts.push(c);
}
function baseText(){
  return {color:C_FROST, fontFamily:"'Microsoft YaHei',sans-serif", fontSize:11};
}
function drawRadar(score){
  var dims = ["有氧能力","通气效率","耐力储备","训练负荷","高强度占比","监测覆盖"];
  var vals = dims.map(function(d){ return score[d]!=null?score[d]:0; });
  chart("c_radar", {
    textStyle:baseText(),
    tooltip:{},
    radar:{ indicator:dims.map(function(d){return {name:d,max:100};}), radius:"60%",
      splitArea:{areaStyle:{color:["rgba(18,43,61,.6)","rgba(15,38,54,.6)"]}},
      splitLine:{lineStyle:{color:C_LINE}}, axisLine:{lineStyle:{color:C_LINE}},
      axisName:{color:C_FROST, fontSize:11} },
    series:[{type:"radar", data:[{value:vals, name:"百分位",
      areaStyle:{color:"rgba(87,176,232,.18)"}, lineStyle:{color:C_ICE, width:2},
      itemStyle:{color:C_ICE}, symbolSize:4}]}]
  });
}
function drawHR(p){
  var s = p.sessions.slice().reverse().slice(0,20);
  var names = s.map(function(x){ return x.date.slice(5); });
  var avgs = s.map(function(x){ return x.avg_hr; });
  var maxs = s.map(function(x){ return x.max_hr; });
  chart("c_hr", {
    textStyle:baseText(),
    tooltip:{trigger:"axis"},
    grid:{left:40,right:16,top:24,bottom:26},
    xAxis:{type:"category", data:names, axisLine:{lineStyle:{color:C_LINE}},
      axisLabel:{color:C_FROST, fontSize:10}},
    yAxis:{type:"value", name:"bpm", nameTextStyle:{color:C_FROST},
      axisLabel:{color:C_FROST}, splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:[
      {name:"平均HR", type:"bar", data:avgs, barMaxWidth:16,
       itemStyle:{color:{type:"linear",x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:"#4fd0ee"},{offset:1,color:"#2a8fb0"}]}},
       label:{show:true,position:"top",fontSize:9,color:C_FROST}},
      {name:"最高HR", type:"line", data:maxs, symbolSize:4,
       itemStyle:{color:C_AMBER}, lineStyle:{width:1.4, color:"rgba(242,169,59,.7)"}}
    ]
  });
}
function drawTrend(p){
  var w = p.weeks;
  chart("c_trend", {
    textStyle:baseText(),
    tooltip:{trigger:"axis"},
    legend:{top:0, textStyle:{color:C_FROST}, data:["平均心率","高强度%"]},
    grid:{left:42,right:42,top:34,bottom:24},
    xAxis:{type:"category", data:w.map(function(x){ return x.week.slice(0,7)+"周"; }),
      axisLine:{lineStyle:{color:C_LINE}}, axisLabel:{color:C_FROST}},
    yAxis:[{type:"value",name:"bpm",nameTextStyle:{color:C_FROST},axisLabel:{color:C_FROST},
            splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
           {type:"value",name:"%",nameTextStyle:{color:C_FROST},axisLabel:{color:C_FROST},splitLine:{show:false}}],
    series:[
      {name:"平均心率",type:"bar",data:w.map(function(x){return x.avg_hr;}),barMaxWidth:26,
       itemStyle:{color:"rgba(87,176,232,.85)"},
       label:{show:true,position:"top",fontSize:9,color:C_FROST}},
      {name:"高强度%",type:"line",yAxisIndex:1,data:w.map(function(x){return +x.z45.toFixed(1);}),
       itemStyle:{color:C_AMBER},lineStyle:{width:2},symbolSize:5,
       label:{show:true,position:"top",fontSize:9,color:C_AMBER}}
    ]
  });
}
function drawCPET(p){
  var el = document.getElementById("c_cpet");
  if(!p.cpet){ el.innerHTML = '<div class="emptybox">暂无 CPET 数据 · 建议安排测试</div>'; return; }
  var c = p.cpet;
  var rows = [
    ["相对摄氧量", fmt(c.vo2kg)+" ml/kg/min", "全队中位约 66", c.vo2kg>=70?"优":(c.vo2kg>=60?"中":"需关注")],
    ["预测达成率", pct(c.pctnorm), "≥100% 达到设备预测", c.pctnorm>=100?"达标":"未达标"],
    ["通气效率", fmt(c.slope)+" VE/VCO2", "<30 优秀 · 越低越好", c.slope<30?"优":(c.slope<35?"中":"需关注")],
    ["VT1 占峰值", pct(c.vt1_pct), "≥70% 耐力储备良好", c.vt1_pct>=70?"良好":"一般"],
    ["峰值功率", fmt(c.wr)+" W", "运动负荷能力", "-"],
    ["测试次数", c.n_tests+" 次", "含复测", "-"],
  ];
  el.innerHTML = '<table><thead><tr><th>指标</th><th>数值</th><th>参考</th><th>评价</th></tr></thead><tbody>'+
    rows.map(function(r){ return '<tr><td>'+r[0]+'</td><td><b>'+r[1]+'</b></td><td style="color:#5d7889">'+r[2]+'</td><td>'+r[3]+'</td></tr>'; }).join("")+'</tbody></table>';
}
function drawBlood(p){
  var keys = ["ck","cortisol","testosterone","urea","ldh"];
  var names = {"ck":"CK","cortisol":"皮质醇","testosterone":"睾酮","urea":"尿素","ldh":"LDH"};
  var el = document.getElementById("blood");
  if(!Object.keys(p.blood).length){ el.innerHTML = '<div class="emptybox">暂无血液指标数据</div>'; return; }
  var html = '<div class="blood">';
  keys.forEach(function(k){
    var b = p.blood[k]; if(!b) return;
    var cls = "";
    if(k=="ck" && b.value>=500) cls="hi";
    if(k=="cortisol" && b.value>25) cls="hi";
    if(k=="urea" && b.value>8) cls="hi";
    if(k=="ldh" && b.value>400) cls="hi";
    html += '<div class="bcell"><div class="tp">'+names[k]+' · '+esc(b.timepoint)+'</div>'+
      '<div class="n '+cls+'">'+fmt(b.value)+' <span class="u">'+esc(b.unit||"")+'</span></div></div>';
  });
  html += '</div><div class="legend">红色=超参考上限（CK≥500 / 皮质醇&gt;25 / 尿素&gt;8 / LDH&gt;400）</div>';
  el.innerHTML = html;
}
function drawPretest(p){
  var el = document.getElementById("c_pretest");
  var pt = p.pretest;
  if(!pt){
    el.innerHTML = '<div class="emptybox">暂无前测数据</div>';
    return;
  }
  var cards = [
    ["FMS 总分", pt.fms!=null?pt.fms:"-", pt.fms>=30?"优":(pt.fms>=24?"中":"关注")],
    ["CMJ 纵跳", pt.cmj!=null?pt.cmj+"cm":"-", pt.cmj>=28?"优":(pt.cmj>=20?"中":"关注")],
    ["血乳酸(前)", pt.lactate_pre!=null?pt.lactate_pre:"-", "mmol/L"],
    ["YBT 前伸", pt.ybt_ant!=null?pt.ybt_ant:"-", "cm"],
    ["踝背屈ROM", pt.rom_dorsi!=null?pt.rom_dorsi+"°":"-", pt.rom_dorsi>=40?"良好":"关注"],
    ["COP面积", pt.cop!=null?pt.cop:"-", "mm²"],
  ];
  var cardCls = function(c){ return c=="优"||c=="良好"?"ok":(c=="中"?"":"hi"); };
  el.innerHTML =
    '<div class="cards" style="margin-bottom:8px">'+
    cards.map(function(c){
      var cl = c[2]=="优"||c[2]=="良好" ? "ok" : (c[2]=="中" ? "" : (c[2]=="关注"||c[2]=="hi" ? "hi" : ""));
      return '<div class="card"><div class="v" style="font-size:19px">'+c[1]+'</div>'+
        '<div class="l">'+c[0]+'</div><div class="d">'+esc(c[2])+'</div></div>';
    }).join("")+'</div>'+
    '<div style="height:190px" id="c_pretest_chart"></div>'+
    '<div class="legend">与全队比较的百分位 · 中位线=50%</div>'+
    '<div class="insight" id="pretest_insight" style="margin-top:8px"></div>';
  // 全队百分位条形图
  var ps = p.pre_score || {};
  var items = [
    ["FMS", ps.fms], ["CMJ", ps.cmj], ["YBT前伸", ps.ybt_ant],
    ["提踵", ps.heel], ["踝背屈", ps.rom], ["三连跳", ps.jump3], ["COP稳定", ps.cop],
  ];
  var c = echarts.init(document.getElementById("c_pretest_chart"));
  c.setOption({
    textStyle:baseText(),
    tooltip:{trigger:"axis", axisPointer:{type:"shadow"},
      formatter:function(pp){ return pp[0].name+" · 全队前 "+pp[0].value+"%"; }},
    grid:{left:70,right:40,top:8,bottom:22},
    xAxis:{type:"value", max:100, axisLabel:{color:C_FROST,fontSize:9},
      splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    yAxis:{type:"category", data:items.map(function(i){return i[0];}),
      axisLabel:{color:C_FROST,fontSize:10}},
    series:[{type:"bar", data:items.map(function(i){
      var v = i[1]!=null?i[1]:0;
      return {value:v, itemStyle:{color: v>=70 ? "rgba(78,197,139,.9)" : v>=40 ? "rgba(87,176,232,.85)" : "rgba(242,169,59,.9)"}};
    }), barMaxWidth:12,
      label:{show:true,position:"right",fontSize:9,color:C_FROST,
        formatter:function(pp){ return pp.value>0?pp.value+"%":""; }},
      markLine:{silent:true, symbol:"none", data:[{xAxis:50}],
        lineStyle:{color:C_AMBER,type:"dashed",width:1},
        label:{show:true,formatter:"中位",color:C_AMBER,fontSize:9,position:"insideEndTop"}}}]
  });
  charts.push(c);
  // 一句话洞察：找最强/最弱
  var labels = {fms:"FMS", cmj:"CMJ纵跳", ybt_ant:"YBT前伸", heel:"重复提踵",
    rom:"踝背屈ROM", jump3:"单腿三连跳", cop:"COP静态平衡"};
  var tips = {fms:"基础动作质量扎实", cmj:"下肢爆发力偏弱，建议加强跳跃训练",
    ybt_ant:"动态平衡有提升空间", heel:"踝关节耐力需加强",
    rom:"踝背屈活动度需关注，注意牵拉", jump3:"连续爆发力待提升",
    cop:"静态平衡控制需加强"};
  var entries = Object.keys(ps).filter(function(k){ return ps[k]!=null; });
  var weak = null, strong = null;
  entries.forEach(function(k){
    if(weak==null || ps[k]<ps[weak]) weak = k;
    if(strong==null || ps[k]>ps[strong]) strong = k;
  });
  var txt = "";
  if(strong && ps[strong]!=null && ps[strong]>=60)
    txt += "全队对比，" + labels[strong] + " 是强项（前 " + ps[strong].toFixed(0) + "%）。";
  if(weak && ps[weak]!=null && ps[weak]<45)
    txt += labels[weak] + " 是短板（仅前 " + ps[weak].toFixed(0) + "%），" + tips[weak] + "。";
  if(!txt) txt = "各项体能指标与全队基本持平，保持系统训练即可。";
  document.getElementById("pretest_insight").innerHTML = "◆ " + txt;
}
function drawAcute(p){
  var el = document.getElementById("c_acute");
  var ac = p.acute;
  if(!ac){
    el.innerHTML = '<div class="emptybox">暂无急性疲劳实验数据</div>';
    return;
  }
  var cmj24 = (ac.cmj_pre!=null && ac.cmj_24h!=null)
    ? Math.round((ac.cmj_24h - ac.cmj_pre)/ac.cmj_pre*100) : null;
  var cmj72 = (ac.cmj_pre!=null && ac.cmj_72h!=null)
    ? Math.round((ac.cmj_72h - ac.cmj_pre)/ac.cmj_pre*100) : null;
  var cards = [
    ["干预", ac.intervention||"-", ""],
    ["造模负荷", ac.load_pct!=null?ac.load_pct+"%":"-", ""],
    ["CMJ 24h", cmj24!=null?(cmj24>=0?"+"+cmj24+"%":cmj24+"%"):"-", cmj24!=null&&cmj24<0?"下降":(cmj24!=null?"恢复":"" )],
    ["VAS 疼痛", ac.vas_post!=null?ac.vas_post:"-", ac.vas_post>5?"偏高":(ac.vas_post!=null?"正常":"")],
    ["RPE 疲劳", ac.rpe_post!=null?ac.rpe_post:"-", ac.rpe_post>17?"很高":(ac.rpe_post!=null?"正常":"")],
    ["血乳酸后", ac.lactate_post!=null?ac.lactate_post:"-", "mmol/L"],
  ];
  el.innerHTML =
    '<div class="cards" style="margin-bottom:8px">'+
    cards.map(function(c){
      var cl = (c[2]=="偏高"||c[2]=="很高"||c[2]=="下降") ? "hi" : (c[2]=="恢复" ? "ok" : "");
      return '<div class="card"><div class="v" style="font-size:19px">'+c[1]+'</div>'+
        '<div class="l">'+c[0]+'</div><div class="d">'+esc(c[2])+'</div></div>';
    }).join("")+'</div>'+
    '<div style="height:190px" id="c_acute_chart"></div>'+
    '<div class="legend">CMJ 纵跳恢复曲线 · 虚线=造模前基线</div>'+
    '<div class="insight" id="acute_insight" style="margin-top:8px"></div>';
  // CMJ 恢复曲线
  var c = echarts.init(document.getElementById("c_acute_chart"));
  var pts = [
    ["前测", ac.cmj_pre], ["24h", ac.cmj_24h], ["72h", ac.cmj_72h]
  ].filter(function(x){ return x[1]!=null; });
  c.setOption({
    textStyle:baseText(),
    tooltip:{trigger:"axis",
      formatter:function(ps){
        return ps[0].name + " · CMJ <b style='color:"+C_ICE+"'>" + ps[0].value + " cm</b>" +
          (ac.cmj_pre!=null ? "（基线 "+ac.cmj_pre+"）" : "");
      }},
    grid:{left:38,right:16,top:16,bottom:22},
    xAxis:{type:"category", data:pts.map(function(x){return x[0];}),
      axisLine:{lineStyle:{color:C_LINE}}, axisLabel:{color:C_FROST}},
    yAxis:{type:"value", name:"cm", nameTextStyle:{color:C_FROST,fontSize:9},
      axisLabel:{color:C_FROST,fontSize:9}, splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}},
      min:function(v){ return Math.max(0, Math.floor((v.min-2)/2)*2); }},
    series:[{type:"line", data:pts.map(function(x){return x[1];}),
      symbolSize:7, itemStyle:{color:C_ICE}, lineStyle:{width:2.4},
      areaStyle:{color:"rgba(87,176,232,.12)"},
      label:{show:true,position:"top",fontSize:10,color:C_FROST,
        formatter:function(pp){ return pp.value+" cm"; }},
      markLine:{silent:true, symbol:"none",
        data: ac.cmj_pre!=null ? [{yAxis:ac.cmj_pre}] : [],
        lineStyle:{color:C_AMBER,type:"dashed",width:1},
        label:{show:true,formatter:"基线 "+ac.cmj_pre,color:C_AMBER,fontSize:9,position:"insideEndTop"}}}]
  });
  charts.push(c);
  // 一句话洞察
  var txt = "";
  if(cmj24!=null)
    txt += "造模后 24h CMJ " + (cmj24>=0?"恢复":"下降") + " " + Math.abs(cmj24) + "%" +
      (cmj72!=null ? "，72h " + (cmj72>=0?"进一步恢复":"仍低于基线") + "。" : "。");
  else txt += "CMJ 恢复数据待补测。";
  if(ac.vas_post!=null && ac.vas_post>5)
    txt += "主观疼痛 VAS " + ac.vas_post + " 偏高" + (ac.rpe_post!=null&&ac.rpe_post>17? "、RPE " + ac.rpe_post + " 疲劳感很高":"") + "，建议加强放松与恢复安排。";
  else if(ac.rpe_post!=null && ac.rpe_post>17)
    txt += "RPE " + ac.rpe_post + " 疲劳感很高，注意训练量调整。";
  else txt += "主观疲劳指标在可接受范围。";
  if(ac.hrv_sdnn!=null && ac.hrv_sdnn<30)
    txt += "HRV SDNN " + ac.hrv_sdnn + "ms 偏低，副交感恢复不足，建议关注睡眠。";
  document.getElementById("acute_insight").innerHTML = "◆ " + txt;
}
function drawTrainRec(name){
  var el = document.getElementById("train_rec");
  var dbRows = (CUR && DATA.profiles[CUR] && DATA.profiles[CUR].train_rec) || [];
  var local = [];
  try{ local = JSON.parse(localStorage.getItem("stss_train_v1")) || []; }catch(e){}
  var seen = {};
  dbRows.forEach(function(r){ seen[r.id || r.date+"_db"] = 1; });
  local.forEach(function(r){
    if(r.athlete == name && !seen[r.id]){ seen[r.id] = 1; dbRows.push(r); }
  });
  var rows = dbRows.filter(function(r){ return r.athlete == name; }).slice(0, 12);
  var TYPES = {ice:"冰上计时", physical:"陆地素质", session:"训练课", note:"记录"};
  var CLS = {ice:"i", physical:"p", session:"s", note:"n"};
  if(!rows.length){
    el.innerHTML = '<div class="emptybox">本机暂无专项记录 · <a href="训练数据录入.html" style="color:'+C_ICE+'">去录入 →</a></div>';
    return;
  }
  el.innerHTML = '<table><thead><tr><th>日期</th><th>类型</th><th>内容</th></tr></thead><tbody>' +
    rows.map(function(r){
      var s = "";
      var t = r.entry_type || r.type;
      if(t=="ice") s = r.project+" · "+r.time_value+(r.split_text?" · "+r.split_text:"");
      else if(t=="physical") s = (r.test_item||r.test||"-")+" · "+(r.value_num!=null?r.value_num:r.value)+r.unit;
      else if(t=="session"){
        var cs = r.contents;
        var ct = Array.isArray(cs) ? cs.join("/") : String(cs||"").split(",").filter(Boolean).join("/");
        s = ct+" · "+((r.sets_num||r.sets)?(r.sets_num||r.sets)+"组":"")+(r.rating?(" · "+"★".repeat(r.rating)):"");
      }
      else s = r.note;
      if(r.note && t!="note") s += " · "+r.note;
      return '<tr><td style="font-family:var(--mono)">'+esc(r.date)+'</td>'+
        '<td><span class="ty '+CLS[t]+'">'+TYPES[t]+'</span></td>'+
        '<td>'+esc(s)+'</td></tr>';
    }).join("") + '</tbody></table>' +
    '<div class="legend">共 '+dbRows.filter(function(r){return r.athlete==name;}).length+' 条 · 含已入库记录与本机新录入</div>';
}
function entryAll(name){
  var dbRows = (CUR && DATA.profiles[CUR] && DATA.profiles[CUR].train_rec) || [];
  var local = [];
  try{ local = JSON.parse(localStorage.getItem("stss_train_v1")) || []; }catch(e){}
  var seen = {};
  dbRows.forEach(function(r){ seen[r.id || r.date+"_db"] = 1; });
  local.forEach(function(r){
    if(r.athlete == name && !seen[r.id]){ seen[r.id] = 1; dbRows.push(r); }
  });
  return dbRows.filter(function(r){ return r.athlete == name; });
}
function t2sec(t){
  if(t == null) return null;
  t = String(t).trim();
  var m = t.match(/^(\d+):([0-5]?\d)(?:[.:](\d+))?$/);
  if(m) return (+m[1])*60 + (+m[2]) + (+("0."+(m[3]||"0")));
  var v = parseFloat(t);
  return isNaN(v) ? null : v;
}
function sec2t(s){
  if(s == null) return "-";
  var m = Math.floor(s/60), sec = s - m*60;
  return m + ":" + sec.toFixed(2).padStart(5, "0");
}
function drawEntryTrends(name){
  var rows = entryAll(name);
  drawIceTrend(rows);
  drawPhysTrend(rows);
  drawSessTrend(rows);
}
function drawIceTrend(rows){
  var el = document.getElementById("c_ent_ice"); if(!el) return;
  var ice = rows.filter(function(r){ return (r.entry_type||r.type)=="ice" && t2sec(r.time_value||r.time)!=null; })
    .map(function(r){ return {date:r.date, proj:r.project||"其他", sec:t2sec(r.time_value||r.time)}; });
  if(!ice.length){
    el.innerHTML = '<div class="emptybox">暂无计时数据 · <a href="#" onclick="return openEntryFromChart()" style="color:'+C_ICE+'">去录入</a></div>';
    return;
  }
  var projs = {};
  ice.forEach(function(r){ (projs[r.proj] = projs[r.proj]||[]).push(r); });
  var series = Object.keys(projs).map(function(proj){
    var pts = projs[proj].sort(function(a,b){ return a.date < b.date ? -1 : 1; });
    var minSec = Math.min.apply(null, pts.map(function(p){ return p.sec; }));
    var prPt = pts.filter(function(p){ return p.sec == minSec; })[0];
    return {
      name: proj, type:"line", symbolSize:5, data: pts.map(function(p){ return [+(p.date.replace(/-/g,"").slice(4)), +p.sec.toFixed(2)]; }),
      itemStyle:{color:C_ICE}, lineStyle:{width:2},
      markPoint:{ data:[{coord:[+(prPt.date.replace(/-/g,"").slice(4)), +minSec.toFixed(2)], name:"最好", symbolSize:34, label:{fontSize:9, color:"#10151f"},
        itemStyle:{color:C_AMBER}}] }
    };
  });
  var c = echarts.init(el);
  c.setOption({
    textStyle:baseText(), tooltip:{trigger:"axis",
      formatter:function(ps){
        var d = ps[0].axisValue;
        return ps.map(function(p){
          return p.marker + p.seriesName + " · " + sec2t(p.value[1]);
        }).join("<br>") + "<br><span style='color:#5d7889'>" + (ps[0].name) + "</span>";
      }},
    grid:{left:38,right:16,top:22,bottom:24},
    xAxis:{type:"category", data:[], axisLine:{lineStyle:{color:C_LINE}}, axisLabel:{color:C_FROST,fontSize:9,formatter:function(v){return v.slice(0,2)+"-"+v.slice(2);}}},
    yAxis:{type:"value", name:"秒", nameTextStyle:{color:C_FROST,fontSize:9}, axisLabel:{color:C_FROST,fontSize:9}, splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:series
  });
  charts.push(c);
}
function drawPhysTrend(rows){
  var el = document.getElementById("c_ent_phys"); if(!el) return;
  var phys = rows.filter(function(r){
      if((r.entry_type||r.type) != "physical") return false;
      return r.value_num != null || r.value != null;
    })
    .map(function(r){ return {date:r.date, test:r.test_item||r.test||"其他", val:+(r.value_num!=null?r.value_num:r.value), unit:r.unit||""}; });
  if(!phys.length){
    el.innerHTML = '<div class="emptybox">暂无素质数据 · <a href="#" onclick="return openEntryFromChart()" style="color:'+C_ICE+'">去录入</a></div>';
    return;
  }
  var tests = {};
  phys.forEach(function(r){ (tests[r.test] = tests[r.test]||[]).push(r); });
  var series = Object.keys(tests).map(function(t){
    var pts = tests[t].sort(function(a,b){ return a.date < b.date ? -1 : 1; });
    return { name:t, type:"line", symbolSize:5, data:pts.map(function(p){ return [+(p.date.replace(/-/g,"").slice(4)), p.val]; }),
      itemStyle:{color:C_OK}, lineStyle:{width:2} };
  });
  var c = echarts.init(el);
  c.setOption({
    textStyle:baseText(), tooltip:{trigger:"axis"},
    grid:{left:38,right:16,top:22,bottom:24},
    xAxis:{type:"category", data:[], axisLine:{lineStyle:{color:C_LINE}}, axisLabel:{color:C_FROST,fontSize:9,formatter:function(v){return v.slice(0,2)+"-"+v.slice(2);}}},
    yAxis:{type:"value", axisLabel:{color:C_FROST,fontSize:9}, splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
    series:series
  });
  charts.push(c);
}
function drawSessTrend(rows){
  var el = document.getElementById("c_ent_sess"); if(!el) return;
  var sess = rows.filter(function(r){ return (r.entry_type||r.type)=="session"; })
    .map(function(r){
      var cs = r.contents;
      var txt = Array.isArray(cs) ? cs.join("/") : String(cs||"").split(",").filter(Boolean).join("/");
      return {date:r.date, sets:+(r.sets_num!=null?r.sets_num:r.sets)||0, rating:r.rating||0, contents:txt};
    })
    .sort(function(a,b){ return a.date < b.date ? -1 : 1; });
  if(!sess.length){
    el.innerHTML = '<div class="emptybox">暂无训练课记录 · <a href="#" onclick="return openEntryFromChart()" style="color:'+C_ICE+'">去录入</a></div>';
    return;
  }
  var c = echarts.init(el);
  c.setOption({
    textStyle:baseText(),
    tooltip:{trigger:"axis", formatter:function(ps){
      var i = ps[0].dataIndex, s = sess[i];
      return esc(s.date) + "<br>组数: " + s.sets + "<br>质量: " + (s.rating?("★".repeat(s.rating)):"-") + "<br>内容: " + esc(s.contents||"-");
    }},
    grid:{left:34,right:14,top:22,bottom:24},
    xAxis:{type:"category", data:sess.map(function(s){ return s.date.slice(5); }), axisLine:{lineStyle:{color:C_LINE}}, axisLabel:{color:C_FROST,fontSize:9,rotate:sess.length>5?30:0}},
    yAxis:{type:"value", name:"组数", nameTextStyle:{color:C_FROST,fontSize:9}, axisLabel:{color:C_FROST,fontSize:9}, splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}, minInterval:1},
    series:[{type:"bar", data:sess.map(function(s){ return s.sets; }), barMaxWidth:24,
      itemStyle:{color:function(pp){
        var r = sess[pp.dataIndex].rating;
        return r>=4 ? "rgba(87,176,232,.9)" : r>=2 ? "rgba(242,169,59,.85)" : "rgba(95,184,110,.8)";
      }},
      label:{show:true,position:"top",fontSize:9,color:C_FROST}}]
  });
  charts.push(c);
}
function openEntryFromChart(){
  document.getElementById("btnEntry").click();
  return false;
}
/* ---- 内嵌录入（共用组件） ---- */
window.__ENTRY_ATHLETES__ = DATA.athletes.map(function(a){ return {name:a.name, coach:a.coach}; });
window.__onEntrySaved__ = function(rec){
  if(CUR && rec.athlete == (DATA.athletes.find(function(a){return a.subject_id==CUR;})||{}).name){
    drawTrainRec(rec.athlete);
    drawEntryTrends(rec.athlete);
  }
};
__ENTRY_JS__
document.getElementById("btnEntry").onclick = function(){
  document.getElementById("entryView").classList.add("show");
  document.body.style.overflow = "hidden";
  var sel = document.getElementById("athSel");
  var cur = DATA.athletes.find(function(a){ return a.subject_id == CUR; });
  if(cur && cur.name){ sel.value = cur.name; }
  ErenderList(); EupdateCnt();
};
document.getElementById("btnBack").onclick = function(){
  document.getElementById("entryView").classList.remove("show");
  document.body.style.overflow = "";
};
/* 导出 / 复制 / 导入（复用录入组件数据函数） */
function openModal(title, text, readonly){
  document.getElementById("modalTitle").textContent = title;
  var ta = document.getElementById("modalText");
  ta.value = text; ta.readOnly = readonly;
  document.getElementById("modal").classList.add("show");
}
document.getElementById("modalNo").onclick = function(){ document.getElementById("modal").classList.remove("show"); };
document.getElementById("modalCopy").onclick = function(){
  var ta = document.getElementById("modalText");
  ta.select();
  var ok = false;
  try{ ok = document.execCommand("copy"); }catch(e){}
  if(navigator.clipboard){ navigator.clipboard.writeText(ta.value).then(function(){ Etoast("已复制"); }); return; }
  Etoast(ok ? "已复制" : "复制失败");
};
document.getElementById("btnExport").onclick = function(){
  var all = Eload();
  if(!all.length){ Etoast("暂无数据可导出"); return; }
  var json = JSON.stringify(all, null, 1);
  var a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff"+json], {type:"application/json"}));
  a.download = "训练数据导出_"+Etoday()+".json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 800);
  Etoast("已导出 "+all.length+" 条");
};
document.getElementById("btnCopy").onclick = function(){
  var all = Eload();
  if(!all.length){ Etoast("暂无数据"); return; }
  openModal("复制数据（粘贴发回，即可入库）", JSON.stringify(all), true);
};
document.getElementById("btnImport").onclick = function(){
  openModal("粘贴数据以合并（JSON 文本）", "", false);
  document.getElementById("modalCopy").textContent = "合并导入";
  document.getElementById("modalCopy").onclick = function(){
    try{
      var arr = JSON.parse(document.getElementById("modalText").value);
      if(!Array.isArray(arr)) throw 0;
      var all = Eload(), seen = {};
      all.forEach(function(r){ seen[r.id]=1; });
      var added = 0;
      arr.forEach(function(r){ if(r && r.id && !seen[r.id]){ all.push(r); seen[r.id]=1; added++; } });
      EsaveAll(all); ErenderList(); EupdateCnt();
      document.getElementById("modal").classList.remove("show");
      Etoast("合并 "+added+" 条");
    }catch(e){ Etoast("格式不对，请检查 JSON"); }
    document.getElementById("modalCopy").textContent = "复制";
  };
};
initSidebar();
</script></body></html>
"""


def main():
    data = build_data()
    js = open(ECHARTS, encoding="utf-8").read()
    html = (HTML
            .replace("__ECHARTS__", js)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__ENTRY_HTML__", ENTRY_HTML)
            .replace("__ENTRY_JS__", ENTRY_JS)
            .replace("__N__", str(len(data["athletes"])))
            .replace("__META__", data["meta"]["built_at"]))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()

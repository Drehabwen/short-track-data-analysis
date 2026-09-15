# -*- coding: utf-8 -*-
"""单运动员画像分析报告生成器

用法：python build_athlete_analysis.py [姓名]   （默认使用示例运动员）
产出：最大摄氧量/<姓名>_画像分析.html（自包含，含 ECharts）
"""

import json
import os
import sqlite3
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\DEV\blood"
DB = os.path.join(ROOT, "blood.db")
OUT_DIR = os.path.join(ROOT, "最大摄氧量")
ECHARTS = r"D:\DEV\dashboard\echarts.min.js"

_C_RED = "#e05b4f"
_C_AMBER = "#f2a93b"
_C_ICE = "#38c3e0"
_C_FROST = "#9fb8c8"


def q(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def pct_rank(vals, v, higher=True):
    s = pd.Series(vals).dropna()
    if pd.isna(v) or s.empty:
        return None
    r = (s < v).mean() * 100
    return round(r if higher else 100 - r)


def collect(name):
    d = {}
    d["ath"] = q("SELECT * FROM athletes WHERE name=?", (name,))
    if d["ath"].empty:
        return None
    sid = d["ath"].iloc[0]["subject_id"]
    d["sid"] = sid
    d["hr"] = q(
        """SELECT date(datetime) d, session_name, session_type, avg_hr, max_hr,
                  z1,z2,z3,z4,z5, duration_min
           FROM hr_sessions WHERE subject_id=? ORDER BY datetime""", (sid,))
    d["cpet"] = q(
        """SELECT test_start, valid_class, vo2kg_peak, vo2kg_pctnorm,
                  slope_ve_vco2, vo2kg_vt1_pctmax, rer_peak, hr_peak, peak_wr
           FROM cpet_tests WHERE subject_id=? ORDER BY test_start""", (sid,))
    d["blood"] = q(
        """SELECT timepoint, analyte, result_value, unit
           FROM blood_markers WHERE subject_id=? ORDER BY timepoint""", (sid,))
    d["pre"] = q("SELECT * FROM pretest WHERE subject_id=?", (sid,))
    d["ac"] = q("SELECT * FROM acute_fatigue WHERE subject_id=?", (sid,))
    # 全队百分位
    all_cpet = q("SELECT name, vo2kg_peak FROM cpet_tests WHERE vo2kg_peak IS NOT NULL")
    all_cpet = all_cpet.sort_values("vo2kg_peak", ascending=False).drop_duplicates("name")
    all_pre = q("SELECT name, fms_total, cmj_height_cm FROM pretest")
    all_eyes = q("""SELECT name,
                    (COALESCE(ybt_eyes_closed_l,0)+COALESCE(ybt_eyes_closed_r,0))/2 AS eyes
                    FROM pretest WHERE ybt_eyes_closed_l IS NOT NULL""")
    all_ac = q("SELECT name, avg_power_w, peak_power_w, cmj_pre, vas_post, lactate_rest FROM acute_fatigue")
    vo2 = d["cpet"]["vo2kg_peak"].max()
    d["pct"] = {
        "vo2": pct_rank(all_cpet["vo2kg_peak"], vo2),
        "fms": pct_rank(all_pre["fms_total"], d["pre"].iloc[0]["fms_total"] if not d["pre"].empty else None),
        "cmj": pct_rank(all_pre["cmj_height_cm"], d["pre"].iloc[0]["cmj_height_cm"] if not d["pre"].empty else None),
        "pow": pct_rank(all_ac["avg_power_w"], d["ac"].iloc[0]["avg_power_w"] if not d["ac"].empty else None),
        "peak": pct_rank(all_ac["peak_power_w"], d["ac"].iloc[0]["peak_power_w"] if not d["ac"].empty else None),
        "vas": pct_rank(all_ac["vas_post"], d["ac"].iloc[0]["vas_post"] if not d["ac"].empty else None),
        "lac_rest": pct_rank(all_ac["lactate_rest"], d["ac"].iloc[0]["lactate_rest"] if not d["ac"].empty else None),
    }
    eyes_mean = None
    if not d["pre"].empty and pd.notna(d["pre"].iloc[0]["ybt_eyes_closed_l"]):
        eyes_mean = (d["pre"].iloc[0]["ybt_eyes_closed_l"] +
                     d["pre"].iloc[0]["ybt_eyes_closed_r"]) / 2
    d["pct"]["eyes"] = pct_rank(all_eyes["eyes"], eyes_mean)
    d["best_cpet"] = (None if d["cpet"].empty else
                      d["cpet"].sort_values("vo2kg_peak", ascending=False).iloc[0])
    return d


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>__NAME__ · 画像分析</title>
<style>
:root{--ink:#0b1e2d;--panel:#122b3d;--panel2:#0f2636;--ice:#eaf4fa;--frost:#9fb8c8;
  --line:#1e3b4f;--cyan:#38c3e0;--amber:#f2a93b;--red:#e05b4f;--ok:#4ec58b;
  --mono:'Cascadia Mono','Consolas',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;background:var(--ink);color:var(--ice);
  background-image:radial-gradient(1100px 500px at 85% -10%,rgba(56,195,224,.08),transparent 60%)}
.wrap{max-width:1080px;margin:0 auto;padding:24px 22px 60px}
.head{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:8px}
.head .nm{font-size:30px;font-weight:800;letter-spacing:3px}
.head .meta{font-size:13px;color:var(--frost);margin-top:4px}
.head .tag{font-size:11px;background:rgba(56,195,224,.15);color:var(--cyan);
  border:1px solid rgba(56,195,224,.4);border-radius:16px;padding:3px 12px}
.date{font-size:12px;color:#5d7889;margin-bottom:22px;font-family:var(--mono)}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}
.kpi{flex:1;min-width:140px;background:var(--panel);border:1px solid var(--line);
  border-left:3px solid var(--cyan);border-radius:10px;padding:11px 14px}
.kpi .v{font-size:21px;font-weight:800;font-family:var(--mono)}
.kpi .l{font-size:11px;color:var(--frost);margin-top:2px}
.kpi .d{font-size:10px;color:#5d7889;margin-top:1px}
.kpi.hot{border-left-color:var(--amber)}
.sec{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px;margin-bottom:18px}
.sec h2{font-size:15px;letter-spacing:2px;margin-bottom:4px;color:var(--ice)}
.sec h2 span{color:var(--cyan)}
.sec .sub{font-size:11px;color:#5d7889;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart{height:250px}
.insight{background:rgba(56,195,224,.07);border-left:3px solid var(--cyan);border-radius:4px;
  padding:9px 13px;font-size:12.5px;color:var(--frost);line-height:1.8;margin-top:12px}
.insight b{color:var(--ice)}
.adv{background:var(--panel2);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;margin-top:12px}
.adv .t{font-size:13px;font-weight:700;color:var(--cyan);margin-bottom:6px}
.adv ul{margin-left:18px;font-size:12.5px;line-height:2;color:var(--ice)}
.adv ul li b{color:var(--amber)}
.prob{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--red);
  border-radius:10px;padding:13px 16px;margin-top:10px}
.prob .t{font-size:13px;font-weight:700;color:#ff8b7f;margin-bottom:5px}
.prob .e{font-size:12px;color:var(--frost);line-height:1.9}
.prob .e b{color:var(--ice)}
.prob .r{font-size:11px;color:var(--amber);margin-top:4px}
.badge{display:inline-block;font-size:10px;border-radius:5px;padding:1px 7px;font-weight:700;margin-left:6px}
.badge.g{background:var(--ok);color:#0b1e2d}.badge.o{background:var(--amber);color:#0b1e2d}
.badge.r{background:var(--red);color:#fff}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
th,td{padding:6px 9px;border-bottom:1px solid rgba(30,59,79,.6);text-align:left}
th{color:var(--frost);font-size:11px;letter-spacing:.5px}
td b{font-family:var(--mono);color:var(--ice)}
@media (max-width:860px){.grid2{grid-template-columns:1fr}}
@media print{body{background:#fff}.sec{break-inside:avoid}}
</style>
<script>__ECHARTS__</script>
</head><body><div class="wrap">
<div class="head">
  <div><div class="nm">__NAME__ <span class="badge __CLS__">__CLS_TXT__</span></div>
  <div class="meta">__GENDER__ · __AGE__岁 · __COACH__组 · __INTERV__组 · __HEIGHT__cm / __WEIGHT__kg · BMI __BMI__</div></div>
  <span style="flex:1"></span>
  <span class="tag">画像分析报告</span>
</div>
<div class="date">编制日期 __DATE__ · 数据截至 2026-08-09</div>
<div class="kpis">
  <div class="kpi"><div class="v">__VO2__<small style="font-size:11px;color:#5d7889"> ml/kg/min</small></div><div class="l">__VO2_LBL__</div><div class="d">全队前 __VO2_PCT__% · 中位66</div></div>
  <div class="kpi"><div class="v">__FMS__</div><div class="l">FMS 总分</div><div class="d">全队前 __FMS_PCT__% · ≥30 优秀</div></div>
  <div class="kpi"><div class="v">__CMJ__ cm</div><div class="l">CMJ 纵跳</div><div class="d">全队前 __CMJ_PCT__%</div></div>
  <div class="kpi"><div class="v">__POW__ W</div><div class="l">造模平均功率</div><div class="d">全队前 __POW_PCT__% · __POW_D__</div></div>
  <div class="kpi __CK_HOT__"><div class="v">__CK__ U/L</div><div class="l">CK 72h</div><div class="d">基线 __CK_BL__ · __CK_D__</div></div>
</div>

<div class="sec"><h2>一、<span>有氧能力</span> CPET</h2>
  <div class="sub">__CPET_SUB__</div>
  <div class="chart" id="c_radar"></div>
  <div class="insight">__INS1__</div>
</div>

<div class="sec"><h2>二、<span>训练负荷</span> 心率监测</h2>
  <div class="sub">7 个监测场次 · 均心 __HR_AVG__ · 最高 __HR_MAX__ · Z4+Z5 占比 __HR_Z45__%</div>
  <div class="chart" id="c_hr"></div>
  <div class="insight">__INS2__</div>
</div>

<div class="sec"><h2>三、<span>前测体能</span> 基础动作与双侧对称性</h2>
  <div class="sub">FMS __FMS__（__FMS_LBL__）· CMJ __CMJ__cm · 重点看左右差异</div>
  <div class="grid2">
    <div class="chart" id="c_asym"></div>
    <div><table>
      <tr><th>指标</th><th>左</th><th>右</th><th>差异</th></tr>
      __ASYMTABLE__
    </table></div>
  </div>
  <div class="insight">__INS3__</div>
</div>

<div class="sec"><h2>四、<span>恢复状态</span> 血液与急性疲劳</h2>
  <div class="sub">__AC_SUB__</div>
  <div class="grid2">
    <div class="chart" id="c_blood"></div>
    <div class="chart" id="c_cmj"></div>
  </div>
  <div class="insight">__INS4__</div>
</div>

<div class="sec"><h2>五、<span>问题分析</span></h2>
  <div class="sub">基于当前数据的五大问题，按严重程度排序</div>
  __PROBLEMS__
</div>

<div class="sec"><h2>六、<span>训练建议</span></h2>
  __ADVICE__
</div>
</div>
<script>
var D = __DATA__;
var C_ICE="#38c3e0", C_FROST="#9fb8c8", C_LINE="#1e3b4f", C_AMBER="#f2a93b", C_OK="#4ec58b", C_RED="#e05b4f";
function baseText(){return {color:C_FROST,fontFamily:"'Microsoft YaHei',sans-serif",fontSize:11}}
function mk(id, opt){var el=document.getElementById(id);var c=echarts.init(el);c.setOption(opt);}
function tool(){return {textStyle:baseText()}}
// 雷达：五项能力百分位
mk("c_radar", Object.assign(tool(), {
  tooltip:{},
  radar:{indicator:[{name:"有氧能力",max:100},{name:"动作质量FMS",max:100},
    {name:"做功输出",max:100},{name:"恢复(CMJ)",max:100},{name:"平衡(闭眼站)",max:100}],
    radius:"62%",splitArea:{areaStyle:{color:["rgba(18,43,61,.6)","rgba(15,38,54,.6)"]}},
    splitLine:{lineStyle:{color:C_LINE}},axisLine:{lineStyle:{color:C_LINE}},axisName:{color:C_FROST}},
  series:[{type:"radar",data:[{value:D.radar,name:"全队百分位",
    areaStyle:{color:"rgba(56,195,224,.18)"},lineStyle:{color:C_ICE,width:2},itemStyle:{color:C_ICE},symbolSize:4}]}]
}));
// 心率场次
mk("c_hr", Object.assign(tool(), {
  tooltip:{trigger:"axis"},
  grid:{left:120,right:30,top:10,bottom:24},
  xAxis:{type:"value",name:"bpm",nameTextStyle:{color:C_FROST},axisLabel:{color:C_FROST}},
  yAxis:{type:"category",data:D.hrNames,axisLabel:{color:C_FROST,fontSize:10},axisLine:{lineStyle:{color:C_LINE}}},
  series:[{type:"bar",data:D.hrAvg,barMaxWidth:13,
    itemStyle:{color:function(p){return D.hrType[p.dataIndex]=="冰上"?"rgba(56,195,224,.85)":"rgba(95,176,110,.85)";}},
    label:{show:true,position:"right",fontSize:9,color:C_FROST}}]
}));
// 左右对比
mk("c_asym", Object.assign(tool(), {
  tooltip:{trigger:"axis"},
  legend:{top:0,textStyle:{color:C_FROST},data:["左","右"]},
  grid:{left:110,right:24,top:28,bottom:22},
  xAxis:{type:"value",axisLabel:{color:C_FROST,fontSize:9}},
  yAxis:{type:"category",data:D.asymNames,axisLabel:{color:C_FROST,fontSize:10}},
  series:[
    {name:"左",type:"bar",data:D.asymL,itemStyle:{color:"rgba(56,195,224,.8)"},barMaxWidth:11},
    {name:"右",type:"bar",data:D.asymR,itemStyle:{color:"rgba(242,169,59,.85)"},barMaxWidth:11,
     label:{show:true,position:"right",fontSize:9,color:C_FROST,formatter:function(p){return p.value;}}}
  ]
}));
// 血液趋势
mk("c_blood", Object.assign(tool(), {
  tooltip:{trigger:"axis"},
  legend:{top:0,textStyle:{color:C_FROST},data:D.bloodNames},
  grid:{left:38,right:14,top:30,bottom:22},
  xAxis:{type:"category",data:["基线","24H","72H"],axisLabel:{color:C_FROST},axisLine:{lineStyle:{color:C_LINE}}},
  yAxis:{type:"value",axisLabel:{color:C_FROST,fontSize:9},splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
  series:D.bloodSeries
}));
// CMJ 恢复
mk("c_cmj", Object.assign(tool(), {
  tooltip:{trigger:"axis"},
  title:{text:"CMJ 纵跳恢复",left:"center",top:0,textStyle:{color:C_FROST,fontSize:12}},
  grid:{left:34,right:14,top:34,bottom:22},
  xAxis:{type:"category",data:["前测","24h","72h"],axisLabel:{color:C_FROST},axisLine:{lineStyle:{color:C_LINE}}},
  yAxis:{type:"value",min:20,max:30,axisLabel:{color:C_FROST,fontSize:9},splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
  series:[{type:"line",data:D.cmj,markLine:{silent:true,symbol:"none",data:[{yAxis:D.cmj[0]}],
    lineStyle:{color:C_AMBER,type:"dashed",width:1},label:{show:true,formatter:"基线",color:C_AMBER,fontSize:9,position:"insideEndTop"}},
    symbolSize:7,itemStyle:{color:C_OK},lineStyle:{width:2.4},areaStyle:{color:"rgba(78,197,139,.12)"},
    label:{show:true,position:"top",fontSize:10,color:C_FROST,formatter:function(p){return p.value+" cm";}}}]
}));
</script></body></html>
"""


def fmt(v, d=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "示例运动员"
    d = collect(name)
    if d is None:
        print("未找到运动员:", name)
        return
    a = d["ath"].iloc[0]
    pre = d["pre"].iloc[0] if not d["pre"].empty else None
    ac = d["ac"].iloc[0] if not d["ac"].empty else None
    hr = d["hr"]
    best = d["best_cpet"]
    pct = d["pct"]
    # 有效性分级
    if best is None:
        cls, cls_txt = "r", "未测"
    elif best["valid_class"].startswith("有效"):
        cls, cls_txt = "g", "有效"
    elif best["valid_class"].startswith("亚极量"):
        cls, cls_txt = "o", "亚极量"
    else:
        cls, cls_txt = "r", "无效"
    # 血液
    blood = d["blood"]
    ck = blood[blood["analyte"] == "ck"]
    ck_bl = ck[ck["timepoint"] == "BL"]["result_value"].iloc[0] if not ck[ck["timepoint"] == "BL"].empty else None
    ck_72 = ck[ck["timepoint"] == "72H"]["result_value"].iloc[0] if not ck[ck["timepoint"] == "72H"].empty else None
    cort = blood[blood["analyte"] == "cortisol"]
    ldh = blood[blood["analyte"] == "ldh"]
    def series_rows(an):
        sub = blood[blood["analyte"] == an].set_index("timepoint")
        return [sub.loc[tp, "result_value"] if tp in sub.index else None for tp in ["BL", "24H", "72H"]]
    # 心率
    hr_names = hr["session_name"].tolist()
    hr_avg = [None if pd.isna(x) else round(x, 1) for x in hr["avg_hr"]]
    hr_type = hr["session_type"].tolist()
    # 左右对比
    asym = []
    if pre is not None:
        pairs = [
            # YBT 列名是"摆动腿"，有效读数是支撑腿：摆动腿左=右腿支撑
            ("YBT前伸·左腿支撑(cm)", pre["ybt_right_ant"], pre["ybt_left_ant"]),
            ("闭眼单脚站(s)", pre["ybt_eyes_closed_l"], pre["ybt_eyes_closed_r"]),
            ("踝背屈ROM(°)", pre["rom_ankle_dorsi_l"], pre["rom_ankle_dorsi_r"]),
            ("单腿跳(cm)", pre["jump_single_l"], pre["jump_single_r"]),
            ("三连跳(cm)", pre["jump_triple_l"], pre["jump_triple_r"]),
        ]
        for nm2, l, r in pairs:
            dl = "" if pd.isna(l) else f"{float(l):.1f}" if isinstance(l, float) else str(l)
            dr = "" if pd.isna(r) else f"{float(r):.1f}" if isinstance(r, float) else str(r)
            diff = "-"
            if not pd.isna(l) and not pd.isna(r) and float(r) > 0:
                pct_d = abs(float(r) - float(l)) / max(float(r), float(l)) * 100
                diff = f"{pct_d:.0f}%"
            asym.append((nm2, dl, dr, diff))
    asym_table = "".join(
        f"<tr><td>{n}</td><td><b>{l}</b></td><td><b>{r}</b></td><td>{df}</td></tr>"
        for n, l, r, df in asym)
    # 雷达
    recov = 50
    if ac is not None and not pd.isna(ac["cmj_pre"]) and not pd.isna(ac["cmj_72h"]):
        recov = 50 + (ac["cmj_72h"] / ac["cmj_pre"] - 1) * 500
        recov = max(0, min(100, recov))
    radar = {
        "有氧能力": pct["vo2"], "动作质量FMS": pct["fms"],
        "做功输出": pct["peak"], "恢复(CMJ)": round(recov),
        "平衡(闭眼站)": pct["eyes"] if pct["eyes"] is not None else 40,
    }
    hr_avg_v = round(hr["avg_hr"].mean(), 1) if len(hr) else None
    hr_max_v = int(hr["max_hr"].max()) if len(hr) else None
    hr_z45 = round((hr["z4"].mean() + hr["z5"].mean()), 1) if len(hr) else None
    vo2_v = best["vo2kg_peak"] if best is not None else None
    def nv(v, d=1):
        return "-" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{d}f}"
    tests = d["cpet"]
    n_invalid = int(tests["valid_class"].str.startswith("无效").sum()) if not tests.empty else 0
    n_sub = int(tests["valid_class"].str.startswith("亚极量").sum()) if not tests.empty else 0
    n_valid = int(tests["valid_class"].str.startswith("有效").sum()) if not tests.empty else 0
    bmi = (a["weight_kg"] / (a["height_cm"] / 100) ** 2) if a["height_cm"] else None
    vo2_pct_v = pct["vo2"]

    # 左右不对称数据
    def num(x):
        return None if pre is None or pd.isna(pre[x]) else float(pre[x])
    eyes_l, eyes_r = num("ybt_eyes_closed_l"), num("ybt_eyes_closed_r")
    rom_l, rom_r = num("rom_ankle_dorsi_l"), num("rom_ankle_dorsi_r")
    ybt_l, ybt_r = num("ybt_right_ant"), num("ybt_left_ant")
    jump_l, jump_r = num("jump_single_l"), num("jump_single_r")
    triple_l, triple_r = num("jump_triple_l"), num("jump_triple_r")

    def gap(a, b):
        if a is None or b is None or max(a, b) == 0:
            return None
        return abs(a - b) / max(a, b) * 100

    eye_gap = gap(eyes_l, eyes_r)
    rom_gap = None if rom_l is None or rom_r is None else abs(rom_l - rom_r)
    ybt_gap = gap(ybt_l, ybt_r)
    weak_side = None
    if eyes_l is not None and eyes_r is not None:
        weak_side = "右" if eyes_r < eyes_l else "左"
    asym_big = (eye_gap is not None and eye_gap >= 25) or \
               (rom_gap is not None and rom_gap >= 10) or \
               (ybt_gap is not None and ybt_gap >= 10)

    ck_ratio = (ck_72 / ck_bl) if ck_72 is not None and ck_bl else None
    hrv_missing = ac is None or pd.isna(ac["hrv_sdnn"])
    lac_post_missing = pre is None or pd.isna(pre["lactate_post0"])
    lac_rest = float(ac["lactate_rest"]) if ac is not None and pd.notna(ac["lactate_rest"]) else None
    cmj_seq = [ac["cmj_pre"], ac["cmj_24h"], ac["cmj_72h"]] if ac is not None else []
    cmj72_pct = None
    if len(cmj_seq) == 3 and cmj_seq[0]:
        cmj72_pct = (cmj_seq[2] / cmj_seq[0] - 1) * 100

    # ============ 动态问题分析 ============
    probs = []
    # ① 有氧
    if best is not None and vo2_pct_v is not None and vo2_pct_v < 45:
        probs.append(("有氧能力偏弱（全队后段）",
                      f"相对摄氧量 <b>{nv(vo2_v)}</b>（全队前 {vo2_pct_v}%，中位 66）；"
                      f"体重 {nv(a['weight_kg'])}kg / BMI {nv(bmi)}。",
                      "影响：长距离供能与高强度维持受限，需复测+训练双管齐下。"))
    if best is not None and (n_invalid or n_sub):
        probs.append(("CPET 测试质量未达有效标准",
                      f"{n_invalid} 次无效 + {n_sub} 次亚极量，最优为「{best['valid_class']}」；"
                      f"真实峰值摄氧量可能更高或更低，结论有不确定性。",
                      "影响：有氧数据只能作参考下限，复测前不据此下训练定论。"))
    if best is None:
        probs.append(("缺少有效有氧数据",
                      "暂无 CPET 有效测试。",
                      "影响：有氧能力无法评估，建议尽快安排测试。"))
    # ② 强度
    if hr_z45 is not None and hr_z45 < 5:
        probs.append(("训练强度结构失衡——高强度暴露不足",
                      f"{len(hr)} 场监测 Z4+Z5 仅 <b>{nv(hr_z45)}%</b>（均心 {nv(hr_avg_v)} bpm，最高 {hr_max_v} bpm）。",
                      "影响：专项高强度供能刺激不足，与有氧发展受限互相印证。"))
    # ③ 不对称
    if asym_big:
        side = weak_side or "一侧"
        probs.append((f"左右功能不对称（{side}侧偏弱）",
                      f"闭眼单脚站 左 {nv(eyes_l,0)}s vs 右 <b>{nv(eyes_r,0)}s</b>；"
                      f"踝背屈 ROM 左 {nv(rom_l,0)}° vs 右 <b>{nv(rom_r,0)}°</b>；"
                      f"YBT 前伸 左支撑 {nv(ybt_l,0)} vs 右支撑 <b>{nv(ybt_r,0)}</b>。",
                      "影响：单侧稳定性/活动度不足，急转急停场景扭伤风险高。"))
    # ④ 恢复
    if ck_ratio is not None and ck_72 is not None and ck_ratio >= 2:
        probs.append(("恢复偏慢（72h 肌肉酶未回落）",
                      f"CK {nv(ck_bl,0)}→{nv(ck_72,0)} U/L（72h 为基线 {ck_ratio:.1f} 倍）"
                      f"{'; CMJ 72h ' + ('+' if cmj72_pct and cmj72_pct>0 else '') + nv(cmj72_pct,1) + '%' if cmj72_pct is not None else ''}。",
                      "影响：主客观恢复不一致，需补 HRV 并观察下一周期。"))
    if cmj72_pct is not None and cmj72_pct <= -10:
        probs.append(("CMJ 72h 未恢复（仍低于基线）",
                      f"CMJ {nv(cmj_seq[0])}→{nv(cmj_seq[1])}→{nv(cmj_seq[2])}cm（72h {cmj72_pct:.1f}%），"
                      "跳跃功能 72h 仍未回到基线。",
                      "影响：提示恢复不足或训练后疲劳累积，建议减量并加强恢复。"))
    if hrv_missing:
        probs.append(("HRV 恢复数据缺失",
                      "无 SDNN/RMSSD 记录，自主神经恢复无法评估。",
                      "影响：是否可上强度只能靠主观判断。"))
    # ⑤ 数据缺口
    gaps = []
    if n_invalid or (best is not None and best["valid_class"].startswith("亚极量")):
        gaps.append("CPET 未达有效")
    if lac_post_missing:
        gaps.append("血乳酸运动后缺失")
    if hrv_missing:
        gaps.append("HRV 未测")
    if gaps:
        probs.append(("关键数据缺口",
                      "；".join(gaps) + "。",
                      "影响：建议补齐后再细化训练处方。"))

    problems_html = "".join(
        f'<div class="prob"><div class="t">{"①②③④⑤⑥"[i]}</div>'
        f'<div class="e"><b>{t}</b>：{e}</div><div class="r">▸ {r}</div></div>'
        for i, (t, e, r) in enumerate(probs[:6]))

    # ============ 动态洞察 ============
    if best is None:
        ins1 = "暂无有效 CPET 数据，建议尽快安排测试。"
        cpet_sub = "暂无测试记录"
    else:
        parts2 = []
        if n_invalid:
            parts2.append(f"{n_invalid} 次无效")
        if n_sub:
            parts2.append(f"{n_sub} 次亚极量")
        if n_valid:
            parts2.append(f"{n_valid} 次有效")
        cpet_sub = "·".join(parts2) or "1 次测试"
        cpet_sub += "，最优为「" + best["valid_class"] + "」"
        ins1 = (f"相对摄氧量 <b>{nv(best['vo2kg_peak'])}</b>（全队前 {vo2_pct_v}% · 中位 66），"
                f"预测达成率 <b>{nv(best['vo2kg_pctnorm'],0)}%</b>、VT1 占峰值 <b>{nv(best['vo2kg_vt1_pctmax'],0)}%</b>、"
                f"峰值功率 <b>{nv(best['peak_wr'],0)}W</b>。")
        if best["valid_class"].startswith("亚极量"):
            ins1 += "本次为亚极量，真实最大值可能更高。"
        if n_invalid:
            ins1 += f"另有 {n_invalid} 次无效测试，建议复测确认。"

    if len(hr):
        max_r = hr.loc[hr["max_hr"].idxmax()]
        ins2 = f"{len(hr)} 场监测平均心率 <b>{nv(hr_avg_v)}</b> bpm，Z4+Z5 合计 <b>{nv(hr_z45)}%</b>"
        if hr_z45 is not None and hr_z45 < 5:
            ins2 += (f"；最高 {hr_max_v} bpm 出现在 {max_r['d']}（{max_r['session_name']}）。"
                     "高强度暴露不足，建议逐步补充 Z4 间歇。")
        else:
            ins2 += "，强度结构较均衡。"
    else:
        ins2 = "暂无心率监测记录，建议补测。"

    if pre is not None:
        ins3 = (f"FMS <b>{nv(pre['fms_total'],0)}</b>（全队前 {pct['fms']}%）· "
                f"CMJ {nv(pre['cmj_height_cm'])}cm（前 {pct['cmj']}%）")
        if asym_big:
            ins3 += (f"。左右差异明显（闭眼站 左{nv(eyes_l,0)}/右{nv(eyes_r,0)}s、"
                     f"踝ROM 左{nv(rom_l,0)}/右{nv(rom_r,0)}°），{weak_side or '一侧'}侧稳定性偏弱，"
                     "建议优先纠正，降低扭伤风险。")
        else:
            ins3 += "，左右对称性良好。"
    else:
        ins3 = "暂无前测数据。"

    if ac is not None:
        parts = [f"干预：{ac['intervention'] or '-'} · 造模负荷 {nv(ac['load_pct'],0)}% · "
                 f"峰值功率 {nv(ac['peak_power_w'],0)}W（前 {pct['peak']}%）"]
        if cmj72_pct is not None:
            parts.append(f"CMJ {nv(cmj_seq[0])}→{nv(cmj_seq[1])}→<b>{nv(cmj_seq[2])}cm"
                         f"（72h {'+' if cmj72_pct>0 else ''}{cmj72_pct:.1f}%）")
        if ck_72 is not None:
            parts.append(f"CK 72h <b>{nv(ck_72,0)}</b>（基线 {ck_ratio:.1f} 倍）")
        ins4 = "；".join(parts) + "。"
        if cmj72_pct is not None and cmj72_pct >= 0 and ck_ratio is not None and ck_ratio >= 2:
            ins4 += "功能恢复与酶学恢复不一致（CMJ 已回弹但 CK 未回落），建议补 HRV 持续观察。"
        ac_sub = (f"{ac['intervention'] or '-'} · 造模负荷 {nv(ac['load_pct'],0)}% · "
                  f"峰值功率 {nv(ac['peak_power_w'],0)}W（前 {pct['peak']}%）")
    else:
        ins4 = "暂无急性疲劳实验数据。"
        ac_sub = "暂无急性疲劳实验数据"

    # ============ 动态训练建议 ============
    adv = []
    if best is not None and (vo2_pct_v is not None and vo2_pct_v < 55 or n_invalid or n_sub):
        bmi_txt = f"（BMI {nv(bmi)} → 目标 20 以下）" if bmi and bmi >= 20 else ""
        adv.append(("有氧能力提升（6-8 周）",
                    f"<li>每周 <b>2-3 次 Zone2 有氧</b>（心率 120-140 bpm）30-40 分钟；</li>"
                    f"<li>1 个月后<b>复测 CPET</b>（当前未达有效标准），关注体重/体脂 {bmi_txt}；</li>"
                    "<li>每节课带心率，保证每周冰上+陆地各至少 1 次监测。</li>"))
    if asym_big:
        side_cn = "右" if weak_side == "右" else "左"
        adv.append((f"{side_cn}侧稳定性纠正（每天 10 分钟）",
                    f"<li>{side_cn}踝背屈拉伸：弓步压踝 <b>3×30s</b>（当前 {nv(rom_l,0)}° vs {nv(rom_r,0)}°）；</li>"
                    f"<li>{side_cn}腿单脚平衡：睁眼 60s → 闭眼 30s 进阶，每周 4-5 次；</li>"
                    f"<li>{side_cn}侧提踵/单腿跳 30-50 次/天，逐步缩小左右差。</li>"))
    if hr_z45 is not None and hr_z45 < 5:
        adv.append(("高强度训练量补充",
                    f"<li>每周 <b>1-2 次 Z4 间歇</b>（如 4×30s 冲刺 + 2min 恢复），"
                    f"把 Z4+Z5 从 {nv(hr_z45)}% 提到 5-10%；</li>"
                    "<li>安排在状态好的训练日，避免与恢复课相邻。</li>"))
    adv.append(("恢复管理",
               "<li>训练后即刻冷身/拉伸；<b>CK≥500 U/L 次日减量</b>；</li>"
               "<li>每周晨起测 <b>2 次 HRV</b>" + ("（当前缺失）" if hrv_missing else "") + "，结合睡眠 7-8h 判断恢复；</li>"
               + (f"<li>静息乳酸 {nv(lac_rest)} 偏高，注意测试前状态与睡眠。</li>" if lac_rest is not None and lac_rest > 6 else "")))
    if gaps:
        adv.append(("数据补齐（1 周内）",
                    "<li>" + "；".join(gaps) + "。</li><li>补齐后再细化强度阈值处方。</li>"))
    cn_num = "①②③④⑤⑥"
    advice_html = "".join(
        f'<div class="adv"><div class="t">{cn_num[i]} {t}</div><ul>{items}</ul></div>'
        for i, (t, items) in enumerate(adv))
    data = {
        "radar": [radar["有氧能力"], radar["动作质量FMS"], radar["做功输出"], radar["恢复(CMJ)"], radar["平衡(闭眼站)"]],
        "hrNames": hr_names, "hrAvg": hr_avg, "hrType": hr_type,
        "asymNames": [x[0] for x in asym],
        "asymL": [float(x[1]) if x[1] != "-" else None for x in asym],
        "asymR": [float(x[2]) if x[2] != "-" else None for x in asym],
        "bloodNames": ["CK", "皮质醇", "LDH"],
        "bloodSeries": [
            {"name": "CK", "type": "line", "data": series_rows("ck"),
             "itemStyle": {"color": _C_RED}, "symbolSize": 5,
             "label": {"show": True, "position": "top", "fontSize": 9, "color": _C_FROST}},
            {"name": "皮质醇", "type": "line", "data": series_rows("cortisol"),
             "itemStyle": {"color": _C_AMBER}, "symbolSize": 5},
            {"name": "LDH", "type": "line", "data": series_rows("ldh"),
             "itemStyle": {"color": _C_ICE}, "symbolSize": 5},
        ],
        "cmj": [ac["cmj_pre"], ac["cmj_24h"], ac["cmj_72h"]] if ac is not None else [],
    }
    html = (HTML
            .replace("__ECHARTS__", open(ECHARTS, encoding="utf-8").read())
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__NAME__", name)
            .replace("__CLS__", cls).replace("__CLS_TXT__", cls_txt)
            .replace("__GENDER__", str(a["gender"] or "男/女"))
            .replace("__AGE__", fmt(a["age"]))
            .replace("__COACH__", str(a["coach"] or "-"))
            .replace("__INTERV__", str(a["intervention"] or "-"))
            .replace("__HEIGHT__", fmt(a["height_cm"]))
            .replace("__WEIGHT__", fmt(a["weight_kg"]))
            .replace("__BMI__", fmt(a["weight_kg"] / (a["height_cm"] / 100) ** 2) if a["height_cm"] else "-")
            .replace("__DATE__", pd.Timestamp.now().strftime("%Y-%m-%d"))
            .replace("__VO2__", fmt(vo2_v))
            .replace("__VO2_LBL__", "相对摄氧量（" + (cls_txt or "未测") + "）")
            .replace("__VO2_PCT__", str(pct["vo2"] if pct["vo2"] is not None else "-"))
            .replace("__FMS__", fmt(pre["fms_total"]) if pre is not None else "-")
            .replace("__FMS_PCT__", str(pct["fms"] if pct["fms"] is not None else "-"))
            .replace("__FMS_LBL__", ("优" if pre is not None and pd.notna(pre["fms_total"]) and pre["fms_total"] >= 30
                                     else "中" if pre is not None and pd.notna(pre["fms_total"]) and pre["fms_total"] >= 24
                                     else "关注" if pre is not None else "-"))
            .replace("__CMJ__", fmt(pre["cmj_height_cm"]) if pre is not None else "-")
            .replace("__CMJ_PCT__", str(pct["cmj"] if pct["cmj"] is not None else "-"))
            .replace("__POW__", fmt(ac["avg_power_w"], 0) if ac is not None else "-")
            .replace("__POW_PCT__", str(pct["pow"] if pct["pow"] is not None else "-"))
            .replace("__POW_D__", ("输出能力强" if pct["pow"] is not None and pct["pow"] >= 70 else
                                   "输出中等" if pct["pow"] is not None else "-"))
            .replace("__PEAK__", fmt(ac["peak_power_w"], 0) if ac is not None else "-")
            .replace("__PEAK_PCT__", str(pct["peak"] if pct["peak"] is not None else "-"))
            .replace("__CK__", fmt(ck_72, 0) if ck_72 is not None else "-")
            .replace("__CK_BL__", fmt(ck_bl, 0) if ck_bl is not None else "-")
            .replace("__CK_D__", ("未回落" if ck_ratio is not None and ck_ratio >= 2
                                  else "已回落" if ck_ratio is not None and ck_ratio < 2 else "-"))
            .replace("__CK_HOT__", "hot" if ck_ratio is not None and ck_ratio >= 2 else "")
            .replace("__HR_AVG__", fmt(hr_avg_v))
            .replace("__HR_MAX__", str(hr_max_v or "-"))
            .replace("__HR_Z45__", fmt(hr_z45))
            .replace("__CPET_SUB__", cpet_sub)
            .replace("__INS1__", ins1)
            .replace("__INS2__", ins2)
            .replace("__INS3__", ins3)
            .replace("__INS4__", ins4)
            .replace("__AC_SUB__", ac_sub)
            .replace("__PROBLEMS__", problems_html)
            .replace("__ADVICE__", advice_html)
            .replace("__ASYMTABLE__", asym_table))
    out = os.path.join(OUT_DIR, f"{name}_画像分析.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", out, f"({os.path.getsize(out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()

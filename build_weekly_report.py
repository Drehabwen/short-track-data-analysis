# -*- coding: utf-8 -*-
"""生成数据采集与分析周报（自包含交互 HTML，ECharts 内嵌，覆盖全部数据域）。"""
import json
import os

import pandas as pd

BASE = r"D:\DEV\blood"
ECHARTS = r"D:\DEV\dashboard\echarts.min.js"
OUT = os.path.join(BASE, "数据采集与分析周报_0727-0821.html")
CPET_DIR = r"D:\DEV\blood\最大摄氧量\最大摄氧量数据"
HR_DIR = r"D:\DEV\blood\心率"

stats = json.load(open(os.path.join(BASE, "weekly_stats.json"), encoding="utf-8"))
uni = json.load(open(os.path.join(BASE, "unified_stats.json"), encoding="utf-8"))
cpet = pd.read_csv(os.path.join(CPET_DIR, "cpet_enriched.csv"), encoding="utf-8-sig")
cpet["start"] = pd.to_datetime(cpet["start"])
cpet["date"] = cpet["start"].dt.date.astype(str)


def cls(r):
    if pd.isna(r["V'O2/kg_peak"]) or not r.get("has_exercise", False):
        return "无效"
    if pd.notna(r.get("exercise_dur_s", None)) and r["exercise_dur_s"] < 180:
        return "无效"
    if pd.notna(r["meas_max_rer"]):
        if r["meas_max_rer"] >= 1.05:
            return "有效"
        if r["meas_max_rer"] >= 1.00:
            return "亚极量"
    return "亚极量"


cpet["cls"] = cpet.apply(cls, axis=1)
order = {"有效": 0, "亚极量": 1, "无效": 2}
cpet["_k"] = cpet.apply(
    lambda r: (order[r["cls"]], -r["V'O2/kg_peak"] if pd.notna(r["V'O2/kg_peak"]) else 1e9),
    axis=1)
best = cpet.sort_values("_k").drop_duplicates("name", keep="first")
valid = best[best["cls"] != "无效"]

hr_prof = pd.read_csv(os.path.join(HR_DIR, "hr_profile.csv"), encoding="utf-8-sig")
pre = pd.read_csv(r"D:\DEV\blood\统一数据集\前测明细表.csv", encoding="utf-8-sig")

outputs = [
    ("论文级统一数据集", "统一数据集/统一数据集_受试者主表.csv", "77 人 × 105 字段（实验+恢复+血液+前测+心率整合）"),
    ("数据完整性矩阵", "统一数据集/数据完整性矩阵.csv", "36 个数据域按人评估完整率"),
    ("整合报告", "统一数据集/整合报告.md", "链接概况/异名归一/完整率/缺口说明"),
    ("最大摄氧量交互分析仪表盘", "最大摄氧量/最大摄氧量数据/最大摄氧量深度分析.html", "CPET+心率联合交互分析"),
    ("最大摄氧量深度分析 Excel", "最大摄氧量/最大摄氧量数据/最大摄氧量深度分析.xlsx", "11 个 Sheet 完整统计"),
    ("CPET 清洗数据", "最大摄氧量/最大摄氧量数据/cpet_enriched.csv", "66 份测试结构化提取（含 08-06/07 新批次）"),
    ("教练版简报表", "心率/心率简报表_教练版_0728-0730.html", "17 板块，含教练C复合场次拆分"),
    ("心率周对比", "心率/心率周对比_上周vs本周.html", "上周 vs 本周（按 15:22 拆分修正）"),
    ("心率数据大屏", "心率/心率大屏_精美版.html", "教练画像/热力图/强度对比"),
    ("心率画像汇总", "心率/hr_profile.csv", "50 场次全量解析，每人 HRmax/区间/训练量"),
    ("血液数据包", "blood_reports_package_20260726", "0713 血液报告图片 + 复核版数据表"),
    ("教练C分段模块", "zhang_split.py", "复合场次 15:22 拆分，TRIMP 口径统一"),
]

blood_curve = uni["blood_analytes"]
cmj_med = {}
master = pd.read_csv(r"D:\DEV\blood\统一数据集\统一数据集_受试者主表.csv", encoding="utf-8-sig")
for col in ["cmj_pre", "cmj_24h", "cmj_72h"]:
    v = pd.to_numeric(master[col], errors="coerce").dropna()
    cmj_med[col] = round(float(v.median()), 1) if len(v) else None
fms = [round(float(v)) for v in pd.to_numeric(pre["fms_total"], errors="coerce").dropna()]

# 干预三组恢复曲线
GRP_MAP = {"ck": ["blood_ck_BL", "blood_ck_24H", "blood_ck_72H"],
           "cmj": ["cmj_pre", "cmj_24h", "cmj_72h"],
           "hr": ["hr_rest_avg", "hr_24h_avg", "hr_72h_avg"]}
grp = {}
for key, cols in GRP_MAP.items():
    grp[key] = {}
    for g in ["拔罐+推拿", "艾灸+推拿", "常规恢复"]:
        sub = master[master["intervention"] == g]
        grp[key][g] = [round(float(pd.to_numeric(sub[c], errors="coerce").mean()), 1)
                       if pd.to_numeric(sub[c], errors="coerce").notna().any() else None
                       for c in cols]

# 8/11 之后新增训练场次（按日聚合，来自系统心率库）
import sqlite3
_con = sqlite3.connect(r"D:\DEV\blood\blood_reports_package_20260726-141357\outputs\dist\blood.db")
_cur = _con.cursor()
_cur.execute("""
SELECT date(datetime) d, COUNT(*) n, ROUND(AVG(avg_hr),1), MAX(max_hr),
       ROUND(AVG(z4)+AVG(z5),1)
FROM hr_sessions WHERE datetime >= '2026-08-11'
GROUP BY datetime ORDER BY datetime
""")
new_sess = [{"date": r[0][5:], "n": r[1], "avg": r[2], "mx": r[3], "z45": r[4]} for r in _cur.fetchall()]
_con.close()

data = {
    "stats": stats, "uni": uni,
    "vo2kg_dist": sorted([round(float(v)) for v in valid["V'O2/kg_peak"].dropna()]),
    "gender": {
        "male": [round(float(v)) for v in valid[valid["gender"] == "男性"]["V'O2/kg_peak"].dropna()],
        "female": [round(float(v)) for v in valid[valid["gender"] == "女性"]["V'O2/kg_peak"].dropna()],
    },
    "rank": [{"name": r["name"], "vo2kg": round(float(r["V'O2/kg_peak"])),
              "pct": round(float(r["V'O2/kg_peak_pctnorm"])), "rer": round(float(r["meas_max_rer"]), 2),
              "cls": r["cls"]}
             for _, r in valid.sort_values("V'O2/kg_peak", ascending=False).iterrows()],
    "rer": [round(float(v), 2) for v in best["meas_max_rer"].dropna()],
    "cls_cnt": cpet["cls"].value_counts().to_dict(),
    "cpet_dates": cpet.groupby("date")["file"].count().to_dict(),
    "hr_prof": [{"name": r["athlete"], "sess": int(r["n_sessions"]), "min": round(float(r["total_min"])),
                 "max": int(r["max_hr"]), "z": [round(float(r[f"z{i}"]), 1) for i in range(1, 6)],
                 "z45": round(float(r["z45"]), 1)}
                for _, r in hr_prof.sort_values("z45", ascending=False).iterrows()],
    "intv": uni["interventions"],
    "groups": uni["groups"],
    "cmj": cmj_med,
    "hr_rec": {k: uni[k] for k in ["hr_rest_avg", "hr_post_avg", "hr_24h_avg", "hr_72h_avg"]},
    "lactate": {k: uni[k] for k in ["lactate_rest", "lactate_post", "lactate_interv"]},
    "blood": blood_curve,
    "grp": grp,
    "fms": fms,
    "comp": uni["completeness"],
    "new_sess": new_sess,
    "cross": [
        {"name": "运动员A", "z45": 53.0, "vo2kg": 60},
        {"name": "运动员B", "z45": 37.0, "vo2kg": 34},
        {"name": "运动员D", "z45": 28.5, "vo2kg": 71},
        {"name": "运动员E", "z45": 24.0, "vo2kg": 81},
        {"name": "运动员C", "z45": 19.0, "vo2kg": 46},
        {"name": "朴灿曦", "z45": 19.0, "vo2kg": 73},
        {"name": "运动员F", "z45": 18.5, "vo2kg": 91},
        {"name": "郑军令", "z45": 15.5, "vo2kg": 72},
        {"name": "姜童", "z45": 15.0, "vo2kg": 61},
        {"name": "程伟豪", "z45": 13.0, "vo2kg": 77},
        {"name": "陈米可", "z45": 12.0, "vo2kg": 77},
        {"name": "关子依", "z45": 11.0, "vo2kg": 58},
        {"name": "周孟轩", "z45": 7.0, "vo2kg": 66},
        {"name": "曲欣妍", "z45": 2.0, "vo2kg": 80},
        {"name": "王紫溪", "z45": 1.0, "vo2kg": 64},
    ],
    "outputs": outputs,
}

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
echarts_js = open(ECHARTS, encoding="utf-8").read()

html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数据采集与分析周报 · 2026.07–08</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#F2F5F8; color:#22303C; }
  .hero { background:linear-gradient(120deg,#0F2A44,#1F4E79 55%,#2E6DA4); color:#fff; padding:30px 32px 24px; }
  .hero h1 { margin:0; font-size:26px; letter-spacing:1px; }
  .hero .sub { opacity:.85; font-size:13px; margin-top:6px; }
  .hero .tags { margin-top:12px; display:flex; gap:8px; flex-wrap:wrap; }
  .hero .tag { background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25);
               border-radius:14px; padding:3px 12px; font-size:12px; }
  .wrap { max-width:1240px; margin:0 auto; padding:20px 22px 80px; }
  .kpis { display:flex; gap:12px; flex-wrap:wrap; margin:18px 0; }
  .kpi { flex:1; min-width:140px; background:#fff; border:1px solid #E3E8EE; border-radius:10px; padding:14px 16px; }
  .kpi .v { font-size:25px; font-weight:700; color:#1F4E79; }
  .kpi .l { font-size:12.5px; color:#55606B; margin-top:2px; }
  .kpi .s { font-size:11.5px; color:#8A94A0; margin-top:1px; }
  h2 { font-size:19px; border-left:4px solid #1F4E79; padding-left:10px; margin:36px 0 12px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  @media (max-width:960px) { .grid { grid-template-columns:1fr; } }
  .fig { background:#fff; border:1px solid #E3E8EE; border-radius:10px; padding:8px; }
  .fig .chart { width:100%; height:340px; }
  .chart.tall { height:460px; }
  .card { background:#fff; border:1px solid #E3E8EE; border-radius:10px; padding:16px 18px; margin-top:14px; }
  table { border-collapse:collapse; width:100%; font-size:12.5px; }
  th { background:#1F4E79; color:#fff; padding:7px 9px; text-align:left; }
  td { border-bottom:1px solid #EDF0F3; padding:6px 9px; }
  tr:nth-child(even) td { background:#F8FAFC; }
  .tl { position:relative; padding-left:22px; }
  .tl::before { content:""; position:absolute; left:6px; top:4px; bottom:4px; width:2px; background:#C7D3DE; }
  .tl-item { position:relative; padding:6px 0 13px; }
  .tl-item::before { content:""; position:absolute; left:-19px; top:10px; width:9px; height:9px;
                     border-radius:50%; background:#1F4E79; }
  .tl-date { font-weight:700; color:#1F4E79; font-size:13px; }
  .tl-desc { font-size:13px; color:#3D4852; line-height:1.65; }
  .note { background:#FFF8E6; border:1px solid #F0DC9E; border-radius:8px; padding:11px 15px;
          font-size:12.5px; line-height:1.7; color:#6B5317; margin:12px 0; }
  .warn { background:#FDECEA; border:1px solid #F2C1BB; border-radius:8px; padding:11px 15px;
          font-size:12.5px; line-height:1.7; color:#8C3B33; margin:12px 0; }
  .ok { background:#EAF6EF; border:1px solid #B9DFC9; border-radius:8px; padding:11px 15px;
        font-size:12.5px; line-height:1.7; color:#24613B; margin:12px 0; }
</style></head><body>
<div class="hero">
  <h1>数据采集与分析周报</h1>
  <div class="sub">七台河短道速滑队 · 2026.07–08 · 急性疲劳与干预恢复研究 + 训练心率监测 + 最大摄氧量测试 + 前测素质</div>
  <div class="tags"><span class="tag">77 人研究队列</span><span class="tag">89 人前测素质</span>
    <span class="tag">810 条血液化验</span><span class="tag">__S_HR__ 个训练场次</span>
    <span class="tag">66 份 CPET</span><span class="tag">173.6 万心率点</span></div>
</div>
<div class="wrap">
  <div class="kpis">
    <div class="kpi"><div class="v">__U_N__</div><div class="l">研究队列</div><div class="s">男/女 · C/L/Y/Z 四组</div></div>
    <div class="kpi"><div class="v">__U_PRE__</div><div class="l">前测素质人数</div><div class="s">FMS/YBT/CMJ/ROM/力台</div></div>
    <div class="kpi"><div class="v">__U_BLD__</div><div class="l">血液化验条数</div><div class="s">__U_BLDS__ 人 · 5 项指标 × BL/24h/72h</div></div>
    <div class="kpi"><div class="v">__S_HR__</div><div class="l">训练心率场次</div><div class="s">__S_HRATH__ 人 · __S_PTS__ 万点</div></div>
    <div class="kpi"><div class="v">__S_CPET__</div><div class="l">CPET 测试</div><div class="s">__S_CPETSUB__</div></div>
    <div class="kpi"><div class="v">__S_OUT__</div><div class="l">分析产出物</div><div class="s">仪表盘/Excel/报告/数据集</div></div>
  </div>

  <h2>一、本周工作总览</h2>
  <div class="card">
    <div class="tl">
      <div class="tl-item"><div class="tl-date">07 月中旬前 · 前测素质测试</div>
        <div class="tl-desc">89 人完成运动素质前测：FMS 功能性动作筛查、YBT 平衡、关节活动度与肌力、单腿跳/三连跳、CMJ、肌张力、力台重心、血乳酸、专项能力基线。</div></div>
      <div class="tl-item"><div class="tl-date">07-11 ~ 07-30 · 训练心率持续监测</div>
        <div class="tl-desc">5 位教练 45 个场次（冰上 9、陆地 9、晨脉恢复 14、疲劳/干预专项 13），136.5 万逐秒心率点，84 名运动员，448 条人次记录。</div></div>
      <div class="tl-item"><div class="tl-date">07-13 ~ 07-14 · 急性造模与干预实验</div>
        <div class="tl-desc">77 人按教练分 4 组（C/L/Y/Z），急性疲劳造模后随机干预：拔罐+推拿 / 艾灸+推拿 / 常规恢复；采集造模负荷与 5 段功率。</div></div>
      <div class="tl-item"><div class="tl-date">07-14 ~ 07-18 · 恢复期多维度监测</div>
        <div class="tl-desc">24h/72h 晨脉（HR）、血液生化（睾酮/皮质醇/尿素/CK/LDH，810 条）、CMJ、VAS、RPE、血乳酸、HRV 采集。</div></div>
      <div class="tl-item"><div class="tl-date">07-27 ~ 08-05 · 最大摄氧量(CPET)测试</div>
        <div class="tl-desc">MetaMax 3B 递增负荷心肺运动试验完成新增测试、复测与补录，形成累计分析样本。</div></div>
      <div class="tl-item"><div class="tl-date">08-04 ~ 08-06 · 新增训练场次（新教练教练F首次纳入）</div>
        <div class="tl-desc">新增 5 个场次：8.4 教练F冰上、8.4 教练C陆上、8.6 教练A陆上、8.6 教练B冰上、8.6 教练A冰上；60 人次、52 名运动员，训练强度高于 7 月均值（均心 124.8 vs 113.2）。</div></div>
      <div class="tl-item"><div class="tl-date">08-11 ~ 08-21 · 训练心率持续监测（新增 15 个场次）</div>
        <div class="tl-desc">新增 8/11–8/21 共 15 个训练场次，覆盖教练F、教练B、教练A、教练E等；累计 69 个场次、87 名运动员、约 297 万逐秒心率点。</div></div>
      <div class="tl-item"><div class="tl-date">08-03 ~ 08-06 · 整合与系统分析</div>
        <div class="tl-desc">生成论文级统一数据集（77 人主表 × 105 字段 + 完整率矩阵）；CPET 深度分析、心率周对比、教练简报表、数据大屏、交互仪表盘、教练C复合场次拆分。</div></div>
    </div>
  </div>

  <h2>二、数据采集体系（六大数据域）</h2>
  <div class="card">
    <table>
      <thead><tr><th>数据域</th><th>规模</th><th>内容</th><th>时间</th></tr></thead>
      <tbody>
        <tr><td><b>① 研究队列</b></td><td>77 人 · 105 字段</td><td>人口学/分组/干预/造模负荷/功率</td><td>07-13~14</td></tr>
        <tr><td><b>② 前测素质</b></td><td>89 人 · 142 字段</td><td>FMS/YBT/ROM/肌力/跳跃/肌张力/力台/血乳酸</td><td>07 月中旬前</td></tr>
        <tr><td><b>③ 恢复监测</b></td><td>77 人</td><td>CMJ/VAS/RPE/血乳酸/心率/HRV（静息→即刻→24h→72h）</td><td>07-13~18</td></tr>
        <tr><td><b>④ 血液生化</b></td><td>69 人 · 810 条</td><td>睾酮/皮质醇/尿素/CK/LDH × BL/24H/72H</td><td>07-14~18</td></tr>
        <tr><td><b>⑤ 训练心率</b></td><td>__S_HR__ 场 · __S_HRATH__ 人 · __S_PTS__ 万点</td><td>逐秒心率 + 区间/TRIMP/强度（含 8 月新场次与教练F）</td><td>07-11~08-21</td></tr>
        <tr><td><b>⑥ CPET</b></td><td>66 份 · 55 人</td><td>递增负荷摄氧量测试（含 08-06/07 新批次）</td><td>07-27~08-07</td></tr>
        <tr><td><b>⑦ 滑冰成绩</b></td><td>speedtrack</td><td>500/1000/1500m 计时（独立体系）</td><td>07 月</td></tr>
      </tbody>
    </table>
  </div>
  <div class="grid">
    <div class="fig"><div id="c_intv" class="chart"></div></div>
    <div class="fig"><div id="c_group" class="chart"></div></div>
    <div class="fig"><div id="c_type" class="chart"></div></div>
    <div class="fig"><div id="c_cpetdate" class="chart"></div></div>
  </div>

  <h2>三、恢复监测与血液生化</h2>
  <div class="grid">
    <div class="fig"><div id="c_hrrec" class="chart"></div></div>
    <div class="fig"><div id="c_cmj" class="chart"></div></div>
    <div class="fig"><div id="c_blood" class="chart"></div></div>
    <div class="fig"><div id="c_fms" class="chart"></div></div>
  </div>
  <div class="card">
    <p><b>恢复规律（77 人队列）：</b>运动即刻心率 128.4 bpm、血乳酸 15.2 mmol/L、VAS 6.5、RPE 16.5，确认造模强度充分；
    24h 心率回落至 95.9、72h 89.9（低于静息 96.4）；CK 基线 215.7 → 24h 288.6（+34%）→ 72h 212.8 回落；
    尿素、皮质醇、LDH 基本平稳；CMJ 24h 下降、72h 部分恢复。</p>
    <p><b>前测素质：</b>FMS 总分 86 人，均值 30.6/42（P25–P75 见分布图），队列功能动作基础良好。</p>
  </div>

  <h2>四、新数据小分析（干预组对比 / 造模反应 / 素质关联）</h2>
  <div class="grid">
    <div class="fig"><div id="c_g_ck" class="chart"></div></div>
    <div class="fig"><div id="c_g_cmj" class="chart"></div></div>
    <div class="fig"><div id="c_g_hr" class="chart"></div></div>
    <div class="card">
      <p><b>① 干预三组恢复对比：</b>三组均呈"24h 指标偏移 → 72h 回落"模式。CK 24h 变化：拔罐+推拿 +129、艾灸+推拿 +107、常规恢复 +77（拔罐组基线最低 173，升幅最大）；CMJ 三组 24h 均下降约 1–2 cm 后恢复；晨脉 72h 均回到 86–92 bpm。</p>
      <p><b>② 造模强度与恢复反应：</b>乳酸即刻 vs 心率即刻 r=0.13、造模负荷% vs CK24hΔ r=0.03、平均功率 vs 乳酸 r=-0.01——均无显著相关，恢复反应主要由个体差异决定，而非造模强度。</p>
      <p><b>③ 前测素质 × 有氧能力：</b>VO2/kg 与 FMS（r=-0.08）、YBT（r=-0.22）、CMJ（r=-0.06）、500m（r=0.03）均无显著相关（n≈31–33）——功能动作筛查与最大有氧能力是不同维度，不能互相替代。</p>
    </div>
    <div class="fig"><div id="c_newhr" class="chart"></div></div>
    <div class="fig"><div id="c_cross" class="chart"></div></div>
    <div class="card">
      <p><b>④ 新增训练场次：</b>不同训练日的平均心率与高强度占比存在差异，建议结合训练类型和恢复状态持续跟踪。</p>
      <p><b>⑤ 训练强度 × 有氧能力交叉（关键发现）：</b>训练强度与 CPET 结果不一致的个体应优先复测，并检查低龄组校准及测试质量。</p>
    </div>
  </div>

  <h2>五、数据处理与质量控制</h2>
  <div class="grid">
    <div class="fig"><div id="c_comp" class="chart"></div></div>
    <div class="fig"><div id="c_rer" class="chart"></div></div>
  </div>
  <div class="card">
    <p><b>CPET 有效性：</b>按有效、亚极量和无效分级；主分析仅纳入符合预设质量标准的测试，峰值可能因努力度不足而低估。</p>
    <p><b>研究数据完整率：</b>前测 100%、心率任一 96%、血液 BL 88% → 24H 62% → 72H 55%（逐时点脱落）；HRV 仅运动前 30% 有数据；干预方式缺失 10 人（组间分析前需处理）。</p>
    <p><b>异名归一：</b>已知姓名别名通过本地映射表归一；无法可靠链接的记录不强行合并。</p>
  </div>

  <h2>六、核心分析成果</h2>
  <div class="grid">
    <div class="fig"><div id="c_hist" class="chart"></div></div>
    <div class="fig"><div id="c_gender" class="chart"></div></div>
    <div class="fig wide"><div id="c_rank" class="chart tall"></div></div>
    <div class="fig"><div id="c_hrzone" class="chart"></div></div>
    <div class="fig"><div id="c_split" class="chart"></div></div>
  </div>
  <div class="card">
    <p><b>有氧能力：</b>报告汇总符合质量标准的测试，并分析 VO2/kg、预测值达成率及 BMI 相关性。</p>
    <p><b>训练强度：</b>冰上相对强度 73% vs 陆地 70%；教练C 7.28 拆分后冰上段均心 138 vs 陆地段 108（+30 bpm），修正了原"低强度"结论；教练D场次出现全期最高心率 215 bpm。</p>
  </div>

  <h2>七、分析产出物清单</h2>
  <div class="card">
    <table>
      <thead><tr><th>产出物</th><th>路径</th><th>说明</th></tr></thead>
      <tbody>__OUTPUTS__</tbody>
    </table>
  </div>

  <h2>八、问题与建议</h2>
  <div class="card">
    <div class="warn"><b>需立即解决：</b>CPET 需佩戴心率带；复核 MetaMax 校准（8–9 岁组异常高值）；干预方式缺失 10 人需补齐；亚极量者安排复测。</div>
    <div class="note"><b>数据管理：</b>统一姓名写法；建立 场次→文件→运动员 主数据表；血液 24H/72H 脱落率 38%/45%，需评估缺失机制；CMJ 前测存在明显离群值需清洗。</div>
    <div class="ok"><b>后续计划：</b>干预三组（拔罐/艾灸/常规）恢复效果组间比较（CK/CMJ/HR 主效应）；晨脉恢复曲线；前测素质与有氧能力关联；speedtrack 成绩归一后并入；每月复测积累纵向数据。</div>
  </div>
</div>
<script>__ECHARTS__</script>
<script>
const DATA = __DATA__;
const U = DATA.uni;
const C = {};
["c_intv","c_group","c_type","c_cpetdate","c_hrrec","c_cmj","c_blood","c_fms",
 "c_comp","c_rer","c_hist","c_gender","c_rank","c_hrzone","c_split",
 "c_g_ck","c_g_cmj","c_g_hr","c_newhr","c_cross"].forEach(id => {
  C[id] = echarts.init(document.getElementById(id));
});
window.addEventListener("resize", () => Object.values(C).forEach(c => c.resize()));
const ZC = ["#5b8fc7","#5fb06e","#e0c34e","#e58f4f","#d05555"];
const axis = t => ({type:"value",name:t,axisLabel:{fontSize:10}});
const cat = (d,rot) => ({type:"category",data:d,axisLabel:{rotate:rot||0,fontSize:10}});
function bar(id,title,xd,yd,color){
  C[id].setOption({title:{text:title,left:"center",textStyle:{fontSize:15}},tooltip:{},
    grid:{left:46,right:16,top:44,bottom:34},xAxis:cat(xd),yAxis:{type:"value",minInterval:1},
    series:[{type:"bar",data:yd,itemStyle:{color:color},label:{show:true,position:"top"}}]});
}
function lineC(id,title,xd,series){
  C[id].setOption({title:{text:title,left:"center",textStyle:{fontSize:15}},tooltip:{trigger:"axis"},
    legend:{top:28},grid:{left:48,right:20,top:60,bottom:34},xAxis:cat(xd),yAxis:{type:"value"},
    series:series});
}

const intv = Object.entries(DATA.intv).filter(([k])=>k!=="NaN").sort((a,b)=>b[1]-a[1]);
bar("c_intv","干预方式分组",intv.map(x=>x[0]),intv.map(x=>x[1]),"#2E8B57");
const grp = Object.entries(DATA.groups).sort((a,b)=>b[1]-a[1]);
bar("c_group","教练组人数",grp.map(x=>x[0]),grp.map(x=>x[1]),"#1F4E79");
C.c_type.setOption({title:{text:"训练场次类型构成",left:"center",textStyle:{fontSize:15}},
  tooltip:{trigger:"item",formatter:p=>`${p.name}: ${p.value} 场`},legend:{bottom:0},
  series:[{type:"pie",radius:["42%","68%"],center:["50%","46%"],data:[
    {name:"冰上",value:DATA.stats.hr_by_type["冰上"],itemStyle:{color:"#3f7fb8"}},
    {name:"陆地",value:DATA.stats.hr_by_type["陆地"],itemStyle:{color:"#4f9a5e"}},
    {name:"晨脉/恢复",value:DATA.stats.hr_by_type["晨脉/恢复"],itemStyle:{color:"#e0c34e"}},
    {name:"疲劳/干预专项",value:DATA.stats.hr_by_type["其他"],itemStyle:{color:"#b56b6b"}}]}]});
bar("c_cpetdate","CPET 测试日期分布",Object.keys(DATA.cpet_dates),Object.values(DATA.cpet_dates),"#2E86AB",35);

const hrRec = ["静息","运动即刻","24h","72h"].map((x,i)=>[x,[U.hr_rest_avg,U.hr_post_avg,U.hr_24h_avg,U.hr_72h_avg][i]?.mean]);
lineC("c_hrrec","心率恢复曲线 (bpm)",["静息","运动即刻","24h","72h"],
  [{type:"line",data:["rest","post","24h","72h"].map(k=>U["hr_"+k+"_avg"].mean),
    itemStyle:{color:"#1F4E79"},lineStyle:{width:3},symbolSize:9,
    label:{show:true,formatter:p=>p.value}}]);
lineC("c_cmj","CMJ 恢复 (cm)",["前测","24h","72h"],
  [{type:"line",data:[DATA.cmj.cmj_pre,DATA.cmj.cmj_24h,DATA.cmj.cmj_72h],
    itemStyle:{color:"#2E8B57"},lineStyle:{width:3},symbolSize:9,label:{show:true,formatter:p=>p.value}}]);
lineC("c_blood","血液生化指标变化",["BL","24H","72H"],
  ["ck","urea","cortisol","ldh","testosterone"].map((a,i)=>({
    name:{ck:"CK (U/L)",urea:"尿素 (mmol/L)",cortisol:"皮质醇 (ug/dL)",ldh:"LDH (U/L)",testosterone:"睾酮 (nmol/L)"}[a],
    type:"line",data:["BL","24H","72H"].map(tp=>DATA.blood[a]?.[tp]?.mean ?? null),
    itemStyle:{color:["#C44E52","#E8A33D","#4C72B0","#9467BD","#2E8B57"][i]},
    lineStyle:{width:2.5},symbolSize:7})));
C.c_fms.setOption({title:{text:"前测 FMS 总分分布（满分42）",left:"center",textStyle:{fontSize:15}},
  tooltip:{trigger:"axis"},grid:{left:44,right:16,top:44,bottom:34},
  xAxis:cat(["<26","26-28","28-30","30-32","32-34","34-36","36+"],0),yAxis:{type:"value",minInterval:1},
  series:[{type:"bar",data:["<26","26-28","28-30","30-32","32-34","34-36","36+"].map(b=>{
    const [lo,hi]=b==="<26"?[0,26]:b==="36+"?[36,99]:b.split("-").map(Number);
    return DATA.fms.filter(v=>v>=lo&&v<hi).length;}),itemStyle:{color:"#9467BD"},
    label:{show:true,position:"top"}}]});

bar("c_comp","数据域完整率 (%)",Object.keys(DATA.comp),Object.values(DATA.comp).map(x=>Math.round(x)),
  "#E8A33D");
C.c_rer.setOption({title:{text:"CPET 最大 RER 分布（努力度）",left:"center",textStyle:{fontSize:15}},
  tooltip:{trigger:"axis"},grid:{left:44,right:16,top:44,bottom:34},
  xAxis:cat(["0.86-0.95","0.95-1.00","1.00-1.05","1.05-1.10","1.10-1.20","1.20+"]),
  yAxis:{type:"value",minInterval:1},
  series:[{type:"bar",data:[
    DATA.rer.filter(x=>x>=0.86&&x<0.95).length,DATA.rer.filter(x=>x>=0.95&&x<1.0).length,
    DATA.rer.filter(x=>x>=1.0&&x<1.05).length,DATA.rer.filter(x=>x>=1.05&&x<1.10).length,
    DATA.rer.filter(x=>x>=1.10&&x<1.20).length,DATA.rer.filter(x=>x>=1.20).length],
    itemStyle:{color:"#C44E52"},label:{show:true,position:"top"}}]});

const bins=[]; for(let lo=30;lo<95;lo+=5) bins.push([lo,lo+5]);
C.c_hist.setOption({title:{text:"相对摄氧量分布（52 人）",left:"center",textStyle:{fontSize:15}},
  tooltip:{trigger:"axis"},grid:{left:44,right:16,top:44,bottom:40},
  xAxis:cat(bins.map(b=>b[0]+"-"+b[1]),35),yAxis:{type:"value",minInterval:1},
  series:[{type:"bar",data:bins.map(b=>DATA.vo2kg_dist.filter(v=>v>=b[0]&&v<b[1]).length),
    itemStyle:{color:"#2E86AB"},label:{show:true,position:"top"}}]});

function box(a){a=a.sort((x,y)=>x-y);return [a[0],a[Math.floor(a.length*.25)],a[Math.floor(a.length*.5)],a[Math.floor(a.length*.75)],a[a.length-1]];}
C.c_gender.setOption({title:{text:"男女相对摄氧量对比",left:"center",textStyle:{fontSize:15}},
  tooltip:{},grid:{left:52,right:16,top:44,bottom:30},
  xAxis:cat(["男性 (n="+DATA.gender.male.length+")","女性 (n="+DATA.gender.female.length+")"]),
  yAxis:{type:"value",name:"ml/kg/min"},
  series:[{type:"boxplot",data:[box(DATA.gender.male),box(DATA.gender.female)],itemStyle:{color:"#4C72B0"}}]});

C.c_rank.setOption({title:{text:"相对摄氧量排名",left:"center",textStyle:{fontSize:15}},
  tooltip:{formatter:p=>`${p.name}: ${p.value} ml/kg/min<br>%预测 ${p.data.pct}% · RER ${p.data.rer}`},
  grid:{left:110,right:60,top:44,bottom:26},xAxis:{type:"value"},
  yAxis:{type:"category",data:DATA.rank.map(r=>r.name),inverse:true},
  series:[{type:"bar",data:DATA.rank.map(r=>({value:r.vo2kg,name:r.name,pct:r.pct,rer:r.rer,
    itemStyle:{color:r.cls==="有效"?"#1F77B4":"#E8A33D"}})),label:{show:true,position:"right"}}]});

const hp = DATA.hr_prof.slice(0,25);
C.c_hrzone.setOption({title:{text:"训练心率区间构成（Top25 高强度）",left:"center",textStyle:{fontSize:15}},
  tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},legend:{top:28},
  grid:{left:100,right:20,top:62,bottom:26},xAxis:{type:"value",max:100},
  yAxis:{type:"category",data:hp.map(x=>x.name),inverse:true},
  series:["Z1","Z2","Z3","Z4","Z5"].map((zn,i)=>({name:zn,type:"bar",stack:"z",barWidth:13,
    itemStyle:{color:ZC[i]},data:hp.map(x=>x.z[i])}))});

C.c_split.setOption({title:{text:"教练C 7.28 复合场次拆分",left:"center",textStyle:{fontSize:15}},
  tooltip:{},legend:{top:28},grid:{left:46,right:20,top:60,bottom:34},
  xAxis:cat(["陆地（前段 103min）","冰上（后段 71min）"]),yAxis:{type:"value"},
  series:[
    {name:"平均心率",type:"bar",data:[108,138],itemStyle:{color:"#4f9a5e"},label:{show:true,position:"top"}},
    {name:"人均≥160min",type:"bar",data:[3.4,22.1],itemStyle:{color:"#d05555"},label:{show:true,position:"top"}}]});

const GCOL = {"拔罐+推拿":"#2E8B57","艾灸+推拿":"#E8A33D","常规恢复":"#8A94A0"};
function grpLine(id,title,key,xlab){
  C[id].setOption({title:{text:title,left:"center",textStyle:{fontSize:15}},
    tooltip:{trigger:"axis"},legend:{top:28},
    grid:{left:48,right:20,top:60,bottom:34},
    xAxis:cat(xlab),yAxis:{type:"value"},
    series:Object.entries(DATA.grp[key]).map(([g,v])=>({
      name:g,type:"line",data:v,itemStyle:{color:GCOL[g]},
      lineStyle:{width:2.8},symbolSize:8,label:{show:true,formatter:p=>p.value}}))});
}
grpLine("c_g_ck","干预组 CK 恢复对比 (U/L)", "ck", ["基线","24h","72h"]);
grpLine("c_g_cmj","干预组 CMJ 恢复对比 (cm)", "cmj", ["前测","24h","72h"]);
grpLine("c_g_hr","干预组晨脉恢复对比 (bpm)", "hr", ["静息","24h","72h"]);

C.c_newhr.setOption({title:{text:"新增场次强度对比（08-04 vs 08-06）",left:"center",textStyle:{fontSize:15}},
  tooltip:{},legend:{top:28},grid:{left:48,right:20,top:60,bottom:34},
  xAxis:cat(DATA.new_sess.map(x=>x.date+" ("+x.n+"人次)")),yAxis:{type:"value",name:"bpm / %"},
  series:[
    {name:"平均心率",type:"bar",data:DATA.new_sess.map(x=>x.avg),itemStyle:{color:"#4C72B0"},label:{show:true,position:"top"}},
    {name:"最大心率",type:"bar",data:DATA.new_sess.map(x=>x.mx),itemStyle:{color:"#C44E52"},label:{show:true,position:"top"}},
    {name:"高强度占比Z4+Z5%",type:"line",data:DATA.new_sess.map(x=>x.z45),itemStyle:{color:"#2E8B57"},label:{show:true,position:"top"}}]});

C.c_cross.setOption({title:{text:"训练高强度占比 × VO2/kg（新场次，点选查详情）",left:"center",textStyle:{fontSize:15}},
  tooltip:{formatter:p=>`${p.data.name}<br>Z4+Z5: ${p.data.value[0]}%<br>VO2/kg: ${p.data.value[1]}`},
  grid:{left:52,right:22,top:44,bottom:42},xAxis:{type:"value",name:"Z4+Z5 占比 (%)"},
  yAxis:{type:"value",name:"VO2/kg",min:30},
  series:[{type:"scatter",symbolSize:14,itemStyle:{color:"#1F77B4"},
    data:DATA.cross.map(x=>({name:x.name,value:[x.z45,x.vo2kg]})),
    label:{show:true,formatter:p=>p.data.name,position:"top",fontSize:10}}]});
</script>
</body></html>"""

html = (html
        .replace("__U_N__", str(uni["n_subjects"]))
        .replace("__U_PRE__", str(uni["n_pre"]))
        .replace("__U_BLD__", str(uni["n_blood"]))
        .replace("__U_BLDS__", str(uni["n_blood_subjects"]))
        .replace("__S_HR__", str(stats["hr_sessions"]))
        .replace("__S_HRATH__", str(stats["hr_athletes"]))
        .replace("__S_PTS__", f"{stats['hr_points']/1e4:.1f}")
        .replace("__S_CPET__", str(stats["cpet_tests"]))
        .replace("__S_CPETSUB__", f"{stats['cpet_subjects']} 人 · 男 {stats['cpet_male']} / 女 {stats['cpet_female']}")
        .replace("__S_OUT__", str(len(outputs)))
        .replace("__ECHARTS__", echarts_js)
        .replace("__DATA__", payload))
out_rows = "".join(
    f"<tr><td><b>{a}</b></td><td style='font-size:11.5px'>{b}</td><td>{c}</td></tr>"
    for a, b, c in outputs)
html = html.replace("__OUTPUTS__", out_rows)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("written:", OUT, "size:", os.path.getsize(OUT))

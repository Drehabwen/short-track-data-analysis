# -*- coding: utf-8 -*-
"""全队潜力排名报告生成器

用法：python build_potential_ranking.py [前N名默认20]
产出：最大摄氧量/全队潜力排名.html

评分模型（透明可调）：
  有氧能力 40%（相对摄氧量全队百分位）
  耐力储备 15%（VT1% 占峰值比例百分位）
  通气效率 10%（VE/VCO2 斜率百分位，低为好）
  做功输出 15%（CPET 峰值功率百分位）
  动作质量 10%（FMS 百分位）
  下肢爆发 10%（CMJ 百分位）
  小年龄加成：≤11 岁 +5 分
  缺项按可得权重归一（不因缺测而扣分）
"""

import json
import os
import sqlite3
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\DEV\blood"
DB = os.path.join(ROOT, "blood.db")
OUT = os.path.join(ROOT, "最大摄氧量", "全队潜力排名.html")
ECHARTS = r"D:\DEV\dashboard\echarts.min.js"

WEIGHTS = {"vo2": 40, "vt1": 15, "slope": 10, "wr": 15, "fms": 10, "cmj": 10}
ORDER = {"有效(达最大标准)": 0, "亚极量(接近最大)": 1, "亚极量(RER<1.00)": 1,
         "无效测试(未完成运动)": 2}


def q(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def pct(vals, v, higher=True):
    s = pd.Series(vals).dropna()
    if pd.isna(v) or s.empty:
        return None
    r = (s < v).mean() * 100
    return r if higher else 100 - r


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    cpet = q("""SELECT name, age_years, vo2kg_peak, vo2kg_vt1_pctmax,
                       slope_ve_vco2, peak_wr, valid_class FROM cpet_tests""")
    cpet["_o"] = cpet["valid_class"].map(ORDER).fillna(2)
    best = (cpet.sort_values(["_o", "vo2kg_peak"], ascending=[True, False])
            .drop_duplicates("name"))
    pre = q("SELECT name, fms_total, cmj_height_cm FROM pretest")
    ath = q("SELECT name, age, gender, coach FROM athletes")

    vo2_all = best["vo2kg_peak"].dropna()
    slope_all = best["slope_ve_vco2"].dropna()
    vt1_all = best["vo2kg_vt1_pctmax"].dropna()
    wr_all = best["peak_wr"].dropna()
    fms_all = pre["fms_total"].dropna()
    cmj_all = pre["cmj_height_cm"].dropna()

    rows = []
    for _, r in best.iterrows():
        if pd.isna(r["vo2kg_peak"]):
            continue
        a = ath[ath["name"] == r["name"]]
        age = a["age"].iloc[0] if not a.empty else r["age_years"]
        coach = a["coach"].iloc[0] if not a.empty else None
        pt = pre[pre["name"] == r["name"]]
        fms = pt["fms_total"].iloc[0] if not pt.empty else None
        cmj = pt["cmj_height_cm"].iloc[0] if not pt.empty else None
        comp = {
            "vo2": pct(vo2_all, r["vo2kg_peak"]),
            "vt1": pct(vt1_all, r["vo2kg_vt1_pctmax"]),
            "slope": pct(slope_all, r["slope_ve_vco2"], False),
            "wr": pct(wr_all, r["peak_wr"]),
            "fms": pct(fms_all, fms),
            "cmj": pct(cmj_all, cmj),
        }
        wsum = sum(WEIGHTS[k] for k in WEIGHTS if comp[k] is not None)
        score = (sum(WEIGHTS[k] * comp[k] for k in WEIGHTS if comp[k] is not None)
                 / wsum if wsum else 0)
        if age is not None and pd.notna(age) and age <= 11:
            score += 5
        rows.append({
            "name": r["name"], "age": (round(float(age), 1) if pd.notna(age) else None),
            "coach": coach, "cls": r["valid_class"], "score": round(score, 1),
            "vo2": r["vo2kg_peak"], "vt1": r["vo2kg_vt1_pctmax"],
            "slope": r["slope_ve_vco2"], "wr": r["peak_wr"],
            "fms": fms, "cmj": cmj, "comp": comp,
        })
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)

    top = df.head(top_n)
    data = {
        "names": top["name"].tolist(),
        "scores": top["score"].tolist(),
        "ages": [("-" if pd.isna(x) else x) for x in top["age"]],
        "clss": top["cls"].tolist(),
        "table": top[["rank", "name", "age", "coach", "score", "vo2", "vt1",
                      "slope", "wr", "fms", "cmj", "cls"]].to_dict("records"),
        "dims": ["有氧", "耐力储备", "通气效率", "做功", "动作", "爆发"],
        "top5": [
            {"name": r["name"], "vals": [r["comp"]["vo2"], r["comp"]["vt1"],
                                          r["comp"]["slope"], r["comp"]["wr"],
                                          r["comp"]["fms"], r["comp"]["cmj"]]}
            for _, r in df.head(5).iterrows()
        ],
    }
    # 观察名单与说明
    focus = []
    for _, r in df.head(6).iterrows():
        note = ""
        if r["age"] is not None and r["age"] <= 11:
            note += "小年龄+高有氧，重点观察"
        if "亚极量" in str(r["cls"]):
            note += ("；亚极量，真实值可能更高" if note else "亚极量，真实值可能更高")
        if r["comp"]["slope"] is not None and r["comp"]["slope"] >= 90:
            note += ("；呼吸经济性全队前列" if note else "呼吸经济性全队前列")
        focus.append({"name": r["name"], "score": r["score"], "note": note or "综合表现均衡"})
    data["focus"] = focus
    data["n"] = len(df)

    html = (HTML
            .replace("__ECHARTS__", open(ECHARTS, encoding="utf-8").read())
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__N__", str(len(df)))
            .replace("__DATE__", pd.Timestamp.now().strftime("%Y-%m-%d")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")
    print(df.head(10)[["rank", "name", "age", "score", "vo2", "cls"]].to_string(index=False))


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>全队潜力排名</title>
<style>
:root{--ink:#0b1e2d;--panel:#122b3d;--panel2:#0f2636;--ice:#eaf4fa;--frost:#9fb8c8;
  --line:#1e3b4f;--cyan:#38c3e0;--amber:#f2a93b;--red:#e05b4f;--ok:#4ec58b;
  --mono:'Cascadia Mono','Consolas',monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Microsoft YaHei','PingFang SC',sans-serif;background:var(--ink);color:var(--ice);
  background-image:radial-gradient(1100px 500px at 85% -10%,rgba(56,195,224,.08),transparent 60%)}
.wrap{max-width:1160px;margin:0 auto;padding:24px 22px 60px}
.head{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px}
.head h1{font-size:24px;letter-spacing:3px}
.head h1 em{font-style:normal;color:var(--cyan)}
.head .meta{color:var(--frost);font-size:12px}
.date{font-size:11.5px;color:#5d7889;font-family:var(--mono);margin-bottom:20px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:14px}
.box h2{font-size:14px;letter-spacing:2px;margin-bottom:10px}
.box h2 span{color:var(--cyan)}
.chart{height:420px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:7px 9px;border-bottom:1px solid rgba(30,59,79,.6);text-align:left}
th{color:var(--frost);font-size:10.5px;letter-spacing:.5px}
td b{font-family:var(--mono);color:var(--ice)}
.r1{color:var(--amber);font-weight:800}
.r2{color:#c9d8e4;font-weight:700}
.r3{color:#b9855a;font-weight:700}
.bw{font-size:9.5px;border-radius:5px;padding:1px 6px;font-weight:700}
.bw.g{background:var(--ok);color:#0b1e2d}.bw.o{background:var(--amber);color:#0b1e2d}.bw.r{background:#5d7889;color:#fff}
.focus{display:flex;gap:10px;flex-wrap:wrap}
.fcard{flex:1;min-width:200px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.fcard .n{font-size:15px;font-weight:800}
.fcard .s{font-size:11px;color:var(--cyan);margin:2px 0}
.fcard .d{font-size:11px;color:var(--frost);line-height:1.7}
.note{font-size:11.5px;color:#5d7889;line-height:1.9;margin-top:10px}
@media (max-width:860px){.grid2{grid-template-columns:1fr}}
@media print{body{background:#fff}}
</style>
<script>__ECHARTS__</script>
</head><body><div class="wrap">
<div class="head"><h1>全队<em>潜力排名</em></h1>
  <span class="meta">七台河短道速滑训练基地 · 基于 CPET/前测/急性疲劳数据</span></div>
<div class="date">编制日期 __DATE__ · 共 __N__ 人进入排名 · 评分模型：有氧40% + 耐力储备15% + 通气效率10% + 做功15% + 动作10% + 爆发10% + 小年龄加成</div>

<div class="grid2">
  <div class="box"><h2><span>TOP20</span> 潜力分布</h2><div class="chart" id="c_bar"></div></div>
  <div class="box"><h2><span>TOP5</span> 能力画像（全队百分位）</h2><div class="chart" id="c_radar"></div></div>
</div>

<div class="box"><h2><span>重点观察名单</span></h2>
  <div class="focus" id="focus"></div>
</div>

<div class="box"><h2><span>完整排名</span> 前 __N__ 名</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>排名</th><th>姓名</th><th>年龄</th><th>教练</th><th>潜力分</th>
    <th>VO₂</th><th>VT1%</th><th>通气效率</th><th>功率W</th><th>CMJ</th><th>FMS</th><th>测试</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table></div>
</div>

<div class="note"><b>模型说明与局限：</b>各维度取全队百分位，缺测项按可得权重归一（不因缺测扣分）；≤11岁加5分。
排名仅基于当前一次CPET与前测数据，未纳入技术、心理、训练年限；部分测试为亚极量/未测，8-10岁组存在设备校准疑点。
本榜用于圈定重点观察名单，不作成才定论。</div>
</div>
<script>
var D = __DATA__;
var C_ICE="#38c3e0", C_FROST="#9fb8c8", C_LINE="#1e3b4f", C_AMBER="#f2a93b", C_OK="#4ec58b";
function baseText(){return {color:C_FROST,fontFamily:"'Microsoft YaHei',sans-serif",fontSize:11}}
function mk(id,opt){var c=echarts.init(document.getElementById(id));c.setOption(opt);}
function clsBadge(c){
  if(String(c).indexOf("有效")==0) return '<span class="bw g">有效</span>';
  if(String(c).indexOf("亚极量")==0) return '<span class="bw o">亚极量</span>';
  return '<span class="bw r">无效</span>';
}
// 条形图
mk("c_bar", {textStyle:baseText(), tooltip:{trigger:"axis",axisPointer:{type:"shadow"},
  formatter:function(ps){return ps[0].name+"<br>潜力分 <b style='color:"+C_ICE+"'>"+ps[0].value+"</b>";}},
  grid:{left:80,right:50,top:10,bottom:24},
  xAxis:{type:"value",max:100,axisLabel:{color:C_FROST,fontSize:9},splitLine:{lineStyle:{color:"rgba(30,59,79,.5)"}}},
  yAxis:{type:"category",data:D.names.slice().reverse(),axisLabel:{color:C_FROST,fontSize:10}},
  series:[{type:"bar",data:D.scores.slice().reverse(),barMaxWidth:12,
    itemStyle:{color:function(p){var i=D.scores.length-1-p.dataIndex;return i==0?"rgba(242,169,59,.95)":i==1?"rgba(201,216,228,.85)":i==2?"rgba(185,133,90,.85)":"rgba(56,195,224,.75)";}},
    label:{show:true,position:"right",fontSize:9,color:C_FROST}}]
});
// TOP5 雷达
mk("c_radar", {textStyle:baseText(), tooltip:{},
  legend:{top:0,textStyle:{color:C_FROST,fontSize:10},data:D.top5.map(function(t){return t.name;})},
  radar:{indicator:D.dims.map(function(d){return {name:d,max:100};}),radius:"58%",
    splitArea:{areaStyle:{color:["rgba(18,43,61,.6)","rgba(15,38,54,.6)"]}},
    splitLine:{lineStyle:{color:C_LINE}},axisLine:{lineStyle:{color:C_LINE}},axisName:{color:C_FROST,fontSize:10}},
  series:[{type:"radar",data:D.top5.map(function(t,i){
    return {name:t.name,value:t.vals.map(function(v){return v==null?0:v;}),
      lineStyle:{color:["#f2a93b","#c9d8e4","#b9855a","#38c3e0","#4ec58b"][i],width:2},
      itemStyle:{color:["#f2a93b","#c9d8e4","#b9855a","#38c3e0","#4ec58b"][i]},
      areaStyle:{opacity:0.05},symbolSize:3};
  })}]
});
// 观察名单
document.getElementById("focus").innerHTML = D.focus.map(function(f){
  return '<div class="fcard"><div class="n">'+f.name+'</div><div class="s">潜力分 '+f.score+'</div><div class="d">'+f.note+'</div></div>';
}).join("");
// 完整排名表
document.getElementById("tbody").innerHTML = D.table.map(function(r){
  var rk = r.rank<=3 ? '<span class="r'+r.rank+'">'+r.rank+'</span>' : r.rank;
  var f = function(v,d){return (v==null||isNaN(v))?"-":Number(v).toFixed(d==null?1:d);};
  return '<tr><td>'+rk+'</td><td><b>'+r.name+'</b></td><td>'+(r.age==null?"-":r.age)+'</td><td>'+(r.coach||"-")+
    '</td><td><b>'+r.score+'</b></td><td>'+f(r.vo2)+'</td><td>'+f(r.vt1)+'</td><td>'+f(r.slope)+
    '</td><td>'+f(r.wr)+'</td><td>'+f(r.cmj)+'</td><td>'+f(r.fms)+'</td><td>'+clsBadge(r.cls)+'</td></tr>';
}).join("");
</script></body></html>
"""


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""更多图表示例：动态排名 / 平行坐标 / 旭日 / 仪表盘 / 气泡散点 / 桑基"""
import os, sys, re, json, glob
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import openpyxl

BASE = r'D:\DEV\blood\心率'
OUT = os.path.join(BASE, '更多图表_示例.html')
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
FILES = [
    '2026-07-28_教练A陆上.xlsx', '2026-07-28_教练B陆地.xlsx', '2026-07-28_教练C陆上.xlsx',
    '2026-07-28_教练B冰上.xlsx', '2026-07-28_教练D冰上.xlsx',
    '2026-07-30_教练E冰上.xlsx', '2026-07-30_教练E陆地.xlsx',
]
COACH_NAMES = ['教练A', '教练B', '教练C', '教练D', '教练E']
CMAP = {'教练A': '#7a6f9e', '教练B': '#4f9a5e', '教练C': '#c7a04a', '教练D': '#3f7fb8', '教练E': '#b56b6b'}

def to_seconds(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    m = re.match(r'^(\d+):(\d{1,2}):(\d{1,2})(?:\.\d+)?$', s)
    if m:
        return int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
    try:
        return float(s)
    except Exception:
        return None

def pct(v):
    try:
        return float(str(v).rstrip('%'))
    except Exception:
        return np.nan

def calc_trimp(dur_s, zones):
    if zones is None or any(np.isnan(z) for z in zones):
        return np.nan
    m = dur_s/60.0
    return sum(m*z/100.0*w for z, w in zip(zones, [1, 2, 3, 4, 5]))

def extract_coach(name):
    for c in COACH_NAMES:
        if c in name:
            return c
    return ''

def load_session(fn):
    wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
    ws = wb['团队综合报告']
    meta = None
    report = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] and str(row[0]).startswith('训练名称'):
            meta = str(row[0])
            continue
        if row[0] and row[1] is not None and str(row[0]) != '姓名':
            try:
                report[str(row[0])] = tuple(pct(x) for x in row[6:11])
            except Exception:
                pass
    parts = {}
    for chunk in meta.split('   '):
        if ': ' in chunk:
            k, v = chunk.split(': ', 1)
            parts[k] = v
    athletes = []
    for sn in wb.sheetnames:
        if sn in ('团队综合报告', '阶段报告'):
            continue
        s = wb[sn]
        ts, hs = [], []
        first = True
        for row in s.iter_rows(values_only=True):
            if first:
                first = False
                continue
            t = to_seconds(row[0])
            if t is not None:
                ts.append(t)
                try:
                    hs.append(float(row[1]))
                except Exception:
                    hs.append(np.nan)
        ts = np.array(ts); hs = np.array(hs)
        valid = hs[hs > 0]
        dur = float(ts[-1]) if ts.size else 0.0
        step = float(np.median(np.diff(ts))) if ts.size > 1 else 1.0
        zones = report.get(sn)
        athletes.append({
            'name': sn,
            'avg': float(valid.mean()) if valid.size else np.nan,
            'max': float(valid.max()) if valid.size else np.nan,
            'hi_min': float(np.sum(valid >= 160)) * step / 60.0,
            'trimp': calc_trimp(dur, zones),
            'zones': zones,
        })
    wb.close()
    return {'date': parts.get('训练日期', '')[:10], 'name': parts.get('训练名称', ''),
            'coach': extract_coach(parts.get('训练名称', '')),
            'type': '冰上' if '冰' in parts.get('训练名称', '') else '陆地',
            'athletes': athletes}

sessions = [load_session(os.path.join(BASE, f)) for f in FILES]

# 全周期（动态排名用）
period = []
for fn in sorted(glob.glob(os.path.join(BASE, '*.xlsx'))):
    s = load_session(fn)
    if s['athletes']:
        period.append({'date': s['date'], 'coach': s['coach'],
                       'trimp': float(np.nansum([a['trimp'] for a in s['athletes'] if not np.isnan(a['trimp'])]))})
dates = sorted({s['date'] for s in period if s['date'] >= '2026-07-21'})
acc = {c: 0.0 for c in COACH_NAMES}
race_frames = []
for d in dates:
    for s in period:
        if s['date'] == d:
            acc[s['coach']] += s['trimp']
    race_frames.append({'date': d, 'data': sorted([(c, round(acc[c])) for c in COACH_NAMES], key=lambda x: -x[1])})

# 平行坐标 / 气泡 / 桑基 / 旭日 / 仪表盘 数据
ath_rows = []
bubble = []
sun_children = []
sankey_links = []
for s in sessions:
    coach_node = None
    for child in sun_children:
        if child['name'] == s['coach']:
            coach_node = child
            break
    if coach_node is None:
        coach_node = {'name': s['coach'], 'children': [], 'itemStyle': {'color': CMAP[s['coach']]}}
        sun_children.append(coach_node)
    coach_node['children'].append({'name': f"{s['date'][5:]} {s['name']}", 'value': len(s['athletes'])})
    for a in s['athletes']:
        ath_rows.append([a['name'], s['coach'], round(a['avg']), round(a['max']),
                         round(a['hi_min'], 1), round(a['trimp']) if not np.isnan(a['trimp']) else 0])
        bubble.append([round(a['avg']), round(a['max']), round(a['trimp']) if not np.isnan(a['trimp']) else 0,
                       CMAP[s['coach']], a['name']])
    for v in ('冰上', '陆地'):
        if s['type'] == v:
            sankey_links.append({'source': s['coach'], 'target': v, 'value': len(s['athletes'])})

coach_z45 = {}
for s in sessions:
    for a in s['athletes']:
        if a['zones'] is not None and not any(np.isnan(x) for x in a['zones']):
            coach_z45.setdefault(s['coach'], []).append(a['zones'][3] + a['zones'][4])
def J(x):
    return json.dumps(x, ensure_ascii=False)

def ech(id_, body, h=360):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')
frames_js = J([{'date': f['date'], 'data': [[n, v] for n, v in f['data']]} for f in race_frames])
race_max = max(v for f in race_frames for _, v in f['data'])
ch = {}
ch['c_race'] = ech('c_race', """
var frames = """ + frames_js + """;
var cmap = """ + J(CMAP) + """;
var i = 0;
function step(){
  if(i < frames.length){
    var f = frames[i];
    c.setOption({
     tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
     toolbox:{right:10,feature:{saveAsImage:{name:'教练负荷排名动画',pixelRatio:2},restore:{}}},
     title:{text:'各教练累计负荷（TRIMP）· ' + f.date, left:'center', textStyle:{fontSize:14}},
     grid:{left:70,right:60,top:40,bottom:30},
     xAxis:{type:'value',max:""" + str(int(race_max*1.05)) + """},
     yAxis:{type:'category',data:f.data.map(function(x){return x[0];}),inverse:true},
     series:[{type:'bar',barWidth:'55%',
      data:f.data.map(function(x){return {value:x[1],itemStyle:{color:cmap[x[0]]}};}),
      label:{show:true,position:'right',fontSize:11},animationDuration:650}]
    });
    i++; setTimeout(step, 900);
  }
}
step();""", 380)

par_items = [{'value': [r[2], r[3], r[4], r[5], r[1]], 'name': r[0],
              'lineStyle': {'color': CMAP[r[1]], 'width': 1.1}} for r in ath_rows]
ch['c_parallel'] = ech('c_parallel', """
c.setOption({
 tooltip:{formatter:function(p){var v=p.value;return (p.name||'')+'<br>平均HR:'+v[0]+' · 最大HR:'+v[1]+'<br>≥160min:'+v[2]+' · TRIMP:'+v[3];}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员多指标平行坐标',pixelRatio:2},restore:{}}},
 parallelAxis:[
  {dim:0,name:'平均HR',min:90,max:175},
  {dim:1,name:'最大HR',min:150,max:220},
  {dim:2,name:'≥160min',min:0,max:60},
  {dim:3,name:'TRIMP',min:0,max:350},
  {dim:4,name:'教练',type:'category',data:""" + J(COACH_NAMES) + """}
 ],
 parallel:{left:70,right:80,top:40,bottom:40,axisLabel:{fontSize:9}},
 series:[{type:'parallel',lineStyle:{width:1.1},
  data:""" + J(par_items) + """}]
});""", 400)

sun = {'name': '全部7-28~30', 'children': sun_children}
ch['c_sunburst'] = ech('c_sunburst', """
c.setOption({
 tooltip:{formatter:function(p){var t=p.treePathInfo||[];var names=t.map(function(x){return x.name;}).join(' / ');return names+(p.value?('<br>人次: '+p.value):'');}},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练-场次旭日图',pixelRatio:2},restore:{}}},
 series:[{type:'sunburst',data:""" + J(sun) + """,radius:['12%','88%'],
  label:{fontSize:9},itemStyle:{borderColor:'#fff',borderWidth:1}}]
});""", 430)

gauge_series = []
for i, c in enumerate(COACH_NAMES):
    if c not in coach_z45:
        continue
    center = (['17%', '38%'], ['50%', '38%'], ['83%', '38%'], ['30%', '85%'], ['70%', '85%'])[i] if len(COACH_NAMES) == 5 else ['50%', '50%']
    v = round(float(np.mean(coach_z45[c])))
    gauge_series.append(
        "{name:'" + c + "',type:'gauge',center:" + J(center) + ",radius:'72%',min:0,max:60,splitNumber:6," +
        "axisLine:{lineStyle:{width:8,color:[[0.5,'#5fb06e'],[0.8,'#e0c34e'],[1,'#d05555']]}}," +
        "pointer:{itemStyle:{color:'#39454f'}},axisTick:{show:false},splitLine:{length:8,lineStyle:{width:1}}," +
        "axisLabel:{fontSize:7,distance:10}," +
        "title:{offsetCenter:[0,'72%'],fontSize:11,color:'#39454f'}," +
        "detail:{valueAnimation:true,offsetCenter:[0,'38%'],fontSize:16,fontWeight:'bold',formatter:'{value}%'}," +
        "data:[{value:" + str(v) + ",name:'" + c + "'}]}"
    )
ch['c_gauge'] = ech('c_gauge', """
c.setOption({
 tooltip:{formatter:function(p){return p.name+'<br>高强度区间占比: '+p.value+'%';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练高强度仪表盘',pixelRatio:2},restore:{}}},
 series:[""" + ','.join(gauge_series) + """]
});""", 420)

top5 = sorted(bubble, key=lambda b: -b[2])[:5]
ch['c_bubble'] = ech('c_bubble', """
c.setOption({
 tooltip:{formatter:function(p){return (p.name||'')+'<br>平均HR: '+p.value[0]+' · 最大HR: '+p.value[1]+'<br>TRIMP: '+p.value[2];}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员强度气泡图',pixelRatio:2},restore:{}}},
 legend:{data:['全部运动员','负荷TOP5'],top:0},
 grid:{left:55,right:25,top:40,bottom:55},
 xAxis:{type:'value',name:'平均心率',min:90,max:175},
 yAxis:{type:'value',name:'最大心率',min:150,max:220},
 series:[
  {name:'全部运动员',type:'scatter',
   data:""" + J([{'value': [b[0], b[1], b[2]], 'symbolSize': max(6, min(26, int(np.sqrt(b[2])*0.55))),
                  'itemStyle': {'color': b[3], 'opacity': 0.7}, 'name': b[4]} for b in bubble]) + """},
  {name:'负荷TOP5',type:'effectScatter',rippleEffect:{scale:2.5},
   data:""" + J([{'value': [b[0], b[1], b[2]], 'symbolSize': 16, 'itemStyle': {'color': b[3], 'shadowBlur': 8}, 'name': b[4]} for b in top5]) + """}
 ]});""", 400)

sankey_nodes = [{'name': c} for c in COACH_NAMES] + [{'name': '冰上'}, {'name': '陆地'}]
ch['c_sankey'] = ech('c_sankey', """
c.setOption({
 tooltip:{trigger:'item',triggerOn:'mousemove'},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练-场地桑基图',pixelRatio:2},restore:{}}},
 series:[{type:'sankey',data:""" + J(sankey_nodes) + """,links:""" + J(sankey_links) + """,
  label:{fontSize:11},itemStyle:{borderColor:'#fff',borderWidth:1},
  lineStyle:{color:'gradient',opacity:0.5}}]
});""", 400)

echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()

def panel(title, note, body):
    return (f'<div class="panel"><h3>{title}</h3><div class="note">{note}</div>{body}</div>')

html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>更多图表示例 · 心率数据</title>
<style>
body { font-family:'Microsoft YaHei',sans-serif; margin:0; background:#f5f3ee; color:#333; }
.wrap { max-width:1160px; margin:0 auto; padding:24px; }
h1 { font-size:22px; margin:0 0 2px; }
.sub { color:#888; font-size:13px; margin-bottom:20px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:16px; }
.panel { background:#fff; border:1px solid #ece7dc; border-radius:12px; padding:14px; box-shadow:0 4px 14px rgba(0,0,0,0.04); }
.panel h3 { margin:0 0 4px; font-size:14px; color:#39454f; }
.panel .note { color:#98a0a8; font-size:12px; margin-bottom:6px; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<h1>更多图表示例（交互版）</h1>
<div class="sub">6 种新图型，数据为 7-28~30 及 7-21~30 心率数据 · 悬停查看，右上角可导出图片</div>
<div class="grid">
""" + panel('动态排名条形图（动画）', '各教练累计负荷随时间增长的排名变化，自动播放', ch['c_race']) + """
""" + panel('平行坐标（运动员多指标画像）', '每条线=一名运动员，跨 平均HR/最大HR/高强度min/TRIMP 四维对比', ch['c_parallel']) + """
""" + panel('旭日图（教练 → 场次 → 人次）', '层级结构看各教练组构成', ch['c_sunburst']) + """
""" + panel('仪表盘（各教练高强度区间占比）', '0~60% 刻度，指针指示当前水平', ch['c_gauge']) + """
""" + panel('气泡散点图（平均×最大心率，气泡=TRIMP）', '红色涟漪点为负荷 TOP5 运动员', ch['c_bubble']) + """
""" + panel('桑基图（教练 → 场地 → 人次）', '各教练冰上/陆地训练量分配', ch['c_sankey']) + """
</div>
<script>
window.addEventListener('resize', function(){
  document.querySelectorAll('div[id^="c_"]').forEach(function(d){ var i=echarts.getInstanceByDom(d); if(i) i.resize(); });
});
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'更多图表示例已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')

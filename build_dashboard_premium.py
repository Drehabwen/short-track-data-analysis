# -*- coding: utf-8 -*-
"""精美大屏版：深色数据大屏风格 · 7-28~30 心率"""
import os, sys, re, json, glob
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import openpyxl

BASE = r'D:\DEV\blood\心率'
OUT = os.path.join(BASE, '心率大屏_精美版.html')
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
FILES = [
    '2026-07-28_教练A陆上.xlsx', '2026-07-28_教练B陆地.xlsx', '2026-07-28_教练C陆上.xlsx',
    '2026-07-28_教练B冰上.xlsx', '2026-07-28_教练D冰上.xlsx',
    '2026-07-30_教练E冰上.xlsx', '2026-07-30_教练E陆地.xlsx',
]
COACH_NAMES = ['教练A', '教练B', '教练C', '教练D', '教练E']
CMAP = {'教练A': '#7a6f9e', '教练B': '#4f9a5e', '教练C': '#c7a04a', '教练D': '#3f7fb8', '教练E': '#b56b6b'}
ICE, LAND, MAX_C = '#3f7fb8', '#4f9a5e', '#d05555'
ZC2 = ['#5b8fc7', '#5fb06e', '#e0c34e', '#e58f4f', '#d05555']

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

def load_session(fn, need_series=False):
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
    return {
        'file': os.path.basename(fn),
        'date': parts.get('训练日期', '')[:10],
        'name': parts.get('训练名称', ''),
        'coach': extract_coach(parts.get('训练名称', '')),
        'type': '冰上' if '冰' in parts.get('训练名称', '') else '陆地',
        'dur': parts.get('训练时长', ''),
        'athletes': athletes,
    }

sessions = [load_session(os.path.join(BASE, f)) for f in FILES]
labels = [f"{s['date'][5:]} {s['name']}" for s in sessions]
venue = [ICE if s['type'] == '冰上' else LAND for s in sessions]
avg_list = [round(float(np.nanmean([a['avg'] for a in s['athletes']])), 1) for s in sessions]
max_list = [round(float(np.nanmax([a['max'] for a in s['athletes']]))) for s in sessions]
hi_list = [round(float(np.nanmean([a['hi_min'] for a in s['athletes']])), 1) for s in sessions]
trimp_list = [round(float(np.nansum([a['trimp'] for a in s['athletes'] if not np.isnan(a['trimp'])]))) for s in sessions]
nc = [len(s['athletes']) for s in sessions]
kpi_avg = round(float(np.nanmean(avg_list)))
kpi_trimp = sum(trimp_list)
kpi_hi = round(float(np.nanmean(hi_list)))
kpi_ath = sum(nc)
# ---------- 全周期扫描（日历热力图） ----------
period = []
for fn in sorted(glob.glob(os.path.join(BASE, '*.xlsx'))):
    s = load_session(fn)
    if s['athletes']:
        hips = [a['hi_min'] for a in s['athletes']]
        period.append({'date': s['date'], 'coach': s['coach'],
                       'hi_per': float(np.mean(hips)), 'n': len(hips)})
daily_map = {}
for s in period:
    daily_map.setdefault(s['date'], []).append(s)
cal_data = []
for d in sorted(daily_map):
    ss = daily_map[d]
    cal_data.append([d, round(float(np.mean([x['hi_per'] for x in ss])), 1)])
cal_max = max(max(5, v) for _, v in cal_data)

# ---------- 雷达（教练画像） ----------
radar_data = []
for c in COACH_NAMES:
    aths = [a for s in sessions if s['coach'] == c for a in s['athletes']]
    if not aths:
        continue
    trimps = [a['trimp'] for a in aths if not np.isnan(a['trimp'])]
    zs = [a['zones'] for a in aths if a['zones'] is not None and not any(np.isnan(x) for x in a['zones'])]
    z45 = np.nanmean([z[3]+z[4] for z in zs]) if zs else 0
    radar_data.append({
        'name': c,
        'value': [round(float(np.nanmean([a['avg'] for a in aths])), 1),
                  round(float(np.nanmax([a['max'] for a in aths]))),
                  round(float(np.nanmean([a['hi_min'] for a in aths])), 1),
                  round(float(np.nansum(trimps)/len(aths)), 1) if trimps else 0,
                  round(float(z45), 1)],
    })

# ---------- 热力图（运动员×场次） ----------
heat_names = sorted({a['name'] for s in sessions for a in s['athletes']},
                    key=lambda nm: -np.nanmean([a['avg'] for s in sessions for a in s['athletes'] if a['name'] == nm]))
heat = []
for y, nm in enumerate(heat_names):
    for xj, s in enumerate(sessions):
        for a in s['athletes']:
            if a['name'] == nm and not np.isnan(a['avg']):
                heat.append([xj, y, round(a['avg'])])

# ---------- 各教练 TRIMP（本周） ----------
coach_trimp = []
for c in COACH_NAMES:
    ss = [s for s in sessions if s['coach'] == c]
    if ss:
        coach_trimp.append({'name': c, 'trimp': sum(trimp_list[i] for i, s in enumerate(sessions) if s['coach'] == c),
                            'color': CMAP[c]})

def J(x):
    return json.dumps(x, ensure_ascii=False)

def ech(id_, body, h=360):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')

TS = "textStyle:{color:'#cfd9e6'},"
ch = {}
ch['c_combo'] = ech('c_combo', """
c.setOption({
 """ + TS + """
 tooltip:{trigger:'axis',backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'}},
 legend:{data:['平均心率','最大心率'],top:0,textStyle:{color:'#cfd9e6'}},
 toolbox:{right:10,feature:{saveAsImage:{name:'心率强度',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 grid:{left:55,right:25,top:45,bottom:70},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10,color:'#aebcd0'},axisLine:{lineStyle:{color:'rgba(255,255,255,0.18)'}}},
 yAxis:{type:'value',name:'次/分',max:240,axisLabel:{color:'#aebcd0'},splitLine:{lineStyle:{color:'rgba(255,255,255,0.08)'}}},
 series:[
  {name:'平均心率',type:'bar',barWidth:'34%',data:""" + J(avg_list) + """,label:{show:true,position:'top',fontSize:9,color:'#e6eefb'},
   itemStyle:{color:function(p){return new echarts.graphic.LinearGradient(0,0,0,1,[
     {offset:0,color:p.dataIndex%2===0?'#7fd0ff':'#9be8a0'},{offset:1,color:""" + J(venue) + """[p.dataIndex]}]);},borderRadius:[4,4,0,0]}},
  {name:'最大心率',type:'line',data:""" + J(max_list) + """,itemStyle:{color:'#ff9a9a'},lineStyle:{width:2.5,shadowBlur:8,shadowColor:'#ff9a9a'},symbolSize:7,label:{show:true,position:'top',fontSize:8,color:'#ffd0d0'}}
 ]});""", 400)

radar_js = ','.join(
    "{name:'" + r['name'] + "',value:" + J(r['value']) +
    ",areaStyle:{color:'" + CMAP.get(r['name'], '#888') + "',opacity:0.25}," +
    "itemStyle:{color:'" + CMAP.get(r['name'], '#888') + "',shadowBlur:10,shadowColor:'" + CMAP.get(r['name'], '#888') + "'}}"
    for r in radar_data)
ch['c_radar'] = ech('c_radar', """
c.setOption({
 """ + TS + """
 tooltip:{backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'}},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练画像雷达',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 legend:{data:""" + J([r['name'] for r in radar_data]) + """,top:0,textStyle:{color:'#cfd9e6'}},
 radar:{indicator:[{name:'平均心率',max:160},{name:'最大心率',max:220},{name:'人均≥160min',max:35},
   {name:'人均TRIMP',max:320},{name:'高强度区间%',max:60}],
   radius:'66%',center:['50%','56%'],
   axisName:{color:'#aebcd0'},axisLine:{lineStyle:{color:'rgba(255,255,255,0.15)'}},
   splitLine:{lineStyle:{color:'rgba(255,255,255,0.10)'}},splitArea:{areaStyle:{color:['rgba(255,255,255,0.02)','rgba(255,255,255,0.04)']}}},
 series:[{type:'radar',data:[""" + radar_js + """]}]
});""", 430)

ch['c_calendar'] = ech('c_calendar', """
c.setOption({
 """ + TS + """
 tooltip:{backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'},
  formatter:function(p){return p.value[0]+'<br>人均高强度: '+p.value[1]+' 分钟';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'训练强度日历',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 visualMap:{min:0,max:""" + str(cal_max) + """,calculable:true,orient:'horizontal',left:'center',bottom:0,
  textStyle:{color:'#aebcd0'},inRange:{color:['#12203a','#1d4a7a','#3f7fb8','#e0a34f','#d05555']}},
 calendar:{range:['2026-07-11','2026-07-30'],cellSize:['auto',24],
  itemStyle:{borderWidth:1,borderColor:'#0e1524',color:'#16233c'},
  yearLabel:{show:false},dayLabel:{nameMap:['日','一','二','三','四','五','六'],firstDay:0,fontSize:9,color:'#8ea0b8'},
  monthLabel:{nameMap:['1月','2月','3月','4月','5月','6月','7月','8月'],fontSize:9,color:'#aebcd0'}},
 series:[{type:'heatmap',coordinateSystem:'calendar',data:""" + J(cal_data) + """}]
});""", 380)

ch['c_heat'] = ech('c_heat', """
c.setOption({
 """ + TS + """
 tooltip:{backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'},
  formatter:function(p){return """ + J(heat_names) + """[p.value[1]]+' · '+""" + J(labels) + """[p.value[0]]+'<br>平均心率: '+p.value[2]+' bpm';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员场次热力',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 visualMap:{min:90,max:180,calculable:true,orient:'horizontal',left:'center',bottom:0,textStyle:{color:'#aebcd0'},
  inRange:{color:['#101b30','#1d4a7a','#3f7fb8','#ff9a9a']}},
 grid:{left:85,right:20,top:15,bottom:70},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:8,color:'#aebcd0'},axisLine:{lineStyle:{color:'rgba(255,255,255,0.15)'}}},
 yAxis:{type:'category',data:""" + J(heat_names) + """,axisLabel:{fontSize:7,color:'#aebcd0'},axisLine:{lineStyle:{color:'rgba(255,255,255,0.15)'}}},
 series:[{type:'heatmap',data:""" + J(heat) + """,label:{show:true,fontSize:6,color:'#e6eefb'}}]
});""", max(560, len(heat_names)*16+90))

ch['c_trimp'] = ech('c_trimp', """
c.setOption({
 """ + TS + """
 tooltip:{trigger:'axis',backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'}},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练负荷',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 grid:{left:55,right:25,top:35,bottom:50},
 xAxis:{type:'category',data:""" + J([c['name'] for c in coach_trimp]) + """,axisLabel:{fontSize:11,color:'#aebcd0'},axisLine:{lineStyle:{color:'rgba(255,255,255,0.18)'}}},
 yAxis:{type:'value',name:'总TRIMP',axisLabel:{color:'#aebcd0'},splitLine:{lineStyle:{color:'rgba(255,255,255,0.08)'}}},
 series:[{type:'bar',barWidth:'46%',data:""" + J([{'value': c['trimp'], 'itemStyle': {'color': c['color']}} for c in coach_trimp]) + """,
  label:{show:true,position:'top',fontSize:10,color:'#e6eefb'},itemStyle:{borderRadius:[4,4,0,0]}}]
});""", 360)

rose_coaches = [c for c in COACH_NAMES if any(s['coach'] == c for s in sessions)]
rose_z = {}
for c in rose_coaches:
    zs = [a['zones'] for s in sessions if s['coach'] == c
          for a in s['athletes'] if a['zones'] is not None and not any(np.isnan(x) for x in a['zones'])]
    rose_z[c] = [round(float(x), 1) for x in np.mean(np.array(zs), axis=0)] if zs else [0, 0, 0, 0, 0]
rose_centers = (['17%', '34%'], ['50%', '34%'], ['83%', '34%'], ['30%', '78%'], ['70%', '78%'])
rose_series_js = []
for i, c in enumerate(rose_coaches):
    z = rose_z[c]
    data_js = ','.join("{name:'区间%d',value:%s,itemStyle:{color:'%s'}}" % (k+1, str(z[k]), ZC2[k]) for k in range(5))
    rose_series_js.append(
        "{name:'" + c + "',type:'pie',roseType:'area',radius:['18%','62%'],center:" + J(rose_centers[i]) +
        ",data:[" + data_js + "],label:{show:true,formatter:'{c}%',fontSize:6,color:'#cfd9e6'},labelLine:{length:4,length2:2}}"
    )
rose_graphic_js = ','.join(
    "{type:'text',left:'" + rose_centers[i][0] + "',top:'" + rose_centers[i][1] +
    "',style:{text:'" + c + "',fontSize:11,fontWeight:'bold',fill:'#e6eefb',textAlign:'center'}}"
    for i, c in enumerate(rose_coaches))
ch['c_rose'] = ech('c_rose', """
c.setOption({
 """ + TS + """
 tooltip:{trigger:'item',backgroundColor:'rgba(15,23,42,0.9)',borderColor:'rgba(127,208,255,0.3)',textStyle:{color:'#e6eefb'},
  formatter:function(p){return p.seriesName+' · '+p.name+': '+p.value+'%';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'区间玫瑰',pixelRatio:2,backgroundColor:'#0e1524'},restore:{}}},
 legend:{data:['区间1','区间2','区间3','区间4','区间5'],bottom:0,textStyle:{color:'#cfd9e6'}},
 series:[""" + ','.join(rose_series_js) + """],
 graphic:[""" + rose_graphic_js + """]
});""", 470)
# ---------- HTML ----------
echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()

def panel(title, body):
    return f'<div class="panel"><h3>{title}</h3>{body}</div>'

kpi_cards = ''
for label, val in [('本周场次', '7'), ('覆盖人次', str(kpi_ath)), ('平均心率', f'{kpi_avg} bpm'),
                   ('总负荷TRIMP', f'{kpi_trimp:,}'), ('人均高强度', f'{kpi_hi} min')]:
    kpi_cards += f'<div class="kpi"><div class="v">{val}</div><div class="l">{label}</div></div>'

html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>心率数据大屏 · 7-28~30（精美版）</title>
<style>
body { margin:0; font-family:'Microsoft YaHei',sans-serif;
  background:radial-gradient(1200px 600px at 20% -10%, #16233c 0%, #0a1120 55%); color:#dbe4f0; min-height:100vh; }
.wrap { max-width:1240px; margin:0 auto; padding:26px; }
h1 { font-size:26px; margin:0;
  background:linear-gradient(90deg,#7fd0ff,#9be8a0,#ffe08a); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.sub { color:#7f8fa3; font-size:13px; margin:8px 0 20px; }
.kpis { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:18px; }
.kpi { flex:1; min-width:150px; background:rgba(255,255,255,0.045);
  border:1px solid rgba(255,255,255,0.10); border-radius:14px; padding:16px; text-align:center;
  backdrop-filter:blur(6px); box-shadow:0 8px 24px rgba(0,0,0,0.25); }
.kpi .v { font-size:28px; font-weight:800;
  background:linear-gradient(90deg,#7fd0ff,#9be8a0); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.kpi .l { color:#8ea0b8; font-size:12px; margin-top:4px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:16px; }
.panel { background:rgba(255,255,255,0.035); border:1px solid rgba(255,255,255,0.09);
  border-radius:14px; padding:14px; box-shadow:0 10px 30px rgba(0,0,0,0.30); }
.panel h3 { margin:0 0 6px; font-size:14px; color:#cfe0f2; font-weight:600; }
.foot { color:#5f7088; font-size:11px; margin-top:22px; text-align:center; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<h1>心率数据大屏 · 2026-07-28 ~ 07-30</h1>
<div class="sub">陈/李/张/姚/于 五组教练 · 7 场训练 · 全部图表可悬停查看，右上角可导出图片</div>
<div class="kpis">""" + kpi_cards + """</div>
<div class="grid">
""" + panel('心率强度：平均（渐变柱）＋最大（发光折线）', ch['c_combo']) + """
""" + panel('各教练训练画像（雷达图）', ch['c_radar']) + """
""" + panel('每日训练强度（7-11 ~ 7-30 日历热力图）', ch['c_calendar']) + """
""" + panel('运动员 × 场次平均心率（热力图）', ch['c_heat']) + """
""" + panel('各教练总负荷（TRIMP）', ch['c_trimp']) + """
""" + panel('各教练心率区间（玫瑰图）', ch['c_rose']) + """
</div>
<div class="foot">数据来源：D:\\DEV\\blood\\心率 · 单文件离线可用 · 生成于 2026-08-05</div>
<script>
window.addEventListener('resize', function(){
  document.querySelectorAll('div[id^="c_"]').forEach(function(d){ var i=echarts.getInstanceByDom(d); if(i) i.resize(); });
});
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'精美大屏已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')

# -*- coding: utf-8 -*-
"""教练版简报表 v4：ECharts 全交互（悬停/缩放/一键导出），无 PNG"""
import os, sys, re, json, html, glob
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import openpyxl

BASE = r'D:\DEV\blood\心率'
OUT = os.path.join(BASE, '心率简报表_教练版_0728-0730.html')
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
FILES = [
    '2026-07-28_教练A陆上.xlsx', '2026-07-28_教练B陆地.xlsx', '2026-07-28_教练C陆上.xlsx',
    '2026-07-28_教练B冰上.xlsx', '2026-07-28_教练D冰上.xlsx',
    '2026-07-30_教练E冰上.xlsx', '2026-07-30_教练E陆地.xlsx',
]
ICE, LAND, MAX_C = '#3f7fb8', '#4f9a5e', '#d05555'
ZC = ['#5b8fc7', '#5fb06e', '#e0c34e', '#e58f4f', '#d05555']
COACH_NAMES = ['教练A', '教练B', '教练C', '教练D', '教练E']
MIX = '#b59bd6'
TYPE_OVERRIDES = {'2026-07-28_教练C陆上.xlsx': '陆上+冰上'}
TYPE_NOTES = {'2026-07-28_教练C陆上.xlsx': '前段陆地、后段冰上（复合场次）'}

def vcolor(t):
    return ICE if t == '冰上' else (LAND if t == '陆地' else MIX)

def extract_coach(name):
    for c in COACH_NAMES:
        if c in name:
            return c
    return ''

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
    minutes = dur_s/60.0
    return sum(minutes*z/100.0*w for z, w in zip(zones, [1, 2, 3, 4, 5]))

sessions = []
for fn in FILES:
    wb = openpyxl.load_workbook(os.path.join(BASE, fn), read_only=True, data_only=True)
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
    stype = TYPE_OVERRIDES.get(os.path.basename(fn), '冰上' if '冰' in parts.get('训练名称', '') else '陆地')
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
        avg = float(valid.mean()) if valid.size else np.nan
        mx = float(valid.max()) if valid.size else np.nan
        zeros = int(np.sum(hs == 0))
        dur = float(ts[-1]) if ts.size else 0.0
        step = float(np.median(np.diff(ts))) if ts.size > 1 else 1.0
        zones = report.get(sn)
        athletes.append({
            'name': sn, 't': ts, 'h': hs,
            'avg': avg, 'max': mx,
            'zero_rate': zeros*100.0/max(len(hs), 1),
            'hi_min': float(np.sum(valid >= 160)) * step / 60.0,
            'trimp': calc_trimp(dur, zones),
            'zones': zones,
        })
    wb.close()
    athletes.sort(key=lambda a: -a['avg'])
    trimps = [a['trimp'] for a in athletes if not np.isnan(a['trimp'])]
    sessions.append({
        'date': parts.get('训练日期', '')[:10],
        'name': parts.get('训练名称', ''), 'dur': parts.get('训练时长', ''),
        'type': stype, 'coach': extract_coach(parts.get('训练名称', '')),
        'file': os.path.basename(fn), 'athletes': athletes,
        'team_avg': float(np.nanmean([a['avg'] for a in athletes])),
        'team_sd': float(np.nanstd([a['avg'] for a in athletes])),
        'team_max': float(np.nanmax([a['max'] for a in athletes])),
        'hi_min_per': float(np.nanmean([a['hi_min'] for a in athletes])),
        'trimp_sum': float(np.nansum(trimps)) if trimps else 0.0,
    })

focus = []
seen = set()
def add_focus(name, scope, avg, mx, reason, order):
    key = (name, scope.split(' ')[0])
    if key in seen:
        for f in focus:
            if (f['name'], f['scope'].split(' ')[0]) == key:
                if reason not in f['reason']:
                    f['reason'] += '；' + reason
                f['order'] = min(f['order'], order)
        return
    seen.add(key)
    focus.append({'name': name, 'scope': scope, 'avg': avg, 'max': mx,
                  'reason': reason, 'order': order})
for s in sessions:
    for a in s['athletes']:
        if a['zero_rate'] >= 5:
            add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
                      f"心率数据缺失 {a['zero_rate']:.0f}%（心率带异常）", 0)
top_avg = sorted(((a['avg'], a, s) for s in sessions for a in s['athletes']), reverse=True)[:3]
for avg, a, s in top_avg:
    add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
              f"单场平均心率最高（{a['avg']:.0f} bpm）", 1)
for s in sessions:
    for a in s['athletes']:
        if a['max'] >= 210:
            add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
                      f"心率峰值过高（{a['max']:.0f} bpm）", 2)
trimp_by, scope_by, best = {}, {}, {}
for s in sessions:
    for a in s['athletes']:
        if not np.isnan(a['trimp']):
            trimp_by[a['name']] = trimp_by.get(a['name'], 0.0) + a['trimp']
            scope_by.setdefault(a['name'], []).append((s['date'], s['name']))
            b = best.get(a['name'], (0.0, 0.0))
            best[a['name']] = (max(b[0], a['avg']), max(b[1], a['max']))
multi = {k: v for k, v in trimp_by.items() if len(scope_by[k]) >= 2}
for nm, tp in sorted(multi.items(), key=lambda x: -x[1])[:5]:
    if nm in {f['name'] for f in focus}:
        continue
    avg, mx = best[nm]
    scopes = '、'.join(f"{d} {n}" for d, n in scope_by[nm])
    add_focus(nm, scopes, avg, mx,
              f"跨 {len(scope_by[nm])} 场累计负荷最高（TRIMP {tp:.0f}），注意疲劳累积", 3)
focus.sort(key=lambda f: f['order'])

import collections
coach_agg = collections.OrderedDict()
for s in sessions:
    m = re.search(r'[\u4e00-\u9fa5]{1,2}教练', s['name'])
    coach = m.group(0) if m else s['name']
    d = coach_agg.setdefault(coach, {'sessions': set(), 'zs': []})
    d['sessions'].add(s['name'])
    for a in s['athletes']:
        if a['zones'] is not None and not any(np.isnan(z) for z in a['zones']):
            d['zs'].append(a['zones'])
coach_z = {c: [float(x) for x in np.mean(np.array(d['zs']), axis=0)] for c, d in coach_agg.items() if d['zs']}
coach_n = {c: (len(d['sessions']), len(d['zs'])) for c, d in coach_agg.items() if d['zs']}
coach_list = list(coach_z)
hi_coach = max(coach_list, key=lambda c: coach_z[c][3]+coach_z[c][4])
lo_coach = min(coach_list, key=lambda c: coach_z[c][3]+coach_z[c][4])
zone_note = (f'高强度区间（4+5）占比最高的是 {hi_coach} 组（{coach_z[hi_coach][3]+coach_z[hi_coach][4]:.0f}%），'
             f'最低的是 {lo_coach} 组（{coach_z[lo_coach][3]+coach_z[lo_coach][4]:.0f}%）。')
# ---------- 全周期扫描（日历/堆叠面积用） ----------
period = []
for fn in sorted(glob.glob(os.path.join(BASE, '*.xlsx'))):
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
    date = parts.get('训练日期', '')[:10]
    coach = extract_coach(parts.get('训练名称', ''))
    hips, trs, n = [], [], 0
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
        hips.append(float(np.sum(valid >= 160)) * step / 60.0)
        t = calc_trimp(dur, zones)
        if not np.isnan(t):
            trs.append(t)
        n += 1
    wb.close()
    if n:
        period.append({'date': date, 'coach': coach,
                       'hi_per': float(np.mean(hips)), 'trimp': float(np.sum(trs)), 'n': n})

daily_map = {}
for s in period:
    daily_map.setdefault(s['date'], []).append(s)
cal_data = []
for d in sorted(daily_map):
    ss = daily_map[d]
    cal_data.append([d, round(float(np.mean([x['hi_per'] for x in ss])), 1)])
cal_max = max(max(5, v) for _, v in cal_data)
st_dates = sorted({s['date'] for s in period if s['date'] >= '2026-07-21'})
CMAP2 = {'教练A': '#7a6f9e', '教练B': '#4f9a5e', '教练C': '#c7a04a', '教练D': '#3f7fb8', '教练E': '#b56b6b'}
st_series = []
for c in COACH_NAMES:
    vals = [round(sum(s['trimp'] for s in period if s['date'] == d and s['coach'] == c)) for d in st_dates]
    st_series.append({'name': c, 'data': vals, 'color': CMAP2.get(c, '#888')})
radar_data = []
for c in coach_list:
    aths = [a for s in sessions if s['coach'] == c for a in s['athletes']]
    trimps = [a['trimp'] for a in aths if not np.isnan(a['trimp'])]
    z45 = coach_z[c][3] + coach_z[c][4] if c in coach_z else np.nan
    radar_data.append({
        'name': c,
        'value': [round(float(np.nanmean([a['avg'] for a in aths])), 1),
                  round(float(np.nanmax([a['max'] for a in aths]))),
                  round(float(np.nanmean([a['hi_min'] for a in aths])), 1),
                  round(float(np.nansum(trimps)/len(aths)), 1) if trimps else 0,
                  round(float(z45), 1)],
    })
# ---------- 图表数据准备 ----------
def J(x):
    return json.dumps(x, ensure_ascii=False)
labels = [f"{s['date'][5:]} {s['name']}" for s in sessions]
venue = [vcolor(s['type']) for s in sessions]
avg_list = [round(s['team_avg'], 1) for s in sessions]
max_list = [round(s['team_max']) for s in sessions]
dur_list = []
for s in sessions:
    h, m, sec = s['dur'].split(':')
    dur_list.append(int(h)*60 + int(m) + int(sec)/60.0)
nc = [len(s['athletes']) for s in sessions]
hi_list = [round(s['hi_min_per'], 1) for s in sessions]

heat_names = sorted({a['name'] for s in sessions for a in s['athletes']},
                    key=lambda nm: -np.nanmean([a['avg'] for s in sessions for a in s['athletes'] if a['name'] == nm]))
heat = []
for y, nm in enumerate(heat_names):
    for xj, s in enumerate(sessions):
        for a in s['athletes']:
            if a['name'] == nm and not np.isnan(a['avg']):
                heat.append([xj, y, round(a['avg'])])

def downsample(arr, n=600):
    arr = np.asarray(arr)
    if arr.size <= n:
        return arr
    idx = np.linspace(0, arr.size-1, n).astype(int)
    return arr[idx]
curve_sel = [4, 2, 1, 6]
curve_data = []
for idx in curve_sel:
    s = sessions[idx]
    n = min(len(a['t']) for a in s['athletes'])
    t = downsample(s['athletes'][0]['t'][:n]/60.0)
    H = np.array([downsample(a['h'][:n], 600) for a in s['athletes']])
    H = np.where(H > 0, H, np.nan)
    avg = np.nanmean(H, axis=0)
    lo = np.nanmin(H, axis=0)
    hi = np.nanmax(H, axis=0)
    curve_data.append({
        'title': f"{s['date'][5:]} {s['name']}（{len(s['athletes'])}人）",
        'color': venue[idx],
        't': [round(float(v), 1) for v in t],
        'avg': [None if np.isnan(v) else round(float(v), 1) for v in avg],
        'lo': [None if np.isnan(v) else round(float(v), 1) for v in lo],
        'hi': [None if np.isnan(v) else round(float(v), 1) for v in hi],
    })

box_data = []
for s in sessions:
    av = [a['avg'] for a in s['athletes']]
    q = np.percentile(av, [0, 25, 50, 75, 100])
    box_data.append([round(float(x), 1) for x in q])
scat_box = []
for xj, s in enumerate(sessions):
    rng = np.random.default_rng(xj)
    jit = rng.uniform(-0.18, 0.18, len(s['athletes']))
    for a, jv in zip(s['athletes'], jit):
        scat_box.append([xj + jv, round(a['avg'], 1)])

err_data = [[round(s['team_avg']-s['team_sd'], 1), round(s['team_avg']+s['team_sd'], 1)] for s in sessions]
coach_color = {'教练A': '#7a6f9e', '教练B': '#4f9a5e', '教练C': '#c7a04a', '教练D': '#3f7fb8', '教练E': '#b56b6b'}
ath_coach = {}
for s in sessions:
    m = re.search(r'[\u4e00-\u9fa5]{1,2}教练', s['name'])
    coach = m.group(0) if m else '?'
    for a in s['athletes']:
        ath_coach.setdefault(a['name'], coach)
rank = []
for nm, coach in ath_coach.items():
    vals = [a['avg'] for s in sessions for a in s['athletes'] if a['name'] == nm]
    rank.append((nm, float(np.mean(vals)), coach))
rank.sort(key=lambda r: -r[1])
rank = rank[:15]
lolli_names = [r[0] for r in rank]
lolli_vals = [round(r[1], 1) for r in rank]
lolli_cols = [coach_color.get(r[2], '#888') for r in rank]

# ---------- ECharts 图表 ----------
def ech(id_, body, h=360):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')

ch = {}
ch['c_hr'] = ech('c_hr', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['平均心率','最大心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'心率强度对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'次/分',max:240},
 series:[
  {name:'平均心率',type:'bar',barWidth:'30%',data:""" + J(avg_list) + """,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}},label:{show:true,position:'top',fontSize:9}},
  {name:'最大心率',type:'bar',barWidth:'30%',data:""" + J(max_list) + """,itemStyle:{color:'#d05555'},label:{show:true,position:'top',fontSize:9}}
 ]});""", 380)

ch['c_dur'] = ech('c_dur', """
c.setOption({
 tooltip:{trigger:'axis',formatter:function(p){var i=p[0].dataIndex;return """ + J(labels) + """[i]+'<br>训练时长: '+p[0].value+' 分钟<br>人数: '+""" + J(nc) + """[i]+' 人';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'训练时长与人数',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'分钟'},
 series:[{name:'训练时长(分钟)',type:'bar',barWidth:'42%',data:""" + J(dur_list) + """,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}},label:{show:true,position:'top',formatter:'{c}min',fontSize:9}}]
});""", 360)

ch['c_load'] = ech('c_load', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动负荷对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'人均分钟'},
 series:[{name:'人均≥160次/分(分钟)',type:'bar',barWidth:'42%',data:""" + J(hi_list) + """,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}},label:{show:true,position:'top',formatter:'{c}min',fontSize:9}}]
});""", 360)

for coach in coach_list:
    ch[f'c_coach_{coach}'] = ech(f'c_coach_{coach}', """
c.setOption({
 title:{text:'""" + coach + """',left:4,top:2,textStyle:{fontSize:11}},
 tooltip:{trigger:'axis',formatter:function(p){return '区间'+(p[0].dataIndex+1)+': '+p[0].value+'%';}},
 toolbox:{right:6,feature:{saveAsImage:{name:'""" + coach + """_区间分布',pixelRatio:2}}},
 grid:{left:38,right:10,top:32,bottom:24},
 xAxis:{type:'category',data:['区间1','区间2','区间3','区间4','区间5'],axisLabel:{fontSize:8}},
 yAxis:{type:'value',max:60,axisLabel:{fontSize:8}},
 series:[{type:'bar',data:""" + J(coach_z[coach]) + """,itemStyle:{color:function(p){return """ + J(ZC) + """[p.dataIndex];}},barWidth:'55%',label:{show:true,position:'top',fontSize:8,formatter:'{c}%'}}]
});""", 250)

donut_series = []
for i, coach in enumerate(coach_list):
    z = coach_z[coach]
    hi_v = round(z[3]+z[4])
    center = (['17%', '38%'], ['50%', '38%'], ['83%', '38%'], ['30%', '82%'], ['70%', '82%'])[i] if len(coach_list) == 5 else ['50%', '50%']
    data_js = ','.join("{name:'区间%d',value:%s,itemStyle:{color:'%s'}}" % (k+1, str(z[k]), ZC[k]) for k in range(5))
    donut_series.append(
        "{name:'" + coach + "',type:'pie',radius:['46%','64%'],center:" + J(center) + ",data:[" + data_js + "],"
        "label:{show:true,position:'center',formatter:function(){return '{n|" + coach + "}\\n{v|高强度 " + str(hi_v) + "%}';},"
        "rich:{n:{fontSize:12,fontWeight:'bold',color:'#39454f',lineHeight:18},v:{fontSize:10,color:'#888',lineHeight:14}}},"
        "labelLine:{show:false},emphasis:{label:{show:true,fontSize:11}}}"
    )
ch['c_donuts'] = ech('c_donuts', """
c.setOption({
 tooltip:{trigger:'item',formatter:function(p){return p.seriesName+' · '+p.name+': '+p.value+'%';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'各教练区间占比',pixelRatio:2},restore:{}}},
 legend:{data:['区间1','区间2','区间3','区间4','区间5'],bottom:2,itemWidth:12,itemHeight:8,textStyle:{fontSize:10}},
 series:[""" + ','.join(donut_series) + """]
});""", 470)

for i, cd in enumerate(curve_data):
    ch[f'c_curve_{i}'] = ech(f'c_curve_{i}', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:6,feature:{saveAsImage:{name:'""" + cd['title'][:20] + """_曲线',pixelRatio:2}}},
 grid:{left:45,right:12,top:32,bottom:28},
 title:{text:'""" + cd['title'] + """',left:0,textStyle:{fontSize:11}},
 xAxis:{type:'category',data:""" + J(cd['t']) + """,axisLabel:{show:false},splitLine:{show:false}},
 yAxis:{type:'value',min:40,max:220,axisLabel:{fontSize:8}},
 series:[
  {name:'下限',type:'line',stack:'b',data:""" + J(cd['lo']) + """,symbol:'none',lineStyle:{opacity:0},tooltip:{show:false},emphasis:{disabled:true}},
  {name:'全员范围',type:'line',stack:'b',data:""" + J([None if (l is None or h is None) else round(h-l, 1) for l, h in zip(cd['lo'], cd['hi'])]) + """,symbol:'none',lineStyle:{opacity:0},areaStyle:{color:'""" + cd['color'] + """',opacity:0.25},tooltip:{show:false}},
  {name:'平均心率',type:'line',data:""" + J(cd['avg']) + """,symbol:'none',lineStyle:{width:2,color:'""" + cd['color'] + """'}}
 ]});""", 300)

ch['c_heat'] = ech('c_heat', """
c.setOption({
 tooltip:{formatter:function(p){return """ + J(heat_names) + """[p.value[1]]+' · '+""" + J(labels) + """[p.value[0]]+'<br>平均心率: '+p.value[2]+' bpm';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员场次热力图',pixelRatio:2},restore:{}}},
 visualMap:{min:90,max:180,calculable:true,orient:'horizontal',left:'center',bottom:0,
  inRange:{color:['#eef2f6','#aac7e0','#5b8fc7','#d05555']}},
 grid:{left:80,right:20,top:12,bottom:66},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:9}},
 yAxis:{type:'category',data:""" + J(heat_names) + """,axisLabel:{fontSize:8}},
 series:[{type:'heatmap',data:""" + J(heat) + """,label:{show:true,fontSize:7,color:'#39454f'}}]
});""", max(560, len(heat_names)*16+90))

ch['c_err'] = ech('c_err', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['范围(±SD)','平均心率','最大心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'平均心率误差条',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'次/分',max:240},
 series:[
  {name:'范围(±SD)',type:'bar',data:""" + J(err_data) + """,barWidth:26,itemStyle:{color:'rgba(63,127,184,0.28)'}},
  {name:'平均心率',type:'bar',data:""" + J(avg_list) + """,barWidth:26,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}},label:{show:true,position:'top',fontSize:8}},
  {name:'最大心率',type:'scatter',data:""" + J(max_list) + """,itemStyle:{color:'#d05555'},symbol:'diamond',symbolSize:12}
 ]});""", 380)

ch['c_box'] = ech('c_box', """
c.setOption({
 tooltip:{trigger:'item',formatter:function(p){if(p.seriesType==='boxplot'){var i=p.dataIndex;var v=p.value;return """ + J(labels) + """[i]+'<br>最小: '+v[1]+'<br>下四分位: '+v[2]+'<br>中位数: '+v[3]+'<br>上四分位: '+v[4]+'<br>最大: '+v[5];}return p.seriesName;}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员心率分布箱线图',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'运动员平均心率(次/分)'},
 series:[
  {name:'分布',type:'boxplot',data:""" + J(box_data) + """,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}}},
  {name:'个体',type:'scatter',data:""" + J(scat_box) + """,itemStyle:{color:'#555',opacity:0.5},symbolSize:6}
 ]});""", 390)

ch['c_lolli'] = ech('c_lolli', """
c.setOption({
 tooltip:{trigger:'item',formatter:function(p){return p.name+'<br>平均心率: '+p.value+' bpm';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'平均心率排名',pixelRatio:2},restore:{}}},
 grid:{left:110,right:45,top:30,bottom:30},
 xAxis:{type:'value',name:'平均心率(次/分)'},
 yAxis:{type:'category',inverse:true,data:""" + J(lolli_names) + """,axisLabel:{fontSize:9}},
 series:[
  {name:'排名',type:'bar',data:""" + J(lolli_vals) + """,barWidth:4,itemStyle:{color:function(p){return """ + J(lolli_cols) + """[p.dataIndex];}}},
  {name:'点',type:'scatter',data:""" + J(lolli_vals) + """,symbolSize:11,itemStyle:{color:function(p){return """ + J(lolli_cols) + """[p.dataIndex];}},label:{show:true,position:'right',formatter:function(p){return p.value;},fontSize:8}}
 ]});""", max(360, len(lolli_vals)*22+60))

ch['c_combo'] = ech('c_combo', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['平均心率','最大心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'强度组合图',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:75},
 xAxis:{type:'category',data:""" + J(labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'次/分',max:240},
 series:[
  {name:'平均心率',type:'bar',barWidth:'36%',data:""" + J(avg_list) + """,itemStyle:{color:function(p){return """ + J(venue) + """[p.dataIndex];}},label:{show:true,position:'top',fontSize:8}},
  {name:'最大心率',type:'line',data:""" + J(max_list) + """,itemStyle:{color:'#d05555'},lineStyle:{width:2.5},symbolSize:7,label:{show:true,position:'top',fontSize:8}}
 ]});""", 380)

radar_series_js = ','.join(
    "{name:'" + r['name'] + "',value:" + J(r['value']) +
    ",areaStyle:{color:'" + CMAP2.get(r['name'], '#888') + "',opacity:0.15}," +
    "itemStyle:{color:'" + CMAP2.get(r['name'], '#888') + "'}}" for r in radar_data)
ch['c_radar'] = ech('c_radar', """
c.setOption({
 tooltip:{},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练训练画像雷达图',pixelRatio:2},restore:{}}},
 legend:{data:""" + J([r['name'] for r in radar_data]) + """,top:0},
 radar:{indicator:[{name:'平均心率',max:160},{name:'最大心率',max:220},
   {name:'人均≥160min',max:35},{name:'人均TRIMP',max:320},{name:'高强度区间%',max:60}],
   radius:'68%',center:['50%','55%']},
 series:[{type:'radar',data:[""" + radar_series_js + """]}]
});""", 430)

rose_series = []
for i, coach in enumerate(coach_list):
    z = coach_z[coach]
    center = (['17%', '34%'], ['50%', '34%'], ['83%', '34%'], ['30%', '78%'], ['70%', '78%'])[i] if len(coach_list) == 5 else ['50%', '50%']
    data_js = ','.join("{name:'区间%d',value:%s,itemStyle:{color:'%s'}}" % (k+1, str(z[k]), ZC[k]) for k in range(5))
    rose_series.append(
        "{name:'" + coach + "',type:'pie',roseType:'area',radius:['18%','62%'],center:" + J(center) +
        ",data:[" + data_js + "],label:{show:true,formatter:'{c}%',fontSize:7,color:'#555'},labelLine:{length:5,length2:3}}"
    )
rose_graphic = ','.join(
    "{type:'text',left:'" + x + "',top:'" + y + "',style:{text:'" + coach +
    "',fontSize:11,fontWeight:'bold',fill:'#39454f',textAlign:'center'}}"
    for coach, (x, y) in zip(coach_list, (['17%', '2%'], ['50%', '2%'], ['83%', '2%'], ['30%', '46%'], ['70%', '46%'])))
ch['c_rose'] = ech('c_rose', """
c.setOption({
 tooltip:{trigger:'item',formatter:function(p){return p.seriesName+' · '+p.name+': '+p.value+'%';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'各教练区间玫瑰图',pixelRatio:2},restore:{}}},
 legend:{data:['区间1','区间2','区间3','区间4','区间5'],bottom:0,itemWidth:12,itemHeight:8,textStyle:{fontSize:10}},
 series:[""" + ','.join(rose_series) + """],
 graphic:[""" + rose_graphic + """]
});""", 470)

ch['c_calendar'] = ech('c_calendar', """
c.setOption({
 tooltip:{formatter:function(p){return p.value[0]+'<br>人均高强度时间: '+p.value[1]+' 分钟';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'训练强度日历热力图',pixelRatio:2},restore:{}}},
 visualMap:{min:0,max:""" + str(cal_max) + """,calculable:true,orient:'horizontal',left:'center',bottom:0,
  inRange:{color:['#f6f1e6','#e0c34e','#e58f4f','#d05555']}},
 calendar:{range:['2026-07-11','2026-07-30'],cellSize:['auto',24],
  itemStyle:{borderWidth:1,borderColor:'#fff'},
  yearLabel:{show:false},
  dayLabel:{nameMap:['日','一','二','三','四','五','六'],firstDay:0,fontSize:9},
  monthLabel:{nameMap:['1月','2月','3月','4月','5月','6月','7月','8月'],fontSize:9}},
 series:[{type:'heatmap',coordinateSystem:'calendar',data:""" + J(cal_data) + """}]
});""", 380)

st_series_js = ','.join(
    "{name:'" + s['name'] + "',type:'line',stack:'total',symbol:'none',lineStyle:{width:0}," +
    "areaStyle:{opacity:0.75},itemStyle:{color:'" + s['color'] + "'},data:" + J(s['data']) + "}"
    for s in st_series)
ch['c_stacked'] = ech('c_stacked', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:""" + J([s['name'] for s in st_series]) + """,top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'各教练每日负荷走势',pixelRatio:2},restore:{}}},
 grid:{left:60,right:25,top:42,bottom:60},
 xAxis:{type:'category',data:""" + J(st_dates) + """,axisLabel:{rotate:30,fontSize:9}},
 yAxis:{type:'value',name:'总TRIMP'},
 series:[""" + st_series_js + """]
});""", 390)

# ---------- 教练C7.28 分段分析 ----------
zh = next(s for s in sessions if s['file'] == '2026-07-28_教练C陆上.xlsx')
nz = min(len(a['t']) for a in zh['athletes'])
HZ = np.array([a['h'][:nz] for a in zh['athletes']])
HZ = np.where(HZ > 0, HZ, np.nan)
avgz = np.nanmean(HZ, axis=0)
nzm = nz // 60
pmz = avgz[:nzm*60].reshape(-1, 60).mean(axis=1)
lowz = pmz < 90
best = None
i = 0
while i < len(lowz):
    if lowz[i]:
        j = i
        while j < len(lowz) and lowz[j]:
            j += 1
        if best is None or (j - i) > (best[1] - best[0]):
            best = (i, j)
        i = j
    else:
        i += 1
land_end, ice_start = best
# 已按教练确认时间 15:22（录制后 103 分 13 秒 = 6193 秒）固定拆分点
land_end = ice_start = 6193.0 / 60.0

def seg_rows(lo_min, hi_min):
    lo = int(lo_min*60); hi = int(hi_min*60)
    S = HZ[:, lo:hi]
    S = np.where(S > 0, S, np.nan)
    out = []
    for i in range(S.shape[0]):
        v = S[i]
        v = v[~np.isnan(v)]
        if len(v) == 0:
            out.append({'avg': np.nan, 'max': np.nan, 'g160': np.nan, 'g170': np.nan, 'g180': np.nan})
        else:
            out.append({'avg': v.mean(), 'max': v.max(),
                        'g160': np.sum(v >= 160)/60.0, 'g170': np.sum(v >= 170)/60.0,
                        'g180': np.sum(v >= 180)/60.0})
    return out

land_rows = seg_rows(0, land_end)
ice_rows = seg_rows(ice_start, nz/60.0)
zh_names = [a['name'] for a in zh['athletes']]
zh_max_x = round(nz/60.0, 1)

def team_row(rows):
    return [round(float(np.nanmean([r['avg'] for r in rows])), 1),
            round(float(np.nanmax([r['max'] for r in rows]))),
            round(float(np.nanmean([r['g160'] for r in rows])), 1),
            round(float(np.nanmean([r['g170'] for r in rows])), 1),
            round(float(np.nanmean([r['g180'] for r in rows])), 1)]

L5 = team_row(land_rows); I5 = team_row(ice_rows)
t5_headers = ['段', '时长min', '平均心率', '最大心率', '≥160min', '≥170min', '≥180min']
t5_rows = [['陆地（前段）', str(round(land_end, 1))] + [str(x) for x in L5],
           ['冰上（后段）', str(round(zh_max_x - ice_start, 1))] + [str(x) for x in I5],
           ['变化', ''] + [f'{b-a:+.1f}' for a, b in zip(L5, I5)]]

zh_pairs = sorted(zip(zh_names, land_rows, ice_rows), key=lambda x: -(x[2]['avg'] - x[1]['avg']))
t6_headers = ['姓名', '陆地均心', '冰上均心', '升幅', '冰上最大', '冰上≥160min']
t6_rows = []
for nm, lr, ir in zh_pairs:
    if np.isnan(ir['avg']):
        t6_rows.append([nm, f"{lr['avg']:.0f}" if not np.isnan(lr['avg']) else '-', '数据缺失', '-', '-', '-'])
    else:
        t6_rows.append([nm, f"{lr['avg']:.0f}", f"{ir['avg']:.0f}", f"{ir['avg']-lr['avg']:+.0f}",
                        f"{ir['max']:.0f}", f"{ir['g160']:.1f}"])

step_idx = np.linspace(0, nz-1, 600).astype(int)
zc_t = [round(float(v), 1) for v in zh['athletes'][0]['t'][:nz][step_idx]/60.0]
zc_avg = [None if np.isnan(v) else round(float(v), 1) for v in avgz[step_idx]]
ch['c_zhang'] = ech('c_zhang', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练C728_分段曲线',pixelRatio:2},restore:{}}},
 grid:{left:50,right:20,top:30,bottom:30},
 xAxis:{type:'category',data:""" + J(zc_t) + """,axisLabel:{show:false},splitLine:{show:false}},
 yAxis:{type:'value',min:40,max:220,axisLabel:{fontSize:9}},
 series:[{type:'line',data:""" + J(zc_avg) + """,symbol:'none',lineStyle:{width:1.8,color:'#3f7fb8'},
  markArea:{silent:true,data:[
   [{xAxis:0,name:'陆地',label:{position:'insideTop',formatter:'陆地',color:'#4f7a4f',fontSize:11}},
    {xAxis:""" + str(land_end) + """,itemStyle:{color:'rgba(143,169,122,0.18)'}}],
   [{xAxis:""" + str(ice_start) + """,label:{position:'insideTop',formatter:'冰上 15:22→',color:'#2f6690',fontSize:11}},
    {xAxis:""" + str(zh_max_x) + """,itemStyle:{color:'rgba(112,147,169,0.20)'}}]
  ]},
  markLine:{silent:true,symbol:'none',lineStyle:{color:'#888',type:'dashed',width:1},
   data:[{xAxis:""" + str(land_end) + """}]}
 }]
});""", 420)

# ---------- 展示用拆分（柱状图/热力图/场次表：教练C7.28 拆成前段陆地+后段冰上） ----------
import sys
sys.path.insert(0, r'D:\DEV\blood')
from zhang_split import split as zhang_split_segments
_zseg = zhang_split_segments()
land_trimp_sum = round(sum(r['land_trimp'] for r in _zseg
                           if r.get('land_trimp') is not None and not np.isnan(r['land_trimp'])))
ice_trimp_sum = round(sum(r['ice_trimp'] for r in _zseg
                          if r.get('ice_trimp') is not None and not np.isnan(r['ice_trimp'])))

disp = []
for s in sessions:
    hh, mm, sec = s['dur'].split(':')
    full_min = int(hh)*60 + int(mm) + int(sec)/60.0
    if s['file'] != '2026-07-28_教练C陆上.xlsx':
        disp.append({'date': s['date'], 'name': s['name'], 'type': s['type'], 'coach': s['coach'],
                     'file': s['file'], 'dur_min': round(full_min, 1),
                     'dur': s['dur'], 'n': len(s['athletes']),
                     'team_avg': s['team_avg'], 'team_max': s['team_max'],
                     'hi_min_per': s['hi_min_per'], 'trimp_sum': s['trimp_sum'],
                     'note': TYPE_NOTES.get(s['file'], ''),
                     'ath_avg': {a['name']: a['avg'] for a in s['athletes']}})
    else:
        disp.append({'date': s['date'], 'name': '教练C陆地（前段）', 'type': '陆地', 'coach': '教练C',
                     'file': s['file'], 'dur_min': round(land_end, 1),
                     'dur': f"{int(land_end)//60:02d}:{int(land_end)%60:02d}",
                     'n': len(s['athletes']), 'team_avg': L5[0], 'team_max': L5[1],
                     'hi_min_per': L5[2], 'trimp_sum': land_trimp_sum,
                     'note': '前段陆地、后段冰上（复合场次）',
                     'ath_avg': {nm: (round(lr['avg']) if not np.isnan(lr['avg']) else None) for nm, lr in zip(zh_names, land_rows)}})
        disp.append({'date': s['date'], 'name': '教练C冰上（后段）', 'type': '冰上', 'coach': '教练C',
                     'file': s['file'], 'dur_min': round(zh_max_x - ice_start, 1),
                     'dur': f"{int(zh_max_x - ice_start)//60:02d}:{int(zh_max_x - ice_start)%60:02d}",
                     'n': len(s['athletes']), 'team_avg': I5[0], 'team_max': I5[1],
                     'hi_min_per': I5[2], 'trimp_sum': ice_trimp_sum,
                     'note': '前段陆地、后段冰上（复合场次）',
                     'ath_avg': {nm: (round(ir['avg']) if not np.isnan(ir['avg']) else None) for nm, ir in zip(zh_names, ice_rows)}})

d_labels = [f"{s['date'][5:]} {s['name']}" for s in disp]
d_venue = [vcolor(s['type']) for s in disp]
d_avg = [round(s['team_avg'], 1) for s in disp]
d_max = [round(s['team_max']) for s in disp]
d_hi = [round(s['hi_min_per'], 1) for s in disp]
d_dur = [round(s['dur_min']) for s in disp]
d_nc = [s['n'] for s in disp]

heat_names2 = sorted({a['name'] for s in sessions for a in s['athletes']},
                     key=lambda nm: -np.nanmean([a['avg'] for s in sessions for a in s['athletes'] if a['name'] == nm]))
heat2 = []
for y, nm in enumerate(heat_names2):
    for xj, ds in enumerate(disp):
        v = ds['ath_avg'].get(nm)
        if v is not None and not np.isnan(v):
            heat2.append([xj, y, int(round(v))])

ch['c_hr'] = ech('c_hr', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['平均心率','最大心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'心率强度对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:75},
 xAxis:{type:'category',data:""" + J(d_labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'次/分',max:240},
 series:[
  {name:'平均心率',type:'bar',barWidth:'30%',data:""" + J(d_avg) + """,itemStyle:{color:function(p){return """ + J(d_venue) + """[p.dataIndex];}},label:{show:true,position:'top',fontSize:9}},
  {name:'最大心率',type:'bar',barWidth:'30%',data:""" + J(d_max) + """,itemStyle:{color:'#d05555'},label:{show:true,position:'top',fontSize:9}}
 ]});""", 380)

ch['c_dur'] = ech('c_dur', """
c.setOption({
 tooltip:{trigger:'axis',formatter:function(p){var i=p[0].dataIndex;return """ + J(d_labels) + """[i]+'<br>训练时长: '+p[0].value+' 分钟<br>人数: '+""" + J(d_nc) + """[i]+' 人';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'训练时长与人数',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:75},
 xAxis:{type:'category',data:""" + J(d_labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'分钟'},
 series:[{name:'训练时长(分钟)',type:'bar',barWidth:'42%',data:""" + J(d_dur) + """,itemStyle:{color:function(p){return """ + J(d_venue) + """[p.dataIndex];}},label:{show:true,position:'top',formatter:'{c}min',fontSize:9}}]
});""", 360)

ch['c_load'] = ech('c_load', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动负荷对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:75},
 xAxis:{type:'category',data:""" + J(d_labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'人均分钟'},
 series:[{name:'人均≥160次/分(分钟)',type:'bar',barWidth:'42%',data:""" + J(d_hi) + """,itemStyle:{color:function(p){return """ + J(d_venue) + """[p.dataIndex];}},label:{show:true,position:'top',formatter:'{c}min',fontSize:9}}]
});""", 360)

ch['c_combo'] = ech('c_combo', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['平均心率','最大心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'强度组合图',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:75},
 xAxis:{type:'category',data:""" + J(d_labels) + """,axisLabel:{rotate:25,fontSize:10}},
 yAxis:{type:'value',name:'次/分',max:240},
 series:[
  {name:'平均心率',type:'bar',barWidth:'36%',data:""" + J(d_avg) + """,itemStyle:{color:function(p){return """ + J(d_venue) + """[p.dataIndex];}},label:{show:true,position:'top',fontSize:8}},
  {name:'最大心率',type:'line',data:""" + J(d_max) + """,itemStyle:{color:'#d05555'},lineStyle:{width:2.5},symbolSize:7,label:{show:true,position:'top',fontSize:8}}
 ]});""", 380)

ch['c_heat'] = ech('c_heat', """
c.setOption({
 tooltip:{formatter:function(p){return """ + J(heat_names2) + """[p.value[1]]+' · '+""" + J(d_labels) + """[p.value[0]]+'<br>平均心率: '+p.value[2]+' bpm';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'运动员场次热力图',pixelRatio:2},restore:{}}},
 visualMap:{min:90,max:180,calculable:true,orient:'horizontal',left:'center',bottom:0,
  inRange:{color:['#eef2f6','#aac7e0','#5b8fc7','#d05555']}},
 grid:{left:80,right:20,top:12,bottom:66},
 xAxis:{type:'category',data:""" + J(d_labels) + """,axisLabel:{rotate:25,fontSize:9}},
 yAxis:{type:'category',data:""" + J(heat_names2) + """,axisLabel:{fontSize:8}},
 series:[{type:'heatmap',data:""" + J(heat2) + """,label:{show:true,fontSize:7,color:'#39454f'}}]
});""", max(560, len(heat_names2)*16+90))

CHART_HTML = {
    'hr': ch['c_hr'], 'dur': ch['c_dur'], 'load': ch['c_load'],
    'coach_bars': '<div style="display:flex;flex-wrap:wrap;gap:10px">' +
                  ''.join(f'<div style="flex:1;min-width:180px">{ch[f"c_coach_{c}"]}</div>' for c in coach_list) + '</div>',
    'donuts': ch['c_donuts'],
    'curves': '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:10px">' +
              ''.join(ch[f'c_curve_{i}'] for i in range(len(curve_data))) + '</div>',
    'heat': ch['c_heat'], 'err': ch['c_err'], 'box': ch['c_box'], 'lolli': ch['c_lolli'],
    'combo': ch['c_combo'], 'radar': ch['c_radar'], 'rose': ch['c_rose'],
    'calendar': ch['c_calendar'], 'stacked': ch['c_stacked'],
    'zhang': ch['c_zhang'],
}
# ---------- 表格 ----------
def table_to_html(headers, rows):
    th = ''.join(f'<th>{html.escape(h)}</th>' for h in headers)
    trs = []
    for r in rows:
        trs.append('<tr>' + ''.join(f'<td>{html.escape(str(c))}</td>' for c in r) + '</tr>')
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'

def tblbox(name, headers, rows, caption=''):
    return (f'<div class="tblbox">'
            f'<div class="tblbar">'
            f'<button class="dl" data-name="{name}" onclick="exportTableCSV(this)">导出CSV</button>'
            f'<button class="dl" onclick="copyTable(this)">复制表格</button>'
            + (f'<span class="cap">{caption}</span>' if caption else '')
            + '</div>' + table_to_html(headers, rows) + '</div>')

t1_headers = ['#', '日期', '训练内容', '场地', '时长', '人数', '平均心率', '最大心率', '人均≥160min', '总负荷TRIMP']
t1_rows = []
for i, s in enumerate(disp, 1):
    trimp = f"{s['trimp_sum']:.0f}" if s['trimp_sum'] is not None else '-'
    t1_rows.append([str(i), s['date'], s['name'], s['type'], s['dur'], str(s['n']),
                    f"{s['team_avg']:.0f}", f"{s['team_max']:.0f}", f"{s['hi_min_per']:.0f}", trimp])
t0_headers = ['#', '日期', '训练内容', '教练', '场地', '时长', '人数', '来源文件', '备注']
t0_rows = []
for i, s in enumerate(disp, 1):
    t0_rows.append([str(i), s['date'], s['name'], s['coach'], s['type'], s['dur'],
                    str(s['n']), s['file'], s['note']])
t4_headers = ['教练', '场次数', '人次', '区间1%', '区间2%', '区间3%', '区间4%', '区间5%', '高强度(4+5)%']
t4_rows = []
for c in coach_list:
    z = coach_z[c]
    t4_rows.append([c, str(coach_n[c][0]), str(coach_n[c][1])] +
                   [f"{v:.0f}" for v in z] + [f"{z[3]+z[4]:.0f}"])
t2_headers = ['姓名', '场次', '平均心率', '最大心率', '关注原因']
t2_rows = [[f['name'], f['scope'], f"{f['avg']:.0f}", f"{f['max']:.0f}", f['reason']] for f in focus]
t3_headers = ['日期', '训练内容', '运动员', '平均心率', '最大心率', '≥160min', 'TRIMP']
t3_rows = []
for s in sessions:
    for a in s['athletes']:
        warn = ' *' if a['zero_rate'] >= 5 else ''
        t3_rows.append([s['date'], s['name'], a['name'] + warn,
                        f"{a['avg']:.0f}", f"{a['max']:.0f}", f"{a['hi_min']:.0f}", f"{a['trimp']:.0f}"])

echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()

tc = {'冰上': 0, '陆地': 0, '陆上+冰上': 0}
for s in sessions:
    tc[s['type']] = tc.get(s['type'], 0) + 1
sub_scope = f"冰上 {tc['冰上']} 场 / 陆地 {tc['陆地']} 场" + (f" / 陆上+冰上 {tc['陆上+冰上']} 场" if tc.get('陆上+冰上') else '')

html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>心率简报表 · 7-28~7-30（教练版·交互）</title>
<style>
body { font-family:'Microsoft YaHei',sans-serif; margin:0; background:#faf9f6; color:#333; }
.wrap { max-width:1100px; margin:0 auto; padding:24px; }
h1 { font-size:22px; margin:0 0 2px; }
.sub { color:#888; font-size:13px; margin-bottom:18px; }
h2 { font-size:16px; border-left:4px solid #3f7fb8; padding-left:8px; margin:28px 0 8px; }
table { border-collapse:collapse; width:100%; font-size:13px; background:#fff; }
th,td { padding:6px 8px; border-bottom:1px solid #e8e4da; text-align:left; }
th { background:#37424f; color:#fff; font-weight:600; }
tbody tr:nth-child(even) { background:#faf9f6; }
.tblbox { margin:14px 0; }
.tblbar { display:flex; gap:8px; margin-bottom:6px; align-items:center; flex-wrap:wrap; }
.tblbar .cap { color:#888; font-size:12px; margin-left:auto; }
button.dl { background:#f0ece2; border:1px solid #ddd5c4; color:#555; border-radius:5px; padding:4px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
button.dl:hover { background:#e6e0d2; }
.note { background:#fdf6ea; border:1px solid #ecdcb8; border-radius:6px; padding:10px 14px; font-size:12.5px; color:#7a6634; margin:12px 0; }
.warn { background:#fdeeee; border:1px solid #ecc; border-radius:6px; padding:10px 14px; font-size:12.5px; color:#a33; margin:12px 0; }
.chartbox { background:#fff; border:1px solid #ece7dc; border-radius:8px; padding:8px; margin:12px 0; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<h1>心率简报表 · 2026-07-28 ~ 07-30（交互版）</h1>
<div class="sub">共 7 场训练（""" + sub_scope + """）· 52 名运动员。所有图表可<b>悬停查看数据、滚动缩放</b>，每个图表右上角有「保存为图片」按钮，看完可一键导出 PNG；表格可导出 CSV 或复制到 Word/Excel。</div>
<h2>一、场次总览（含运动负荷）</h2>
""" + tblbox('场次总览', t1_headers, t1_rows) + """
<div class="note">指标说明：<b>人均≥160min</b>=每人平均在心率 160 次/分以上的时间；<b>总负荷TRIMP</b>=按心率区间加权的训练量（区间越高权重越大），数字越大说明这堂课越累。</div>
<h2>二、数据清单（文件来源）</h2>
""" + tblbox('数据清单', t0_headers, t0_rows) + """
<div class="note">教练C 7.28 已按<b>前段陆地 + 后段冰上</b>拆分为两个条目展示（柱状图、热力图、场次表同步拆分；分段依据见第三板块，分段行总负荷TRIMP已按区间校准口径分摊计算）。拆分点：<b>15:22</b>（录制后 103 分 13 秒，教练确认）。</div>
<h2>三、教练C7.28 复合场次分段分析</h2>
""" + tblbox('分段对比', t5_headers, t5_rows) + """
<div class="chartbox">""" + CHART_HTML['zhang'] + """</div>
""" + tblbox('个人分段响应', t6_headers, t6_rows) + """
<div class="note">分段依据：全队心率在 91~103 分钟出现低谷（均心 &lt;90bpm），为陆地→冰上的休息切换窗口；已按教练确认时间 <b>15:22</b>（录制后 103 分 13 秒）拆分。冰上段平均心率显著高于陆地段（全队 +30 bpm），高强度时间集中在冰上段；运动员G冰上段数据缺失无法评估。</div>
<h2>四、心率强度对比</h2>
<div class="chartbox">""" + CHART_HTML['hr'] + """</div>
<div class="chartbox">""" + CHART_HTML['combo'] + """</div>
<h2>五、训练时长与人数</h2>
<div class="chartbox">""" + CHART_HTML['dur'] + """</div>
<h2>六、运动负荷对比</h2>
<div class="chartbox">""" + CHART_HTML['load'] + """</div>
<h2>七、各教练训练心率区间分布</h2>
""" + tblbox('各教练心率区间分布', t4_headers, t4_rows) + """
<div class="chartbox">""" + CHART_HTML['coach_bars'] + """</div>
<div class="chartbox">""" + CHART_HTML['donuts'] + """</div>
<div class="chartbox">""" + CHART_HTML['rose'] + """</div>
<div class="note">""" + zone_note + """</div>
<h2>八、各教练训练画像（雷达图）</h2>
<div class="chartbox">""" + CHART_HTML['radar'] + """</div>
<div class="note">雷达图五个维度（平均/最大心率、人均≥160min、人均TRIMP、高强度区间%）已按同一比例尺展示，越往外越强，可直接比较 5 位教练的训练画像。</div>
<h2>九、心率曲线与全员波动范围</h2>
<div class="chartbox">""" + CHART_HTML['curves'] + """</div>
<h2>十、运动员 × 场次平均心率热力图</h2>
<div class="chartbox">""" + CHART_HTML['heat'] + """</div>
<h2>十一、平均心率 ± 个体差异</h2>
<div class="chartbox">""" + CHART_HTML['err'] + """</div>
<h2>十二、运动员心率分布箱线图</h2>
<div class="chartbox">""" + CHART_HTML['box'] + """</div>
<h2>十三、平均心率排名</h2>
<div class="chartbox">""" + CHART_HTML['lolli'] + """</div>
<h2>十四、每日训练强度日历热力图</h2>
<div class="chartbox">""" + CHART_HTML['calendar'] + """</div>
<div class="note">覆盖 7-11~7-30 全部场次：7-11~7-18 为急性实验期，7-21 起为常规训练。悬停可看具体日期与人均高强度分钟。</div>
<h2>十五、各教练每日负荷走势（堆叠面积）</h2>
<div class="chartbox">""" + CHART_HTML['stacked'] + """</div>
<h2>十六、需要重点关注的成员</h2>
""" + tblbox('重点关注成员', t2_headers, t2_rows) + """
<div class="warn">⚠ 心率带异常（数据缺失较多，运动员明细中标注 *）的成员：教练C陆上 7.28 的<b>运动员G</b>、<b>运动员H</b>，下次训练前请检查心率带佩戴。</div>
<h2>十七、运动员明细（按平均心率从高到低）</h2>
""" + tblbox('运动员明细', t3_headers, t3_rows) + """
<script>
function toast(msg){
  var el = document.getElementById('toast');
  if(!el){ el = document.createElement('div'); el.id='toast';
    el.style.cssText='position:fixed;left:50%;bottom:32px;transform:translateX(-50%);background:#37424f;color:#fff;padding:8px 18px;border-radius:18px;font-size:13px;z-index:99;opacity:0;transition:opacity .2s';
    document.body.appendChild(el); }
  el.textContent = msg; el.style.opacity = '1';
  clearTimeout(el._t); el._t = setTimeout(function(){ el.style.opacity='0'; }, 2000);
}
function tableToCSV(tbl){
  return [...tbl.querySelectorAll('tr')].map(function(tr){
    return [...tr.querySelectorAll('th,td')].map(function(c){
      var t = (c.innerText || '').replace(/\\s+/g, ' ').trim();
      return /[",\\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
    }).join(',');
  }).join('\\r\\n');
}
function exportTableCSV(btn){
  var box = btn.closest('.tblbox');
  var csv = '\\ufeff' + tableToCSV(box.querySelector('table'));
  var a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8'}));
  a.download = (btn.getAttribute('data-name') || '表格') + '.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
}
async function copyTable(btn){
  var box = btn.closest('.tblbox');
  var tbl = box.querySelector('table');
  var htmlStr = tbl.outerHTML;
  var plain = tableToCSV(tbl).replace(/,/g, '\\t');
  try {
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([htmlStr], {type:'text/html'}),
      'text/plain': new Blob([plain], {type:'text/plain'})
    })]);
    toast('已复制表格，可粘贴到 Word / Excel');
  } catch(e){
    try { await navigator.clipboard.writeText(plain); toast('已复制表格（文本格式）'); }
    catch(e2){ toast('复制失败，请手动框选表格复制'); }
  }
}
window.addEventListener('resize', function(){
  document.querySelectorAll('div[id^="c_"]').forEach(function(d){ var i=echarts.getInstanceByDom(d); if(i) i.resize(); });
});
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'交互版简报表已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')

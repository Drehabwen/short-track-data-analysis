# -*- coding: utf-8 -*-
"""周对比报告：上周(7-21~23) vs 本周(7-28~30) 训练强度 + 重点关注运动员追踪"""
import os, sys, re, json, html, glob
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import openpyxl

BASE = r'D:\DEV\blood\心率'
OUT = os.path.join(BASE, '心率周对比_上周vs本周.html')
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
LAST = {'2026-07-21', '2026-07-22', '2026-07-23'}
THIS = {'2026-07-28', '2026-07-30'}
ICE, LAND, MAX_C = '#3f7fb8', '#4f9a5e', '#d05555'
ZC = ['#5b8fc7', '#5fb06e', '#e0c34e', '#e58f4f', '#d05555']
LW_C, TW_C = '#9aa7b5', '#3f7fb8'
COACH_NAMES = ['教练A', '教练B', '教练C', '教练D', '教练E']
TYPE_OVERRIDES = {'2026-07-28_教练C陆上.xlsx': '陆上+冰上'}

def extract_coach(name):
    for c in COACH_NAMES:
        if c in name:
            return c
    return name

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

files = sorted(f for f in glob.glob(os.path.join(BASE, '*.xlsx')) if os.path.basename(f)[:10] in LAST | THIS)
sessions = []
for fn in files:
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
    week = 'last' if date in LAST else 'this'
    stype = TYPE_OVERRIDES.get(os.path.basename(fn), '冰上' if '冰' in parts.get('训练名称', '') else '陆地')
    coach = extract_coach(parts.get('训练名称', ''))
    if os.path.basename(fn) == '2026-07-28_教练C陆上.xlsx':
        # 复合场次：前段陆地 + 后段冰上，按 15:22（录制后 6193 秒）拆分
        sys.path.insert(0, r'D:\DEV\blood')
        from zhang_split import split as zhang_split_sessions
        segs = {r['name']: r for r in zhang_split_sessions()}
        ath_names = [sn for sn in wb.sheetnames if sn not in ('团队综合报告', '阶段报告')]
        for label, st, key in (('教练C陆地（前段）', '陆地', 'land'),
                               ('教练C冰上（后段）', '冰上', 'ice')):
            ath = []
            for nm in ath_names:
                r = segs.get(nm)
                if r is None or not r.get('ok') or r.get(key) is None:
                    continue
                seg = r[key]
                ath.append({'name': nm, 'avg': seg['avg'], 'max': seg['max'],
                            'zero_rate': np.nan, 'hi_min': seg['g160'],
                            'trimp': r[f'{key}_trimp'], 'zones': None})
            d_min = segs['杜可昕'][key]['min'] if segs.get('杜可昕') else 0
            sessions.append({
                'date': date, 'week': week, 'coach': coach, 'type': st,
                'name': label, 'dur': f"{int(d_min)//60:02d}:{int(d_min)%60:02d}",
                'athletes': ath,
                'team_avg': float(np.nanmean([a['avg'] for a in ath])) if ath else float('nan'),
                'team_max': float(np.nanmax([a['max'] for a in ath])) if ath else float('nan'),
                'hi_min_per': float(np.nanmean([a['hi_min'] for a in ath])) if ath else float('nan'),
                'trimp_sum': float(np.nansum([a['trimp'] for a in ath
                                              if not np.isnan(a['trimp'])])) if ath else 0.0,
            })
        wb.close()
        continue
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
            'zero_rate': int(np.sum(hs == 0))*100.0/max(len(hs), 1),
            'hi_min': float(np.sum(valid >= 160)) * step / 60.0,
            'trimp': calc_trimp(dur, zones),
            'zones': zones,
        })
    wb.close()
    sessions.append({
        'date': date, 'week': week, 'coach': coach, 'type': stype,
        'name': parts.get('训练名称', ''), 'dur': parts.get('训练时长', ''),
        'athletes': athletes,
        'team_avg': float(np.nanmean([a['avg'] for a in athletes])),
        'team_max': float(np.nanmax([a['max'] for a in athletes])),
        'hi_min_per': float(np.nanmean([a['hi_min'] for a in athletes])),
        'trimp_sum': float(np.nansum([a['trimp'] for a in athletes if not np.isnan(a['trimp'])])),
    })

print(f'共加载 {len(sessions)} 场：上周 {sum(1 for s in sessions if s["week"]=="last")} 场，本周 {sum(1 for s in sessions if s["week"]=="this")} 场')
coach_order = []
for s in sessions:
    if s['coach'] not in coach_order:
        coach_order.append(s['coach'])
# ---------- 教练 × 周 聚合 ----------
def agg_pool(week, coach=None):
    pool = [a for s in sessions if s['week'] == week and (coach is None or s['coach'] == coach) for a in s['athletes']]
    ss = [s for s in sessions if s['week'] == week and (coach is None or s['coach'] == coach)]
    if not pool:
        return None
    zs = [a['zones'] for a in pool if a['zones'] is not None and not any(np.isnan(x) for x in a['zones'])]
    return {
        'n_sess': len(ss),
        'n_ath': len(pool),
        'avg': float(np.nanmean([a['avg'] for a in pool])),
        'max': float(np.nanmax([a['max'] for a in pool])),
        'hi_per': float(np.nanmean([a['hi_min'] for a in pool])),
        'trimp': float(np.nansum([a['trimp'] for a in pool if not np.isnan(a['trimp'])])),
        'zone45': float(np.nanmean([z[3]+z[4] for z in zs])) if zs else np.nan,
    }

overall_last = agg_pool('last')
overall_this = agg_pool('this')
coach_agg = {}
for c in coach_order:
    coach_agg[c] = {'last': agg_pool('last', c), 'this': agg_pool('this', c)}

# ---------- 上周重点关注（同一套规则） ----------
last_sessions = [s for s in sessions if s['week'] == 'last']
focus_last = []
seen = set()
def add_focus(name, scope, avg, mx, reason, order):
    key = (name, scope.split(' ')[0])
    if key in seen:
        for f in focus_last:
            if (f['name'], f['scope'].split(' ')[0]) == key:
                if reason not in f['reason']:
                    f['reason'] += '；' + reason
                f['order'] = min(f['order'], order)
        return
    seen.add(key)
    focus_last.append({'name': name, 'scope': scope, 'avg': avg, 'max': mx,
                       'reason': reason, 'order': order})
for s in last_sessions:
    for a in s['athletes']:
        if a['zero_rate'] >= 15:
            add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
                      f"心率数据缺失 {a['zero_rate']:.0f}%（心率带异常）", 0)
top_avg = sorted(((a['avg'], a, s) for s in last_sessions for a in s['athletes']), reverse=True)[:3]
for avg, a, s in top_avg:
    add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
              f"单场平均心率最高（{a['avg']:.0f} bpm）", 1)
for s in last_sessions:
    for a in s['athletes']:
        if a['max'] >= 210:
            add_focus(a['name'], f"{s['date']} {s['name']}", a['avg'], a['max'],
                      f"心率峰值过高（{a['max']:.0f} bpm）", 2)
trimp_by, scope_by, best = {}, {}, {}
for s in last_sessions:
    for a in s['athletes']:
        if not np.isnan(a['trimp']):
            trimp_by[a['name']] = trimp_by.get(a['name'], 0.0) + a['trimp']
            scope_by.setdefault(a['name'], []).append((s['date'], s['name']))
            b = best.get(a['name'], (0.0, 0.0))
            best[a['name']] = (max(b[0], a['avg']), max(b[1], a['max']))
multi = {k: v for k, v in trimp_by.items() if len(scope_by[k]) >= 2}
for nm, tp in sorted(multi.items(), key=lambda x: -x[1])[:5]:
    if nm in {f['name'] for f in focus_last}:
        continue
    avg, mx = best[nm]
    scopes = '、'.join(f"{d} {n}" for d, n in scope_by[nm])
    add_focus(nm, scopes, avg, mx,
              f"跨 {len(scope_by[nm])} 场累计负荷最高（TRIMP {tp:.0f}），注意疲劳累积", 3)
focus_last.sort(key=lambda f: f['order'])

# ---------- 个体周汇总 ----------
def weekly_stats(name, week):
    ss = [s for s in sessions if s['week'] == week]
    rows = [(s, a) for s in ss for a in s['athletes'] if a['name'] == name]
    if not rows:
        return None
    avgs = [a['avg'] for _, a in rows]
    return {
        'n': len(rows),
        'avg': float(np.nanmean(avgs)),
        'max': float(np.nanmax([a['max'] for _, a in rows])),
        'trimp': float(np.nansum([a['trimp'] for _, a in rows if not np.isnan(a['trimp'])])),
        'hi': float(np.nansum([a['hi_min'] for _, a in rows])),
        'zero_max': max(a['zero_rate'] for _, a in rows),
        'sess': '、'.join(f"{s['date'][5:]} {s['name']}" for s, _ in rows),
    }

track = []
for f in focus_last:
    lw = weekly_stats(f['name'], 'last')
    tw = weekly_stats(f['name'], 'this')
    status = '本周未出场'
    if tw:
        if tw['zero_max'] >= 5:
            status = '数据异常（心率带）'
        else:
            d = tw['avg'] - lw['avg']
            status = '强度上升' if d >= 3 else ('强度下降' if d <= -3 else '强度持平')
            if tw['n'] >= 2 and tw['trimp'] >= 500:
                status += '，负荷仍高'
    track.append({'name': f['name'], 'reason': f['reason'], 'lw': lw, 'tw': tw, 'status': status})
# ---------- ECharts ----------
def J(x):
    return json.dumps(x, ensure_ascii=False)
def ech(id_, body, h=360):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')

coaches = coach_order
avg_l = [round(coach_agg[c]['last']['avg'], 1) if coach_agg[c]['last'] else None for c in coaches]
avg_t = [round(coach_agg[c]['this']['avg'], 1) if coach_agg[c]['this'] else None for c in coaches]
hi_l = [round(coach_agg[c]['last']['hi_per'], 1) if coach_agg[c]['last'] else None for c in coaches]
hi_t = [round(coach_agg[c]['this']['hi_per'], 1) if coach_agg[c]['this'] else None for c in coaches]
tr_l = [round(coach_agg[c]['last']['trimp']) if coach_agg[c]['last'] else None for c in coaches]
tr_t = [round(coach_agg[c]['this']['trimp']) if coach_agg[c]['this'] else None for c in coaches]
z45_l = [round(coach_agg[c]['last']['zone45'], 1) if coach_agg[c]['last'] and not np.isnan(coach_agg[c]['last']['zone45']) else None for c in coaches]
z45_t = [round(coach_agg[c]['this']['zone45'], 1) if coach_agg[c]['this'] and not np.isnan(coach_agg[c]['this']['zone45']) else None for c in coaches]

def group_js(name, data, color, fname):
    return ("{name:'" + name + "',type:'bar',barWidth:'28%',data:" + J(data) +
            ",itemStyle:{color:'" + color + "'},label:{show:true,position:'top',fontSize:8},"
            "tooltip:{formatter:function(p){return p.seriesName+'<br>'+p.name+'：'+p.value;}}}")

ch = {}
ch['c_avg'] = ech('c_avg', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{data:['上周平均心率','本周平均心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练平均心率周对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:45},
 xAxis:{type:'category',data:""" + J(coaches) + """,axisLabel:{fontSize:10}},
 yAxis:{type:'value',name:'次/分'},
 series:[""" + group_js('上周平均心率', avg_l, LW_C, '') + "," + group_js('本周平均心率', avg_t, TW_C, '') + """]
});""", 360)

ch['c_hi'] = ech('c_hi', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{data:['上周人均≥160min','本周人均≥160min'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练高强度时间周对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:45},
 xAxis:{type:'category',data:""" + J(coaches) + """,axisLabel:{fontSize:10}},
 yAxis:{type:'value',name:'人均分钟'},
 series:[""" + group_js('上周人均≥160min', hi_l, LW_C, '') + "," + group_js('本周人均≥160min', hi_t, TW_C, '') + """]
});""", 360)

ch['c_trimp'] = ech('c_trimp', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{data:['上周总TRIMP','本周总TRIMP'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练训练负荷周对比',pixelRatio:2},restore:{}}},
 grid:{left:60,right:25,top:42,bottom:45},
 xAxis:{type:'category',data:""" + J(coaches) + """,axisLabel:{fontSize:10}},
 yAxis:{type:'value',name:'TRIMP'},
 series:[""" + group_js('上周总TRIMP', tr_l, LW_C, '') + "," + group_js('本周总TRIMP', tr_t, TW_C, '') + """]
});""", 360)

ch['c_zone'] = ech('c_zone', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{data:['上周高强度区间%','本周高强度区间%'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练高强度区间周对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:45},
 xAxis:{type:'category',data:""" + J(coaches) + """,axisLabel:{fontSize:10}},
 yAxis:{type:'value',name:'区间4+5占比%'},
 series:[""" + group_js('上周高强度区间%', z45_l, LW_C, '') + "," + group_js('本周高强度区间%', z45_t, TW_C, '') + """]
});""", 360)

focus_chart = [t for t in track if t['tw']]
f_names = [t['name'] for t in focus_chart]
f_lw = [round(t['lw']['avg'], 1) for t in focus_chart]
f_tw = [round(t['tw']['avg'], 1) for t in focus_chart]
ch['c_focus'] = ech('c_focus', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{data:['上周平均心率','本周平均心率'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'重点运动员周对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:42,bottom:60},
 xAxis:{type:'category',data:""" + J(f_names) + """,axisLabel:{rotate:25,fontSize:9}},
 yAxis:{type:'value',name:'次/分'},
 series:[""" + group_js('上周平均心率', f_lw, LW_C, '') + "," + group_js('本周平均心率', f_tw, TW_C, '') + """]
});""", 380)

# ---------- 表格 ----------
def table_to_html(headers, rows):
    th = ''.join(f'<th>{html.escape(h)}</th>' for h in headers)
    trs = []
    for r in rows:
        trs.append('<tr>' + ''.join(f'<td>{html.escape(str(c))}</td>' for c in r) + '</tr>')
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'

def tblbox(name, headers, rows):
    return (f'<div class="tblbox">'
            f'<div class="tblbar">'
            f'<button class="dl" data-name="{name}" onclick="exportTableCSV(this)">导出CSV</button>'
            f'<button class="dl" onclick="copyTable(this)">复制表格</button></div>'
            + table_to_html(headers, rows) + '</div>')

def delta(vl, vt):
    if vl is None or vt is None:
        return '-'
    d = vt - vl
    return f"{d:+.0f}"

t1_headers = ['教练', '上周场次', '本周场次', '上周人次', '本周人次', '上周均心', '本周均心', '均心变化',
              '上周人均≥160', '本周人均≥160', '变化', '上周人均TRIMP', '本周人均TRIMP', '人均变化',
              '上周总TRIMP', '本周总TRIMP', '总量变化']
t1_rows = []
for c in coaches:
    L, T = coach_agg[c]['last'], coach_agg[c]['this']
    if not L or not T:
        continue
    lp, tp = L['trimp']/L['n_ath'], T['trimp']/T['n_ath']
    t1_rows.append([c, str(L['n_sess']), str(T['n_sess']), str(L['n_ath']), str(T['n_ath']),
                    f"{L['avg']:.0f}", f"{T['avg']:.0f}", delta(L['avg'], T['avg']),
                    f"{L['hi_per']:.0f}", f"{T['hi_per']:.0f}", delta(L['hi_per'], T['hi_per']),
                    f"{lp:.0f}", f"{tp:.0f}", delta(lp, tp),
                    f"{L['trimp']:.0f}", f"{T['trimp']:.0f}", delta(L['trimp'], T['trimp'])])

t2_headers = ['运动员', '上周关注原因', '上周均心', '上周峰值', '上周TRIMP', '本周出场',
              '本周均心', '本周峰值', '本周TRIMP', '本周状态']
t2_rows = []
for t in track:
    tw = t['tw']
    t2_rows.append([t['name'], t['reason'],
                    f"{t['lw']['avg']:.0f}", f"{t['lw']['max']:.0f}", f"{t['lw']['trimp']:.0f}",
                    f"{tw['n']}次" if tw else '未出场',
                    f"{tw['avg']:.0f}" if tw else '-',
                    f"{tw['max']:.0f}" if tw else '-',
                    f"{tw['trimp']:.0f}" if tw else '-',
                    t['status']])

def card(label, last, this):
    return (f'<div style="flex:1;min-width:150px;background:#fff;border:1px solid #ece7dc;border-radius:10px;padding:12px;text-align:center">'
            f'<div style="color:#888;font-size:12px">{label}</div>'
            f'<div style="font-size:17px;font-weight:700;color:#39454f;margin-top:4px">'
            f'<span style="color:#9aa7b5">{last}</span> → <span style="color:#3f7fb8">{this}</span></div></div>')

cards = ('<div style="display:flex;flex-wrap:wrap;gap:10px;margin:14px 0">'
         + card('场次', overall_last['n_sess'], overall_this['n_sess'])
         + card('运动员人次', overall_last['n_ath'], overall_this['n_ath'])
         + card('平均心率(bpm)', f"{overall_last['avg']:.0f}", f"{overall_this['avg']:.0f}")
         + card('总负荷TRIMP', f"{overall_last['trimp']:.0f}", f"{overall_this['trimp']:.0f}")
         + '</div>')

echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()
html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>训练强度周对比 · 上周(7-21~23) vs 本周(7-28~30)</title>
<style>
body { font-family:'Microsoft YaHei',sans-serif; margin:0; background:#faf9f6; color:#333; }
.wrap { max-width:1100px; margin:0 auto; padding:24px; }
h1 { font-size:22px; margin:0 0 2px; }
.sub { color:#888; font-size:13px; margin-bottom:18px; }
h2 { font-size:16px; border-left:4px solid #3f7fb8; padding-left:8px; margin:28px 0 8px; }
table { border-collapse:collapse; width:100%; font-size:12.5px; background:#fff; }
th,td { padding:6px 8px; border-bottom:1px solid #e8e4da; text-align:left; }
th { background:#37424f; color:#fff; font-weight:600; }
tbody tr:nth-child(even) { background:#faf9f6; }
.tblbox { margin:14px 0; }
.tblbar { display:flex; gap:8px; margin-bottom:6px; }
button.dl { background:#f0ece2; border:1px solid #ddd5c4; color:#555; border-radius:5px; padding:4px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
button.dl:hover { background:#e6e0d2; }
.note { background:#fdf6ea; border:1px solid #ecdcb8; border-radius:6px; padding:10px 14px; font-size:12.5px; color:#7a6634; margin:12px 0; }
.chartbox { background:#fff; border:1px solid #ece7dc; border-radius:8px; padding:8px; margin:12px 0; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<h1>训练强度周对比 · 上周（7-21~23） vs 本周（7-28~30）</h1>
<div class="sub">对比对象为同一批教练组的冰上/陆地训练（陈、李、张、姚、于）。7-11~7-18 为急性实验期，未纳入对比。图表可悬停查看、右上角可导出图片；表格可导出CSV或复制。</div>
""" + cards + """
<h2>一、教练训练强度对比</h2>
""" + tblbox('教练强度对比', t1_headers, t1_rows) + """
<div class="note">为什么会出现"强度上升但总负荷下降"：<b>总TRIMP = 人均负荷 × 人次（训练量）</b>。本周每人普遍更累（人均TRIMP上升，如教练D 94→182、教练B 137→295），但部分组本周场次/人次减少（教练D 58→22 人次、教练A 29→16），总量随之下降。看强度请优先看"人均"列，看训练量看"人次/总分钟"。</div>
<div class="chartbox">""" + ch['c_avg'] + """</div>
<div class="chartbox">""" + ch['c_hi'] + """</div>
<div class="chartbox">""" + ch['c_trimp'] + """</div>
<div class="chartbox">""" + ch['c_zone'] + """</div>
<h2>二、上周重点关注运动员 · 本周追踪</h2>
""" + tblbox('重点关注追踪', t2_headers, t2_rows) + """
<div class="chartbox">""" + ch['c_focus'] + """</div>
 <div class="note">状态判定：本周未出场=无本周数据；数据异常=本周心率带缺失较多；强度上升/下降=本周平均心率较上周变化 ≥±3 bpm；负荷仍高=本周 ≥2 场且累计 TRIMP ≥500。上表"上周关注原因"沿用上周同套规则（数据缺失/单场最高/峰值过高/累计负荷）。另：教练C 7.28 为<b>前段陆地、后段冰上</b>的复合场次，已按教练确认时间 <b>15:22</b>（录制后 103 分 13 秒）拆分为两个场次统计；运动员G冰上段数据缺失不纳入统计。</div>
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
print(f'周对比报告已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')
print('\n上周重点关注:')
for t in track:
    tw = t['tw']
    tw_s = '未出场' if not tw else f"{tw['n']}次 均心{tw['avg']:.0f}"
    print(f"  {t['name']} | {t['reason'][:30]} | 上周均心{t['lw']['avg']:.0f} | 本周{tw_s} | {t['status']}")

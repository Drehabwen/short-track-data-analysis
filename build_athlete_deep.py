# -*- coding: utf-8 -*-
"""运动员深度分析：单人多源数据（CPET/前测/实验/血液/心率）整合报告
用法：python build_athlete_deep.py [姓名]，默认使用示例运动员"""
import os, sys, re, glob, csv, json, html
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')

NAME = sys.argv[1] if len(sys.argv) > 1 else '示例运动员'
UNI = r'D:\DEV\blood\统一数据集'
DIR = r'D:\DEV\blood\最大摄氧量\最大摄氧量数据'
OUT = os.path.join(r'D:\DEV\blood\最大摄氧量', f'运动员深度分析_{NAME}.html')
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

# ---------- CPET 解析 ----------
def parse_workbook(path):
    tree = ET.parse(path)
    root = tree.getroot()
    for ws in root.findall('.//ss:Worksheet', NS):
        rows = []
        for row in ws.findall('.//ss:Row', NS):
            cells = []
            for c in row.findall('ss:Cell', NS):
                d = c.find('ss:Data', NS)
                cells.append(d.text if d is not None and d.text else '')
            rows.append(cells)
        return rows

def norm(s):
    return str(s).strip().strip('"').replace(' ', '')

def find_row(rows, start, key):
    for i in range(start, len(rows)):
        if rows[i] and norm(rows[i][0]) == key:
            return i
    return None

def kv(rows, key):
    for r in rows:
        if r and norm(r[0]) == key and len(r) > 1:
            return r[1]
    return ''

def num(s):
    s = str(s).strip()
    if s in ('', '-', 'NaN'):
        return None
    try:
        return float(s)
    except Exception:
        return None

def tsec(s):
    try:
        p = str(s).strip().split(':')
        if len(p) == 3:
            return float(p[0])*3600 + float(p[1])*60 + float(p[2])
        return float(p[0])
    except Exception:
        return None

def parse_cpet(path):
    rows = parse_workbook(path)
    r = {}
    r['sex'] = kv(rows, '性别'); r['birth'] = kv(rows, '出生日期')
    h = kv(rows, '身高'); w = kv(rows, '体重')
    r['height_cm'] = num(re.sub(r'[^0-9.]', '', h)) if h else None
    r['weight_kg'] = num(re.sub(r'[^0-9.]', '', w)) if w else None
    r['bmi'] = num(kv(rows, 'BMI'))
    r['start'] = kv(rows, '开始时间'); r['duration'] = kv(rows, '持续时间')
    si = find_row(rows, 0, '总结表')
    summary = {}
    if si is not None:
        hdr = [norm(x) for x in rows[si+1]]
        for row in rows[si+2:]:
            if not row or not norm(row[0]):
                break
            summary[norm(row[0])] = {hdr[j]: row[j] if j < len(row) else '' for j in range(len(hdr))}
    def sv(var, col):
        return num(summary.get(var, {}).get(col, ''))
    r['vo2peak'] = sv("V'O2", 'V\'O2peak'); r['vo2peak_kg'] = sv("V'O2/kg", 'V\'O2peak')
    r['pct_norm'] = sv("V'O2", 'V\'O2peak%Norm')
    r['vt1_kg'] = sv("V'O2/kg", 'VT1'); r['vt1_pct'] = sv("V'O2/kg", 'VT1%Max')
    r['vt2_kg'] = sv("V'O2/kg", 'VT2')
    li = find_row(rows, si+1, '斜率值')
    if li is not None:
        for row in rows[li+1:]:
            if row and norm(row[0]) == "V'E(V'CO2)":
                r['slope'] = num(row[2] if len(row) > 2 else '')
                break
    mi = find_row(rows, 0, 'MeasurementData')
    if mi is None:
        for i, row in enumerate(rows):
            if row and 'Measurement' in str(row[0]):
                mi = i; break
    if mi is not None:
        hdr = [norm(x) for x in rows[mi+1]]
        idx = {name: j for j, name in enumerate(hdr) if name}
        def ci(keys):
            for k in keys:
                if k in idx:
                    return idx[k]
            return None
        i_t = ci(['t']); i_st = ci(['阶段']); i_v = ci(["V'O2/kg"])
        i_r = ci(['RER']); i_hr = ci(['HR']); i_ve = ci(["V'E"])
        t_, st_, v_, r_, hr_, ve_ = [], [], [], [], [], []
        for row in rows[mi+3:]:
            if not row:
                continue
            tt = tsec(row[i_t]) if i_t is not None and len(row) > i_t else None
            if tt is None:
                continue
            t_.append(tt)
            st_.append(row[i_st] if i_st is not None and len(row) > i_st else '')
            v_.append(num(row[i_v]) if i_v is not None and len(row) > i_v else None)
            rr = num(row[i_r]) if i_r is not None and len(row) > i_r else None
            r_.append(rr if rr is not None and rr < 2.5 else None)
            hr_.append(num(row[i_hr]) if i_hr is not None and len(row) > i_hr else None)
            ve_.append(num(row[i_ve]) if i_ve is not None and len(row) > i_ve else None)
        step = max(1, len(t_)//700)
        r['t'] = t_[::step]; r['st'] = st_[::step]; r['v'] = v_[::step]
        r['r'] = r_[::step]; r['hr'] = hr_[::step]; r['ve'] = ve_[::step]
        valid = lambda a: [x for x in a if x is not None]
        r['hr_max'] = max(valid(hr_)) if valid(hr_) else None
        r['rer_max'] = max(valid(r_)) if valid(r_) else None
        r['ve_max'] = max(valid(ve_)) if valid(ve_) else None
    return r

cpet_file = None
for f in glob.glob(os.path.join(DIR, 'CPET__*.xml')):
    base = os.path.basename(f)
    if NAME.replace('_', '') in base.replace('_', ''):
        cpet_file = f
        break
cpet = parse_cpet(cpet_file) if cpet_file else {}

# ---------- 统一数据集 ----------
def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

main_rows = read_csv(os.path.join(UNI, '统一数据集_受试者主表.csv'))
main = next((r for r in main_rows if r['name'] == NAME), None)
pt_rows = read_csv(os.path.join(UNI, '前测明细表.csv'))
pt = next((r for r in pt_rows if r.get('name') == NAME), None)
blood_rows = [r for r in read_csv(os.path.join(UNI, '血液明细表_链接后.csv')) if r.get('实验表姓名') == NAME]
hr_rows = [r for r in read_csv(os.path.join(UNI, '心率明细表.csv')) if r.get('姓名') == NAME]
profile_rows = read_csv(r'D:\DEV\blood\最大摄氧量\最大摄氧量_人员档案.csv')
profile = next((r for r in profile_rows if r.get('name') == NAME), None)

print(f'姓名: {NAME}')
print(f'  CPET: {bool(cpet)} | 主表: {bool(main)} | 前测: {bool(pt)} | 血液 {len(blood_rows)} 条 | 心率 {len(hr_rows)} 场 | 档案: {bool(profile)}')
from datetime import datetime
def age_at(birth, start):
    try:
        b = datetime.strptime(str(birth).split(' ')[0].replace('/', '-'), '%Y-%m-%d')
        s = datetime.strptime(str(start)[:10].replace('/', '-'), '%Y-%m-%d')
        return round((s - b).days / 365.25, 1)
    except Exception:
        return None
age = age_at(cpet.get('birth') or (profile or {}).get('birth'), cpet.get('start'))

def fnum(x):
    try:
        return float(x)
    except Exception:
        return None

def pct_rank(vals, v, lower_better=False):
    vals = [x for x in vals if x is not None]
    if v is None or not vals:
        return None
    if lower_better:
        cnt = sum(1 for x in vals if x > v)
    else:
        cnt = sum(1 for x in vals if x < v)
    return round(cnt / max(len(vals)-1, 1) * 100)

# 前测雷达（同龄/全队百分位）
def gv(row, *keys):
    for k in keys:
        if row and row.get(k) not in (None, ''):
            return fnum(row[k])
    return None
dim_defs = [
    ('FMS总分', lambda r: gv(r, 'fms_total'), False),
    ('YBT前伸(cm)', lambda r: (lambda a, b: (a+b)/2 if a is not None and b is not None else None)(
        gv(r, 'ybt_left_ant'), gv(r, 'ybt_right_ant')), False),
    ('CMJ(cm)', lambda r: gv(r, 'cmj_height_cm'), False),
    ('500m速度', lambda r: (lambda t: 500/t if t else None)(gv(r, 'profile_time_500m_s')), False),
    ('踝背屈ROM', lambda r: (lambda a, b: (a+b)/2 if a is not None and b is not None else None)(
        gv(r, 'rom_strength_ankle_dorsi_l'), gv(r, 'rom_strength_ankle_dorsi_r')), False),
    ('膝伸肌力(N)', lambda r: (lambda a, b: (a+b)/2 if a is not None and b is not None else None)(
        gv(r, 'rom_strength_knee_ext_str_l'), gv(r, 'rom_strength_knee_ext_str_r')), False),
    ('力台面积(倒)', lambda r: (lambda a, b: (a+b)/2 if a is not None and b is not None else None)(
        gv(r, 'cop_left_ellipse_area'), gv(r, 'cop_right_ellipse_area')), True),
]
radar_dims, radar_vals, radar_raw = [], [], {}
for label, fn, lower in dim_defs:
    cohort = [fn(r) for r in pt_rows]
    v = fn(pt)
    pr = pct_rank(cohort, v, lower)
    radar_dims.append(label)
    radar_vals.append(pr if pr is not None else 0)
    radar_raw[label] = v

# 实验响应
def exp_num(key):
    return fnum(main.get(key)) if main else None
lac_pts = [('静息', exp_num('lactate_rest')), ('即刻', exp_num('lactate_post')), ('干预后', exp_num('lactate_interv'))]
hr_pts = [('静息', exp_num('hr_rest_avg')), ('即刻', exp_num('hr_post_avg')),
          ('24h', exp_num('hr_24h_avg')), ('72h', exp_num('hr_72h_avg'))]
cmj_pts = [('运动前', exp_num('cmj_pre')), ('24h', exp_num('cmj_24h')), ('72h', exp_num('cmj_72h'))]

# 血液
tp_order = ['BL', '24H', '72H']
analytes = ['testosterone', 'cortisol', 'urea', 'ck', 'ldh']
blood_map = {}
for r in blood_rows:
    tp = r.get('timepoint', '').strip()
    an = r.get('analyte', '').strip()
    blood_map.setdefault(an, {})[tp] = fnum(r.get('result_value'))
blood_series = []
for an in analytes:
    pts = [(tp, blood_map.get(an, {}).get(tp)) for tp in tp_order]
    base = next((v for _, v in pts if v is not None), None)
    if base:
        blood_series.append({'name': an, 'raw': [v for _, v in pts],
                             'pct': [round((v/base)*100, 1) if v is not None else None for _, v in pts]})

# 心率训练
hr_rows_sorted = sorted(hr_rows, key=lambda r: r.get('日期', ''))
hr_dates = [r.get('日期', '') for r in hr_rows_sorted]
hr_avg = [fnum(r.get('平均心率')) or 0 for r in hr_rows_sorted]
hr_trimp = [fnum(r.get('TRIMP')) or 0 for r in hr_rows_sorted]
hr_sess = [f"{r.get('日期', '')[5:]} {r.get('场次', '')}" for r in hr_rows_sorted]
hr_maxv = [fnum(r.get('最大心率')) or 0 for r in hr_rows_sorted]
trimp_total = sum(hr_trimp)

def J(x):
    return json.dumps(x, ensure_ascii=False)

def ech(id_, body, h=380):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')

ch = {}
# CPET 曲线
rec_idx = -1
for i, s in enumerate(cpet.get('st', [])):
    if '恢复' in str(s):
        rec_idx = i; break
mark_area = []
if rec_idx >= 0 and cpet.get('t'):
    mark_area.append([{'xAxis': cpet['t'][rec_idx], 'itemStyle': {'color': 'rgba(184,178,166,0.25)'}},
                      {'xAxis': cpet['t'][-1]}])
mark_lines = []
if cpet.get('vt1_kg'):
    mark_lines.append({'yAxis': cpet['vt1_kg'], 'lineStyle': {'color': '#7a6f9e', 'type': 'dashed'}, 'label': {'formatter': 'VT1'}})
if cpet.get('vo2peak_kg'):
    mark_lines.append({'yAxis': cpet['vo2peak_kg'], 'lineStyle': {'color': '#d05555', 'type': 'dashed'}, 'label': {'formatter': 'VO2peak'}})
ch['c_cpet'] = ech('c_cpet', """
c.setOption({
 tooltip:{trigger:'axis',formatter:function(ps){
  var st=''; try{ st = (ST[ps[0].dataIndex]||''); }catch(e){}
  var s='<b>""" + html.escape(NAME) + """</b> '+(st||'')+'<br>';
  ps.forEach(function(p){ s += p.marker+p.seriesName+': '+p.value+'<br>'; });
  return s; }},
 toolbox:{right:10,feature:{saveAsImage:{name:'""" + html.escape(NAME) + """_CPET',pixelRatio:2},restore:{}}},
 legend:{data:['V\\'O2/kg','RER'],top:0},
 grid:{left:55,right:55,top:35,bottom:40},
 xAxis:{type:'category',data:""" + J(cpet.get('t', [])) + """,axisLabel:{show:false},name:'时间'},
 yAxis:[{type:'value',name:'ml/kg/min',min:0,max:120},
        {type:'value',name:'RER',min:0.6,max:1.4}],
 series:[
  {name:'V\\'O2/kg',type:'line',data:""" + J(cpet.get('v', [])) + """,symbol:'none',lineStyle:{width:1.8,color:'#3f7fb8'},
   areaStyle:{color:'rgba(63,127,184,0.12)'},markArea:{silent:true,data:""" + J(mark_area) + """},
   markLine:{silent:true,symbol:'none',data:""" + J(mark_lines) + """}},
  {name:'RER',type:'line',yAxisIndex:1,data:""" + J(cpet.get('r', [])) + """,symbol:'none',lineStyle:{width:1.2,color:'#d05555'}}
 ]});""", 420)

# 前测雷达
ch['c_pretest'] = ech('c_pretest', """
c.setOption({
 tooltip:{formatter:function(p){var i=p.value[0];return '<b>""" + html.escape(NAME) + """</b><br>'+
   """ + J(radar_dims) + """[i]+'：超过全队 '+p.value[1]+'%';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'""" + html.escape(NAME) + """_体能画像',pixelRatio:2},restore:{}}},
 radar:{indicator:""" + J([{'name': d, 'max': 100} for d in radar_dims]) + """,radius:'68%',center:['50%','55%'],
  axisName:{color:'#39454f',fontSize:10}},
 series:[{type:'radar',data:[{value:""" + J(radar_vals) + """,name:'""" + html.escape(NAME) + """',
  areaStyle:{color:'rgba(63,127,184,0.25)'},itemStyle:{color:'#3f7fb8'}}]}]
});""", 430)

# 实验响应：血乳酸 / 心率 / CMJ
def line_pts(pts):
    return [{'value': v, 'name': n} for n, v in pts if v is not None]
ch['c_lac'] = ech('c_lac', """
c.setOption({
 tooltip:{trigger:'item'},
 toolbox:{right:10,feature:{saveAsImage:{name:'血乳酸响应',pixelRatio:2},restore:{}}},
 grid:{left:50,right:20,top:25,bottom:40},
 xAxis:{type:'category',data:""" + J([n for n, v in lac_pts if v is not None]) + """},
 yAxis:{type:'value',name:'mmol/L'},
 series:[{type:'line',data:""" + J([v for n, v in lac_pts if v is not None]) + """,symbolSize:9,
  lineStyle:{width:2,color:'#d05555'},itemStyle:{color:'#d05555'},
  label:{show:true,position:'top',fontSize:10}}]
});""", 300)
ch['c_hrr'] = ech('c_hrr', """
c.setOption({
 tooltip:{trigger:'item'},
 toolbox:{right:10,feature:{saveAsImage:{name:'心率响应',pixelRatio:2},restore:{}}},
 grid:{left:50,right:20,top:25,bottom:40},
 xAxis:{type:'category',data:""" + J([n for n, v in hr_pts if v is not None]) + """},
 yAxis:{type:'value',name:'次/分'},
 series:[{type:'line',data:""" + J([v for n, v in hr_pts if v is not None]) + """,symbolSize:9,
  lineStyle:{width:2,color:'#3f7fb8'},itemStyle:{color:'#3f7fb8'},
  label:{show:true,position:'top',fontSize:10}}]
});""", 300)
ch['c_cmj'] = ech('c_cmj', """
c.setOption({
 tooltip:{trigger:'item'},
 toolbox:{right:10,feature:{saveAsImage:{name:'CMJ变化',pixelRatio:2},restore:{}}},
 grid:{left:50,right:20,top:25,bottom:40},
 xAxis:{type:'category',data:""" + J([n for n, v in cmj_pts if v is not None]) + """},
 yAxis:{type:'value',name:'cm'},
 series:[{type:'bar',data:""" + J([{'value': v, 'itemStyle': {'color': '#4f9a5e'}} for n, v in cmj_pts if v is not None]) + """,
  barWidth:'45%',label:{show:true,position:'top',fontSize:10}}]
});""", 300)

# 心率训练
ch['c_hrload'] = ech('c_hrload', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{data:['平均心率','TRIMP'],top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'训练负荷',pixelRatio:2},restore:{}}},
 grid:{left:55,right:60,top:35,bottom:70},
 xAxis:{type:'category',data:""" + J(hr_sess) + """,axisLabel:{rotate:30,fontSize:8}},
 yAxis:[{type:'value',name:'次/分'},
        {type:'value',name:'TRIMP'}],
 series:[
  {name:'平均心率',type:'bar',data:""" + J(hr_avg) + """,itemStyle:{color:'#3f7fb8'},label:{show:true,position:'top',fontSize:8}},
  {name:'TRIMP',type:'line',yAxisIndex:1,data:""" + J(hr_trimp) + """,symbol:'none',lineStyle:{width:2,color:'#d05555'}}
 ]});""", 380)

# 血液（归一化 BL=100）
ch['c_blood'] = ech('c_blood', """
var BTN = """ + J([b['name'] for b in blood_series]) + """;
var RAW = """ + J([b['raw'] for b in blood_series]) + """;
c.setOption({
 tooltip:{trigger:'axis',formatter:function(ps){
  var s=ps[0].axisValue+'<br>';
  ps.forEach(function(p){
    var i=BTN.indexOf(p.seriesName); var raw=(RAW[i]||[])[p.dataIndex];
    s += p.marker+p.seriesName+': '+p.value+'%'+(raw!=null?'（'+raw+'）':'')+'<br>';
  });
  return s; }},
 legend:{data:""" + J([b['name'] for b in blood_series]) + """,top:0},
 toolbox:{right:10,feature:{saveAsImage:{name:'血液生化趋势',pixelRatio:2},restore:{}}},
 grid:{left:50,right:20,top:35,bottom:40},
 xAxis:{type:'category',data:""" + J(tp_order) + """},
 yAxis:{type:'value',name:'占基线 %（BL=100）'},
   series:""" + J([{'name': b['name'], 'type': 'line', 'data': b['pct'], 'symbolSize': 6} for b in blood_series]) + """
});""", 380)

# ---------- 解读 ----------
ins = []
if cpet.get('vo2peak_kg'):
    v = cpet['vo2peak_kg']
    lvl = '优秀' if v >= 60 else ('良好' if v >= 50 else '中等')
    ins.append(('心肺耐力', f"相对 VO2max {v:.0f} ml/kg/min（{lvl}），达预测值的 {cpet.get('pct_norm', 0):.0f}%"))
if cpet.get('vt1_pct'):
    ins.append(('通气阈', f"VT1 出现在 {cpet['vt1_pct']:.0f}% 最大摄氧量处（{'良好' if cpet['vt1_pct'] >= 70 else '一般'}，≥70% 耐力储备好）"))
if cpet.get('slope'):
    s = cpet['slope']
    ins.append(('通气效率', f"V'E/V'CO2 斜率 {s:.1f}（{'优秀' if s < 30 else ('良好' if s < 35 else '偏弱')}，越低越好）"))
if cpet.get('rer_max'):
    ins.append(('测试质量', f"RERmax {cpet['rer_max']:.2f}（{'有效' if cpet['rer_max'] >= 1.0 else '可能未达极限'}，≥1.0 判定 VO2max 有效）"))
if pt and radar_raw.get('FMS总分') is not None:
    ins.append(('FMS', f"功能性动作筛查总分 {radar_raw['FMS总分']:.0f}/35（同队百分位 {radar_vals[0]}%）"))
if radar_raw.get('CMJ(cm)') is not None:
    ins.append(('弹跳力', f"CMJ 纵跳 {radar_raw['CMJ(cm)']:.1f} cm（百分位 {radar_vals[2]}%）"))
if radar_raw.get('500m速度') is not None:
    ins.append(('专项速度', f"500m 成绩 {radar_raw['500m速度'] and round(500/radar_raw['500m速度'], 2)} s（速度百分位 {radar_vals[3]}%）"))
if main:
    ins.append(('实验干预', f"急性疲劳实验分组：{main.get('intervention') or '未记录'}，造模负荷 {main.get('load_pct') or '-'}%"))
    if exp_num('cmj_pre') and exp_num('cmj_24h'):
        d = exp_num('cmj_24h') - exp_num('cmj_pre')
        ins.append(('恢复能力', f"CMJ 24h 较运动前 {d:+.1f} cm（{'恢复/增强' if d >= 0 else '下降'}，反映急性疲劳后恢复）"))
if blood_map.get('ck', {}).get('24H') and blood_map.get('ck', {}).get('BL'):
    ck = blood_map['ck']
    ratio = ck['24H'] / ck['BL'] if ck.get('BL') else None
    if ratio:
        ins.append(('肌肉损伤', f"肌酸激酶 CK 24h 为基线的 {ratio:.1f} 倍（{ck['24H']:.0f} U/L）——肌肉损伤/训练应激水平"))
if trimp_total:
    ins.append(('训练负荷', f"心率数据 {len(hr_rows)} 场，累计 TRIMP {trimp_total:.0f}，场均心率 {sum(hr_avg)/len(hr_avg):.0f} bpm"))

# ---------- 表格 ----------
def table_to_html(headers, rows):
    th = ''.join(f'<th>{html.escape(h)}</th>' for h in headers)
    trs = []
    for r in rows:
        trs.append('<tr>' + ''.join(f'<td>{html.escape(str(c))}</td>' for c in r) + '</tr>')
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'

def tblbox(name, headers, rows):
    return (f'<div class="tblbox"><div class="tblbar">'
            f'<button class="dl" data-name="{name}" onclick="exportTableCSV(this)">导出CSV</button>'
            f'<button class="dl" onclick="copyTable(this)">复制表格</button></div>'
            + table_to_html(headers, rows) + '</div>')

basic_rows = [['姓名', NAME], ['性别', cpet.get('sex') or (main or {}).get('gender') or '-'],
              ['出生日期', cpet.get('birth') or (profile or {}).get('birth') or '-'],
              ['年龄（测试时）', f"{age} 岁" if age else '-'],
              ['身高', f"{cpet.get('height_cm') or (main or {}).get('height_cm') or '-'} cm"],
              ['体重', f"{cpet.get('weight_kg') or (main or {}).get('weight_kg') or '-'} kg"],
              ['BMI', cpet.get('bmi') or (main or {}).get('bmi') or '-'],
              ['CPET 设备', cpet.get('device', '-')], ['测试时间', cpet.get('start', '-')]]

cpet_rows = [['相对 VO2max', f"{cpet['vo2peak_kg']:.0f} ml/kg/min" if cpet.get('vo2peak_kg') else '-'],
             ['绝对 VO2max', f"{cpet['vo2peak']:.2f} L/min" if cpet.get('vo2peak') else '-'],
             ['预测达成率', f"{cpet['pct_norm']:.0f}%" if cpet.get('pct_norm') else '-'],
             ['VT1 通气阈', f"{cpet['vt1_kg']:.0f} ml/kg/min（{cpet['vt1_pct']:.0f}% max）" if cpet.get('vt1_kg') else '-'],
             ['通气效率斜率', f"{cpet['slope']:.1f}" if cpet.get('slope') else '-'],
             ['RERmax', f"{cpet['rer_max']:.2f}" if cpet.get('rer_max') else '-'],
             ['最大通气量', f"{cpet['ve_max']:.0f} L/min" if cpet.get('ve_max') else '-'],
             ['测试时长', cpet.get('duration', '-')]]

pt_rows_out = [[d, f"{radar_raw.get(d):.1f}" if radar_raw.get(d) is not None else '-',
                f"{p}%" if p is not None else '-'] for d, p in zip(radar_dims, radar_vals)]

exp_rows = []
if main:
    exp_rows = [['分组/干预', main.get('intervention') or '-'], ['造模负荷', main.get('load_pct') or '-'],
                ['CMJ 前/24h/72h', ' / '.join(str(x) if x is not None else '-' for x in [exp_num('cmj_pre'), exp_num('cmj_24h'), exp_num('cmj_72h')])],
                ['血乳酸 静息/即刻/干预后', ' / '.join(str(x) if x is not None else '-' for x in [exp_num('lactate_rest'), exp_num('lactate_post'), exp_num('lactate_interv')])],
                ['心率 静息/即刻/24h/72h', ' / '.join(str(x) if x is not None else '-' for x in [exp_num('hr_rest_avg'), exp_num('hr_post_avg'), exp_num('hr_24h_avg'), exp_num('hr_72h_avg')])]]

blood_rows_out = []
for an in analytes:
    m = blood_map.get(an, {})
    blood_rows_out.append([an] + [f"{m.get(tp)}" if m.get(tp) is not None else '-' for tp in tp_order])

hr_tbl = [['日期', '场次', '类型', '时长min', '平均心率', '最大心率', 'TRIMP', '≥160min']]
for r in hr_rows_sorted:
    hr_tbl.append([r.get('日期', ''), r.get('场次', ''), r.get('类型', ''), r.get('时长min', ''),
                   r.get('平均心率', ''), r.get('最大心率', ''), r.get('TRIMP', ''), r.get('高强度min', '')])

ins_html = ''
for label, txt in ins:
    ins_html += f'<div style="margin:6px 0"><span style="display:inline-block;min-width:88px;color:#3f7fb8;font-weight:700">{label}</span>{txt}</div>'

cards = ''
for k, v in [('年龄', f"{age}岁" if age else '-'), ('相对VO2max', f"{cpet.get('vo2peak_kg', 0):.0f} ml/kg/min" if cpet.get('vo2peak_kg') else '-'),
             ('预测达成', f"{cpet.get('pct_norm', 0):.0f}%" if cpet.get('pct_norm') else '-'),
             ('累计TRIMP', f"{trimp_total:.0f}" if trimp_total else '-'),
             ('心率场次', f"{len(hr_rows)} 场")]:
    cards += f'<div class="kpi"><div class="v">{v}</div><div class="l">{k}</div></div>'

echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()
html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>运动员深度分析 · """ + html.escape(NAME) + """</title>
<style>
body { font-family:'Microsoft YaHei',sans-serif; margin:0; background:#f5f3ee; color:#333; }
.wrap { max-width:1120px; margin:0 auto; padding:24px; }
h1 { font-size:24px; margin:0 0 2px; }
.sub { color:#888; font-size:13px; margin-bottom:16px; }
h2 { font-size:17px; border-left:4px solid #3f7fb8; padding-left:8px; margin:28px 0 8px; }
table { border-collapse:collapse; width:100%; font-size:12.5px; background:#fff; }
th,td { padding:5px 8px; border-bottom:1px solid #e8e4da; text-align:left; }
th { background:#37424f; color:#fff; font-weight:600; }
tbody tr:nth-child(even) { background:#faf9f6; }
.tblbox { margin:12px 0; }
.tblbar { display:flex; gap:8px; margin-bottom:6px; }
button.dl { background:#f0ece2; border:1px solid #ddd5c4; color:#555; border-radius:5px; padding:4px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
button.dl:hover { background:#e6e0d2; }
.chartbox { background:#fff; border:1px solid #ece7dc; border-radius:10px; padding:10px; margin:12px 0; }
.kpis { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
.kpi { flex:1; min-width:140px; background:#fff; border:1px solid #ece7dc; border-radius:10px; padding:12px; text-align:center; }
.kpi .v { font-size:20px; font-weight:800; color:#3f7fb8; }
.kpi .l { color:#888; font-size:12px; margin-top:3px; }
.grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:10px; }
.ins { background:#fbfaf7; border:1px solid #e0dbd0; border-radius:10px; padding:12px 16px; font-size:13px; margin:10px 0; }
.badge { display:inline-block; background:#e8eee3; color:#5f7d55; border-radius:10px; padding:1px 8px; font-size:11px; margin-left:6px; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<h1>运动员深度分析 · """ + html.escape(NAME) + """</h1>
<div class="sub">整合心肺功能（CPET）、体能前测、急性疲劳实验、血液生化、训练心率五类数据</div>
<div class="kpis">""" + cards + """</div>
<h2>基本信息</h2>
""" + tblbox('基本信息', ['项目', '内容'], basic_rows) + """
<h2>一、心肺功能（CPET）</h2>
""" + tblbox('CPET指标', ['指标', '数值'], cpet_rows) + """
<div class="chartbox">""" + ch['c_cpet'] + """</div>
<h2>二、体能画像（前测，百分位）</h2>
<div class="grid2"><div class="chartbox">""" + ch['c_pretest'] + """</div></div>
""" + tblbox('前测关键指标', ['指标', '数值', '同队百分位'], pt_rows_out) + """
<h2>三、急性疲劳实验响应</h2>
""" + tblbox('实验响应', ['项目', '数值'], exp_rows) + """
<div class="grid2">
<div class="chartbox">""" + ch['c_lac'] + """</div>
<div class="chartbox">""" + ch['c_hrr'] + """</div>
<div class="chartbox">""" + ch['c_cmj'] + """</div>
</div>
<h2>四、训练负荷（心率监控）</h2>
<div class="chartbox">""" + ch['c_hrload'] + """</div>
""" + tblbox('心率场次', hr_tbl[0], hr_tbl[1:]) + """
<h2>五、血液生化（BL / 24H / 72H）</h2>
<div class="chartbox">""" + ch['c_blood'] + """</div>
""" + tblbox('血液明细', ['指标', 'BL', '24H', '72H'], blood_rows_out) + """
<h2>六、综合解读</h2>
<div class="ins">""" + ins_html + """</div>
<script>
function toast(msg){
  var el=document.getElementById('toast');
  if(!el){ el=document.createElement('div'); el.id='toast';
    el.style.cssText='position:fixed;left:50%;bottom:32px;transform:translateX(-50%);background:#37424f;color:#fff;padding:8px 18px;border-radius:18px;font-size:13px;z-index:99;opacity:0;transition:opacity .2s';
    document.body.appendChild(el); }
  el.textContent=msg; el.style.opacity='1';
  clearTimeout(el._t); el._t=setTimeout(function(){ el.style.opacity='0'; }, 1800);
}
function tableToCSV(tbl){
  return [...tbl.querySelectorAll('tr')].map(function(tr){
    return [...tr.querySelectorAll('th,td')].map(function(c){
      var t=(c.innerText||'').replace(/\\s+/g,' ').trim();
      return /[",\\n]/.test(t)? '"'+t.replace(/"/g,'""')+'"' : t;
    }).join(',');
  }).join('\\r\\n');
}
function exportTableCSV(btn){
  var box=btn.closest('.tblbox');
  var csv='\\ufeff'+tableToCSV(box.querySelector('table'));
  var a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  a.download=(btn.getAttribute('data-name')||'表格')+'.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 1000);
}
async function copyTable(btn){
  var box=btn.closest('.tblbox');
  var tbl=box.querySelector('table');
  var htmlStr=tbl.outerHTML;
  var plain=tableToCSV(tbl).replace(/,/g,'\\t');
  try {
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([htmlStr],{type:'text/html'}),
      'text/plain': new Blob([plain],{type:'text/plain'})})]);
    toast('已复制表格');
  } catch(e){
    try { await navigator.clipboard.writeText(plain); toast('已复制表格'); }
    catch(e2){ toast('复制失败'); }
  }
}
window.addEventListener('resize', function(){
  document.querySelectorAll('div[id^="c_"]').forEach(function(d){ var i=echarts.getInstanceByDom(d); if(i) i.resize(); });
});
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'深度分析已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')
print('综合解读:')
for label, txt in ins:
    print(f'  {label}: {txt}')

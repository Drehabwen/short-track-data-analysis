# -*- coding: utf-8 -*-
"""CPET 结果报告：解析 43 场测试 → 每人最优场次 → 交互式 HTML"""
import os, sys, re, glob, csv, json, html
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')

DIR = r'D:\DEV\blood\最大摄氧量数据'
OUT = os.path.join(DIR, '..', '最大摄氧量_结果报告.html')
OUT = os.path.normpath(OUT)
ECHARTS_PATH = r'D:\DEV\dashboard\echarts.min.js'
NS = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}
LOGO_DIR = r'D:\DEV\blood\ref_logos'

def b64img(name, mime):
    import base64
    with open(os.path.join(LOGO_DIR, name), 'rb') as f:
        return f'data:{mime};base64,' + base64.b64encode(f.read()).decode()

LOGO_1 = b64img('image1.png', 'image/png')
LOGO_2 = b64img('image2.jpeg', 'image/jpeg')
LOGO_3 = b64img('image3.jpeg', 'image/jpeg')

import json as _json
with open(r'D:\DEV\blood\最大摄氧量\hr_2wk.json', encoding='utf-8') as _f:
    HR2W = _json.load(_f)

# 本周/上周日期范围（动态，随 hr_2wk.json 更新）
W_THIS = HR2W['this'].get('range', '本周')
W_LAST = HR2W['last'].get('range', '上周')

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

def dur_sec(s):
    p = str(s).split(':')
    if len(p) == 3:
        return int(p[0])*3600 + int(p[1])*60 + int(float(p[2]))
    return 0

def parse_test(path):
    rows = parse_workbook(path)
    rec = {'file': os.path.basename(path)}
    rec['surname'] = kv(rows, '姓'); rec['given'] = kv(rows, '名')
    rec['name'] = rec['surname'] + rec['given']
    rec['sex'] = kv(rows, '性别')
    rec['birth'] = kv(rows, '出生日期')
    h = kv(rows, '身高'); w = kv(rows, '体重')
    rec['height_cm'] = num(re.sub(r'[^0-9.]', '', h)) if h else None
    rec['weight_kg'] = num(re.sub(r'[^0-9.]', '', w)) if w else None
    rec['bmi'] = num(kv(rows, 'BMI'))
    rec['start'] = kv(rows, '开始时间')
    rec['duration'] = kv(rows, '持续时间')
    rec['dur_sec'] = dur_sec(rec['duration'])
    rec['device'] = kv(rows, 'CPET设备')
    rec['pred_vo2max'] = num(re.sub(r'[^0-9.]', '', kv(rows, '最大 摄氧量')))
    rec['pred_vo2kg'] = num(re.sub(r'[^0-9.]', '', kv(rows, '最大 相对摄氧量')))
    si = find_row(rows, 0, '总结表')
    summary = {}
    if si is not None:
        hdr = [norm(x) for x in rows[si+1]]
        for r in rows[si+2:]:
            if not r or not norm(r[0]):
                break
            var = norm(r[0])
            summary[var] = {hdr[j]: r[j] if j < len(r) else '' for j in range(len(hdr))}
    def sv(var, col):
        return num(summary.get(var, {}).get(col, ''))
    rec['vo2peak'] = sv("V'O2", 'V\'O2peak')
    rec['vo2peak_kg'] = sv("V'O2/kg", 'V\'O2peak')
    rec['pct_norm'] = sv("V'O2", 'V\'O2peak%Norm')
    rec['vt1_kg'] = sv("V'O2/kg", 'VT1')
    rec['vt1_pct'] = sv("V'O2/kg", 'VT1%Max')
    rec['vt2_kg'] = sv("V'O2/kg", 'VT2')
    rec['ve_slope'] = None
    li = find_row(rows, si+1, '斜率值')
    if li is not None:
        for r in rows[li+1:]:
            if r and norm(r[0]) == "V'E(V'CO2)":
                rec['ve_slope'] = num(r[2] if len(r) > 2 else '')
                break
    mi = find_row(rows, 0, 'MeasurementData')
    if mi is None:
        for i, r in enumerate(rows):
            if r and 'Measurement' in str(r[0]):
                mi = i; break
    ts = []
    if mi is not None:
        hdr = [norm(x) for x in rows[mi+1]]
        idx = {name: j for j, name in enumerate(hdr) if name}
        def ci(keys):
            for k in keys:
                if k in idx:
                    return idx[k]
            return None
        i_rer = ci(['RER']); i_ve = ci(["V'E"]); i_bf = ci(['BF'])
        i_vo2kg = ci(["V'O2/kg"]); i_stage = ci(['阶段']); i_t = ci(['t'])
        mx = {'rer': None, 've': None, 'bf': None, 'vo2kg': None}
        train_secs = []
        for r in rows[mi+3:]:
            if not r or len(r) < 3:
                continue
            if i_rer is not None and len(r) > i_rer:
                v = num(r[i_rer])
                if v is not None and v < 2.5 and (mx['rer'] is None or v > mx['rer']):
                    mx['rer'] = v
            if i_ve is not None and len(r) > i_ve:
                v = num(r[i_ve])
                if v is not None and (mx['ve'] is None or v > mx['ve']):
                    mx['ve'] = v
            if i_bf is not None and len(r) > i_bf:
                v = num(r[i_bf])
                if v is not None and (mx['bf'] is None or v > mx['bf']):
                    mx['bf'] = v
            if i_vo2kg is not None and len(r) > i_vo2kg:
                v = num(r[i_vo2kg])
                if v is not None and (mx['vo2kg'] is None or v > mx['vo2kg']):
                    mx['vo2kg'] = v
            if i_t is not None and len(r) > i_t and i_stage is not None and len(r) > i_stage:
                tt = tsec(r[i_t])
                if tt is not None and '训练' in str(r[i_stage]):
                    train_secs.append(tt)
            if i_t is not None and i_vo2kg is not None and i_stage is not None:
                pass
        rec['rer_max'] = mx['rer']; rec['ve_max'] = mx['ve']
        rec['bf_max'] = mx['bf']; rec['vo2kg_max'] = mx['vo2kg']
        rec['exercise_dur'] = (train_secs[-1] - train_secs[0]) if len(train_secs) > 1 else None
        # 逐秒曲线（降采样）
        if i_t is not None and i_vo2kg is not None and i_rer is not None:
            t_pts, v_pts, r_pts, st_pts = [], [], [], []
            for r in rows[mi+3:]:
                if not r or len(r) < max(i_t, i_vo2kg, i_rer)+1:
                    continue
                tt = tsec(r[i_t]); vv = num(r[i_vo2kg]); rr = num(r[i_rer])
                if tt is None:
                    continue
                t_pts.append(tt)
                v_pts.append(vv)
                r_pts.append(rr if rr is not None and rr < 2.5 else None)
                st_pts.append(r[i_stage] if i_stage is not None and len(r) > i_stage else '')
            step = max(1, len(t_pts)//600)
            rec['curve_t'] = t_pts[::step]
            rec['curve_v'] = v_pts[::step]
            rec['curve_r'] = r_pts[::step]
            rec['curve_stage'] = st_pts[::step]
    return rec


def parse_msstest(path):
    """解析 MetaMax .msstest（Base64+gzip 的 TestGen XML）→ 与 parse_test 兼容的 rec。"""
    import base64
    import gzip

    raw = open(path, 'rb').read().replace(b'encoding="utf-16"', b'encoding="utf-8"')
    root = ET.fromstring(raw)
    data_b64 = ""
    for el in root.iter():
        if el.tag.split("}")[-1] == "Data":
            data_b64 = (el.text or "").strip()
    blob = base64.b64decode(data_b64)
    inner = gzip.decompress(blob[4:]).replace(b'encoding="utf-16"', b'encoding="utf-8"')
    r2 = ET.fromstring(inner)

    def txt(tag):
        for el in r2.iter():
            if el.tag.split("}")[-1] == tag and (el.text or "").strip():
                return el.text.strip()
        return ""

    # 逐呼吸变量（MetaMax 编号：2001=VO2 2002=VCO2 2003=VE 2016=HR）
    vars_data = {}
    for vd in r2.iter():
        if vd.tag.split("}")[-1] != "VariableData":
            continue
        nr_el = vd.find(".//{*}VariableNr")
        vals_el = vd.find(".//{*}Values")
        nr = nr_el.text.strip() if nr_el is not None and nr_el.text else ""
        nums = []
        if vals_el is not None:
            for d in list(vals_el):
                t = (d.text or "").strip()
                if t and t != "NaN":
                    try:
                        nums.append(float(t))
                    except ValueError:
                        nums.append(None)
                else:
                    nums.append(None)
        if nr:
            vars_data[nr] = nums

    surname = txt("Name")
    given = txt("FirstName")
    sex_raw = txt("Sex")
    sex = "男" if sex_raw == "MALE" else ("女" if sex_raw == "FEMALE" else sex_raw)
    birth = txt("BirthDate")[:10]
    start = txt("TestBegin")[:19]
    dur_ms = txt("TestDurationMeasured")
    dur_sec = int(round(int(dur_ms) / 1000)) if dur_ms.isdigit() else None
    weight = num(txt("PersonInitialWeightForWattWeightWLP"))

    vo2 = vars_data.get("2001", [])
    vco2 = vars_data.get("2002", [])
    ve = vars_data.get("2003", [])
    hr = vars_data.get("2016", [])

    vo2_peak = max((v for v in vo2 if v), default=None)
    ve_peak = max((v for v in ve if v), default=None)
    hr_peak = max((v for v in hr if v), default=None)
    rers = [b / a for a, b in zip(vo2, vco2) if a and b and 0.7 < b / a < 1.5]
    rer_max = max(rers) if rers else None
    vo2kg_peak = (vo2_peak / weight * 1000) if (vo2_peak and weight) else None

    slope = None
    pairs = [(a, b) for a, b in zip(vco2, ve) if a and b]
    if len(pairs) > 10:
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        slope = sxy / sxx if sxx else None

    # 逐呼吸曲线（降采样到 ≤120 点）
    step = max(1, len(vo2) // 120)
    curve_t = list(range(0, len(vo2), step))[:120]
    curve_v = [vo2[i] for i in range(0, len(vo2), step)][:120]
    curve_r = [vco2[i] / vo2[i] if vo2[i] else None for i in range(0, len(vo2), step)][:120]

    return {
        'file': os.path.basename(path),
        'surname': surname, 'given': given, 'name': surname + given,
        'sex': sex, 'birth': birth, 'height_cm': None, 'weight_kg': weight,
        'bmi': None, 'start': start,
        'duration': f"{int(dur_sec // 60)}:{int(dur_sec % 60):02d}" if dur_sec else None,
        'dur_sec': dur_sec, 'device': 'MetaMax 3B',
        'pred_vo2max': None, 'pred_vo2kg': None,
        'vo2peak': vo2_peak, 'vo2peak_kg': vo2kg_peak, 'pct_norm': None,
        'vt1_kg': None, 'vt1_pct': None, 'vt2_kg': None,
        'vo2_peak': vo2_peak, 'vo2_maxabs': vo2_peak,
        'hr_peak': hr_peak, 'rer_peak': rer_max, 'rer_max': rer_max,
        've_peak': ve_peak, 've_max': ve_peak, 'bf_max': None, 'vo2kg_max': vo2kg_peak,
        've_slope': slope,
        'exercise_dur': dur_sec, 'exercise_dur_s': dur_sec,
        'meas_max_vo2kg': vo2kg_peak, 'meas_max_rer': rer_max, 'meas_max_hr': hr_peak,
        'plateau_delta': None,
        'curve_t': curve_t, 'curve_v': curve_v, 'curve_r': curve_r,
        'curve_stage': None,
        '_src': 'msstest',
    }


NEWDIR = os.path.join(DIR, '新的最大摄氧量数据', '新的最大摄氧量数据')
MSTEST_DIR = os.path.join(DIR, '新的最大摄氧量数据', '最大')
# 统一数据源：D:\DEV\blood\最大摄氧量数据（70 份 XML，含 msstest 转换）
files = sorted(glob.glob(os.path.join(DIR, 'CPET*.xml')))
all_tests = []
for f in files:
    try:
        all_tests.append(parse_msstest(f) if f.endswith('.msstest') else parse_test(f))
    except Exception as e:
        print("skip", os.path.basename(f), e)
# 按 人+开始时间 去重（两文件夹可能有重复拷贝）
seen = set()
uniq_tests = []
for t in all_tests:
    k = (t['name'], str(t['start']))
    if k not in seen:
        seen.add(k)
        uniq_tests.append(t)
all_tests = uniq_tests
by_name = {}
for t in all_tests:
    cur = by_name.get(t['name'])
    # 每人取相对摄氧量最高的一场（复测进步自动生效），同分取时长更长
    if cur is None or ((t['vo2peak_kg'] or 0), t['dur_sec']) > \
       ((cur['vo2peak_kg'] or 0), cur['dur_sec']):
        by_name[t['name']] = t
tests = list(by_name.values())
tests.sort(key=lambda t: -(t['vo2peak_kg'] or 0))
print(f'测试总数 {len(all_tests)}，去重后 {len(tests)} 人')

# ── 纵向趋势：每人多次测试的 VO2 变化（复测进步/退步）──
from collections import defaultdict
by_person = defaultdict(list)
for t in all_tests:
    if t.get('vo2peak_kg'):
        by_person[t['name']].append(t)
trends = []
for n, vs in by_person.items():
    if len(vs) < 2:
        continue
    vs_sorted = sorted(vs, key=lambda x: x.get('start') or '')
    first, last = vs_sorted[0], vs_sorted[-1]
    trends.append({
        'name': n,
        'first': round(first['vo2peak_kg'], 1),
        'last': round(last['vo2peak_kg'], 1),
        'delta': round(last['vo2peak_kg'] - first['vo2peak_kg'], 1),
        'n': len(vs),
        'first_date': (first.get('start') or '')[:10],
        'last_date': (last.get('start') or '')[:10],
    })
trends.sort(key=lambda x: -x['delta'])
n_multi = len(trends)
n_progress = sum(1 for t in trends if t['delta'] > 2)
n_regress = sum(1 for t in trends if t['delta'] < -2)
TREND_TEXT = '；<br>'.join(
    "{} {}→{}（{}{}）".format(t['name'], t['first'], t['last'],
                            '+' if t['delta'] > 0 else '', t['delta'])
    for t in trends[:8]
)

# ── 分组差异：干预组对比（映射来自平台 participants 导出 CSV）──
import csv as _csv
_iv_map = {}
_iv_csv = os.path.join(DIR, '干预组映射.csv')
if os.path.exists(_iv_csv):
    with open(_iv_csv, encoding='utf-8-sig') as f:
        for r in _csv.DictReader(f):
            _iv_map[r['name'].strip()] = r['intervention'].strip()
for t in tests:
    t['group'] = _iv_map.get(t['name'], '')
GRP_ORDER = ['常规恢复', '艾灸+推拿', '拔罐+推拿']
grp_data = {g: [t['vo2peak_kg'] for t in tests if t['group'] == g and t['vo2peak_kg']] for g in GRP_ORDER}
grp_stats = {}
for g in GRP_ORDER:
    vals = grp_data[g]
    if vals:
        vals_s = sorted(vals)
        grp_stats[g] = {
            'n': len(vals),
            'med': round(vals_s[len(vals_s)//2], 1),
            'mean': round(sum(vals)/len(vals), 1),
        }
grp_kw = None
try:
    from scipy import stats as _st
    _allg = [grp_data[g] for g in GRP_ORDER if grp_data[g]]
    if len(_allg) >= 2 and all(len(x) >= 3 for x in _allg):
        _h, grp_kw = _st.kruskal(*_allg)
except Exception:
    grp_kw = None

# ── 数据质量筛查：z-score 离群 + 有效性分级清单 ──
import statistics as _stat2
_qvals = [t['vo2peak_kg'] for t in tests if t.get('vo2peak_kg')]
_qmean = sum(_qvals) / len(_qvals) if _qvals else 0
_qsd = _stat2.stdev(_qvals) if len(_qvals) > 1 else 1
for t in tests:
    t['z'] = round((t['vo2peak_kg'] - _qmean) / _qsd, 2) if t.get('vo2peak_kg') else None
high_z = [t for t in tests if t['z'] and t['z'] > 1.5]
low_z = [t for t in tests if t['z'] and t['z'] < -1.5]

def J(x):
    return json.dumps(x, ensure_ascii=False)

def ech(id_, body, h=380):
    return (f'<div id="{id_}" style="width:100%;height:{h}px"></div>\n'
            f'<script>(function(){{var c=echarts.init(document.getElementById("{id_}"));\n{body}\n}}());</script>')

names = [t['name'] for t in tests]
vo2kg = [round(t['vo2peak_kg'] or 0, 1) for t in tests]
vo2abs = [round(t['vo2peak'] or 0, 2) for t in tests]
pct = [round(t['pct_norm'] or 0) for t in tests]
slope = [round(t['ve_slope'] or 0, 1) for t in tests]
vt1p = [round(t['vt1_pct'] or 0) for t in tests]
rer = [round(t['rer_max'] or 0, 2) for t in tests]
sex_cols = ['#3f7fb8' if t['sex'] == '男性' else '#d05555' for t in tests]
dates = [str(t['start'])[:10] for t in tests]
dur = [f"{t['dur_sec']//60}:{t['dur_sec']%60:02d}" for t in tests]

valid_kg = [v for v in vo2kg if v]
valid_rer = [v for v in rer if v]
kpi = {
    '人数': len(tests),
    '平均相对VO2max': f"{sum(valid_kg)/len(valid_kg):.0f} ml/kg/min" if valid_kg else '-',
    '最高相对VO2max': f"{max(valid_kg):.0f}" if valid_kg else '-',
    '平均RER': f"{sum(valid_rer)/len(valid_rer):.2f}" if valid_rer else '-',
}

from datetime import datetime
GEN_TIME = datetime.now().strftime('%Y-%m-%d %H:%M')
def age_at(birth, start):
    try:
        bp = [int(x) for x in str(birth).strip().split(' ')[0].split('/')]
        b = datetime(bp[0], bp[1], bp[2])
        sp = [int(x) for x in str(start).strip().split(' ')[0].split('/')]
        s = datetime(sp[0], sp[1], sp[2])
        return round((s - b).days / 365.25, 1)
    except Exception:
        return None
ages = [age_at(t['birth'], t['start']) for t in tests]
wts = [t['weight_kg'] or 40 for t in tests]
mean_kg = round(sum(vo2kg)/len(vo2kg), 1)

def scatter_pts(xv, yv, names, sex_cols, label_names=None):
    pts = []
    for x, y, n, c in zip(xv, yv, names, sex_cols):
        pts.append({'value': [x, y], 'name': n, 'symbolSize': 15,
                    'itemStyle': {'color': c, 'opacity': 0.75},
                    'label': {'show': label_names is not None and n in label_names,
                              'position': 'top', 'fontSize': 8, 'formatter': '{b}'}})
    return pts

top_names = set(n for _, n in sorted(zip([v or 0 for v in vo2kg], names), reverse=True)[:8])

def test_cls(t):
    if not t.get('vo2peak_kg'):
        return '无效'
    dur = t.get('exercise_dur')
    if dur is not None and dur < 180:
        return '无效'
    r = t.get('rer_max')
    if r is not None:
        if r >= 1.05:
            return '有效'
        if r >= 1.00:
            return '亚极量'
    return '亚极量'
CLS_COLOR = {'有效': '#2E8B57', '亚极量': '#E8A33D', '无效': '#8A94A0'}

ch = {}
age_labels = ['8-10', '10-12', '12-14', '14+']
age_buckets = {k: [] for k in age_labels}
for t in tests:
    a = age_at(t['birth'], t['start'])
    v = t['vo2peak_kg']
    if a is None or not v:
        continue
    if a < 10: age_buckets['8-10'].append(v)
    elif a < 12: age_buckets['10-12'].append(v)
    elif a < 14: age_buckets['12-14'].append(v)
    else: age_buckets['14+'].append(v)

def box5(vals):
    v = sorted(vals)
    n = len(v)
    if n == 2:
        return [v[0], v[0], (v[0] + v[1]) / 2, v[1], v[1]]
    if n == 3:
        return [v[0], v[0], v[1], v[2], v[2]]
    def q(p):
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        return v[f] + (v[c] - v[f]) * (k - f)
    return [v[0], q(0.25), q(0.5), q(0.75), v[-1]]

age_box_data = [box5(age_buckets[k]) if len(age_buckets[k]) >= 2 else None for k in age_labels]

ch['c_age'] = ech('c_age', """
c.setOption({
 tooltip:{trigger:'item'},
 toolbox:{right:10,feature:{saveAsImage:{name:'VO2_年龄组箱线',pixelRatio:2},restore:{}}},
 grid:{left:55,right:30,top:30,bottom:40},
 xAxis:{type:'category',data:""" + J([f"{k}岁" for k in age_labels]) + """},
 yAxis:{type:'value',name:'VO2max（ml/kg/min）',min:30,max:100},
 series:[{type:'boxplot',data:""" + J(age_box_data) + """,
  itemStyle:{color:'#4c72b0'},
  markLine:{silent:true,symbol:'none',data:[{yAxis:""" + str(mean_kg) + """,lineStyle:{color:'#888',type:'dashed'},label:{formatter:'全队均值'}}]}}]
});""", 420)

slope_order = sorted(tests, key=lambda t: (t['ve_slope'] or 999))
slope_names2 = [t['name'] for t in slope_order]
slope_vals2 = [t['ve_slope'] for t in slope_order]
def slope_color(v):
    if not v: return '#c8c8c8'
    if v < 25: return '#2E8B57'
    if v < 30: return '#7FBF6A'
    if v < 35: return '#E8A33D'
    return '#D9534F'
slope_colors = [slope_color(v) for v in slope_vals2]

ch['c_quality'] = ech('c_quality', """
c.setOption({
 tooltip:{formatter:function(p){return p.name+'<br>斜率: '+(p.value||'-')+' · '+p.data.cls;}},
 toolbox:{right:10,feature:{saveAsImage:{name:'通气效率排名',pixelRatio:2},restore:{}}},
 grid:{left:95,right:55,top:20,bottom:20},
 xAxis:{type:'value',name:'V\\'E/V\\'CO2 斜率（越低越好）'},
 yAxis:{type:'category',data:""" + J(slope_names2) + """,inverse:true},
 series:[{type:'bar',data:""" + J([{'value': (v or 0), 'itemStyle': {'color': c}, 'cls': test_cls(t)}
                                   for v, c, t in zip(slope_vals2, slope_colors, slope_order)]) + """,
  label:{show:true,position:'right',formatter:function(p){return p.value||'-';},fontSize:10},
  barMaxWidth:13}]
});""", 430)

vt1_vals = [t['vt1_pct'] for t in tests if t.get('vt1_pct')]
vt1_bins = [50, 60, 70, 80, 90, 101]
vt1_labels = ['50-60', '60-70', '70-80', '80-90', '90+']
vt1_counts = [sum(1 for v in vt1_vals if a <= v < b) for a, b in zip(vt1_bins[:-1], vt1_bins[1:])]

ch['c_vt1s'] = ech('c_vt1s', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'VT1分布',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:30,bottom:35},
 xAxis:{type:'category',data:""" + J(vt1_labels) + """,name:'VT1 占最大摄氧量(%)'},
 yAxis:{type:'value',name:'人数',minInterval:1},
 series:[{type:'bar',data:""" + J(vt1_counts) + """,itemStyle:{color:'#7a6f9e'},
  label:{show:true,position:'top'},barMaxWidth:60,
  markLine:{silent:true,symbol:'none',data:[{xAxis:1.5,lineStyle:{color:'#d05555',type:'dashed'},label:{formatter:'良好 70%'}}]}}]
});""", 330)

import numpy as np
tc_mean, tc_lo, tc_hi = [], [], []
curve_tests = [t for t in tests if t.get('curve_v')]
for pct_pt in range(101):
    vals = []
    for t in curve_tests:
        cv = t['curve_v']
        idx = min(int(pct_pt/100*(len(cv)-1)), len(cv)-1)
        v = cv[idx]
        if v is not None:
            vals.append(v)
    if vals:
        tc_mean.append(round(float(np.mean(vals)), 1))
        tc_lo.append(round(float(np.min(vals)), 1))
        tc_hi.append(round(float(np.max(vals)), 1))
    else:
        tc_mean.append(None); tc_lo.append(None); tc_hi.append(None)

ch['c_team'] = ech('c_team', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'全队平均曲线',pixelRatio:2},restore:{}}},
 legend:{data:['全队平均','全员范围'],top:0},
 grid:{left:55,right:25,top:35,bottom:45},
 xAxis:{type:'category',data:""" + J(list(range(101))) + """,name:'测试进度（%）',axisLabel:{show:false},splitLine:{show:false}},
 yAxis:{type:'value',name:'V\\'O2/kg（ml/kg/min）',min:0},
 series:[
  {name:'下限',type:'line',stack:'b',data:""" + J(tc_lo) + """,symbol:'none',lineStyle:{opacity:0},tooltip:{show:false},emphasis:{disabled:true}},
  {name:'全员范围',type:'line',stack:'b',data:""" + J([None if (a is None or b is None) else round(b-a, 1) for a, b in zip(tc_lo, tc_hi)]) + """,
   symbol:'none',lineStyle:{opacity:0},areaStyle:{color:'rgba(63,127,184,0.22)'},tooltip:{show:false}},
  {name:'全队平均',type:'line',data:""" + J(tc_mean) + """,symbol:'none',lineStyle:{width:2,color:'#3f7fb8'}}
 ]});""", 400)

athlete_js = {}
for t in tests:
    if t.get('curve_t'):
        athlete_js[t['name']] = {
            't': t['curve_t'], 'v': t['curve_v'], 'r': t['curve_r'], 'st': t.get('curve_stage', []),
            'vt1': t['vt1_kg'], 'peak': t['vo2peak_kg'],
            'vo2kg': t['vo2peak_kg'], 'pct': t['pct_norm'], 'vt1p': t['vt1_pct'],
            'slope': t['ve_slope'], 'rer': t['rer_max'], 'sex': t['sex'], 'age': age_at(t['birth'], t['start']),
        }
default_name = tests[0]['name']
ch['c_ath_curve'] = ech('c_ath_curve', """
window.ATH = """ + J(athlete_js) + """;                                                      
window.drawAth = function(name){
  var d = ATH[name] || {t:[],v:[],r:[],st:[]};
  var recIdx = -1;
  for(var i=0;i<d.t.length;i++){ if(String(d.st[i]).indexOf('恢复')>=0){ recIdx=i; break; } }
  var markArea = [];
  if(recIdx>=0){ markArea.push([{xAxis:d.t[recIdx],itemStyle:{color:'rgba(184,178,166,0.25)'}},{xAxis:d.t[d.t.length-1]}]); }
  var markLines = [];
  if(d.vt1){ markLines.push({yAxis:d.vt1,lineStyle:{color:'#7a6f9e',type:'dashed'},label:{formatter:'VT1'} }); }
  if(d.peak){ markLines.push({yAxis:d.peak,lineStyle:{color:'#d05555',type:'dashed'},label:{formatter:'VO2peak'} }); }
  c.setOption({
   tooltip:{trigger:'axis',formatter:function(ps){
     var p=ps[0]; var st=d.st[p.dataIndex]||''; var s='';
     ps.forEach(function(x){ s += x.marker+x.seriesName+': '+x.value+'<br>'; });
     return '<b>'+name+'</b> '+st+'<br>'+s;
   }},
   toolbox:{right:10,feature:{saveAsImage:{name:name+'_CPET曲线',pixelRatio:2},restore:{}}},
   legend:{data:['V\\'O2/kg','RER'],top:0},
   grid:{left:55,right:55,top:35,bottom:40},
   xAxis:{type:'category',data:d.t,axisLabel:{show:false},name:'时间'},
   yAxis:[{type:'value',name:'ml/kg/min',min:0,max:120},
          {type:'value',name:'RER',min:0.6,max:1.4}],
   series:[
    {name:'V\\'O2/kg',type:'line',data:d.v,symbol:'none',lineStyle:{width:1.8,color:'#3f7fb8'},
     areaStyle:{color:'rgba(63,127,184,0.12)'},markArea:{silent:true,data:markArea},markLine:{silent:true,symbol:'none',data:markLines}},
    {name:'RER',type:'line',yAxisIndex:1,data:d.r,symbol:'none',lineStyle:{width:1.2,color:'#d05555'}}
   ]
  });
}
drawAth(""" + J(default_name) + """);
""", 420)

ch['c_ath_radar'] = ech('c_ath_radar', """
window.drawRadar = function(name){
  var d = ATH[name] || {};
  var eff = d.slope ? Math.max(0, Math.round(60 - d.slope)) : 0;
  c.setOption({
   tooltip:{},
   toolbox:{right:10,feature:{saveAsImage:{name:name+'_画像雷达',pixelRatio:2},restore:{}}},
   radar:{indicator:[{name:'相对VO2max',max:100},{name:'预测达成%',max:200},
     {name:'VT1占最大%',max:100},{name:'通气效率分',max:60},{name:'RER',max:1.4}],
     radius:'65%',center:['50%','55%']},
   series:[{type:'radar',
    data:[{name:name,value:[d.vo2kg||0, d.pct||0, d.vt1p||0, eff, d.rer||0],
      areaStyle:{color:'rgba(63,127,184,0.25)'},itemStyle:{color:'#3f7fb8'}}]}]
  });
}
drawRadar(""" + J(default_name) + """);
""", 380)

# ── 图16：复测进步/退步（纵向趋势）──
ch['c_trend'] = ech('c_trend', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'},
   formatter:function(ps){var p=ps[0];var d=p.data;
     return d.name+'（'+d.first_date+' → '+d.last_date+'）<br>首测 '+d.first+' → 末测 '+d.last+' ml/kg/min<br>Δ '+d.delta+'（'+d.n+'次测试）';}},
 toolbox:{right:10,feature:{saveAsImage:{name:'复测趋势',pixelRatio:2},restore:{}}},
 grid:{left:60,right:50,top:20,bottom:30},
 xAxis:{type:'value',name:'Δ VO2/kg (ml/kg/min)'},
 yAxis:{type:'category',data:""" + J([t['name'] for t in trends]) + """,inverse:true,axisLabel:{fontSize:11}},
 series:[{type:'bar',barWidth:14,
   data:""" + J([{'name': t['name'], 'value': t['delta'], 'first': t['first'], 'last': t['last'],
            'first_date': t['first_date'], 'last_date': t['last_date'], 'n': t['n'],
            'itemStyle': {'color': '#2E8B57' if t['delta'] > 0 else '#d05555'}}
           for t in trends]) + """,
   label:{show:true,position:'right',formatter:function(p){return (p.value>0?'+':'')+p.value;}}}]
});""", 380)

# ── 图17：干预组 VO2 箱线对比 ──
GRP_BOX = []
for g in GRP_ORDER:
    vals = grp_data.get(g, [])
    if len(vals) >= 3:
        vals_s = sorted(vals)
        q1 = vals_s[len(vals_s)//4]
        med = vals_s[len(vals_s)//2]
        q3 = vals_s[3*len(vals_s)//4]
        GRP_BOX.append([q1, med, q3, vals_s[0], vals_s[-1]])
    else:
        GRP_BOX.append(None)
ch['c_group'] = ech('c_group', """
c.setOption({
 tooltip:{},
 toolbox:{right:10,feature:{saveAsImage:{name:'干预组VO2对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:25,top:30,bottom:40},
 xAxis:{type:'category',data:""" + J([g for g in GRP_ORDER if len(grp_data.get(g, [])) >= 3]) + """,name:'干预组'},
 yAxis:{type:'value',name:'VO2/kg (ml/kg/min)',min:30,max:100},
 series:[{type:'boxplot',data:""" + J([b for b in GRP_BOX if b]) + """,
   itemStyle:{color:'#4c72b0'},boxWidth:36}]
});""", 380)

# ---------- 表格 ----------
def table_to_html(headers, rows):
    th = ''.join(f'<th>{html.escape(h)}</th>' for h in headers)
    trs = []
    for r in rows:
        trs.append('<tr>' + ''.join(f'<td>{html.escape(str(c))}</td>' for c in r) + '</tr>')
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'

def tblbox(name, headers, rows):
    return (f'<div class="tblbox"><div class="tblbar">'
            f'<button class="dl" data-name="{name}" data-expcsv="1">导出CSV</button>'
            f'<button class="dl" data-copytbl="1">复制表格</button></div>'
            + table_to_html(headers, rows) + '</div>')

hdr = ['姓名', '性别', '测试日期', '时长', '身高cm', '体重kg', 'BMI',
       'VO2peak L/min', 'VO2peak ml/kg/min', '预测达成%', 'VT1%max', 'V\'E/V\'CO2', 'RERmax', 'VEmax L/min', 'BFmax']
rows_t = []
for t in tests:
    rows_t.append([t['name'], t['sex'], dates[tests.index(t)], dur[tests.index(t)],
                   f"{t['height_cm']:.0f}" if t['height_cm'] else '-',
                   f"{t['weight_kg']:.0f}" if t['weight_kg'] else '-',
                   f"{t['bmi']:.0f}" if t['bmi'] else '-',
                   f"{t['vo2peak']:.2f}" if t['vo2peak'] else '-',
                   f"{t['vo2peak_kg']:.0f}" if t['vo2peak_kg'] else '-',
                   f"{t['pct_norm']:.0f}%" if t['pct_norm'] else '-',
                   f"{t['vt1_pct']:.0f}%" if t['vt1_pct'] else '-',
                   f"{t['ve_slope']:.1f}" if t['ve_slope'] else '-',
                   f"{t['rer_max']:.2f}" if t['rer_max'] else '-',
                   f"{t['ve_max']:.0f}" if t['ve_max'] else '-',
                   f"{t['bf_max']:.0f}" if t['bf_max'] else '-'])

cards = ''
for k, v in kpi.items():
    cards += f'<div class="kpi"><div class="v">{v}</div><div class="l">{k}</div></div>'

# ---- 排名图（可切换指标）+ 分布 / 男女对比 ----

rank_order = sorted(tests, key=lambda t: -(t['vo2peak_kg'] or 0))
order_pct = sorted(tests, key=lambda t: -(t['pct_norm'] or 0))
rank_people = [{
    'name': t['name'],
    'vo2kg': round(t['vo2peak_kg'], 1) if t['vo2peak_kg'] else 0,
    'pct': round(t['pct_norm'], 1) if t['pct_norm'] else 0,
    'slope': round(t['ve_slope'], 1) if t['ve_slope'] else 0,
    'rer': round(t['rer_max'], 2) if t['rer_max'] else 0,
    'vt1': round(t['vt1_pct'], 1) if t['vt1_pct'] else 0,
    'color': CLS_COLOR[test_cls(t)],
    'cls': test_cls(t),
} for t in tests]

# ── 综合排名表（多指标可排序）──
RANK_COLS = [
    ('vo2kg', 'VO2/kg'), ('pct', '预测达成%'), ('slope', 'VE/VCO2斜率'),
    ('vt1', 'VT1%'), ('rer', 'RER'),
]
def _fmt(row, key):
    v = row.get(key)
    return ('-' if v is None or v == 0 else
            ('{:.2f}'.format(v) if key == 'rer' else '{:.1f}'.format(v)))
RANK_TABLE_ROWS = []
for _i, _t in enumerate(rank_order, 1):
    RANK_TABLE_ROWS.append({
        'rank': _i, 'name': _t['name'],
        'sex': '男' if _t['sex'] in ('男性', '男') else '女',
        'age': age_at(_t.get('birth'), _t.get('start')),
        'vo2kg': _t['vo2peak_kg'], 'pct': _t.get('pct_norm'),
        'slope': _t.get('ve_slope'), 'vt1': _t.get('vt1_pct'),
        'rer': _t.get('rer_max'), 'cls': test_cls(_t),
    })
_eff_list = sorted([t for t in tests if t.get('ve_slope')], key=lambda t: t['ve_slope'])
TOP_LISTS = [
    ('相对VO2/kg 最高', [(t['name'], t['vo2peak_kg']) for t in rank_order[:5]]),
    ('通气效率最优（斜率最低）', [(t['name'], t['ve_slope']) for t in _eff_list[:5]]),
    ('VT1 耐力储备最高', [(t['name'], t['vt1_pct']) for t in sorted([t for t in tests if t.get('vt1_pct')], key=lambda t: -t['vt1_pct'])[:5]]),
    ('预测达成率最高', [(t['name'], t['pct_norm']) for t in sorted([t for t in tests if t.get('pct_norm')], key=lambda t: -t['pct_norm'])[:5]]),
]

# ── 综合排名表 HTML（多指标可排序）+ Top 榜单 ──
def _rc(r, key, dec=1):
    v = r.get(key)
    if not v:
        return '-'
    return ('{:.0f}'.format(v) if dec == 0 else
            ('{:.2f}'.format(v) if dec == 2 else '{:.1f}'.format(v)))
_top_cards = []
for _title, _items in TOP_LISTS:
    _lis = ''.join(
        '<li><span class="tk">{}</span><b>{}</b></li>'.format(_i + 1, n) for _i, (n, v) in enumerate(_items))
    _top_cards.append('<div class="topcard"><h4>{}</h4><ul>{}</ul></div>'.format(_title, _lis))
RANK_TABLE_HTML = (
    '<p class="lead"><b>综合排名榜</b>（全队明细，点击表头排序，可复制到 Word/导出 CSV）</p>'
    '<details class="guide"><summary>📖 指标计算逻辑说明（每个指标怎么算、怎么解读）</summary>'
    '<table class="qctab"><tr><th>指标</th><th>计算逻辑</th><th>排名方向</th></tr>'
    '<tr><td><b>相对摄氧量 VO2/kg</b></td><td>峰值摄氧量（L/min）÷ 体重（kg）。递增负荷至力竭时的最大摄氧速率，按体重标准化</td><td><b>越高越好</b>，反映每公斤体重有氧供能上限</td></tr>'
    '<tr><td><b>预测达成率 %</b></td><td>实测 VO2peak ÷ 设备预测值 ×100%。预测值按年龄/性别/身高/体重用 Wasserman 方程估算</td><td><b>≥100%</b> 达到预测水平，越高越强</td></tr>'
    '<tr><td><b>VE/VCO2 斜率</b></td><td>运动全程通气量 VE 对 CO2 产量 VCO2 做线性回归的斜率。斜率小 = 同样排出 CO2 所需通气少，呼吸经济</td><td><b>越低越好</b>（&lt;30 优秀）</td></tr>'
    '<tr><td><b>VT1% 耐力储备</b></td><td>第一通气阈（VT1，VE/VO2 开始上升点）对应摄氧量 ÷ VO2peak ×100%。占越高 = 无氧启动越晚</td><td><b>越高越好</b>（≥70% 良好）</td></tr>'
    '<tr><td><b>RER 呼吸交换率</b></td><td>VCO2 ÷ VO2 的峰值。&gt;1.0 说明以无氧供能为主，越接近/超过 1.05 努力度越高</td><td>用作<b>有效性判定</b>：≥1.05 有效</td></tr>'
    '<tr><td><b>有效性分级</b></td><td>有效 = RER≥1.05 且运动时长≥180s；亚极量 = RER 1.00–1.05 或提前终止；无效 = 无有效 VO2</td><td>绿/橙/灰对应 有效/亚极量/无效</td></tr>'
    '</table></details>'
    '<div class="topcards">' + ''.join(_top_cards) + '</div>'
    '<div class="tblbox"><div class="tblbar">'
    '<button class="dl" data-name="综合排名" data-expcsv="1">导出CSV</button>'
    '<button class="dl" data-copytbl="1">复制表格到Word</button></div>'
    '<table id="rank_tbl" class="qctab"><thead><tr>'
    '<th data-k="rank">#</th><th data-k="name">姓名</th><th>性别</th><th data-k="age">年龄</th>'
    '<th data-k="vo2kg">VO2/kg</th><th data-k="pct">预测%</th>'
    '<th data-k="slope">VE斜率</th><th data-k="vt1">VT1%</th>'
    '<th data-k="rer">RER</th><th>分级</th></tr></thead><tbody>'
    + ''.join(
        '<tr><td>{rank}</td><td>{name}</td><td>{sex}</td><td>{age}</td>'
        '<td>{vo2}</td><td>{pct}</td><td>{slope}</td><td>{vt1}</td><td>{rer}</td>'
        '<td class="rcls" style="color:{color}">{cls}</td></tr>'.format(
            rank=r['rank'], name=r['name'], sex=r['sex'], age=_rc(r, 'age', 1),
            vo2=_rc(r, 'vo2kg', 1), pct=_rc(r, 'pct', 1),
            slope=_rc(r, 'slope', 1), vt1=_rc(r, 'vt1', 1),
            rer=_rc(r, 'rer', 2), cls=r['cls'],
            color=CLS_COLOR[r['cls']])
        for r in RANK_TABLE_ROWS)
    + '</tbody></table></div>'
    '<script>'
    '(function(){var t=document.getElementById("rank_tbl"),asc={};'
    't.querySelectorAll("th[data-k]").forEach(function(th){th.style.cursor="pointer";'
    'th.onclick=function(){var k=th.getAttribute("data-k"),tb=t.tBodies[0],rs=[].slice.call(tb.rows);'
    'asc[k]=!asc[k];var dir=asc[k]?1:-1;'
    'rs.sort(function(a,b){var x=a.cells[th.cellIndex].textContent,y=b.cells[th.cellIndex].textContent;'
    'var nx=parseFloat(x),ny=parseFloat(y);'
    'var c=(k==="name"?x.localeCompare(y, "zh"):(isNaN(nx)?x.localeCompare(y):nx-ny))*dir;return c;});'
    'rs.forEach(function(r){tb.appendChild(r);});});})();'
    '</script>'
)

# ── 图18：Top10 排名条形（放大版，分级着色）──
_top10 = [r for r in RANK_TABLE_ROWS if r.get('vo2kg')][:10]
ch['c_topbar'] = ech('c_topbar', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'},
   formatter:function(ps){var p=ps[0];var d=p.data;
     return d.name+'（'+d.sex+'，'+d.age+'岁）<br>VO2/kg: '+d.vo2+'<br>预测达成: '+d.pct+'%<br>VT1: '+d.vt1+'%<br>'+d.cls;}},
 toolbox:{right:10,feature:{saveAsImage:{name:'Top10排名',pixelRatio:2},restore:{}}},
 grid:{left:70,right:55,top:20,bottom:30},
 xAxis:{type:'value',name:'VO2/kg (ml/kg/min)'},
 yAxis:{type:'category',data:""" + J([r['name'] for r in _top10][::-1]) + """,axisLabel:{fontSize:13}},
 series:[{type:'bar',barWidth:18,data:""" + J([
   {'name': r['name'], 'sex': r['sex'], 'age': r['age'], 'vo2': r['vo2kg'],
    'pct': r['pct'], 'vt1': r['vt1'], 'cls': r['cls'], 'value': r['vo2kg'],
    'itemStyle': {'color': CLS_COLOR[r['cls']]}}
   for r in _top10][::-1]) + """,
   label:{show:true,position:'right',fontSize:12,formatter:function(p){return p.value;}}}]
});""", 420)

# ── 图19：Top5 雷达对比（五维能力画像）──
_top5 = [r for r in RANK_TABLE_ROWS if r.get('vo2kg')][:5]
ch['c_topradar'] = ech('c_topradar', """
c.setOption({
 tooltip:{},
 legend:{top:0,data:""" + J([r['name'] for r in _top5]) + """},
 toolbox:{right:10,feature:{saveAsImage:{name:'Top5能力对比',pixelRatio:2},restore:{}}},
 radar:{indicator:[{name:'VO2/kg',max:100},{name:'预测达成%',max:200},
   {name:'VT1占最大%',max:100},{name:'通气效率分',max:60},{name:'RER',max:1.4}],
   radius:'62%',center:['50%','56%']},
 series:[{type:'radar',
   data:""" + J([
     {'name': r['name'],
      'value': [r.get('vo2kg') or 0, r.get('pct') or 0, r.get('vt1') or 0,
                max(0, round(60 - (r.get('slope') or 60), 1)), r.get('rer') or 0],
      'areaStyle': {'opacity': 0.12}}
     for r in _top5]) + """}]
});""", 420)

# ---- 洞察句子（基于当前数据自动生成，供排名切换联动）----
valid_kg_list = sorted(v for v in vo2kg if v)
med_kg = valid_kg_list[len(valid_kg_list)//2] if valid_kg_list else 0
p25_kg = valid_kg_list[len(valid_kg_list)//4] if valid_kg_list else 0
p75_kg = valid_kg_list[3*len(valid_kg_list)//4] if valid_kg_list else 0
cls_counts = {}
for t in tests:
    cls_counts[test_cls(t)] = cls_counts.get(test_cls(t), 0) + 1
invalid_list = [t['name'] for t in tests if test_cls(t) == '无效']
top3 = rank_order[:3]
effs = [t for t in tests if t.get('ve_slope')]
best_eff = min(effs, key=lambda t: t['ve_slope']) if effs else None
worst_eff = max(effs, key=lambda t: t['ve_slope']) if effs else None
n_eff_ok = sum(1 for t in effs if t['ve_slope'] < 30)
vt1s = [t['vt1_pct'] for t in tests if t.get('vt1_pct')]
avg_vt1 = round(sum(vt1s)/len(vt1s), 1) if vt1s else None
n_vt1_ok = sum(1 for v in vt1s if v >= 70)
male_kg = [t['vo2peak_kg'] for t in tests if t['sex'] in ('男性', '男') and t['vo2peak_kg']]
female_kg = [t['vo2peak_kg'] for t in tests if t['sex'] in ('女性', '女') and t['vo2peak_kg']]
male_mean = round(sum(male_kg) / len(male_kg), 1) if male_kg else 0
female_mean = round(sum(female_kg) / len(female_kg), 1) if female_kg else 0
# CPET 概况（动态，HTML 块内不可用 f-string，先算好）
CPET_HDR = (
    f"1. 最大摄氧量测试情况：本周累计完成 <b>{len(all_tests)}</b> 份测试、覆盖 <b>{len(tests)}</b> 人"
    f"（男 {len(male_kg)} / 女 {len(female_kg)}），其中有效 {cls_counts.get('有效', 0)} 人、"
    f"亚极量 {cls_counts.get('亚极量', 0)} 人、无效 {cls_counts.get('无效', 0)} 人；"
    "剩余人员及复测名单下周继续。<br>")

def ins(txt):
    return f'<div class="insight">💡 {txt}</div>'

top3_txt = '、'.join(f"{t['name']}({t['vo2peak_kg']:.0f})" for t in top3)
ins = {
 'age': ins(f"全队最高为 <b>{top3[0]['name']}</b>（{top3[0]['vo2peak_kg']:.0f} ml/kg/min，{age_at(top3[0]['birth'], top3[0]['start'])} 岁）；前 3 名中 2 人来自 8–10 岁组，小龄组数值偏高，解读时建议先复核设备校准。"),
 'rank': ins(f"有效 <b>{cls_counts.get('有效',0)}</b> 人 / 亚极量 <b>{cls_counts.get('亚极量',0)}</b> 人 / 无效 <b>{cls_counts.get('无效',0)}</b> 人；前三名：{top3_txt}。橙色（亚极量）条上的数值大概率低估真实能力。"),
 'hist': ins(f"相对摄氧量中位数 <b>{med_kg}</b> ml/kg/min，P25–P75 为 {p25_kg}–{p75_kg}，主力集中在 60–75 区间。"),
 'gbar': ins(f"男 {male_mean} vs 女 {female_mean} ml/kg/min（差 {abs(round(male_mean-female_mean,1))}）；该年龄段男女有氧差距尚未拉开，选材不必按性别设卡。"),
 'quality': (ins(f"通气效率最优为 <b>{best_eff['name']}</b>（斜率 {best_eff['ve_slope']:.1f}），{n_eff_ok} 人达到优秀（&lt;30）；斜率最高为 {worst_eff['name']}（{worst_eff['ve_slope']:.1f}），通气效率偏弱需关注。") if best_eff else ''),
 'vt1': (ins(f"VT1 占最大摄氧量平均 <b>{avg_vt1}%</b>，{n_vt1_ok} 人达到良好（≥70%）；比例越高说明越晚进入无氧、耐力储备越好。") if avg_vt1 is not None else ''),
 'team': ins("全队平均摄氧曲线随负荷进度上升，尾部抬升幅度反映测试整体努力度；若尾部平坦或回落，提示多数人提前终止（亚极量）。"),
}

pct_vals = [t['pct_norm'] for t in tests if t.get('pct_norm')]
med_pct = sorted(pct_vals)[len(pct_vals)//2] if pct_vals else 0
n_pct_above = sum(1 for v in pct_vals if v >= 100)
top_pct = order_pct[0] if order_pct else None
def inote(txt):
    return f'<div class="insight">💡 {txt}</div>'
ins['rank_pct'] = inote(f"预测达成率中位数 <b>{med_pct:.0f}%</b>，{n_pct_above}/{len(pct_vals)} 人超过预测值；最高为 {top_pct['name']}（{top_pct['pct_norm']:.0f}%）。注意设备 Wasserman 方程对女生参考值偏低。")
ins['rank_slope'] = inote(f"斜率越低通气越高效：最优 {best_eff['name']}（{best_eff['ve_slope']:.1f}）、最差 {worst_eff['name']}（{worst_eff['ve_slope']:.1f}），{n_eff_ok} 人达优秀（&lt;30）。")
ins['rank_rer'] = inote(f"RER 反映测试努力度：{cls_counts.get('有效',0)} 人 ≥1.05（拼尽全力），橙色/灰色条上的 VO2 峰值大概率被低估。")
ins['rank_vt1'] = inote(f"VT1 占最大摄氧量平均 <b>{avg_vt1}%</b>，{n_vt1_ok} 人 ≥70%（耐力储备良好）；比例越高，无氧启动越晚。")

RANK_INS = {'vo2kg': ins['rank'], 'pct': ins['rank_pct'], 'slope': ins['rank_slope'],
            'rer': ins['rank_rer'], 'vt1': ins['rank_vt1']}

# ---- 文字版报告（可直接复制到 Word）----
from collections import defaultdict
n_male = len([t for t in tests if t['sex'] in ('男性', '男') and t['vo2peak_kg']])
n_female = len([t for t in tests if t['sex'] in ('女性', '女') and t['vo2peak_kg']])
ages_all = [a for a in (age_at(t['birth'], t['start']) for t in tests) if a]
age_min, age_max = min(ages_all), max(ages_all)
hist_by_name = defaultdict(list)
for t in all_tests:
    if t.get('vo2peak_kg'):
        hist_by_name[t['name']].append(t['vo2peak_kg'])
improved = sorted([(n, min(v), max(v)) for n, v in hist_by_name.items()
                   if len(v) >= 2 and max(v) - min(v) >= 5],
                  key=lambda x: -(x[2] - x[1]))
need_retest = [t['name'] for t in tests if test_cls(t) == '无效']
top3_line = '；'.join(f"{t['name']}（{t['vo2peak_kg']:.0f} ml/kg/min，{age_at(t['birth'], t['start'])} 岁）"
                      for t in top3)
improved_line = '；'.join(f"{n}（{a}→{b}）" for n, a, b in improved[:5]) if improved else '暂无'
age_groups = {'8-10': 0, '10-12': 0, '12-14': 0, '14-16': 0, '16+': 0}
for a in ages_all:
    if a < 10: age_groups['8-10'] += 1
    elif a < 12: age_groups['10-12'] += 1
    elif a < 14: age_groups['12-14'] += 1
    elif a < 16: age_groups['14-16'] += 1
    else: age_groups['16+'] += 1
tier = {'≥80': 0, '70-79': 0, '60-69': 0, '<60': 0}
for v in valid_kg_list:
    if v >= 80: tier['≥80'] += 1
    elif v >= 70: tier['70-79'] += 1
    elif v >= 60: tier['60-69'] += 1
    else: tier['<60'] += 1
age_groups_txt = '、'.join(f"{k}岁 {v}人" for k, v in age_groups.items())
tier_txt = '、'.join(f"{k} {v}人" for k, v in tier.items())

def nar(h, body):
    return f'<h3>{h}</h3><p>{body}</p>'
narrative = (
    nar("1. 报告摘要", f"本期共完成 {len(all_tests)} 份心肺运动试验（CPET），覆盖 {len(tests)} 名运动员（男 {n_male} / 女 {n_female}，年龄 {age_min:.1f}–{age_max:.1f} 岁）。"
        f"按有效性分级：有效 {cls_counts.get('有效',0)} 人、亚极量 {cls_counts.get('亚极量',0)} 人、无效 {cls_counts.get('无效',0)} 人；"
        f"每人取相对摄氧量最高的场次进行分析。")
    + nar("2. 有氧能力总览", f"全队相对摄氧量中位数 {med_kg} ml/kg/min（P25–P75：{p25_kg}–{p75_kg}）。"
        f"前三名：{top3_line}。男女均值分别为 {male_mean} 与 {female_mean} ml/kg/min，该年龄段差异不大。"
        f"预测达成率中位数 {med_pct:.0f}%，{n_pct_above}/{len(pct_vals)} 人达到或超过设备预测值。")
    + nar("3. 通气与耐力画像", f"通气效率最优为 {best_eff['name']}（V'E/V'CO2 斜率 {best_eff['ve_slope']:.1f}），"
        f"{n_eff_ok} 人达到优秀（<30）；斜率最高（效率最差）为 {worst_eff['name']}（{worst_eff['ve_slope']:.1f}）。"
        f"VT1 占最大摄氧量平均 {avg_vt1}%，{n_vt1_ok} 人达到良好（≥70%），耐力储备整体较好。")
    + nar("4. 复测进步与待复测名单", f"复测进步最明显的：{improved_line}。"
        f"当前无有效数据、需优先安排复测：{'、'.join(need_retest) if need_retest else '无'}。")
    + nar("5. 数据质量与建议", "全部测试未佩戴心率带，无法验证最大努力度；约三分之一测试 RER<1.05 属亚极量，峰值摄氧量可能被低估。"
        "8–9 岁小龄组数值偏高，建议复核 MetaMax 设备校准（标准气体/3L 注射器/环境修正）。"
        "后续测试建议统一佩戴心率带、对亚极量者安排复测，并保持同一套口头鼓励标准。")
)
# ---- 周报式图文版：每章解读文字 ----
def p(h, body):
    return f'<h2>{h}</h2><p class="lead">{body}</p>'

# ── 心率教练动态叙述（来自 hr_2wk.json coach/coach_last）──
_coach_sorted = sorted(HR2W['coach'], key=lambda c: -c['avg_hr'])
_coach_desc = '、'.join("{}（均心{} bpm）".format(c['name'], c['avg_hr']) for c in _coach_sorted)
_coach_names = '、'.join(c['name'] for c in _coach_sorted)
_last_map = {c['name']: c['avg_hr'] for c in HR2W.get('coach_last', [])}
_coach_cmp_parts = []
for _c in _coach_sorted:
    _lv = _last_map.get(_c['name'])
    if _lv is not None:
        _df = _c['avg_hr'] - _lv
        _vb = '回落' if _df < -1 else ('上升' if _df > 1 else '基本持平')
        _coach_cmp_parts.append("{}（{}→{}，{}）".format(_c['name'], _lv, _c['avg_hr'], _vb))
    else:
        _coach_cmp_parts.append("{}（本周{} bpm）".format(_c['name'], _c['avg_hr']))
_coach_cmp = '；'.join(_coach_cmp_parts)

sec = {
 's1': p("一、本周测试概况与数据质量",
    f"本周共完成 <b>{len(all_tests)}</b> 份心肺运动试验（CPET），覆盖 <b>{len(tests)} 名</b>运动员（男 {n_male} / 女 {n_female}，"
    f"年龄 {age_min:.1f}–{age_max:.1f} 岁，年龄组分布：{age_groups_txt}）。所有测试采用 MetaMax 3B 递增负荷方案，"
    "含 3 分钟安静、3 分钟热身、约 12 分钟递增负荷与 3 分钟恢复。"
    f"按有效性分级（图1）：有效 <b>{cls_counts.get('有效',0)}</b> 人、亚极量 <b>{cls_counts.get('亚极量',0)}</b> 人、"
    f"无效 <b>{cls_counts.get('无效',0)}</b> 人，有效与亚极量合计 {cls_counts.get('有效',0)+cls_counts.get('亚极量',0)} 人纳入主分析。"
    "需要说明三点：其一，全部测试未佩戴心率带，无法用心率验证最大努力度，有效性判定仅依赖 RER；"
    "其二，约三分之一测试 RER&lt;1.05 属亚极量，峰值摄氧量可能被低估；"
    "其三，8–10 岁小龄组相对摄氧量数值偏高，建议复核设备校准（标准气体/3L 注射器/环境修正）后再下结论。"),
 's2': p("二、有氧能力总体水平",
    f"全队相对摄氧量中位数 <b>{med_kg}</b> ml/kg/min（P25–P75：{p25_kg}–{p75_kg}），"
    f"按梯队划分：≥80 共 {tier['≥80']} 人、70–79 共 {tier['70-79']} 人、60–69 共 {tier['60-69']} 人、"
    f"&lt;60 共 {tier['<60']} 人——约六成队员集中在 60–75 区间（图2 排名、图3 分布）。"
    f"前三名：{top3_line}；其中 {top3[0]['name']}、{top3[1]['name']} 均属 8–10 岁组，"
    f"是本周最值得注意的两名小龄选手。男女均值分别为 {male_mean} 与 {female_mean} ml/kg/min"
    f"（图4），相差 {abs(round(male_mean-female_mean,1))} ml/kg/min，该年龄段性别差异尚不明显，"
    f"选材不必按性别设卡。预测达成率中位数 {med_pct:.0f}%，{n_pct_above}/{len(pct_vals)} 人达到或超过"
    "设备预测值；但设备采用 Wasserman 成人方程，女生参考值偏低，跨性别比较时以相对摄氧量原始值为准更稳妥。"
    "排名图支持切换指标（相对摄氧量 / 预测达成率 / 通气效率 / RER / VT1%），便于从不同维度观察队员位置。"),
 's3': p("五、年龄与发育视角",
    f"从年龄分布看（图5），全队覆盖 8.6–17.6 岁，各年龄组人数较为均衡（{age_groups_txt}）。"
    f"最高摄氧量的 {top3[0]['name']} 仅 {age_at(top3[0]['birth'], top3[0]['start'])} 岁，"
    "前 3 名中有 2 人来自 8–10 岁组。从生理规律看，青少年相对摄氧量随年龄增长基本保持稳定，"
    "绝对摄氧量则随体型增长而上升；因此小龄组出现全队最高值并不符合常见规律，"
    "更可能是设备校准或体重换算导致的系统偏差，建议对小龄组单独复核后再纳入横向比较。"
    "图5 用各年龄组的箱线图展示分布（方框=四分位区间、横线=中位数）：可直观看到各年龄组的中位水平、"
    "离散程度与离群点，全队均值线（虚线）便于对照每个年龄组的位置。"),
 's4': p("六、通气效率（呼吸经济性）",
    f"通气效率用 V'E/V'CO2 斜率衡量，<b>越低越好</b>（图6 为全队通气效率排名，越靠左越高效）。"
    f"全队最优为 {best_eff['name']}（斜率 {best_eff['ve_slope']:.1f}），{n_eff_ok} 人达到优秀（&lt;30）；"
    f"斜率最高（效率最差）为 {worst_eff['name']}（{worst_eff['ve_slope']:.1f}）。"
    f"值得注意的是，{top3[0]['name']} 摄氧量全队第一但斜率 {top3[0]['ve_slope']:.1f} 仅属中游，"
    "说明其摄氧能力强而呼吸经济性一般，长距离专项中可能较早出现呼吸疲劳，建议在训练中关注呼吸节奏与效率。"
    "通气效率偏低者（斜率较高）建议结合肺功能与呼吸肌耐力做进一步评估。"),
 's5': p("七、耐力储备（VT1 通气阈）",
    f"VT1（第一通气阈）代表有氧向无氧过渡的临界点，占最大摄氧量的比例越高，说明无氧启动越晚、"
    f"耐力储备越好（图7 为全队 VT1% 分布）。全队平均 <b>{avg_vt1}%</b>，{n_vt1_ok} 人达到良好（≥70%），整体耐力基础不错。"
    "VT1 与峰值摄氧量显著正相关：VT1 高者不仅最大摄氧量高，还能在更高强度下维持纯有氧供能，"
    "这对 500m/1000m/1500m 短道项目的途中配速与后程保持能力有直接参考价值。"
    "VT1 偏低者建议加强低强度有氧基础训练（Zone1–2），先把有氧底子打牢，再发展高强度能力。"),
 's6': p("八、测试过程质量（全队平均曲线）",
    "全队平均摄氧曲线（图8）反映测试的整体执行质量：理想状态下曲线应随负荷进度持续上升、"
    "末端出现平台或缓升，说明多数队员坚持到了力竭；若曲线末端平坦甚至回落，提示相当一部分队员"
    "提前终止（亚极量），此时峰值数据只能视为「本次达到值」而非「真实最大值」。"
    f"结合本周 {cls_counts.get('亚极量',0)} 人亚极量的情况，建议对尾部回落明显的个体安排复测，"
    "并在复测时加强口头鼓励与进度提示，尽可能让队员坚持到 RER≥1.05。"),
 's7': p("九、重点运动员与复测",
    f"复测进步最明显：{improved_line}，说明部分队员已熟悉测试流程，成绩趋于真实水平；"
    f"当前无有效数据、需优先安排复测：{'、'.join(need_retest) if need_retest else '无'}。"
    "部分新队员表现突出，建议结合通气效率等指标持续跟踪。"
    "个人分析器（图9）可逐人查看逐秒摄氧曲线（灰底=恢复期，虚线=VT1/VO2peak）与多维雷达画像，"
    "便教练E针对个体制定训练与复测计划。"),
 's8': p("十、结论与建议",
    "综合本周数据，可以形成几点结论：其一，队列有氧基础整体良好，相对摄氧量中位数 66 ml/kg/min、"
    f"约 {round((cls_counts.get('有效',0)+cls_counts.get('亚极量',0))/len(tests)*100)}% 的测试达到可分析标准；"
    "其二，测试质量是当前主要短板——全部测试无心率、亚极量占比高、小龄组校准存疑，"
    "这三点直接限制了对「真实最大摄氧量」的判断；其三，本周部分新入队运动员表现突出，"
    "具备进入重点培养序列的潜力。据此建议：①后续测试统一佩戴心率带，用 HR≥85% 预测值作为第二验证标准；"
    "②对亚极量者优先安排复测；③复核 MetaMax 校准，重点核验低龄组；"
    "④所有数据按有效性分级使用，橙色/灰色数值仅作下限参考，不作横向定论。"),
 's9': p("十一、下周工作安排",
    "① 完成剩余运动员最大摄氧量测试与复测（按质量标记确定优先级）；"
    "② 全部测试统一佩戴心率带，补齐最大努力度验证；③ 复核 MetaMax 气体分析仪校准（标准气体/3L 注射器/环境修正），重点核验 8–9 岁小龄组；"
    "④ 继续长期干预（艾灸+推拿 / 拔罐+推拿 / 常规恢复）并记录出勤；⑤ 补测 24h/48h/72h HRV；"
    "⑥ 训练心率持续监测（每教练每周至少 2 次，冰上、陆地各至少 1 次）；⑦ 统一姓名别名口径并补录新队员档案。"),
's_hr': p("三、训练心率监测（本周）",
    f"本周（{HR2W['this']['range']}）共监测 <b>{HR2W['this']['sessions']}</b> 个训练场次、{HR2W['this']['athletes']} 名运动员，"
    f"全队平均心率 <b>{HR2W['this']['avg_hr']}</b> bpm、高强度区间（Z4+Z5）占比 <b>{HR2W['this']['z45']}%</b>、"
    f"人均训练冲量 TRIMP <b>{HR2W['this']['trimp_mean']:.0f}</b>，单场最高心率 {HR2W['this']['max_hr']} bpm。"
    f"各教练强度差异明显（图1）：{_coach_desc}。"
    f"本周参与监测的为{_coach_names}共{len(HR2W['coach'])}组。"),
's_2wk': p("四、两周对比与追踪",
    f"与上周（{HR2W['last']['range']}）相比，全队平均心率由 {HR2W['last']['avg_hr']} 降至 {HR2W['this']['avg_hr']} bpm"
    f"（{round(HR2W['this']['avg_hr']-HR2W['last']['avg_hr'],1):+.1f}），高强度占比由 {HR2W['last']['z45']}% 降至 {HR2W['this']['z45']}%，"
    f"人均 TRIMP 由 {HR2W['last']['trimp_mean']:.0f} 降至 {HR2W['this']['trimp_mean']:.0f}——"
    f"本周训练负荷较上周整体回落（图2、图3），进入恢复调整周。教练组对比：{_coach_cmp}。重点追踪（表2）："
    f"{'、'.join(t['name'] for t in HR2W['track'][:4])} 等本周训练负荷（TRIMP）较上周明显上升"
    f"（+{min(t['trimp_delta'] for t in HR2W['track']):.0f} 至 +{max(t['trimp_delta'] for t in HR2W['track']):.0f}），"
    "投入度高的同时恢复压力同步升高，建议重点关注睡眠、肌肉酸痛与疲劳状态。"),
}

narrative_section = (
    '<div id="nar_text" style="display:none">' +
    "".join(sec.values()).replace("<h2>", "<p><b>").replace("</h2>", "</b></p>") +
    '</div>'
)

ch['c_rank'] = (
    '<div id="c_rank" style="width:100%;height:1000px"></div>\n'
    '<script>\n'
    'var rankChart = echarts.init(document.getElementById("c_rank"));\n'
    'var RANK_DATA = ' + J(rank_people) + ';\n'
    'var RANK_INS = ' + J(RANK_INS) + ';\n'
    'var RANK_META = {vo2kg:{desc:1,label:"相对摄氧量 (ml/kg/min)"},\n'
    '                pct:{desc:1,label:"预测达成率 (%)"},\n'
    '                slope:{desc:0,label:"V\\\'E/V\\\'CO2 斜率 (越低越好)"},\n'
    '                rer:{desc:1,label:"RER (测试努力度)"},\n'
    '                vt1:{desc:1,label:"VT1 占最大摄氧量 (%)"}};\n'
    'function drawRank(metric){\n'
    '  var meta = RANK_META[metric];\n'
    '  var data = RANK_DATA.map(function(p){\n'
    '    return {name:p.name, value:p[metric], cls:p.cls, itemStyle:{color:p.color}};\n'
    '  }).sort(function(a,b){\n'
    '    if (a.value === 0 && b.value !== 0) return 1;\n'
    '    if (b.value === 0 && a.value !== 0) return -1;\n'
    '    return meta.desc ? b.value-a.value : a.value-b.value;\n'
    '  });\n'
    '  rankChart.setOption({\n'
    '   tooltip:{trigger:"axis",axisPointer:{type:"shadow"},\n'
    '    formatter:function(p){return p.name+"<br>"+p.value+" · "+p.data.cls;}},\n'
    '   toolbox:{right:10,feature:{saveAsImage:{name:"排名_"+metric,pixelRatio:2},restore:{}}},\n'
    '   grid:{left:95,right:60,top:20,bottom:20},\n'
    '   xAxis:{type:"value",name:meta.label},\n'
    '   yAxis:{type:"category",data:data.map(function(d){return d.name;}),inverse:true},\n'
    '   series:[{type:"bar",data:data,\n'
    '    label:{show:true,position:"right",fontSize:10,\n'
    '           formatter:function(p){return p.value || "-";}},\n'
    '    barMaxWidth:13}]\n'
    '  });\n'
    '  var el = document.getElementById("rank_insight");\n'
    '  if(el){ el.innerHTML = RANK_INS[metric]; }\n'
    '}\n'
    'function initRankButtons(){\n'
    '  drawRank("vo2kg");\n'
    '  document.addEventListener("click", function(e){\n'
    '    var t = e.target;\n'
    '    while (t && t !== document) {\n'
    '      if (t.classList && t.classList.contains("rk")) {\n'
    '        document.querySelectorAll(".rk").forEach(function(x){ x.classList.remove("on"); });\n'
    '        t.classList.add("on");\n'
    '        drawRank(t.getAttribute("data-m"));\n'
    '        return;\n'
    '      }\n'
    '      t = t.parentNode;\n'
    '    }\n'
    '  });\n'
    '}\n'
    'if (document.readyState === "loading") {\n'
    '  document.addEventListener("DOMContentLoaded", initRankButtons);\n'
    '} else {\n'
    '  initRankButtons();\n'
    '}\n'
    '</script>'
)

hist_bins = [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]
hist_labels = [f'{a}-{b}' for a, b in zip(hist_bins[:-1], hist_bins[1:])]
hist_counts = [sum(1 for v in vo2kg if a <= v < b) for a, b in zip(hist_bins[:-1], hist_bins[1:])]
ch['c_hist'] = ech('c_hist', """
c.setOption({
 tooltip:{trigger:'axis'},
 toolbox:{right:10,feature:{saveAsImage:{name:'VO2分布',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:20,bottom:40},
 xAxis:{type:'category',data:""" + J(hist_labels) + """,axisLabel:{rotate:35,fontSize:10}},
 yAxis:{type:'value',name:'人数',minInterval:1},
 series:[{type:'bar',data:""" + J(hist_counts) + """,itemStyle:{color:'#3f7fb8'},
  label:{show:true,position:'top'},barMaxWidth:42}]
});""", 360)

male_kg = [t['vo2peak_kg'] for t in tests if t['sex'] in ('男性', '男') and t['vo2peak_kg']]
female_kg = [t['vo2peak_kg'] for t in tests if t['sex'] in ('女性', '女') and t['vo2peak_kg']]
male_mean = round(sum(male_kg) / len(male_kg), 1) if male_kg else 0
female_mean = round(sum(female_kg) / len(female_kg), 1) if female_kg else 0
ch['c_gbar'] = ech('c_gbar', """
c.setOption({
 tooltip:{},
 toolbox:{right:10,feature:{saveAsImage:{name:'男女对比',pixelRatio:2},restore:{}}},
 grid:{left:55,right:20,top:30,bottom:30},
 xAxis:{type:'category',data:['男性 (n=""" + str(len(male_kg)) + """)','女性 (n=""" + str(len(female_kg)) + """)']},
 yAxis:{type:'value',name:'ml/kg/min',min:0},
 series:[{type:'bar',data:[""" + str(male_mean) + """,""" + str(female_mean) + """],
  itemStyle:{color:function(p){return p.dataIndex===0?'#3f7fb8':'#d05555';}},
  label:{show:true,position:'top',formatter:function(p){return p.value+' ml/kg/min';}},
  barMaxWidth:90}]
});""", 360)

ch['c_hr_coach'] = ech('c_hr_coach', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{top:0,data:['平均心率','Z4+Z5%']},
 grid:{left:45,right:45,top:32,bottom:30},
 xAxis:{type:'category',data:""" + J([c['name'] for c in HR2W['coach']]) + """},
 yAxis:[{type:'value',name:'bpm'},{type:'value',name:'%',splitLine:{show:false}}],
 series:[
  {name:'平均心率',type:'bar',data:""" + J([c['avg_hr'] for c in HR2W['coach']]) + """,
   itemStyle:{color:'#3f7fb8'},label:{show:true,position:'top'}},
  {name:'Z4+Z5%',type:'line',yAxisIndex:1,data:""" + J([c['z45'] for c in HR2W['coach']]) + """,
   itemStyle:{color:'#d05555'},label:{show:true,position:'top'}}
 ]});""", 320)

ch['c_hr_2wk'] = ech('c_hr_2wk', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{top:0,data:['上周(""" + W_LAST + """)','本周(""" + W_THIS + """)']},
 grid:{left:45,right:20,top:32,bottom:30},
 xAxis:{type:'category',data:['平均心率(bpm)','Z4+Z5(%)','人均TRIMP']},
 yAxis:{type:'value'},
 series:[
  {name:'上周(""" + W_LAST + """)',type:'bar',data:""" + J([HR2W['last']['avg_hr'], HR2W['last']['z45'], round(HR2W['last']['trimp_mean'])]) + """,
   itemStyle:{color:'#9aa7b5'},label:{show:true,position:'top'}},
  {name:'本周(""" + W_THIS + """)',type:'bar',data:""" + J([HR2W['this']['avg_hr'], HR2W['this']['z45'], round(HR2W['this']['trimp_mean'])]) + """,
   itemStyle:{color:'#3f7fb8'},label:{show:true,position:'top'}}
 ]});""", 320)

def fnum(v, plus=False):
    if v is None:
        return '-'
    return (f"+{v:.1f}" if plus and v > 0 else f"{v:.1f}")

track_rows = [[t['name'],
               fnum(t['avg_l']), fnum(t['avg_t']), fnum(t['hr_delta'], True),
               fnum(t['trimp_l']), fnum(t['trimp_t']), fnum(t['trimp_delta'], True),
               fnum(t['z45_l']), fnum(t['z45_t'])]
              for t in HR2W['track']]
track_html = ('<div class="tblbox"><table><thead><tr>'
              '<th>运动员</th><th>上周均HR</th><th>本周均HR</th><th>HR变化</th>'
              '<th>上周TRIMP</th><th>本周TRIMP</th><th>TRIMP变化</th>'
              '<th>上周Z4+5%</th><th>本周Z4+5%</th></tr></thead><tbody>' +
              ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in track_rows) +
              '</tbody></table></div>')

# ---- 长期干预周报新图表：教练区间堆叠 / 两周对比 ----
ZC_ZONES = ['#5b8fc7', '#5fb06e', '#e0c34e', '#e58f4f', '#d05555']
ch['c_hr_zones'] = ech('c_hr_zones', """
c.setOption({
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 legend:{top:0,data:['Zone1','Zone2','Zone3','Zone4','Zone5']},
 toolbox:{right:10,feature:{saveAsImage:{name:'教练心率区间',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:34,bottom:34},
 xAxis:{type:'category',data:""" + J([z['name'] for z in HR2W['coach_zones']]) + """,
  axisLabel:{rotate:18,fontSize:10}},
 yAxis:{type:'value',name:'占比(%)',max:100},
 series:[""" + ','.join(
    '{name:"Zone' + str(i) + '",type:"bar",stack:"z",barMaxWidth:52,itemStyle:{color:"' + ZC_ZONES[i-1] + '"},data:' + J([z['z'][i-1] for z in HR2W['coach_zones']]) + '}'
    for i in range(1, 6)) + """]
});""", 340)

def cmp_series(key, c_last, c_this):
    cc = [c for c in HR2W['coach_cmp'] if c['this_avg'] is not None]
    return ('[{name:"上周(' + W_LAST + ')",type:"bar",itemStyle:{color:"' + c_last + '"},'
            'label:{show:true,position:"top"},data:' + J([c['last_' + key] for c in cc]) + '},'
            '{name:"本周(' + W_THIS + ')",type:"bar",itemStyle:{color:"' + c_this + '"},'
            'label:{show:true,position:"top"},data:' + J([c['this_' + key] for c in cc]) + '}]')

ch['c_cmp_hr'] = ech('c_cmp_hr', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{top:0,data:['上周(""" + W_LAST + """)','本周(""" + W_THIS + """)']},
 toolbox:{right:10,feature:{saveAsImage:{name:'两周平均心率对比',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:34,bottom:30},
 xAxis:{type:'category',data:""" + J([c['name'] for c in HR2W['coach_cmp'] if c['this_avg'] is not None]) + """},
 yAxis:{type:'value',name:'bpm'},
 series:""" + cmp_series('avg', '#9aa7b5', '#3f7fb8') + """
});""", 320)

ch['c_cmp_z45'] = ech('c_cmp_z45', """
c.setOption({
 tooltip:{trigger:'axis'},
 legend:{top:0,data:['上周(""" + W_LAST + """)','本周(""" + W_THIS + """)']},
 toolbox:{right:10,feature:{saveAsImage:{name:'两周高强度对比',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:34,bottom:30},
 xAxis:{type:'category',data:""" + J([c['name'] for c in HR2W['coach_cmp'] if c['this_avg'] is not None]) + """},
 yAxis:{type:'value',name:'%'},
 series:""" + cmp_series('z45', '#9aa7b5', '#d05555') + """
});""", 320)

zone_lines = []
for z in HR2W['coach_zones']:
    v = z['z']
    z12 = round(v[0] + v[1], 1)
    z45 = round(v[3] + v[4], 1)
    if z45 < 5:
        tag = "训练强度整体偏低，全程无无氧高强度负荷，以低强度有氧为主"
    elif z45 < 15:
        tag = "以有氧为主体，少量穿插高强度训练"
    elif z45 < 25:
        tag = "有氧、混氧、高强度配比全面，训练负荷起伏明显"
    else:
        tag = "高强度占比突出，训练强度密度大"
    zone_lines.append(
        f"{z['name']}：Zone1占{v[0]}%，Zone2占{v[1]}%，Zone3占{v[2]}%，"
        f"Zone4占{v[3]}%，Zone5占{v[4]}%（Zone1+2={z12}%、Z4+5={z45}%）——{tag}")

focus_lines = [f"{f['name']}: 均HR {f['avg']:.0f} bpm—训练投入度高，关注体能与恢复"
               for f in HR2W['focus']]

cmp_lines = []
for c in HR2W['coach_cmp']:
    if c['this_avg'] is None:
        continue
    if c['this_avg'] is not None and c['last_avg'] is not None:
        d = c['this_avg'] - c['last_avg']
        trend = "升至" if d >= 0 else "降至"
        if (c['this_z45'] or 0) == 0:
            cmp_lines.append(
                f"{c['name']}：平均心率由{c['last_avg']}{trend}{c['this_avg']}（{d:+.1f}次/分）；"
                f"高强度占比由{c['last_z45']}%降至0%（本周8月4日陆上训练以低强度有氧为主，无高强度内容）")
        else:
            dz = (c['this_z45'] or 0) - (c['last_z45'] or 0)
            trend_z = "升至" if dz >= 0 else "降至"
            cmp_lines.append(
                f"{c['name']}：平均心率由{c['last_avg']}{trend}{c['this_avg']}（{d:+.1f}次/分）；"
                f"高强度占比由{c['last_z45']}%{trend_z}{c['this_z45']}%（{dz:+.1f}个百分点）")
    else:
        cmp_lines.append(f"{c['name']}：本周首次纳入监测（均心{c['this_avg']}）")

ch['c_cls'] = ech('c_cls', """
c.setOption({
 tooltip:{},
 toolbox:{right:10,feature:{saveAsImage:{name:'有效性分布',pixelRatio:2},restore:{}}},
 grid:{left:45,right:20,top:30,bottom:30},
 xAxis:{type:'category',data:['有效','亚极量','无效']},
 yAxis:{type:'value',name:'人数',minInterval:1},
 series:[{type:'bar',data:[
   {value:""" + str(cls_counts.get('有效', 0)) + """,itemStyle:{color:'#2E8B57'}},
   {value:""" + str(cls_counts.get('亚极量', 0)) + """,itemStyle:{color:'#E8A33D'}},
   {value:""" + str(cls_counts.get('无效', 0)) + """,itemStyle:{color:'#8A94A0'}}],
  label:{show:true,position:'top'},barMaxWidth:80}]
});""", 330)

echarts_js = open(ECHARTS_PATH, encoding='utf-8', errors='ignore').read()
html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>最大摄氧量 CPET 结果报告</title>
<style>
body { font-family:'Microsoft YaHei',sans-serif; margin:0; background:#f5f3ee; color:#333; }
.wrap { max-width:1160px; margin:0 auto; padding:24px; }
h1 { font-size:22px; margin:0 0 2px; }
.sub { color:#888; font-size:13px; margin-bottom:18px; }
h2 { font-size:16px; border-left:4px solid #3f7fb8; padding-left:8px; margin:28px 0 8px; }
table { border-collapse:collapse; width:100%; font-size:12px; background:#fff; }
th,td { padding:5px 7px; border-bottom:1px solid #e8e4da; text-align:left; }
.topcards { display:flex; flex-wrap:wrap; gap:10px; margin:10px 0 6px; }
.topcard { flex:1 1 220px; min-width:210px; background:linear-gradient(160deg,#f4f7fb,#fff); border:1px solid #e3e9f2; border-radius:10px; padding:10px 14px; }
.topcard h4 { margin:0 0 6px; font-size:13px; color:#3f6d9c; border-bottom:1px dashed #d8e0ea; padding-bottom:4px; }
.topcard ul { margin:0; padding:0; list-style:none; }
.topcard li { display:flex; align-items:center; gap:8px; font-size:12px; padding:2px 0; }
.topcard .tk { display:inline-flex; width:20px; height:20px; border-radius:50%; background:#3f7fb8; color:#fff; font-size:11px; align-items:center; justify-content:center; flex:none; }
.topcard li:nth-child(2) .tk { background:#5b8fc0; }
.topcard li:nth-child(n+3) .tk { background:#9db8d4; }
.topcard li b { margin-left:auto; color:#c0392b; font-weight:600; }
#rank_tbl th { cursor:pointer; user-select:none; background:#eef3f9; }
#rank_tbl th:hover { background:#dde8f4; }
#rank_tbl tr:hover { background:#f6f9fd; }
.rcls { font-weight:600; }
details.guide { background:#f7f9fc; border:1px solid #e3e9f2; border-radius:8px; padding:8px 12px; margin:10px 0; }
details.guide summary { cursor:pointer; font-weight:600; color:#3f6d9c; font-size:13px; }
details.guide table { margin-top:8px; }
th { background:#37424f; color:#fff; font-weight:600; }
tbody tr:nth-child(even) { background:#faf9f6; }
.tblbox { margin:12px 0; }
.tblbar { display:flex; gap:8px; margin-bottom:6px; }
button.dl { background:#f0ece2; border:1px solid #ddd5c4; color:#555; border-radius:5px; padding:4px 12px; font-size:12px; cursor:pointer; font-family:inherit; }
button.dl:hover { background:#e6e0d2; }
.rkbar { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px; }
button.rk { background:#f0ece2; border:1px solid #ddd5c4; color:#555; border-radius:6px; padding:5px 14px; font-size:12.5px; cursor:pointer; font-family:inherit; }
button.rk:hover { background:#e6e0d2; }
button.rk.on { background:#3f7fb8; color:#fff; border-color:#3f7fb8; }
.cbar { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.cbar .cap { font-size:13px; font-weight:600; color:#445; }
.cbar .sp { flex:1; }
.chartbox { background:#fff; border:1px solid #ece7dc; border-radius:10px; padding:10px; margin:12px 0; }
.kpis { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
.kpi { flex:1; min-width:150px; background:#fff; border:1px solid #ece7dc; border-radius:10px; padding:12px; text-align:center; }
.kpi .v { font-size:22px; font-weight:800; color:#3f7fb8; }
.kpi .l { color:#888; font-size:12px; margin-top:3px; }
select { font-size:13px; padding:5px 10px; border-radius:6px; border:1px solid #ccc; font-family:inherit; margin-bottom:6px; }
.note { background:#fdf6ea; border:1px solid #ecdcb8; border-radius:6px; padding:10px 14px; font-size:12.5px; color:#7a6634; margin:12px 0; }
.insight { background:#eef4fa; border-left:3px solid #3f7fb8; border-radius:4px; padding:8px 13px; font-size:12.5px; color:#3a4a5a; margin:6px 0 16px; line-height:1.6; }
.nar { background:#fff; border:1px solid #ece7dc; border-radius:8px; padding:14px 20px; font-size:13.5px; line-height:1.9; color:#333; }
.nar h3 { font-size:14px; color:#3f7fb8; margin:12px 0 4px; }
.nar p { margin:4px 0 12px; }
p.lead { font-size:14px; line-height:1.95; color:#333; margin:8px 0 14px; text-align:justify; }
.report-head { display:flex; align-items:center; gap:18px; margin-bottom:4px; padding:14px 18px;
  background:linear-gradient(135deg,#f7fafc,#eef4f8); border:1px solid #d7e3ec; border-radius:10px; }
.report-head .logos { display:flex; align-items:center; gap:10px; }
.report-head .logos img { height:54px; width:auto; object-fit:contain; }
.report-head .head-txt { flex:1; text-align:center; }
.report-head h1 { font-size:26px; margin:0; color:#1f3c55; letter-spacing:2px; }
.report-head .week { font-size:15px; color:#3f7fb8; margin-top:4px; font-weight:600; }
.report-head .sub2 { font-size:12px; color:#8a94a0; margin-top:4px; }
.figcap { text-align:center; font-size:13px; color:#555; font-weight:600; margin:2px 0 4px; }
.figref { color:#3f7fb8; font-weight:600; }
.zonegrid { display:flex; flex-wrap:wrap; gap:10px; }
.zoneitem { flex:1 1 210px; min-width:200px; }
</style>
<script>""" + echarts_js + """</script>
</head><body><div class="wrap">
<div class="report-head">
<div class="logos">
<img src=\"""" + LOGO_1 + """\" alt="logo1">
<img src=\"""" + LOGO_2 + """\" alt="logo2">
<img src=\"""" + LOGO_3 + """\" alt="logo3">
</div>
<div class="head-txt">
<h1>七台河短道速滑训练基地</h1>
<div class="week">2026年8月第3周 · 长期干预工作周报</div>
<div class="sub2">版本 V20 · 监测期 """ + min((t['start'][:10] for t in tests if t.get('start')), default='2026-07-27') + """ ~ 2026-""" + W_THIS.split('~')[-1] + """ · 编制时间 """ + GEN_TIME + """</div>
</div>
</div>
<div class="kpis">""" + cards + """</div>
<!-- 一、干预基本情况 -->
<h2>一、干预基本情况</h2>
<p class="lead">
1. 干预时间：8月4日—8月7日<br>
2. 干预人数：队列共 77 人，其中艾灸+推拿组 22 人、拔罐+推拿组 23 人、常规恢复组 22 人（10 人分组待确认）；本周出勤人次数据待补充。<br>
3. 干预流程：艾灸+推拿组：10min 全身推拿放松 + 18min 全身艾灸包艾灸；拔罐+推拿组：10min 全身推拿放松 + 18min 全身气罐拔罐。<br>
4. 未测项目：24h/48h HRV 未全部采集完成，肌电未测。
</p>
<!-- 二、运动负荷检测情况 -->
<h2>二、运动负荷检测情况</h2>
<p class="lead"><b>1. 本周训练强度总览</b></p>
""" + tblbox('本周训练课', ['序号', '日期', '训练课', '教练', '人数', '平均心率', '最大心率', '时长'],
            [[i + 1, s['date'], s['session'], s['coach'], s['n'], s['avg'], s['mx'],
              f"{int(s['dur_min']) // 60}:{int(s['dur_min']) % 60:02d}"]
             for i, s in enumerate(HR2W['sessions'])]) + """
<div class="figcap" style="text-align:left">表1 各训练课平均心率（本周 """ + W_THIS + """）</div>
<p class="lead"><b>2. 心率区间分布</b>（图1 各教练心率区间分布图）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图1 各教练心率区间分布</span><span class="sp"></span><button class="dl" data-copy="c_hr_zones">复制图片</button></div>
""" + ch['c_hr_zones'] + """
<div class="figcap">图1 各教练心率区间构成（Z1-Z5 堆叠）</div>
</div>
<p class="lead">""" + '；<br>'.join(zone_lines) + """。<br>注：Zone1-2=有氧区，Zone3=混氧区，Zone4-5=无氧高强度区。</p>
<p class="lead"><b>3. 重点关注运动员（训练负荷较高）</b></p>
<p class="lead">""" + '<br>'.join(focus_lines) + """<br>解读：以上运动员本周训练心率水平较高，说明训练参与度较高，同时身体承受的训练压力也相对较大。后续建议重点关注这些队员的恢复情况（睡眠、肌肉酸痛和疲劳感）；若连续多次处于高负荷，可适当降低训练容量、增加低强度恢复训练，避免疲劳累积与运动损伤风险。</p>
<p class="lead"><b>4. 本周与上周训练强度对比</b>（图2、图3）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图2 上周与本周平均心率对比</span><span class="sp"></span><button class="dl" data-copy="c_cmp_hr">复制图片</button></div>
""" + ch['c_cmp_hr'] + """
</div>
<div class="chartbox">
<div class="cbar"><span class="cap">图3 上周与本周高强度区间对比（Z4+Z5）</span><span class="sp"></span><button class="dl" data-copy="c_cmp_z45">复制图片</button></div>
""" + ch['c_cmp_z45'] + """
</div>
<p class="lead">""" + '；<br>'.join(cmp_lines) + """。</p>
<p class="lead"><b>4b. 教练维度心率对比</b>（图4 各教练平均心率与高强度占比）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图4 各教练平均心率与 Z4+Z5 占比</span><span class="sp"></span><button class="dl" data-copy="c_hr_coach">复制图片</button></div>
""" + ch['c_hr_coach'] + """
</div>
<p class="lead"><b>4c. 全队两周总体对比</b>（图5 平均心率 / 高强度占比 / 人均TRIMP）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图5 上周与本周全队总体对比</span><span class="sp"></span><button class="dl" data-copy="c_hr_2wk">复制图片</button></div>
""" + ch['c_hr_2wk'] + """
</div>
<p class="lead"><b>5. 上周重点关注运动员·本周追踪</b></p>
""" + tblbox('重点关注追踪', ['运动员', '上周平均心率', '本周平均心率', '本周状态'],
            [[t['name'], fnum(t['last']), fnum(t['now']), t['status']] for t in HR2W['track2wk']]) + """
<div class="figcap" style="text-align:left">表2 重点关注运动员心率对比</div>
<p class="lead">解读：部分运动员本周缺席训练，无有效数据；部分运动员训练强度显著回落，建议在恢复期保持主动放松，逐步回归正常负荷。</p>
""" + CPET_HDR + """
<!-- 三、最大摄氧量与HRV测试情况 -->
<h2>三、最大摄氧量与HRV测试情况</h2>
<p class="lead">
2. HRV 测试情况：本周未开展，下周安排补测。
</p>
<p class="lead"><b>1. 最大摄氧量排名</b>（图6 交互式，点按钮切换指标）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图6 相对摄氧量排名（可切换相对/绝对/百分比指标）</span><span class="sp"></span><button class="dl" data-copy="c_rank">复制图片</button></div>
""" + ch['c_rank'] + """
</div>
<p class="lead"><b>Top 10 排名</b>（图18 分级着色：绿=有效 橙=亚极量）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图18 相对摄氧量 Top10（绿=有效 橙=亚极量）</span><span class="sp"></span><button class="dl" data-copy="c_topbar">复制图片</button></div>
""" + ch['c_topbar'] + """
</div>
<p class="lead"><b>Top 5 能力雷达对比</b>（图19 VO2/预测达成/VT1/通气效率/RER 五维）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图19 前 5 名运动员多维能力对比</span><span class="sp"></span><button class="dl" data-copy="c_topradar">复制图片</button></div>
""" + ch['c_topradar'] + """
</div>
""" + RANK_TABLE_HTML + """
<p class="lead"><b>2. 测试有效性分级</b>（图7）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图7 有效性分级分布（有效/亚极量/无效）</span><span class="sp"></span><button class="dl" data-copy="c_cls">复制图片</button></div>
""" + ch['c_cls'] + """
</div>
<p class="lead"><b>3. 相对摄氧量分布</b>（图8）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图8 相对摄氧量分布直方图</span><span class="sp"></span><button class="dl" data-copy="c_hist">复制图片</button></div>
""" + ch['c_hist'] + """
</div>
<p class="lead"><b>4. 性别对比</b>（图9）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图9 男女相对摄氧量对比</span><span class="sp"></span><button class="dl" data-copy="c_gbar">复制图片</button></div>
""" + ch['c_gbar'] + """
</div>
<p class="lead"><b>5. 年龄与发育视角</b>（图10 各年龄段 VO2max 箱线图，虚线=全队均值）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图10 年龄与发育视角</span><span class="sp"></span><button class="dl" data-copy="c_age">复制图片</button></div>
""" + ch['c_age'] + """
</div>
<p class="lead"><b>6. VT1 耐力储备</b>（图11 VT1 占最大摄氧量百分比分布，红色虚线=耐力储备参考线）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图11 VT1 耐力储备分布</span><span class="sp"></span><button class="dl" data-copy="c_vt1s">复制图片</button></div>
""" + ch['c_vt1s'] + """
</div>
<p class="lead"><b>7. 测试质量（通气效率）</b>（图12 VE/VCO2 斜率排名，越低越好）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图12 通气效率 VE/VCO2 斜率</span><span class="sp"></span><button class="dl" data-copy="c_quality">复制图片</button></div>
""" + ch['c_quality'] + """
</div>
<p class="lead"><b>8. 全队平均测试曲线</b>（图13 测试进度 vs 相对摄氧量）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图13 全队平均 VO2 测试曲线</span><span class="sp"></span><button class="dl" data-copy="c_team">复制图片</button></div>
""" + ch['c_team'] + """
</div>
<p class="lead"><b>9. 运动员个体测试曲线</b>（图14 选择运动员查看 VO2/kg 与 RER 全程曲线，含 VT1/VO2peak 标记）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图14 运动员 CPET 测试曲线</span>
<select id="ath_sel" class="dl" style="margin-left:10px;font-size:12px;padding:3px 8px" onchange="if(this.value){drawAth(this.value);drawRadar(this.value);}"><option value="">选择运动员</option></select>
<span class="sp"></span><button class="dl" data-copy="c_ath_curve">复制图片</button></div>
""" + ch['c_ath_curve'] + """
</div>
<p class="lead"><b>10. 运动员能力雷达图</b>（图15 相对VO2max/预测达成/VT1占比/通气效率/RER 五维）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图15 运动员能力雷达图</span><span class="sp"></span><button class="dl" data-copy="c_ath_radar">复制图片</button></div>
""" + ch['c_ath_radar'] + """
</div>
<p class="lead"><b>11. 复测进步/退步（纵向趋势）</b>（图16 有多次测试者的 VO2 变化，绿=进步 红=退步）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图16 复测 VO2/kg 变化（""" + str(n_multi) + """ 人多次测试）</span><span class="sp"></span><button class="dl" data-copy="c_trend">复制图片</button></div>
""" + ch['c_trend'] + """
</div>
<p class="lead">解读：""" + str(n_multi) + """ 人有多次测试，其中 """ + str(n_progress) + """ 人进步（Δ&gt;2）、""" + str(n_regress) + """ 人退步（Δ&lt;-2）。""" + TREND_TEXT + """。</p>
<p class="lead"><b>12. 干预组 VO2 对比</b>（图17 常规恢复/艾灸+推拿/拔罐+推拿 三组箱线 + Kruskal-Wallis 检验）</p>
<div class="chartbox">
<div class="cbar"><span class="cap">图17 三干预组 VO2/kg 对比</span><span class="sp"></span><button class="dl" data-copy="c_group">复制图片</button></div>
""" + ch['c_group'] + """
</div>
<p class="lead">解读：""" + ('；'.join("{} 组（n={}）中位数 {} ml/kg/min".format(g, grp_stats[g]['n'], grp_stats[g]['med']) for g in GRP_ORDER if g in grp_stats)) + """。""" + ("三组间差异 Kruskal-Wallis p={:.3f}，{} 统计显著性。".format(grp_kw, '达到' if grp_kw < 0.05 else '未达到') if grp_kw is not None else "三组样本量不足，未做组间检验。") + """</p>
<p class="lead"><b>13. 数据质量筛查</b>（z-score 离群者 &amp; 无效测试清单，需复核/复测）</p>
<table class="qctab"><tr><th>类别</th><th>名单</th><th>说明</th></tr>
<tr><td>VO2 显著偏高（z&gt;1.5）</td><td>""" + ('、'.join(t['name'] for t in high_z) if high_z else '无') + """</td><td>""" + ("含 8-10 岁小龄组，建议复核设备校准" if any(t['z'] and t['z'] > 1.5 and age_at(t.get('birth'), t.get('start')) < 10 for t in tests) else "多为高有氧天赋个体") + """</td></tr>
<tr><td>VO2 显著偏低（z&lt;-1.5）</td><td>""" + ('、'.join(t['name'] for t in low_z) if low_z else '无') + """</td><td>多为亚极量/首次测试，建议复测确认</td></tr>
<tr><td>无效测试（无有效 VO2）</td><td>""" + ('、'.join(invalid_list) if invalid_list else '无') + """</td><td>数据不可用，需重新测试</td></tr>
<tr><td>未达良好 VT1（&lt;70%）</td><td>""" + ('、'.join(t['name'] for t in tests if t.get('vt1p') and t['vt1p'] < 70) if any(t.get('vt1p') and t['vt1p'] < 70 for t in tests) else '无') + """</td><td>建议加强 Zone1-2 有氧基础</td></tr>
</table>
<script>
(function(){
  var sel = document.getElementById('ath_sel');
  if(!sel) return;
  var names = Object.keys(window.ATH || {});
  names.forEach(function(n){
    var o = document.createElement('option');
    o.value = n; o.textContent = n; sel.appendChild(o);
  });
  if(names.length){
    sel.value = names[0];
    window.drawAth && window.drawAth(names[0]);
    window.drawRadar && window.drawRadar(names[0]);
  }
})();
</script>
<!-- 四、下周安排 -->
<h2>四、下周安排</h2>
<p class="lead">
（一）继续长期干预，继续测试最大摄氧量并完成待复测名单。<br>
（二）根据各队训练时间持续跟队，每周至少检测 2 次训练时运动负荷（冰上、陆地至少各一次）。<br>
（三）预计在跟队时/干预时进行 HRV、前测问卷、下肢长补测。
</p>
""" + narrative_section + """
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
function copyChart(btn, id){
  var inst = echarts.getInstanceByDom(document.getElementById(id));
  if(!inst){ toast('未找到图表'); return; }
  var url = inst.getDataURL({type:'png', pixelRatio:2, backgroundColor:'#ffffff'});
  function fallback(){
    var img = new Image();
    img.onload = function(){
      img.style.cssText='position:fixed;left:-9999px;top:0;';
      document.body.appendChild(img);
      var range = document.createRange(); range.selectNode(img);
      var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
      var ok = document.execCommand('copy');
      sel.removeAllRanges(); document.body.removeChild(img);
      toast(ok ? '已复制图片，可直接粘贴到 Word / PPT' : '复制失败，请用图表右上角「保存为图片」');
    };
    img.src = url;
  }
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      fetch(url).then(function(r){ return r.blob(); }).then(function(blob){
        return navigator.clipboard.write([new ClipboardItem({'image/png': blob})]);
      }).then(function(){ toast('已复制图片，可直接粘贴到 Word / PPT'); },
               function(){ fallback(); });
      return;
    }
    throw new Error('no-clipboard');
  } catch(e){ fallback(); }
}
function copyText(btn, id){
  var el = document.getElementById(id);
  var txt = (el.textContent || el.innerText || '').replace(/^\\s+|\\s+$/g, '');
  try {
    navigator.clipboard.writeText(txt).then(function(){ toast('已复制文字，可直接粘贴到 Word'); },
      function(){ selectCopy(el); });
  } catch(e){ selectCopy(el); }
}
function selectCopy(el){
  var range = document.createRange(); range.selectNodeContents(el);
  var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  var ok = document.execCommand('copy');
  sel.removeAllRanges();
  toast(ok ? '已复制文字' : '请手动选中复制');
}
window.addEventListener('resize', function(){
  document.querySelectorAll('div[id^="c_"]').forEach(function(d){ var i=echarts.getInstanceByDom(d); if(i) i.resize(); });
});
function bindAllButtons(){
  document.querySelectorAll('[data-copy]').forEach(function(b){
    b.addEventListener('click', function(){ copyChart(b, b.getAttribute('data-copy')); });
  });
  document.querySelectorAll('[data-copytxt]').forEach(function(b){
    b.addEventListener('click', function(){ copyText(b, b.getAttribute('data-copytxt')); });
  });
  document.querySelectorAll('[data-expcsv]').forEach(function(b){
    b.addEventListener('click', function(){ exportTableCSV(b); });
  });
  document.querySelectorAll('[data-copytbl]').forEach(function(b){
    b.addEventListener('click', function(){ copyTable(b); });
  });
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bindAllButtons);
} else {
  bindAllButtons();
}
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'CPET 结果报告已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')

# 同时输出去重后的 CSV
out_csv = os.path.join(os.path.dirname(OUT), '最大摄氧量_结果表.csv')
with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(hdr)
    w.writerows(rows_t)
print(f'结果表 CSV 已生成: {out_csv}')

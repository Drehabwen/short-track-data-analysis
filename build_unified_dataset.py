# -*- coding: utf-8 -*-
"""论文级统一数据集构建：实验表 × 前测 × 心率 × 血液"""
import os, sys, json, csv, glob, re
os.environ['MPLCONFIGDIR'] = r'D:\DEV\blood\_vizlibs\.mplconfig'
sys.path.insert(0, r'D:\DEV\blood\_vizlibs')
import numpy as np
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')
OUT = r'D:\DEV\blood\统一数据集'
os.makedirs(OUT, exist_ok=True)

# 异名归一（推断同一人，需人工确认）
NAME_ALIASES = {}
def norm(name):
    return NAME_ALIASES.get(name, name)
COACH_NAMES = ['教练A', '教练B', '教练C', '教练D', '教练E']
TYPE_OVERRIDES = {'2026-07-28_教练C陆上.xlsx': '陆上+冰上'}
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

def fnum(v):
    try:
        return float(str(v).replace(',', '.').strip())
    except Exception:
        return np.nan

def calc_trimp(dur_s, zones):
    if zones is None or any(np.isnan(z) for z in zones):
        return np.nan
    minutes = dur_s/60.0
    return sum(minutes*z/100.0*w for z, w in zip(zones, [1, 2, 3, 4, 5]))

# ---------- 1. 实验表 ----------
exp = json.load(open(r'D:\DEV\data\processed\acute_fatigue_experiment.json', encoding='utf-8'))['athletes']
print(f'实验表: {len(exp)} 人')
print('干预缺失人数:', sum(1 for a in exp if not a.get('intervention')))

# ---------- 2. 血液 ----------
blood_path = r'D:\DEV\blood\blood_reports_package_20260726-141357\Academic\outputs\clean_analysis_2026-07-21\blood_results_long_curated.csv'
blood_rows = list(csv.DictReader(open(blood_path, encoding='utf-8-sig')))
blood = {}   # pid -> tp -> analyte -> (value, qualifier)
for r in blood_rows:
    pid = r['participant_id'].strip()
    tp = r['timepoint'].strip()
    an = r['analyte'].strip()
    val = r['result_value'].strip()
    q = r['qualifier'].strip()
    blood.setdefault(pid, {}).setdefault(tp, {})[an] = (val, q)
print(f'血液: {len(blood_rows)} 条, {len(blood)} 人')

# ---------- 3. 前测 ----------
pt = json.load(open(r'D:\DEV\data\processed\pretest_data.json', encoding='utf-8'))['athletes']
pt_by_name = {norm(a['name']): a for a in pt}
print(f'前测: {len(pt)} 人')

# ---------- 4. 心率扫描 ----------
hr_per_session = {}   # name -> list of dicts
for fn in sorted(glob.glob(r'D:\DEV\blood\心率\*.xlsx')):
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
                zones = tuple(pct(x) for x in row[6:11])
                report[str(row[0])] = zones
            except Exception:
                pass
    parts = {}
    for chunk in meta.split('   '):
        if ': ' in chunk:
            k, v = chunk.split(': ', 1)
            parts[k] = v
    sname = parts.get('训练名称', '')
    sdate = parts.get('训练日期', '')[:10]
    stype = TYPE_OVERRIDES.get(os.path.basename(fn), '冰上' if '冰' in sname else ('陆地' if '陆' in sname else '其他'))
    coach = extract_coach(sname)
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
        dur = float(ts[-1]) if ts.size else 0.0
        zeros = int(np.sum(hs == 0))
        zones = report.get(sn)
        trimp = calc_trimp(dur, zones)
        hr_per_session.setdefault(norm(sn), []).append({
            'date': sdate, 'session': sname, 'type': stype, 'coach': coach,
            'avg': avg, 'max': mx, 'duration_min': dur/60.0,
            'zeros': zeros, 'n': int(len(hs)),
            'trimp': trimp,
            'hi_min': dur/60.0*((zones[3]+zones[4])/100.0) if zones is not None and not any(np.isnan(z) for z in zones) else np.nan,
        })
    wb.close()

# 个人最大心率 -> 相对强度
ath_max = {nm: max(x['max'] for x in v if not np.isnan(x['max'])) for nm, v in hr_per_session.items() if v}
hr_agg = {}
for nm, v in hr_per_session.items():
    rels = [x['avg']/ath_max[nm]*100.0 if not np.isnan(x['avg']) else np.nan for x in v]
    trimps = [x['trimp'] for x in v if not np.isnan(x['trimp'])]
    hmin = [x['hi_min'] for x in v if not np.isnan(x['hi_min'])]
    zrs = [x['zeros']*100.0/x['n'] for x in v]
    hr_agg[nm] = {
        'n_sessions': len(v),
        'minutes': sum(x['duration_min'] for x in v),
        'avg_hr': float(np.nanmean([x['avg'] for x in v])),
        'max_hr': float(np.nanmax([x['max'] for x in v])),
        'trimp_sum': float(np.nansum(trimps)) if trimps else np.nan,
        'rel_mean': float(np.nanmean(rels)) if rels else np.nan,
        'zero_rate_mean': float(np.mean(zrs)) if zrs else np.nan,
        'ice': sum(1 for x in v if x['type'] == '冰上'),
        'land': sum(1 for x in v if x['type'] == '陆地'),
    }
print(f'心率: 覆盖 {len(hr_agg)} 人')

# ---------- 5. 主表 ----------
ANALYTES = ['testosterone', 'cortisol', 'urea', 'ck', 'ldh']
TPS = ['BL', '24H', '72H']

def g(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return None

wide = []
for a in exp:
    nm = a['name']
    nnm = norm(nm)
    pt_a = pt_by_name.get(nnm) or {}
    hr = hr_agg.get(nnm) or {}
    row = {
        'subject_id': a['id'], 'name': nm, 'name_aliases': NAME_ALIASES.get(nm, ''),
        'class': a.get('class'), 'coach': a.get('coach'),
        'gender': a.get('gender'), 'age': a.get('age'),
        'height_cm': a.get('height_cm'), 'weight_kg': a.get('weight_kg'),
        'intervention': a.get('intervention'), 'load_pct': a.get('load_pct'),
    }
    for i in range(5):
        row[f'avg_power_p{i+1}'] = fnum(g(a.get('avg_power_w'), f'第{"一二三四五"[i]}次'))
        row[f'peak_power_p{i+1}'] = fnum(g(a.get('peak_power_w'), f'第{"一二三四五"[i]}次'))
    cmj = a.get('cmj_cm') or {}
    row['cmj_pre'] = fnum(g(cmj, '运动前')); row['cmj_24h'] = fnum(g(cmj, '24h')); row['cmj_72h'] = fnum(g(cmj, '72h'))
    vas = a.get('vas') or {}
    row['vas_rest'] = fnum(g(vas, '静息')); row['vas_post'] = fnum(g(vas, '运动后即刻'))
    row['vas_interv'] = fnum(g(vas, '干预后')); row['vas_24h'] = fnum(g(vas, '24h')); row['vas_72h'] = fnum(g(vas, '72h'))
    rpe = a.get('rpe') or {}
    row['rpe_rest'] = fnum(g(rpe, '静息')); row['rpe_post'] = fnum(g(rpe, '运动后即刻'))
    row['rpe_interv'] = fnum(g(rpe, '干预后')); row['rpe_24h'] = fnum(g(rpe, '24h')); row['rpe_72h'] = fnum(g(rpe, '72h'))
    lac = a.get('lactate_mmol_l') or {}
    row['lactate_rest'] = fnum(g(lac, '静息')); row['lactate_post'] = fnum(g(lac, '运动后即刻'))
    row['lactate_interv'] = fnum(g(lac, '干预后'))
    hrx = a.get('hr') or {}
    for k in ['hr_rest_avg', 'hr_rest_max', 'hr_post_avg', 'hr_post_max', 'hr_24h_avg', 'hr_24h_max', 'hr_72h_avg', 'hr_72h_max']:
        row[k] = fnum(g(hrx, k))
    hrv = a.get('hrv_pre') or {}
    row['hrv_sdnn'] = fnum(g(hrv, 'sdnn')); row['hrv_rmssd'] = fnum(g(hrv, 'rmssd'))
    row['hrv_lf_hf'] = fnum(g(hrv, 'lf_hf')); row['hrv_total_power'] = fnum(g(hrv, 'total_power'))
    # 前测
    fms = pt_a.get('fms') or {}
    row['pt_fms_total'] = fnum(g(fms, 'total'))
    ybt = pt_a.get('ybt') or {}
    l, r = ybt.get('left') or {}, ybt.get('right') or {}
    row['pt_ybt_ant_mean'] = np.nanmean([fnum(g(l, 'ant')), fnum(g(r, 'ant'))])
    row['pt_ybt_pm_mean'] = np.nanmean([fnum(g(l, 'post_med')), fnum(g(r, 'post_med'))])
    row['pt_ybt_pl_mean'] = np.nanmean([fnum(g(l, 'post_lat')), fnum(g(r, 'post_lat'))])
    row['pt_heel_raise_mean'] = np.nanmean([fnum(g(ybt, 'heel_raise_l')), fnum(g(ybt, 'heel_raise_r'))])
    row['pt_eyes_closed_mean'] = np.nanmean([fnum(g(ybt, 'eyes_closed_l')), fnum(g(ybt, 'eyes_closed_r'))])
    prof = pt_a.get('profile') or {}
    row['pt_500m_s'] = fnum(g(prof, 'time_500m_s')); row['pt_7lap_s'] = fnum(g(prof, 'time_7lap_s'))
    row['pt_training_years'] = fnum(g(prof, 'training_years')); row['pt_weekly_hours'] = fnum(g(prof, 'weekly_hours'))
    row['pt_injury_3m'] = g(prof, 'injury_3m')
    row['pt_cmj'] = fnum(g(pt_a.get('cmj') or {}, 'height_cm'))
    row['pt_lactate_pre'] = fnum(g(pt_a.get('lactate') or {}, 'pre'))
    rs = pt_a.get('rom_strength') or {}
    row['pt_ankle_dorsi_mean'] = np.nanmean([fnum(g(rs, 'ankle_dorsi_l')), fnum(g(rs, 'ankle_dorsi_r'))])
    row['pt_knee_flex_mean'] = np.nanmean([fnum(g(rs, 'knee_flex_l')), fnum(g(rs, 'knee_flex_r'))])
    row['pt_str_dorsi_mean'] = np.nanmean([fnum(g(rs, 'dorsi_str_l')), fnum(g(rs, 'dorsi_str_r'))])
    cop = pt_a.get('cop') or {}
    cl, cr = cop.get('left') or {}, cop.get('right') or {}
    row['pt_cop_area_mean'] = np.nanmean([fnum(g(cl, 'ellipse_area')), fnum(g(cr, 'ellipse_area'))])
    # 心率聚合
    row['hr_sessions'] = hr.get('n_sessions')
    row['hr_minutes'] = round(hr.get('minutes', 0), 1)
    row['hr_avg'] = round(hr['avg_hr'], 1) if 'avg_hr' in hr else np.nan
    row['hr_max'] = hr.get('max_hr')
    row['hr_trimp_sum'] = round(hr['trimp_sum'], 1) if 'trimp_sum' in hr else np.nan
    row['hr_rel_mean'] = round(hr['rel_mean'], 1) if 'rel_mean' in hr else np.nan
    row['hr_zero_rate_mean'] = round(hr['zero_rate_mean'], 1) if 'zero_rate_mean' in hr else np.nan
    row['hr_ice_sessions'] = hr.get('ice'); row['hr_land_sessions'] = hr.get('land')
    # 血液
    bp = blood.get(a['id'], {})
    for tp in TPS:
        for an in ANALYTES:
            v, q = bp.get(tp, {}).get(an, ('', ''))
            row[f'blood_{an}_{tp}'] = float(v) if v else ''
            row[f'blood_{an}_{tp}_flag'] = q
    wide.append(row)

cols = list(wide[0].keys())
# 数值 NaN 统一输出为空单元格
for r in wide:
    for k in r:
        if isinstance(r[k], float) and np.isnan(r[k]):
            r[k] = ''
with open(os.path.join(OUT, '统一数据集_受试者主表.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(wide)
print(f'主表已写: {len(wide)} 行 × {len(cols)} 列')

# ---------- 6. 完整性矩阵 ----------
def has(v):
    if v is None:
        return 0
    if isinstance(v, float):
        return 0 if np.isnan(v) else 1
    s = str(v).strip()
    return 0 if s in ('', 'nan') else 1

IND = [
    ('基础_性别', lambda r: has(r['gender'])), ('基础_年龄', lambda r: has(r['age'])),
    ('基础_身高', lambda r: has(r['height_cm'])), ('基础_体重', lambda r: has(r['weight_kg'])),
    ('干预方式', lambda r: has(r['intervention'])), ('造模负荷', lambda r: has(r['load_pct'])),
    ('造模_平均功率', lambda r: has(r['avg_power_p1'])), ('造模_峰值功率', lambda r: has(r['peak_power_p1'])),
    ('CMJ_前', lambda r: has(r['cmj_pre'])), ('CMJ_24h', lambda r: has(r['cmj_24h'])),
    ('CMJ_72h', lambda r: has(r['cmj_72h'])), ('VAS', lambda r: has(r['vas_post'])),
    ('RPE', lambda r: has(r['rpe_post'])), ('血乳酸_静息', lambda r: has(r['lactate_rest'])),
    ('血乳酸_即刻', lambda r: has(r['lactate_post'])), ('血乳酸_干预后', lambda r: has(r['lactate_interv'])),
    ('心率_静息', lambda r: has(r['hr_rest_avg'])), ('心率_即刻', lambda r: has(r['hr_post_avg'])),
    ('心率_24h', lambda r: has(r['hr_24h_avg'])), ('心率_72h', lambda r: has(r['hr_72h_avg'])),
    ('HRV_前', lambda r: has(r['hrv_sdnn'])),
    ('前测_FMS', lambda r: has(r['pt_fms_total'])), ('前测_YBT', lambda r: has(r['pt_ybt_ant_mean'])),
    ('前测_ROM肌力', lambda r: has(r['pt_ankle_dorsi_mean'])), ('前测_跳跃', lambda r: has(r['pt_cmj'])),
    ('前测_血乳酸', lambda r: has(r['pt_lactate_pre'])), ('前测_基线', lambda r: has(r['pt_500m_s'])),
    ('前测_肌张力', lambda r: 1 if (pt_by_name.get(norm(r['name'])) or {}).get('muscle_tone') else 0),
    ('前测_力台', lambda r: has(r['pt_cop_area_mean'])),
    ('心率_任一', lambda r: has(r['hr_sessions'])),
    ('血液_BL', lambda r: has(r['blood_ck_BL'])), ('血液_24H', lambda r: has(r['blood_ck_24H'])),
    ('血液_72H', lambda r: has(r['blood_ck_72H'])),
]

matrix = []
for r in wide:
    vals = [fn(r) for _, fn in IND]
    matrix.append([r['subject_id'], r['name']] + vals + [round(100.0*sum(vals)/len(vals), 1)])
with open(os.path.join(OUT, '数据完整性矩阵.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['subject_id', 'name'] + [n for n, _ in IND] + ['完整度%'])
    w.writerows(matrix)
print('完整性矩阵已写')

# 域级完成率
print('\n=== 域级完成率 ===')
for i, (nm, _) in enumerate(IND):
    rate = 100.0*sum(m[2+i] for m in matrix)/len(matrix)
    print(f'{nm}: {rate:.0f}%')

# ---------- 7. 明细表 ----------
def flatten(d, prefix='', sep='_'):
    out = {}
    for k, v in d.items():
        nk = prefix + sep + k if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, nk, sep))
        else:
            out[nk] = v
    return out

with open(os.path.join(OUT, '前测明细表.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    rows = []
    for a in pt:
        flat = flatten(a)
        rows.append(flat)
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

with open(os.path.join(OUT, '心率明细表.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['姓名', '教练', '日期', '场次', '类型', '时长min', '平均心率', '最大心率', 'TRIMP', '高强度min', '0值率%'])
    for nm, v in sorted(hr_per_session.items()):
        for x in v:
            w.writerow([nm, x['coach'], x['date'], x['session'], x['type'], round(x['duration_min'], 1),
                        round(x['avg'], 1) if not np.isnan(x['avg']) else '',
                        round(x['max'], 1) if not np.isnan(x['max']) else '',
                        round(x['trimp'], 1) if not np.isnan(x['trimp']) else '',
                        round(x['hi_min'], 1) if not np.isnan(x['hi_min']) else '',
                        round(x['zeros']*100.0/x['n'], 1)])

exp_by_id = {a['id']: a['name'] for a in exp}
with open(os.path.join(OUT, '血液明细表_链接后.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['participant_id', '实验表姓名', 'timepoint', 'analyte', 'result_value', 'qualifier', 'unit'])
    for r in blood_rows:
        pid = r['participant_id'].strip()
        w.writerow([pid, exp_by_id.get(pid, ''), r['timepoint'], r['analyte'],
                    r['result_value'], r['qualifier'], r['unit']])

# ---------- 8. 热力图 ----------
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
M = np.array([m[2:2+len(IND)] for m in matrix])
fig, ax = plt.subplots(figsize=(12, 0.32*len(M)+2))
ax.imshow(M, aspect='auto', cmap=matplotlib.colors.ListedColormap(['#ece8dd', '#a9c0a0']), vmin=0, vmax=1)
ax.set_yticks(range(len(M)))
ax.set_yticklabels([m[0] for m in matrix], fontsize=5.5)
ax.set_xticks(range(len(IND)))
ax.set_xticklabels([n for n, _ in IND], rotation=60, ha='right', fontsize=6)
ax.set_title('数据完整性热力图（绿=有数据，米色=缺失）', fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(OUT, '完整性热力图.png'), dpi=140, facecolor='white')
plt.close(fig)

# ---------- 9. 报告 ----------
rep = []
rep.append('# 论文级统一数据集 · 整合报告\n')
rep.append('生成时间：2026-08-03\n')
rep.append('## 一、链接概况\n')
rep.append(f'- 实验表（核心）：{len(exp)} 人，编号前缀 C/L/Y/Z（对应陈/李/杨/教练C组）')
rep.append(f'- 血液：{len(blood_rows)} 条化验结果，{len(blood)} 个 participant_id；与实验表编号匹配 {len(set(a["id"] for a in exp) & set(blood))} 人')
rep.append(f'- 前测：{len(pt)} 人，按姓名匹配实验表 {sum(1 for a in exp if norm(a["name"]) in pt_by_name)} 人')
rep.append(f'- 心率：{len(hr_agg)} 人（45 场），按姓名匹配实验表 {sum(1 for a in exp if norm(a["name"]) in hr_agg)} 人')
rep.append('- speedtrack 计时成绩：运动员与实验表无交集，判定为另一套数据，未并入')
rep.append('\n## 二、异名归一（需人工确认）\n')
rep.append('| 实验表姓名 | 前测/心率姓名 | 说明 |')
rep.append('|---|---|---|')
for k, v in NAME_ALIASES.items():
    rep.append(f'| {k} | {v} | 推断为同一人（字形相近），建议核对名单 |')
rep.append('\n## 三、未匹配名单\n')
rep.append('- 实验表有、前测无：' + '、'.join(sorted(set(a['name'] for a in exp) - set(pt_by_name))) )
rep.append('- 实验表有、心率无：' + '、'.join(sorted(set(a['name'] for a in exp) - set(hr_agg))))
rep.append('- 血液有、实验表无：' + '、'.join(sorted(set(blood) - set(a['id'] for a in exp))))
rep.append('\n## 四、域级完整率\n')
for i, (nm, _) in enumerate(IND):
    rep.append(f'- {nm}: {100.0*sum(m[2+i] for m in matrix)/len(matrix):.0f}%')
rep.append('\n## 五、已知缺口与注意事项\n')
rep.append('- 实验表干预方式缺失 ' + str(sum(1 for a in exp if not a.get('intervention'))) + ' 人（做组间分析前必须处理）')
rep.append('- 实验表 HRV 仅"运动前"有数据，24h/48h HRV 全缺失')
rep.append('- 前测血乳酸"造模后"各列基本未填')
rep.append('- 前测有两个 xlsx 版本（blood/前测数据.xlsx 与 data/前测数据 (1).xlsx），名单一致，本数据集以 data 版（8-2 更新）为准')
rep.append('- 心率采样率部分场次为 2 秒（陆地场），逐秒分析时需按实际步长换算分钟数')
rep.append('- 主表中"相对强度"以每人自身观测最大心率为基准，观测最大值可能低估真实 HRmax')
rep.append('\n## 六、文件清单\n')
for fn in sorted(os.listdir(OUT)):
    rep.append(f'- {fn}')
with open(os.path.join(OUT, '整合报告.md'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(rep))
print('\n全部输出完成 →', OUT)

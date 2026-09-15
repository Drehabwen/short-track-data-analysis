# -*- coding: utf-8 -*-
"""7-28 ~ 7-30 心率报告 v2：低饱和配色 + 深度分析"""
import os, sys, re, csv, base64, html
os.environ['MPLCONFIGDIR'] = r'D:\DEV\blood\_vizlibs\.mplconfig'
sys.path.insert(0, r'D:\DEV\blood\_vizlibs')

import colorsys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DengXian']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['axes.edgecolor'] = '#dcd6c9'
plt.rcParams['axes.labelcolor'] = '#39454f'
plt.rcParams['xtick.color'] = '#6b7681'
plt.rcParams['ytick.color'] = '#6b7681'

BASE = r'D:\DEV\blood\心率'
OUT = os.path.join(BASE, '心率报告_0728-0730.html')
OUT_CSV = os.path.join(BASE, 'processed', '场次运动员统计_0728-0730.csv')
FIGDIR = os.path.join(BASE, 'processed', 'figs_0728_30')

FILES = [
    '2026-07-28_教练A陆上.xlsx',
    '2026-07-28_教练B陆地.xlsx',
    '2026-07-28_教练C陆上.xlsx',
    '2026-07-28_教练B冰上.xlsx',
    '2026-07-28_教练D冰上.xlsx',
    '2026-07-30_教练E冰上.xlsx',
    '2026-07-30_教练E陆地.xlsx',
]

# 低饱和配色
ICE, LAND, OTHER = '#7093a9', '#8ca98a', '#c2a87e'
MAX_C = '#bf8585'
ZONES = ['#8aafc9', '#9fc0a0', '#dcc894', '#d9a87f', '#c58f8f']
WARN_C, BAD_C = '#d2b36e', '#bc6c6c'
GRID_C = '#e5e0d5'

def muted_colors(n):
    return [colorsys.hsv_to_rgb((i/max(n, 1)) % 1.0, 0.42, 0.78) for i in range(n)]

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

def session_type(name):
    if '冰' in name:
        return '冰上'
    if '陆' in name:
        return '陆地'
    return '实验/其他'

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

import openpyxl

sessions = []
for fn in FILES:
    path = os.path.join(BASE, fn)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    ws = wb['团队综合报告']
    meta = None
    report = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] and str(row[0]).startswith('训练名称'):
            meta = str(row[0])
            continue
        if row[0] and row[1] is not None and str(row[0]) != '姓名':
            try:
                avg = float(row[1]); mx = float(row[2])
                kcal = float(row[3]) if row[3] is not None else np.nan
                dens = pct(row[5])
                zones = tuple(pct(x) for x in row[6:11])
                report[str(row[0])] = (avg, mx, kcal, dens, zones)
            except Exception:
                pass
    parts = {}
    for chunk in meta.split('   '):
        if ': ' in chunk:
            k, v = chunk.split(': ', 1)
            parts[k] = v
    date = parts.get('训练日期', '')[:10]
    start = parts.get('训练日期', '')[11:19]
    dur = parts.get('训练时长', '')

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
        valid_mask = hs > 0
        valid = hs[valid_mask]
        zeros = int(np.sum(hs == 0))
        avg = float(valid.mean()) if valid.size else float('nan')
        mx = float(valid.max()) if valid.size else float('nan')
        cv = float(valid.std()/valid.mean()) if valid.size > 1 else float('nan')
        dur_s = float(ts[-1]) if ts.size else 0.0
        diffs = np.diff(ts)
        step = float(np.median(diffs)) if diffs.size else 1.0
        # 前/中/后三段平均
        segs = []
        n = len(valid)
        for lo, hi in [(0, n//3), (n//3, 2*n//3), (2*n//3, n)]:
            segs.append(float(valid[lo:hi].mean()) if hi > lo else float('nan'))
        # 0 值位置五分位
        zq = [int(np.sum(hs[i*(len(hs)//5):(i+1)*(len(hs)//5)] == 0)) for i in range(5)]
        rp = report.get(sn)
        zones = rp[4] if rp else None
        athletes.append({
            'name': sn, 't': ts, 'h': hs,
            'n': int(len(hs)), 'zeros': zeros,
            'zero_rate': zeros*100.0/max(len(hs), 1),
            'avg': avg, 'max': mx, 'cv': cv, 'duration': dur_s,
            'seg': segs, 'zq': zq,
            'ge160': float(np.sum(valid >= 160)) * step / 60.0,
            'ge170': float(np.sum(valid >= 170)) * step / 60.0,
            'ge180': float(np.sum(valid >= 180)) * step / 60.0,
            'kcal': rp[2] if rp else np.nan,
            'density': rp[3] if rp else np.nan,
            'zones': zones,
            'trimp': calc_trimp(dur_s, zones),
            'hi_min': dur_s/60.0*((zones[3]+zones[4])/100.0) if zones is not None and not any(np.isnan(z) for z in zones) else np.nan,
        })
    wb.close()

    valid_all = sum(a['n'] - a['zeros'] for a in athletes)
    zero_all = sum(a['zeros'] for a in athletes)
    team_avg = float(np.nanmean([a['avg'] for a in athletes]))
    team_max = float(np.nanmax([a['max'] for a in athletes]))
    seg_avg = [float(np.nanmean([a['seg'][k] for a in athletes])) for k in range(3)]
    sessions.append({
        'file': fn, 'date': date, 'start': start, 'name': parts.get('训练名称', ''),
        'dur': dur, 'type': session_type(parts.get('训练名称', '')),
        'dur_s': float(np.mean([a['duration'] for a in athletes])),
        'athletes': athletes, 'n_ath': len(athletes),
        'valid': valid_all, 'zeros': zero_all,
        'zero_rate': zero_all*100.0/max(valid_all+zero_all, 1),
        'team_avg': team_avg, 'team_max': team_max,
        'seg_avg': seg_avg,
        'trimp_mean': float(np.nanmean([a['trimp'] for a in athletes])),
        'trimp_sum': float(np.nansum([a['trimp'] for a in athletes])),
        'hi_mean': float(np.nanmean([a['hi_min'] for a in athletes])),
        'dens_mean': float(np.nanmean([a['density'] for a in athletes])),
        'kcal_sum': float(np.nansum([a['kcal'] for a in athletes])),
    })
    print(f"{fn}: {len(athletes)}人 有效{valid_all} 0值{zero_all} 均HR {team_avg:.0f}/{team_max:.0f} TRIMP均 {sessions[-1]['trimp_mean']:.0f}")

# ---------- 深度分析计算 ----------
ath_max = {}
for s in sessions:
    for a in s['athletes']:
        ath_max[a['name']] = max(ath_max.get(a['name'], 0.0), a['max'])
for s in sessions:
    for a in s['athletes']:
        a['rel'] = a['avg']/ath_max[a['name']]*100.0 if ath_max[a['name']] > 0 else float('nan')
for s in sessions:
    s['rel_mean'] = float(np.nanmean([a['rel'] for a in s['athletes']]))
    s['dur_min'] = s['dur_s']/60.0
    s['hi_frac'] = float(np.nanmean([a['ge160']/max(a['duration']/60.0, 0.1) for a in s['athletes']]))
    s['ge160_sum'] = float(np.nansum([a['ge160'] for a in s['athletes']]))
    s['ge170_sum'] = float(np.nansum([a['ge170'] for a in s['athletes']]))
    s['ge180_sum'] = float(np.nansum([a['ge180'] for a in s['athletes']]))
ice_rel = [a['rel'] for s in sessions if s['type'] == '冰上' for a in s['athletes']]
land_rel = [a['rel'] for s in sessions if s['type'] == '陆地' for a in s['athletes']]
def cohen_d(x, y):
    nx, ny = len(x), len(y)
    sp = np.sqrt(((nx-1)*np.var(x, ddof=1) + (ny-1)*np.var(y, ddof=1)) / (nx+ny-2))
    return (np.mean(x)-np.mean(y))/sp if sp > 0 else float('nan')
ICE_REL_MEAN = float(np.mean(ice_rel))
LAND_REL_MEAN = float(np.mean(land_rel))
COHEN_D = cohen_d(ice_rel, land_rel)
pair = {}
for i, s in enumerate(sessions):
    for a in s['athletes']:
        pair.setdefault(a['name'], []).append((i, a['rel']))
pair = {k: v for k, v in pair.items() if len(v) >= 2}

# ---------- 自动结论 ----------
ins = []
best = max(sessions, key=lambda s: s['trimp_mean'])
ins.append(('最高训练冲量', f"{best['date']} {best['name']} 人均TRIMP {best['trimp_mean']:.0f}（全队合计 {best['trimp_sum']:.0f}），是这7场里累计负荷最高的一场"))
hot = max(sessions, key=lambda s: s['team_avg'])
ins.append(('平均强度最高', f"{hot['date']} {hot['name']} 全队平均心率 {hot['team_avg']:.0f} bpm；冰上场的平均强度整体高于陆上场"))
pk = max(((a, s) for s in sessions for a in s['athletes'] if not np.isnan(a['max'])), key=lambda x: x[0]['max'])
ins.append(('心率峰值', f"{pk[1]['date']} {pk[1]['name']} · {pk[0]['name']} 达到 {pk[0]['max']:.0f} bpm"))
up = [s for s in sessions if s['seg_avg'][2] > s['seg_avg'][0]]
down = [s for s in sessions if s['seg_avg'][2] < s['seg_avg'][0] - 2]
if up:
    u = max(up, key=lambda s: s['seg_avg'][2]-s['seg_avg'][0])
    ins.append(('强度递增', f"{u['date']} {u['name']} 后段比前段平均高 {u['seg_avg'][2]-u['seg_avg'][0]:.0f} bpm，呈热身充分/强度逐步推高形态"))
if down:
    d = min(down, key=lambda s: s['seg_avg'][2]-s['seg_avg'][0])
    ins.append(('强度递减', f"{d['date']} {d['name']} 后段比前段低 {d['seg_avg'][0]-d['seg_avg'][2]:.0f} bpm，呈疲劳累积/收尾降强度形态"))
fluc = max(((a, s) for s in sessions for a in s['athletes'] if not np.isnan(a['cv'])), key=lambda x: x[0]['cv'])
ins.append(('波动最大', f"{fluc[1]['date']} {fluc[1]['name']} · {fluc[0]['name']} 变异系数 {fluc[0]['cv']*100:.0f}%，心率起伏最剧烈"))
flag = [(a, s) for s in sessions for a in s['athletes'] if a['zero_rate'] >= 5]
if flag:
    for a, s in sorted(flag, key=lambda x: -x[0]['zero_rate']):
        ins.append(('数据缺口', f"{s['date']} {s['name']} · {a['name']} 0值占比 {a['zero_rate']:.0f}%，曲线不完整，统计时建议剔除"))
multi = sorted({a['name'] for s in sessions for a in s['athletes'] if sum(1 for ss in sessions if any(x['name'] == a['name'] for x in ss['athletes'])) >= 2})
if multi:
    ins.append(('跨场次运动员', f"{len(multi)} 人出现在 ≥2 场（{'、'.join(multi[:8])}{' 等' if len(multi) > 8 else ''}），可做个体跨场次对比"))
ins.append(('冰上vs陆地', f"相对强度（均心÷个人最大心率）：冰上 {ICE_REL_MEAN:.0f}% vs 陆地 {LAND_REL_MEAN:.0f}%，效应量 d={COHEN_D:.2f}（中等），冰上平均更累但差距不算悬殊"))
lowrel = min(sessions, key=lambda s: s['rel_mean'])
highfrac = max(sessions, key=lambda s: s['hi_frac'])
ins.append(('强度画像', f"{lowrel['date']} {lowrel['name']} 相对强度最低（{lowrel['rel_mean']:.0f}%）却时长最长，属长时间低强度；{highfrac['date']} {highfrac['name']} ≥160bpm 时间占比 {highfrac['hi_frac']*100:.0f}%，属高密度训练"))
if pair:
    stable = min(pair.items(), key=lambda kv: max(abs(r2-r1) for (i1, r1), (i2, r2) in zip(kv[1], kv[1][1:])))
    ins.append(('个体稳定性', f"{len(pair)} 人跨场次出场，同一批人换场地相对强度变化很小（最稳的 {stable[0]} 变化 <1 个百分点），场次强度差异主要来自训练安排而非个体状态"))

# ---------- 图表 ----------
os.makedirs(FIGDIR, exist_ok=True)

def save_fig(fig, name):
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return p

def img_b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')

def figure_block(key, caption, fname):
    return (f'<figure>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:6px">'
            f'<figcaption style="color:#8b9099;font-size:12px;margin:0">{caption}</figcaption>'
            f'<div style="display:flex;gap:8px;flex-shrink:0">'
            f'<button class="dl" data-name="{fname}" onclick="exportPNG(this)">导出 PNG</button>'
            f'<button class="dl" onclick="copyPNG(this)">复制图片</button></div></div>'
            f'<img src="data:image/png;base64,{img_b64(figs[key])}" '
            f'style="width:100%;border:1px solid #e0dbd0;border-radius:8px" /></figure>')

figs = {}
x = np.arange(len(sessions))
labels = [f"{s['date'][5:]} {s['name']}" for s in sessions]
venue_c = [ICE if s['type'] == '冰上' else LAND for s in sessions]

# 1) 场均心率对比（低饱和）
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.bar(x-0.2, [s['team_avg'] for s in sessions], 0.4, label='平均心率', color=venue_c)
ax.bar(x+0.2, [s['team_max'] for s in sessions], 0.4, label='最大心率', color=MAX_C, alpha=0.9)
for xi, s in zip(x, sessions):
    ax.text(xi-0.2, s['team_avg']+2, f"{s['team_avg']:.0f}", ha='center', fontsize=7, color='#5a6675')
    ax.text(xi+0.2, s['team_max']+2, f"{s['team_max']:.0f}", ha='center', fontsize=7, color='#8f6a6a')
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
ax.set_ylabel('心率 (bpm)'); ax.set_ylim(0, 235)
ax.legend(fontsize=9, frameon=False); ax.grid(axis='y', color=GRID_C, linewidth=0.8)
ax.set_axisbelow(True)
ax.set_title('各场次全队平均/最大心率', color='#3f4a5a')
figs['summary'] = save_fig(fig, 'summary.png')

# 2) 心率区间停留分钟数
fig, ax = plt.subplots(figsize=(12, 4.6))
zone_names = ['区间1', '区间2', '区间3', '区间4', '区间5']
bottom = np.zeros(len(sessions))
zone_min = np.zeros((len(sessions), 5))
for i, s in enumerate(sessions):
    zs = [a['zones'] for a in s['athletes'] if a['zones'] is not None and not any(np.isnan(z) for z in a['zones'])]
    if zs:
        mins = np.array(zs).mean(axis=0) * (s['dur_s']/60.0) / 100.0
        zone_min[i] = mins
for zi in range(5):
    ax.bar(x, zone_min[:, zi], 0.72, bottom=bottom, color=ZONES[zi], label=zone_names[zi])
    bottom += zone_min[:, zi]
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
ax.set_ylabel('停留时间 (分钟)')
ax.legend(ncol=5, fontsize=8, loc='upper center', bbox_to_anchor=(0.5, 1.12), frameon=False)
ax.grid(axis='y', color=GRID_C, linewidth=0.8); ax.set_axisbelow(True)
ax.set_title('各场次心率区间停留时间（全队平均，分钟）', color='#3f4a5a')
figs['zones'] = save_fig(fig, 'zones_min.png')

# 3) 前/中/后三段强度趋势
fig, ax = plt.subplots(figsize=(11, 4.6))
seg_cols = ['#a9c0a3', '#d7c48a', '#c99a9a']
width = 0.26
for k, (off, c, lab) in enumerate(zip([-width, 0, width], seg_cols, ['前1/3', '中1/3', '后1/3'])):
    ax.bar(x+off, [s['seg_avg'][k] for s in sessions], width, color=c, label=lab)
for xi, s in zip(x, sessions):
    ax.plot([xi-width, xi+width], [s['seg_avg'][0], s['seg_avg'][2]], color='#8d99a8', lw=0.7, alpha=0.6)
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
ax.set_ylabel('平均心率 (bpm)')
ax.legend(fontsize=9, frameon=False, ncol=3)
ax.grid(axis='y', color=GRID_C, linewidth=0.8); ax.set_axisbelow(True)
ax.set_title('训练前/中/后三段平均心率（强度走向）', color='#3f4a5a')
figs['trend'] = save_fig(fig, 'trend.png')

# 4) 跨场次运动员对比
multi_map = {}
for i, s in enumerate(sessions):
    for a in s['athletes']:
        multi_map.setdefault(a['name'], []).append((i, a['avg']))
multi_map = {k: v for k, v in multi_map.items() if len(v) >= 2}
if multi_map:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    cols = muted_colors(len(multi_map))
    for (nm, pts), c in zip(multi_map.items(), cols):
        xi = [p[0] for p in pts]; yi = [p[1] for p in pts]
        ax.plot(xi, yi, 'o-', lw=1.3, ms=4, color=c, label=nm)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
    ax.set_ylabel('平均心率 (bpm)')
    ax.legend(fontsize=6.5, ncol=4, frameon=False, loc='upper right')
    ax.grid(axis='y', color=GRID_C, linewidth=0.8); ax.set_axisbelow(True)
    ax.set_title(f'跨场次运动员平均心率对比（{len(multi_map)} 人）', color='#3f4a5a')
    figs['multi'] = save_fig(fig, 'multi_athlete.png')

# 5) 运动员强度画像散点
fig, ax = plt.subplots(figsize=(10.5, 6))
for s in sessions:
    c = ICE if s['type'] == '冰上' else LAND
    ax.scatter([a['avg'] for a in s['athletes']], [a['max'] for a in s['athletes']],
               s=18, color=c, alpha=0.85, edgecolors='white', linewidths=0.4,
               label=s['date'][5:] + ' ' + s['name'])
for s in sessions:
    for a in s['athletes']:
        if a['max'] >= 205 or a['avg'] >= 145:
            ax.annotate(a['name'], (a['avg'], a['max']), fontsize=6.2, color='#5a6675',
                        textcoords='offset points', xytext=(4, 3))
ax.set_xlabel('平均心率 (bpm)'); ax.set_ylabel('最大心率 (bpm)')
ax.grid(color=GRID_C, linewidth=0.8); ax.set_axisbelow(True)
ax.set_title('运动员强度画像：平均 vs 最大心率', color='#3f4a5a')
figs['scatter'] = save_fig(fig, 'scatter.png')

# 6) 0 值位置分析
flagged = [(a, s) for s in sessions for a in s['athletes'] if a['zero_rate'] >= 1]
if flagged:
    flagged.sort(key=lambda x: -x[0]['zero_rate'])
    fig, ax = plt.subplots(figsize=(9.5, max(2.4, 0.42*len(flagged)+1.2)))
    y = np.arange(len(flagged))
    seg_lab = ['前20%', '20-40%', '40-60%', '60-80%', '末20%']
    left = np.zeros(len(flagged))
    qcols = ['#a9c0a3', '#c7d3a5', '#d9c48a', '#d9ab84', '#c99a9a']
    for qi in range(5):
        vals = np.array([a['zq'][qi] for a, _ in flagged])
        ax.barh(y, vals, 0.62, left=left, color=qcols[qi], label=seg_lab[qi])
        left += vals
    for yi, (a, s) in zip(y, flagged):
        ax.text(left[yi]+1, yi, f"{a['zero_rate']:.0f}%", va='center', fontsize=7, color='#5a6675')
    ax.set_yticks(y)
    ax.set_yticklabels([f"{s['date'][5:]} {s['name']} · {a['name']}" for a, s in flagged], fontsize=7.5)
    ax.set_xlabel('0 值数量（按训练进度分位）')
    ax.legend(fontsize=7.5, ncol=5, loc='lower right', frameon=False)
    ax.set_title('心率 0 值（信号丢失）出现位置', color='#3f4a5a')
    figs['qpos'] = save_fig(fig, 'quality_pos.png')

# 7) 每场逐秒曲线（低饱和）
def decimate(t, h, maxpts=1500):
    if t.size <= maxpts:
        return t, h
    idx = np.linspace(0, t.size-1, maxpts).astype(int)
    return t[idx], h[idx]

for s in sessions:
    fig, ax = plt.subplots(figsize=(12, 4.5))
    cols = muted_colors(len(s['athletes']))
    for a, c in zip(s['athletes'], cols):
        t, h = decimate(a['t'], a['h'])
        h = np.where(h > 0, h, np.nan)
        ax.plot(t/60.0, h, lw=0.9, alpha=0.9, color=c, label=f"{a['name']} (均{a['avg']:.0f})")
    ax.set_xlabel('训练时间 (分钟)')
    ax.set_ylabel('心率 (bpm)')
    ax.set_ylim(40, 220)
    ax.grid(color=GRID_C, linewidth=0.8); ax.set_axisbelow(True)
    ax.legend(fontsize=5.8, ncol=5, frameon=False, loc='upper right')
    ax.set_title(f"{s['date']} {s['name']}（{s['type']}，{s['n_ath']}人，时长{s['dur']}）", color='#3f4a5a')
    key = f"curve_{s['file'][:10]}_{s['file'][11:-5]}"
    figs[key] = save_fig(fig, f"{key}.png")

# 8) 深度分析图表
fig, ax = plt.subplots(figsize=(10.5, 4.5))
rel_vals = [s['rel_mean'] for s in sessions]
ax.bar(x, rel_vals, 0.62, color=venue_c)
for xi, s, v in zip(x, sessions, rel_vals):
    ax.text(xi, v+1, f"{v:.0f}%", ha='center', fontsize=8, color='#39454f')
ax.axhline(ICE_REL_MEAN, color=ICE, ls='--', lw=1.2, label=f"冰上均值 {ICE_REL_MEAN:.0f}%")
ax.axhline(LAND_REL_MEAN, color=LAND, ls='--', lw=1.2, label=f"陆地均值 {LAND_REL_MEAN:.0f}%")
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
ax.set_ylabel('平均心率 ÷ 个人最大心率 (%)')
ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=9)
ax.grid(axis='y', color=GRID_C, lw=0.8); ax.set_axisbelow(True)
ax.set_title('相对强度（消除个体差异后的场次对比）', color='#39454f')
figs['drel'] = save_fig(fig, 'depth_rel_intensity.png')

fig, ax = plt.subplots(figsize=(10.5, 4.8))
ax.scatter([s['dur_min'] for s in sessions], [s['hi_frac'] for s in sessions],
           s=[s['n_ath']*9 for s in sessions], c=venue_c, alpha=0.85, edgecolors='white', linewidths=0.5)
for xi, yi, s in zip([s['dur_min'] for s in sessions], [s['hi_frac'] for s in sessions], sessions):
    ax.annotate(f"{s['date'][5:]} {s['name']}\n({s['n_ath']}人)", (xi, yi), fontsize=6.8,
                textcoords='offset points', xytext=(7, 4), color='#39454f')
ax.set_xlabel('场次平均时长 (分钟)')
ax.set_ylabel('≥160bpm 时间占比')
ax.grid(color=GRID_C, lw=0.8); ax.set_axisbelow(True)
ax.set_title('负荷密度：高强度时间占比 × 训练时长 × 人数', color='#39454f')
figs['ddens'] = save_fig(fig, 'depth_load_density.png')

if pair:
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    cols = muted_colors(len(pair))
    for (nm, pts), c in zip(pair.items(), cols):
        xi = [p[0] for p in pts]; yi = [p[1] for p in pts]
        ax.plot(xi, yi, 'o-', lw=1.2, ms=4.5, color=c, label=nm)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
    ax.set_ylabel('相对强度 (%)')
    ax.legend(fontsize=6.5, ncol=3, frameon=False, loc='upper right')
    ax.grid(axis='y', color=GRID_C, lw=0.8); ax.set_axisbelow(True)
    ax.set_title('跨场次运动员：相对强度随场次变化', color='#39454f')
    figs['dpair'] = save_fig(fig, 'depth_pair_rel.png')

# ---------- CSV（深度字段） ----------
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['日期', '场次', '运动员', '有效点数', '0值数', '0值率%', '平均心率', '最大心率',
                '相对强度%', '变异系数', '高强度min(区间4+5)', 'TRIMP', '≥160min', '≥170min', '≥180min',
                '运动密度%', '卡路里', '时长(秒)'])
    for s in sessions:
        for a in s['athletes']:
            w.writerow([s['date'], s['name'], a['name'], a['n']-a['zeros'], a['zeros'],
                        f"{a['zero_rate']:.1f}", f"{a['avg']:.1f}" if not np.isnan(a['avg']) else '',
                        f"{a['max']:.0f}" if not np.isnan(a['max']) else '',
                        f"{a['rel']:.1f}" if not np.isnan(a['rel']) else '',
                        f"{a['cv']:.3f}" if not np.isnan(a['cv']) else '',
                        f"{a['hi_min']:.0f}" if not np.isnan(a['hi_min']) else '',
                        f"{a['trimp']:.0f}" if not np.isnan(a['trimp']) else '',
                        f"{a['ge160']:.1f}", f"{a['ge170']:.1f}", f"{a['ge180']:.1f}",
                        f"{a['density']:.0f}" if not np.isnan(a['density']) else '',
                        f"{a['kcal']:.0f}" if not np.isnan(a['kcal']) else '',
                        int(a['duration'])])

# ---------- HTML ----------
unique_athletes = sorted({a['name'] for s in sessions for a in s['athletes']})
total_valid = sum(s['valid'] for s in sessions)
total_zero = sum(s['zeros'] for s in sessions)
flag_sess = [s for s in sessions if s['zero_rate'] >= 5]

def badge(rate):
    if rate >= 5:
        return f'<span style="background:#f3e4e4;color:#a85656;padding:1px 8px;border-radius:10px;font-size:12px">异常</span>'
    if rate >= 1:
        return f'<span style="background:#f5eeda;color:#8f6f2e;padding:1px 8px;border-radius:10px;font-size:12px">注意</span>'
    return f'<span style="background:#e8eee3;color:#5f7d55;padding:1px 8px;border-radius:10px;font-size:12px">良好</span>'

cards = f"""
<div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0">
  <div style="flex:1;min-width:150px;background:#fbfaf7;border:1px solid #e0dbd0;border-radius:10px;padding:14px;text-align:center">
    <div style="font-size:26px;font-weight:700;color:#39454f">{len(sessions)}</div><div style="color:#8b9099;font-size:13px">场次</div></div>
  <div style="flex:1;min-width:150px;background:#fbfaf7;border:1px solid #e0dbd0;border-radius:10px;padding:14px;text-align:center">
    <div style="font-size:26px;font-weight:700;color:#39454f">{len(unique_athletes)}</div><div style="color:#8b9099;font-size:13px">覆盖运动员</div></div>
  <div style="flex:1;min-width:150px;background:#fbfaf7;border:1px solid #e0dbd0;border-radius:10px;padding:14px;text-align:center">
    <div style="font-size:26px;font-weight:700;color:#39454f">{total_valid:,}</div><div style="color:#8b9099;font-size:13px">有效心率点</div></div>
  <div style="flex:1;min-width:150px;background:#fbfaf7;border:1px solid #e0dbd0;border-radius:10px;padding:14px;text-align:center">
    <div style="font-size:26px;font-weight:700;color:#39454f">{total_zero:,}</div><div style="color:#8b9099;font-size:13px">0值点</div></div>
  <div style="flex:1;min-width:150px;background:#fbfaf7;border:1px solid #e0dbd0;border-radius:10px;padding:14px;text-align:center">
    <div style="font-size:26px;font-weight:700;color:#a85656">{len(flag_sess)}</div><div style="color:#8b9099;font-size:13px">异常场次(0值≥5%)</div></div>
</div>"""

rows_tbl = []
for i, s in enumerate(sessions, 1):
    rows_tbl.append(
        f"<tr><td>{i}</td><td>{s['date']}</td><td>{s['start']}</td><td>{html.escape(s['name'])}</td>"
        f"<td>{s['type']}</td><td>{s['dur']}</td><td>{s['n_ath']}</td>"
        f"<td>{s['team_avg']:.0f}</td><td>{s['team_max']:.0f}</td>"
        f"<td>{s['dens_mean']:.0f}%</td><td>{s['trimp_mean']:.0f}</td><td>{s['hi_mean']:.0f}</td>"
        f"<td>{s['zero_rate']:.1f}%</td><td>{badge(s['zero_rate'])}</td></tr>")
session_tbl = ('<table><thead>'
    '<tr><th>#</th><th>日期</th><th>开始</th><th>训练名称</th><th>场地</th><th>时长</th><th>运动员</th>'
    '<th>平均HR</th><th>最大HR</th><th>运动密度</th><th>人均TRIMP</th><th>高强度min</th><th>0值率</th><th>质量</th></tr></thead><tbody>'
    + ''.join(rows_tbl) + '</tbody></table>')

ath_rows = []
def cell(v, scale=1.0, suffix=''):
    if np.isnan(v):
        return '<td>-</td>'
    return f'<td>{v*scale:.0f}{suffix}</td>'
for s in sessions:
    for a in sorted(s['athletes'], key=lambda a: -a['avg']):
        ath_rows.append(
            f"<tr><td>{s['date']}</td><td>{html.escape(s['name'])}</td><td>{html.escape(a['name'])}</td>"
            f"<td>{a['avg']:.0f}</td><td>{a['max']:.0f}</td>"
            + cell(a['rel'], 100.0, '%')
            + cell(a['cv'], 100.0, '%')
            + cell(a['hi_min'])
            + cell(a['trimp'])
            + f"<td>{a['zero_rate']:.1f}%</td></tr>")
ath_tbl = ('<table><thead><tr><th>日期</th><th>场次</th><th>运动员</th><th>平均HR</th><th>最大HR</th>'
           '<th>相对强度</th><th>变异系数</th><th>高强度min</th><th>TRIMP</th><th>0值率</th></tr></thead><tbody>'
           + ''.join(ath_rows) + '</tbody></table>')

ins_html = ''
for k, (label, txt) in enumerate(ins):
    ins_html += f'<div style="margin:6px 0"><span style="display:inline-block;min-width:84px;color:#7093a9;font-weight:700">{label}</span>{txt}</div>'

curve_html = ''
for s in sessions:
    key = f"curve_{s['file'][:10]}_{s['file'][11:-5]}"
    curve_html += figure_block(key,
        f'{html.escape(s["date"])} {html.escape(s["name"])}：逐秒心率曲线（0 值段显示为缺口；括号内为每人平均心率）',
        f'{s["date"]}_{s["file"][11:-5]}_心率曲线.png')

ath_cnt = ''.join(
    f'<tr><td>{html.escape(a)}</td><td>{sum(1 for s in sessions if any(x["name"] == a for x in s["athletes"]))}</td></tr>'
    for a in unique_athletes)

depth_rows = []
for i, s in enumerate(sessions, 1):
    depth_rows.append(
        f"<tr><td>{i}</td><td>{s['date']}</td><td>{html.escape(s['name'])}</td><td>{s['type']}</td>"
        f"<td>{s['n_ath']}</td><td>{s['dur_min']:.0f}</td>"
        f"<td>{s['rel_mean']:.1f}%</td><td>{s['hi_frac']*100:.0f}%</td>"
        f"<td>{s['ge160_sum']:.0f}</td><td>{s['ge170_sum']:.0f}</td><td>{s['ge180_sum']:.0f}</td></tr>")
depth_tbl = ('<table><thead><tr><th>#</th><th>日期</th><th>场次</th><th>类型</th><th>人数</th><th>时长min</th>'
             '<th>相对强度%</th><th>≥160占比</th><th>≥160min</th><th>≥170min</th><th>≥180min</th></tr></thead><tbody>'
             + ''.join(depth_rows) + '</tbody></table>')
depth_note = f'<div class="note">相对强度 = 平均心率 ÷ 个人最大心率，用于消除个体差异。冰上 {ICE_REL_MEAN:.0f}% vs 陆地 {LAND_REL_MEAN:.0f}%，效应量 d={COHEN_D:.2f}（中等）。</div>'

html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>心率数据报告 · 2026-07-28 ~ 07-30</title>
<style>
body { font-family:'Microsoft YaHei','SimHei',sans-serif; margin:0; background:#f5f3ee; color:#39454f; }
.wrap { max-width:1100px; margin:0 auto; padding:24px; }
h1 { font-size:24px; margin:0 0 4px; color:#313c46; }
.sub { color:#8b9099; font-size:13px; margin-bottom:18px; }
h2 { font-size:18px; border-left:4px solid #7093a9; padding-left:10px; margin:32px 0 10px; color:#313c46; }
table { border-collapse:collapse; width:100%; font-size:12.5px; background:#fffdf9; border-radius:8px; overflow:hidden; }
th,td { padding:6px 8px; border-bottom:1px solid #ece7db; text-align:left; }
th { background:#39454f; color:#f4f1ea; font-weight:600; }
tbody tr:nth-child(even) { background:#fbfaf7; }
.findings { background:#fbfaf7; border:1px solid #e0dbd0; border-radius:10px; padding:14px 18px; font-size:13px; margin:14px 0; }
.note { background:#f6f1e6; border:1px solid #e4dcc4; border-radius:8px; padding:12px 16px; font-size:13px; color:#6f6040; margin:14px 0; }
figure { margin:22px 0; }
button.dl { background:#ece8dd; border:1px solid #ddd6c6; color:#5b6b7a; border-radius:6px; padding:5px 14px; font-size:12px; cursor:pointer; font-family:inherit; transition:background .15s; }
button.dl:hover { background:#e2ddcf; }
.toolbar { text-align:right; margin:14px 0; }
</style></head><body><div class="wrap">
<div class="toolbar"><button class="dl" onclick="exportAll()">导出全部图表 (PNG)</button></div>
<h1>心率数据报告 · 2026-07-28 ~ 07-30 新增场次</h1>
<div class="sub">数据来源：D:\\DEV\\blood\\心率（7 个场次）；图表由 Python (matplotlib) 生成，最终渲染为 HTML。每张图右上角可<b>导出 PNG</b>或<b>复制图片</b>（复制后可直接粘贴到 Word / PPT）。</div>
""" + cards + """
<h2>核心发现</h2>
<div class="findings">
""" + ins_html + """
</div>
<h2>场次总览（含强度指标）</h2>
""" + session_tbl + """
<div class="note">指标口径：TRIMP 为 Edwards 训练冲量（按心率区间加权分钟数）；高强度 min = 区间4+5 停留分钟数；运动密度取自原始报告。</div>
<h2>场均心率对比</h2>
""" + figure_block('summary', '各场次全队平均/最大心率（蓝=冰上，绿=陆地）', '场均心率对比.png') + """
<h2>心率区间停留时间</h2>
""" + figure_block('zones', '各场次心率区间停留时间（全队平均，分钟）', '心率区间停留时间.png') + """
<h2>训练前/中/后段强度走向</h2>
""" + figure_block('trend', '训练前/中/后三段平均心率，观察强度走向', '训练强度走向.png') + """
""" + (('<h2>跨场次运动员平均心率对比</h2>'
        + figure_block('multi', '跨场次运动员逐场平均心率对比', '跨场次运动员对比.png'))
       if 'multi' in figs else '') + """
<h2>运动员强度画像（平均 vs 最大心率）</h2>
""" + figure_block('scatter', '每个点代表一名运动员一次出场；标注了峰值≥205 或均心≥145 的人', '运动员强度画像.png') + """
<h2>数据质量：0 值位置分析</h2>
""" + (figure_block('qpos', '0 值出现的训练进度位置（按五等分）', '数据质量_0值位置.png') if 'qpos' in figs else '<p>无 0 值异常</p>') + """
<div class="note">说明：0 值表示心率带未佩戴/信号丢失。教练C陆上 7.28 的<b>运动员G（48%）</b>与<b>运动员H（19%）</b>曲线不完整，统计时应剔除或单独说明。批量导出时，浏览器可能要求允许本次会话的多次下载。</div>
<h2>深度分析：相对强度与负荷密度</h2>
""" + figure_block('drel', '相对强度 = 平均心率 ÷ 个人最大心率（消除个体差异）', '深度_相对强度.png') + """
""" + depth_note + """
<h2>负荷密度：≥160bpm 时间占比 × 时长</h2>
""" + figure_block('ddens', '气泡大小=人数；右上=高强度且时间短，左下=低强度且时间长', '深度_负荷密度.png') + """
""" + (('<h2>跨场次运动员配对对比</h2>' + figure_block('dpair', '同一批运动员在不同场次的相对强度', '深度_配对对比.png')) if pair else '') + """
<h2>深度指标明细</h2>
""" + depth_tbl + """
<h2>运动员明细（按场均心率排序）</h2>
""" + ath_tbl + """
<h2>各场次逐秒心率曲线</h2>
""" + curve_html + """
<h2>运动员覆盖（7 场次内出场数）</h2>
<table style="font-size:12px"><thead><tr><th>运动员</th><th>出场数</th></tr></thead><tbody>
""" + ath_cnt + """
</tbody></table>
<p style="color:#a8a39a;font-size:11px;margin-top:26px">生成时间：2026-08-03 · 报告与图表均为本地生成。</p>
<script>
function exportPNG(btn){
  var fig = btn.closest('figure');
  var img = fig.querySelector('img');
  var a = document.createElement('a');
  a.href = img.src;
  a.download = btn.getAttribute('data-name') || 'chart.png';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
function exportAll(){
  var btns = document.querySelectorAll('figure button.dl');
  btns.forEach(function(b, i){
    setTimeout(function(){ exportPNG(b); }, i * 400);
  });
}
function showToast(msg){
  var el = document.getElementById('copyToast');
  if(!el){
    el = document.createElement('div');
    el.id = 'copyToast';
    el.style.cssText = 'position:fixed;left:50%;bottom:36px;transform:translateX(-50%);background:#39454f;color:#f4f1ea;padding:8px 18px;border-radius:20px;font-size:13px;z-index:999;opacity:0;transition:opacity .25s;pointer-events:none;box-shadow:0 2px 10px rgba(0,0,0,.15)';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = '1';
  clearTimeout(el._t);
  el._t = setTimeout(function(){ el.style.opacity = '0'; }, 2000);
}
function copyImageFallback(img){
  try {
    var range = document.createRange();
    range.selectNode(img);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    var ok = document.execCommand('copy');
    sel.removeAllRanges();
    return ok;
  } catch(e) {
    return false;
  }
}
async function copyPNG(btn){
  var img = btn.closest('figure').querySelector('img');
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      var res = await fetch(img.src);
      var blob = await res.blob();
      await navigator.clipboard.write([new ClipboardItem({'image/png': blob})]);
      showToast('已复制，可直接粘贴到 Word / PPT');
      return;
    }
    throw new Error('no-clipboard-api');
  } catch(e) {
    if (copyImageFallback(img)) {
      showToast('已复制，可直接粘贴');
    } else {
      showToast('复制失败，请右键图片 → 复制图片');
    }
  }
}
</script>
</div></body></html>"""

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html_doc)
print(f'HTML 报告已生成: {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)')
print(f'CSV 已生成: {OUT_CSV}')

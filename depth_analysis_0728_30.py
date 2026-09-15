# -*- coding: utf-8 -*-
"""7-28~30 深度分析演示：相对强度 / 负荷密度 / 阈值时间 / 配对对比"""
import os, sys, re
os.environ['MPLCONFIGDIR'] = r'D:\DEV\blood\_vizlibs\.mplconfig'
sys.path.insert(0, r'D:\DEV\blood\_vizlibs')

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
FIGDIR = os.path.join(BASE, 'processed', 'figs_0728_30')
ICE, LAND = '#7093a9', '#8ca98a'
GRID_C = '#e5e0d5'

FILES = [
    '2026-07-28_教练A陆上.xlsx', '2026-07-28_教练B陆地.xlsx', '2026-07-28_教练C陆上.xlsx',
    '2026-07-28_教练B冰上.xlsx', '2026-07-28_教练D冰上.xlsx',
    '2026-07-30_教练E冰上.xlsx', '2026-07-30_教练E陆地.xlsx',
]

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
    return '冰上' if '冰' in name else '陆地'

import openpyxl

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
                report[str(row[0])] = (float(row[1]), float(row[2]))
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
        avg = float(valid.mean()) if valid.size else float('nan')
        mx = float(valid.max()) if valid.size else float('nan')
        dur = float(ts[-1]) if ts.size else 0.0
        # 采样间隔（秒）
        diffs = np.diff(ts)
        step = float(np.median(diffs)) if diffs.size else 1.0
        athletes.append({
            'name': sn, 'avg': avg, 'max': mx, 'duration': dur,
            'n': int(len(hs)), 'zeros': int(np.sum(hs == 0)),
            'ge160': float(np.sum(valid >= 160)) * step / 60.0,
            'ge170': float(np.sum(valid >= 170)) * step / 60.0,
            'ge180': float(np.sum(valid >= 180)) * step / 60.0,
            'zones': None,
        })
    wb.close()
    sessions.append({
        'file': fn, 'date': parts.get('训练日期', '')[:10], 'start': parts.get('训练日期', '')[11:19],
        'name': parts.get('训练名称', ''), 'dur': parts.get('训练时长', ''),
        'type': session_type(parts.get('训练名称', '')),
        'athletes': athletes,
        'dur_s': float(np.mean([a['duration'] for a in athletes])),
    })

# 每名运动员的"个人最大心率" = 这些场次里观测到的最大值（作为 HRmax 代理）
ath_max = {}
for s in sessions:
    for a in s['athletes']:
        ath_max[a['name']] = max(ath_max.get(a['name'], 0.0), a['max'])

for s in sessions:
    for a in s['athletes']:
        a['rel'] = a['avg'] / ath_max[a['name']] * 100.0 if ath_max[a['name']] > 0 else np.nan

print('=== 场次深度指标 ===')
print(f"{'场次':<18}{'类型':<5}{'人数':<5}{'时长min':<8}{'相对强度%':<9}{'TRIMP/min':<10}{'≥160min':<9}{'≥170min':<9}{'≥180min':<8}")
for s in sessions:
    rels = [a['rel'] for a in s['athletes']]
    dmin = s['dur_s'] / 60.0
    print(f"{s['date']+' '+s['name']:<18}{s['type']:<5}{len(s['athletes']):<5}{dmin:<8.0f}"
          f"{np.nanmean(rels):<9.1f}{np.nansum([a['ge160']/max(a['duration']/60,0.1) for a in s['athletes']])/len(s['athletes']):<10.2f}"
          f"{np.nansum([a['ge160'] for a in s['athletes']]):<9.1f}"
          f"{np.nansum([a['ge170'] for a in s['athletes']]):<9.1f}"
          f"{np.nansum([a['ge180'] for a in s['athletes']]):<8.1f}")

# 冰上 vs 陆地（相对强度，运动员-场次为单元）
ice_rel = [a['rel'] for s in sessions if s['type'] == '冰上' for a in s['athletes']]
land_rel = [a['rel'] for s in sessions if s['type'] == '陆地' for a in s['athletes']]
def cohen_d(x, y):
    nx, ny = len(x), len(y)
    sp = np.sqrt(((nx-1)*np.var(x, ddof=1) + (ny-1)*np.var(y, ddof=1)) / (nx+ny-2))
    return (np.mean(x) - np.mean(y)) / sp if sp > 0 else float('nan')
print(f'\n冰上相对强度: {np.mean(ice_rel):.1f}% ± {np.std(ice_rel, ddof=1):.1f} (n={len(ice_rel)})')
print(f'陆地相对强度: {np.mean(land_rel):.1f}% ± {np.std(land_rel, ddof=1):.1f} (n={len(land_rel)})')
print(f'Cohen d(冰上-陆地): {cohen_d(ice_rel, land_rel):.2f}（>0.8 为大效应）')

# 同运动员跨场次配对
from collections import defaultdict
pair = defaultdict(list)
for i, s in enumerate(sessions):
    for a in s['athletes']:
        pair[a['name']].append((i, a['rel']))
pair = {k: v for k, v in pair.items() if len(v) >= 2}
print(f'\n跨场次运动员: {len(pair)} 人')
for k, v in sorted(pair.items()):
    print(f'  {k}: ' + ' → '.join(f"{sessions[i]['date'][5:]} {sessions[i]['name']}({r:.0f}%)" for i, r in v))

# ---------- 图 A：相对强度 ----------
fig, ax = plt.subplots(figsize=(10.5, 4.5))
x = np.arange(len(sessions))
labels = [f"{s['date'][5:]} {s['name']}" for s in sessions]
vals = [np.nanmean([a['rel'] for a in s['athletes']]) for s in sessions]
cols = [ICE if s['type'] == '冰上' else LAND for s in sessions]
ax.bar(x, vals, 0.62, color=cols)
for xi, s, v in zip(x, sessions, vals):
    ax.text(xi, v+1, f"{v:.0f}%", ha='center', fontsize=8, color='#39454f')
ax.axhline(np.mean(ice_rel), color=ICE, ls='--', lw=1.2, label=f"冰上均值 {np.mean(ice_rel):.0f}%")
ax.axhline(np.mean(land_rel), color=LAND, ls='--', lw=1.2, label=f"陆地均值 {np.mean(land_rel):.0f}%")
ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
ax.set_ylabel('平均心率占个人最大心率 (%)')
ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=9)
ax.grid(axis='y', color=GRID_C, lw=0.8); ax.set_axisbelow(True)
ax.set_title('相对强度：平均心率 ÷ 个人最大心率（消除个体差异）', color='#39454f')
p1 = os.path.join(FIGDIR, 'depth_rel_intensity.png')
fig.savefig(p1, dpi=140, bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------- 图 B：负荷密度（TRIMP/min 代理） vs 时长 ----------
fig, ax = plt.subplots(figsize=(10.5, 4.8))
dur_min = [s['dur_s']/60 for s in sessions]
dens = [np.nansum([a['ge160']/max(a['duration']/60, 0.1) for a in s['athletes']])/len(s['athletes']) for s in sessions]
sc = ax.scatter(dur_min, dens, s=[len(s['athletes'])*9 for s in sessions],
                c=cols, alpha=0.85, edgecolors='white', linewidths=0.5)
for xi, yi, s, d in zip(dur_min, dens, sessions, [len(s['athletes']) for s in sessions]):
    ax.annotate(f"{s['date'][5:]} {s['name']}\n({d}人)", (xi, yi), fontsize=6.8,
                textcoords='offset points', xytext=(7, 4), color='#39454f')
ax.set_xlabel('场次平均时长 (分钟)')
ax.set_ylabel('≥160bpm 时间占比 (分钟/分钟)')
ax.grid(color=GRID_C, lw=0.8); ax.set_axisbelow(True)
ax.set_title('强度密度 × 时长 × 人数（气泡越大人数越多）', color='#39454f')
p2 = os.path.join(FIGDIR, 'depth_load_density.png')
fig.savefig(p2, dpi=140, bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------- 图 C：跨场次运动员相对强度连线 ----------
if pair:
    import colorsys
    def mcol(n):
        return [colorsys.hsv_to_rgb((i/max(n,1)) % 1.0, 0.42, 0.78) for i in range(n)]
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    for (nm, pts), c in zip(pair.items(), mcol(len(pair))):
        xi = [p[0] for p in pts]; yi = [p[1] for p in pts]
        ax.plot(xi, yi, 'o-', lw=1.2, ms=4.5, color=c, label=nm)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=25, ha='right', fontsize=7.5)
    ax.set_ylabel('相对强度 (%)')
    ax.legend(fontsize=6.5, ncol=3, frameon=False, loc='upper right')
    ax.grid(axis='y', color=GRID_C, lw=0.8); ax.set_axisbelow(True)
    ax.set_title('跨场次运动员：相对强度随场次变化', color='#39454f')
    p3 = os.path.join(FIGDIR, 'depth_pair_rel.png')
    fig.savefig(p3, dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)

print('\n图表已生成:')
for p in [p1, p2] + ([p3] if pair else []):
    print(' ', p)

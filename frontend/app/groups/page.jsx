'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Guide from '@/components/Guide';
import Hint from '@/components/Hint';

const GROUPS = ['常规恢复', '拔罐+推拿', '艾灸+推拿'];
const TP_LABELS = { BL: '训练前', '24H': '24小时后', '72H': '72小时后' };
const ANALYTE_ORDER = ['睾酮', '皮质醇', '尿素', '肌酸激酶', '乳酸脱氢酶 LDH'];

const GUIDE_ROWS = [
  { name: 'Kruskal-Wallis 检验', calc: '多组（3组）非参数检验，比较三组在同一个时间点的中位数是否相同', read: 'p<0.05 说明三组存在显著差异；需结合组间两两比较定位差异来源', color: '#c0392b' },
  { name: 'Friedman 检验', calc: '重复测量非参数检验，比较同一组运动员在 BL/24H/72H 三个时间点的变化', read: 'p<0.05 说明指标随时间显著变化（训练反应存在）' },
  { name: 'Wilcoxon 配对检验', calc: '两两时间点配对比较，p 值经 Holm 校正控制多重比较', read: '定位具体哪个时间点发生显著变化（如 24H 达峰、72H 回落）' },
  { name: 'Spearman 相关 ρ', calc: '两指标排名的相关性（非参数），-1~+1', read: '|ρ|>0.7 强相关（红）、0.4-0.7 中等（橙）、<0.4 弱（绿）', color: '#27ae60' },
  { name: '肌酸激酶 CK', calc: '肌肉损伤标志酶，运动后升高', read: '24H 升高属正常训练反应；72H 仍高提示恢复不足', color: '#c0392b' },
  { name: '睾酮/皮质醇', calc: '合成/分解代谢激素比', read: 'T/C 比值下降提示过度训练风险' },
];

export default function GroupsPage() {
  const [longitudinal, setLongitudinal] = useState(null);
  const [groupComp, setGroupComp] = useState(null);
  const [correlation, setCorrelation] = useState(null);
  const [descriptive, setDescriptive] = useState(null);
  const [performanceCorrelation, setPerformanceCorrelation] = useState(null);
  const [selectedPerformancePair, setSelectedPerformancePair] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.statsLongitudinal(),
      api.statsGroupComparison(),
      api.statsCorrelation(),
      api.statsByTimepoint(),
      api.statsPerformanceCorrelation(),
    ])
      .then(([lg, gc, corr, desc, performanceCorr]) => {
        setLongitudinal(lg);
        setGroupComp(gc);
        setCorrelation(corr);
        setDescriptive(desc);
        setPerformanceCorrelation(performanceCorr);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">统计计算中...</div>;
  if (error) return <div className="error-banner">计算失败：{error}</div>;

  // ── 图1：纵向趋势折线。不同指标单位不一致，统一换算为 BL=100 的相对指数。──
  const trendLines = [];
  if (descriptive) {
    for (const [label, v] of Object.entries(descriptive)) {
      const baseline = v.rows[0]?.median;
      trendLines.push({
        name: label,
        type: 'line',
        data: v.rows.map((r) => ({
          value:
            baseline != null && baseline !== 0 && r.median != null
              ? +((r.median / baseline) * 100).toFixed(1)
              : null,
          raw: r.median,
          unit: v.unit,
        })),
        endLabel: {
          show: true,
          formatter: ({ seriesName }) => seriesName,
          color: 'inherit',
          fontSize: 10,
          distance: 7,
        },
        labelLayout: { moveOverlap: 'shiftY' },
      });
    }
  }
  const trendOption = {
    title: {
      text: '训练后的相对变化轨迹',
      subtext: '各指标以训练前中位数为 100；悬停查看原始值',
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const heading = `<strong>${params[0]?.axisValueLabel || ''}</strong>`;
        const rows = params.map((p) => {
          const raw = p.data?.raw;
          const rawText = raw == null ? '缺失' : `${Number(raw).toFixed(2)} ${p.data?.unit || ''}`;
          return `${p.marker}${p.seriesName}　<b>${p.value ?? '—'}</b> <span style="opacity:.72">(${rawText})</span>`;
        });
        return [heading, ...rows].join('<br/>');
      },
    },
    legend: { show: false },
    grid: { left: 52, right: 92, top: 64, bottom: 36 },
    xAxis: { type: 'category', data: ['BL', '24H', '72H'].map((tp) => TP_LABELS[tp]) },
    yAxis: {
      type: 'value',
      name: '相对指数',
      axisLabel: { formatter: '{value}' },
      splitNumber: 4,
    },
    series: trendLines,
  };

  // ── 图2：组间显著性热力图（指标 × 时间点，颜色=p 值）──
  const kwCells = [];
  const kwY = [];
  if (groupComp) {
    Object.entries(groupComp).forEach(([label, v]) => {
      ['BL', '24H', '72H'].forEach((tp, ti) => {
        const k = v.kruskal?.[tp];
        if (k && k.p != null) {
          kwCells.push([ti, kwY.length, k.p]);
        }
      });
      kwY.push(label);
    });
  }
  const kwOption = {
    title: { text: '哪些时间点出现组间差异？', subtext: 'Kruskal-Wallis 检验；颜色按显著性阈值分段' },
    tooltip: { formatter: (p) => `<strong>${kwY[p.value[1]]}</strong><br/>${TP_LABELS[['BL','24H','72H'][p.value[0]]]}　p=${p.value[2].toFixed(4)}` },
    grid: { left: 112, right: 24, top: 66, bottom: 48 },
    xAxis: { type: 'category', data: ['BL', '24H', '72H'].map((tp) => TP_LABELS[tp]), splitArea: { show: true } },
    yAxis: { type: 'category', data: kwY, splitArea: { show: true } },
    visualMap: {
      type: 'piecewise',
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      dimension: 2,
      itemWidth: 12,
      itemHeight: 8,
      pieces: [
        { lte: 0.01, label: 'p ≤ 0.01', color: '#B84A62' },
        { gt: 0.01, lte: 0.05, label: '0.01 < p ≤ 0.05', color: '#E07A32' },
        { gt: 0.05, label: 'p > 0.05', color: '#DCE6EC' },
      ],
    },
    series: [{
      type: 'heatmap', data: kwCells,
      itemStyle: { borderColor: '#F8FBFC', borderWidth: 4, borderRadius: 6 },
      label: {
        show: true,
        formatter: (p) => `${p.value[2] < 0.001 ? '***' : p.value[2] < 0.01 ? '**' : p.value[2] < 0.05 ? '*' : 'ns'}\np=${p.value[2].toFixed(3)}`,
        fontSize: 10,
        lineHeight: 16,
        color: '#102A43',
      },
    }],
  };

  // ── 图3：相关性热力图 ──
  const corrCells = [];
  const corrIdx = {};
  ANALYTE_ORDER.forEach((a, i) => (corrIdx[a] = i));
  (correlation?.matrix || []).forEach((c) => {
    const ri = corrIdx[c.row];
    const ci = corrIdx[c.column];
    if (ri != null && ci != null && c.rho != null) {
      corrCells.push({
        value: [ci, ri, +c.rho.toFixed(2), c.p, c.n],
        itemStyle: { opacity: c.row === c.column || c.p <= 0.05 ? 1 : 0.45 },
      });
    }
  });
  const corrOption = {
    title: { text: '指标之间如何共同变化？', subtext: 'Spearman ρ；低透明度表示 p > 0.05' },
    tooltip: { formatter: (p) => `<strong>${ANALYTE_ORDER[p.value[1]]} × ${ANALYTE_ORDER[p.value[0]]}</strong><br/>ρ=${p.value[2]}　p=${p.value[3]?.toFixed(4) ?? '—'}　n=${p.value[4] ?? '—'}` },
    grid: { left: 118, right: 32, top: 66, bottom: 58 },
    xAxis: { type: 'category', data: ANALYTE_ORDER, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'category', data: ANALYTE_ORDER },
    visualMap: {
      min: -1, max: 1, calculable: false, orient: 'horizontal', left: 'center', bottom: 4,
      dimension: 2,
      text: ['正相关', '负相关'],
      inRange: { color: ['#2B6CB0', '#F2F6F8', '#D06B2C'] },
    },
    series: [{
      type: 'heatmap',
      data: corrCells,
      itemStyle: { borderColor: '#F8FBFC', borderWidth: 3, borderRadius: 5 },
      label: {
        show: true,
        formatter: (p) => `${p.value[2].toFixed(2)}${p.value[0] !== p.value[1] && p.value[3] <= 0.05 ? '*' : ''}`,
        fontSize: 10,
        color: '#102A43',
      },
    }],
  };

  const longitudinalRows = Object.entries(longitudinal || {}).map(([label, v]) => ({
    label,
    unit: v.unit,
    friedman: v.friedman,
    pairwise: v.pairwise,
  }));

  const sig = (p) => {
    if (p == null) return '—';
    if (p < 0.001) return <strong style={{ color: '#c0392b' }}>***</strong>;
    if (p < 0.01) return <strong style={{ color: '#c0392b' }}>**</strong>;
    if (p < 0.05) return <span style={{ color: '#e67e22', fontWeight: 600 }}>*</span>;
    return 'ns';
  };

  // ═══ 结论先行：提取组间显著差异 ═══
  const groupFindings = [];
  Object.entries(groupComp || {}).forEach(([label, v]) => {
    ['BL', '24H', '72H'].forEach((tp) => {
      const k = v.kruskal?.[tp];
      if (k && k.p != null && k.p < 0.05) {
        groupFindings.push({ label, tp, p: k.p, n: k.n_per_group });
      }
    });
  });

  const performancePairs = performanceCorrelation?.pairs || [];
  const performanceEvents = performanceCorrelation?.events || [];
  const performanceKey = (pair) => `${pair.event}::${pair.metric.key}`;
  const selectedPair = performancePairs.find((pair) => performanceKey(pair) === selectedPerformancePair)
    || performancePairs[0]
    || null;
  const eventPairs = performancePairs.filter((pair) => pair.event === (selectedPair?.event || performanceEvents[0]));
  const strongestPair = performancePairs.slice().sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho))[0] || null;
  const scatterOption = (() => {
    if (!selectedPair?.points?.length) return null;
    const points = selectedPair.points.map((point) => [point.fitness, point.performance, point.name, point.athlete_id]);
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const meanX = xs.reduce((sum, value) => sum + value, 0) / xs.length;
    const meanY = ys.reduce((sum, value) => sum + value, 0) / ys.length;
    const denominator = xs.reduce((sum, value) => sum + (value - meanX) ** 2, 0);
    const slope = denominator ? xs.reduce((sum, value, index) => sum + (value - meanX) * (ys[index] - meanY), 0) / denominator : 0;
    const intercept = meanY - slope * meanX;
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    return {
      title: {
        text: `${selectedPair.event} × ${selectedPair.metric.label}`,
        subtext: `Spearman ρ=${selectedPair.rho.toFixed(2)} · p=${selectedPair.p < 0.001 ? '<0.001' : selectedPair.p.toFixed(3)} · n=${selectedPair.n}`,
      },
      tooltip: {
        formatter: (params) => {
          const value = params.value || [];
          if (params.seriesType === 'line') return '趋势线';
          return `<strong>${value[2] || value[3] || '运动员'}</strong><br/>${selectedPair.metric.label}：${Number(value[0]).toFixed(2)} ${selectedPair.metric.unit}<br/>${selectedPair.event}：${Number(value[1]).toFixed(2)} s`;
        },
      },
      legend: { show: false },
      grid: { left: 64, right: 24, top: 68, bottom: 48 },
      xAxis: { type: 'value', name: `${selectedPair.metric.label}（${selectedPair.metric.unit}）`, nameLocation: 'middle', nameGap: 30 },
      yAxis: { type: 'value', inverse: true, name: `${selectedPair.event}（s，越低越快）`, nameLocation: 'middle', nameGap: 46 },
      series: [
        {
          type: 'scatter',
          data: points,
          symbolSize: 11,
          itemStyle: { color: '#1677ff', opacity: 0.82 },
          emphasis: { itemStyle: { color: '#0b1533', opacity: 1, borderColor: '#fff', borderWidth: 2 } },
        },
        {
          type: 'line',
          data: [[minX, intercept + slope * minX], [maxX, intercept + slope * maxX]],
          symbol: 'none',
          lineStyle: { color: '#e07a32', type: 'dashed', width: 2 },
          tooltip: { show: false },
        },
      ],
    };
  })();

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">组别对比与统计分析</div>
          <div className="page-desc">三种恢复方案效果对比 · 结论优先</div>
        </div>
        <div className="note">
          检验：Friedman（三时间点）/ Kruskal-Wallis（组间）/ Wilcoxon 配对（Holm 校正）
        </div>
      </div>

      {/* ══ 恢复效果结论（教练导向） ══ */}
      <div
        className="card research-finding"
        style={{
          marginBottom: 16,
          borderColor: groupFindings.length ? '#e67e22' : '#b9dfc9',
          borderWidth: 1.5,
        }}
      >
        <div className="card-title research-finding__title">恢复效果结论</div>
        {groupFindings.length === 0 ? (
          <div>
            <p style={{ margin: '0 0 8px' }}>
              三种恢复方案（<strong>常规恢复 / 拔罐+推拿 / 艾灸+推拿</strong>）在各指标、各时间点上
              <strong>均未发现显著差异</strong>（p ≥ 0.05）。
            </p>
            <p className="note" style={{ margin: 0 }}>
              说明目前三种方案的恢复效果整体没有明显高下，可继续按现有方案执行；如需进一步区分，建议结合个体差异和运动员反馈观察。
            </p>
          </div>
        ) : (
          <div>
            <p style={{ margin: '0 0 8px' }}>
              三种恢复方案在以下指标/时间点存在<strong>显著差异</strong>（p &lt; 0.05），建议重点关注：
            </p>
            <ul style={{ margin: '0 0 8px', paddingLeft: 20 }}>
              {groupFindings.map((f, i) => (
                <li key={i}>
                  <strong>{f.label}</strong> · {TP_LABELS[f.tp]}（p={f.p.toFixed(3)}）
                  <span className="note"> n={f.n.join('/')}</span>
                </li>
              ))}
            </ul>
            <p className="note" style={{ margin: 0 }}>
              建议结合下方详细数据，查看差异具体来自哪两组，并关注对应运动员的恢复表现。
            </p>
          </div>
        )}
      </div>

      {/* ══ 成绩 × 体能关联：教练决策优先 ══ */}
      <div className="card research-finding" style={{ marginBottom: 16 }}>
        <div className="card-title research-finding__title">成绩 × 体能关联分析</div>
        <p style={{ margin: '0 0 12px' }}>
          用同一名运动员的最好比赛成绩与体能测试配对，帮助判断<strong>哪些体能指标更值得在训练后关注</strong>。
        </p>
        {performancePairs.length === 0 ? (
          <div className="note">目前没有至少 3 名运动员同时具备比赛成绩和体能数据，暂时无法计算相关性。</div>
        ) : (
          <>
            <div className="grid cols-3" style={{ marginBottom: 14 }}>
              <div className="stat-card">
                <div className="stat-number">{new Set(performancePairs.flatMap((pair) => pair.points.map((point) => point.athlete_id))).size}</div>
                <div className="stat-label">可配对运动员</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{performancePairs.length}</div>
                <div className="stat-label">可分析关系</div>
              </div>
              <div className="stat-card">
                <div className="stat-number" style={{ color: strongestPair && Math.abs(strongestPair.rho) >= 0.7 ? '#c0392b' : 'var(--accent)' }}>
                  {strongestPair ? strongestPair.rho.toFixed(2) : '—'}
                </div>
                <div className="stat-label">最强相关 ρ</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
              <label className="note" htmlFor="performance-event">成绩项目</label>
              <select
                id="performance-event"
                className="input"
                value={selectedPair?.event || ''}
                onChange={(event) => {
                  const next = performancePairs.find((pair) => pair.event === event.target.value);
                  setSelectedPerformancePair(next ? performanceKey(next) : '');
                }}
              >
                {performanceEvents.map((event) => <option key={event} value={event}>{event}</option>)}
              </select>
              <label className="note" htmlFor="performance-metric">体能指标</label>
              <select
                id="performance-metric"
                className="input"
                value={selectedPair ? performanceKey(selectedPair) : ''}
                onChange={(event) => setSelectedPerformancePair(event.target.value)}
              >
                {eventPairs.map((pair) => (
                  <option key={performanceKey(pair)} value={performanceKey(pair)}>{pair.metric.label}（n={pair.n}）</option>
                ))}
              </select>
            </div>
            {scatterOption && <Chart option={scatterOption} height="340px" ariaLabel="成绩与体能指标相关性散点图" />}
            <div className="note" style={{ marginTop: 8 }}>
              {selectedPair.metric.label} 越高与 {selectedPair.event} 用时越短的关系，ρ 会表现为负值；这里只说明统计关联，不代表因果。{performanceCorrelation.method}
            </div>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="data-table">
                <thead><tr><th>成绩项目</th><th>体能指标</th><th>配对 n</th><th>ρ</th><th>p 值</th><th>提示</th></tr></thead>
                <tbody>
                  {performancePairs.slice().sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho)).map((pair) => (
                    <tr key={performanceKey(pair)}>
                      <td>{pair.event}</td>
                      <td>{pair.metric.label}</td>
                      <td>{pair.n}</td>
                      <td style={{ color: Math.abs(pair.rho) >= 0.7 ? '#c0392b' : Math.abs(pair.rho) >= 0.4 ? '#e07a32' : '#27ae60', fontWeight: 700 }}>{pair.rho.toFixed(2)}</td>
                      <td>{pair.p < 0.001 ? '<0.001' : pair.p.toFixed(3)}</td>
                      <td>{Math.abs(pair.rho) >= 0.7 ? '重点关注' : Math.abs(pair.rho) >= 0.4 ? '可观察' : '关系较弱'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <details className="card research-details" style={{ marginBottom: 16 }}>
        <summary className="research-details__summary">
          <span>查看详细统计分析</span>
          <small>趋势 · 显著性 · 相关矩阵</small>
        </summary>

      {/* 图化：趋势 + 显著性热力 + 相关性热力 */}
      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <Chart option={trendOption} height="360px" />
          <Hint text="训练前统一为100，便于比较不同单位指标的变化幅度；悬停可查看原始中位数和单位" />
        </div>
        <div className="card">
          <Chart option={kwOption} height="360px" />
          <Hint text="粉色/橙色表示达到统计显著性阈值；灰色 ns 表示当前数据不足以支持组间差异" />
        </div>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <Chart option={corrOption} height="380px" />
        <Hint text="橙色为正相关、蓝色为负相关；低透明度表示 p>0.05，星号表示 p≤0.05；相关不等于因果" />
      </div>
      <Guide rows={GUIDE_ROWS} title="统计检验与指标解读指南" />

      {/* 组间差异表 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">
          组间差异检验（Kruskal-Wallis，按时间点分层）
          <span className="hint">常规恢复 vs 拔罐+推拿 vs 艾灸+推拿</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>指标</th>
                {['BL', '24H', '72H'].map((tp) => (
                  <th key={tp}>{TP_LABELS[tp]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(groupComp || {}).map(([label, v]) => (
                <tr key={label}>
                  <td><strong>{label}</strong></td>
                  {['BL', '24H', '72H'].map((tp) => {
                    const k = v.kruskal?.[tp];
                    if (!k || k.p == null) {
                      return <td key={tp}>—</td>;
                    }
                    return (
                      <td key={tp}>
                        H={k.statistic.toFixed(2)} · p={k.p.toFixed(4)} {sig(k.p)}
                        <div className="note" style={{ marginTop: 2 }}>
                          n={k.n_per_group.join('/')}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 纵向趋势检验表 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">
          纵向趋势检验（三时间点）
          <span className="hint">* p&lt;0.05 ** p&lt;0.01 *** p&lt;0.001</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>完整三时间点 n</th>
                <th>Friedman χ²</th>
                <th>Friedman p</th>
                <th>BL vs 24H</th>
                <th>BL vs 72H</th>
                <th>24H vs 72H</th>
              </tr>
            </thead>
            <tbody>
              {longitudinalRows.map((row) => (
                <tr key={row.label}>
                  <td><strong>{row.label}</strong></td>
                  <td>{row.friedman.complete_n}</td>
                  <td>{row.friedman.statistic != null ? row.friedman.statistic.toFixed(2) : '—'}</td>
                  <td>{row.friedman.p != null ? row.friedman.p.toFixed(5) : '—'}</td>
                  {row.pairwise.map((pw, i) => (
                    <td key={i}>
                      {pw.p_holm != null ? (
                        <>
                          p={pw.p_holm.toFixed(4)} {sig(pw.p_holm)}
                          <div className="note" style={{ marginTop: 2 }}>
                            Δ中位数 {pw.median_change != null ? (pw.median_change > 0 ? '+' : '') + pw.median_change.toFixed(2) : '—'}
                          </div>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          Friedman 检验对象为三时间点数据完整的运动员（重复测量）；配对检验为 Wilcoxon 符号秩检验，p 值经 Holm 校正。
        </div>
      </div>

      {/* 相关性矩阵 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">指标相关性（Spearman ρ）</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>↳</th>
                {ANALYTE_ORDER.map((a) => (
                  <th key={a}>{a}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ANALYTE_ORDER.map((row) => (
                <tr key={row}>
                  <td><strong>{row}</strong></td>
                  {ANALYTE_ORDER.map((col) => {
                    const cell = correlation?.matrix?.find(
                      (c) => c.row === row && c.column === col
                    );
                    const rho = cell?.rho;
                    const color =
                      rho == null
                        ? 'var(--text-light)'
                        : Math.abs(rho) > 0.7
                          ? '#c0392b'
                          : Math.abs(rho) > 0.4
                            ? '#e67e22'
                            : '#27ae60';
                    return (
                      <td key={col} style={{ color, fontWeight: Math.abs(rho || 0) > 0.7 ? 700 : 400 }}>
                        {rho != null ? rho.toFixed(2) : '—'}
                        {cell?.p != null && rho != null && rho !== 1 && (
                          <span className="note" style={{ marginTop: 2 }}>
                            {' '}(p={cell.p.toFixed(3)})
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          绿色=|ρ|≤0.4 弱相关 · 橙色=0.4&lt;|ρ|≤0.7 中等相关 · 红色=|ρ|&gt;0.7 强相关。睾酮为低于检测限按缺失处理后的非 censored 值。
        </div>
      </div>
      </details>
    </div>
  );
}

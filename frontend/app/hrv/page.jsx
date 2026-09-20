'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

export default function HrvPage() {
  const [overview, setOverview] = useState(null);
  const [rrText, setRrText] = useState('');
  const [rrResult, setRrResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .hrvOverview()
      .then(setOverview)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const levels = overview.levels || {};
  const levelColors = { 恢复良好: '#34c759', 恢复正常: '#a3b9d6', 恢复偏低: '#e58f4f', 疲劳风险: '#d05555' };
  const levelOrder = ['恢复良好', '恢复正常', '恢复偏低', '疲劳风险'];

  const levelOption = {
    title: { text: '全队 HRV 恢复状态分布', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
    tooltip: {},
    xAxis: { type: 'category', data: levelOrder.filter((k) => levels[k]) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        barWidth: 40,
        data: levelOrder.filter((k) => levels[k]).map((k) => ({ value: levels[k], itemStyle: { color: levelColors[k] } })),
        label: { show: true, position: 'top' },
      },
    ],
  };

  const rmssdOption = {
    title: { text: '个体 RMSSD（恢复指标，≥40 正常）', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
    tooltip: {},
    grid: { left: 56, right: 20, top: 36, bottom: 40 },
    xAxis: { type: 'category', data: (overview.athletes || []).map((a) => a.name || a.subject_id), axisLabel: { rotate: 40, fontSize: 10 } },
    yAxis: { type: 'value', name: 'ms' },
    series: [
      {
        type: 'bar',
        data: (overview.athletes || []).map((a) => a.rmssd),
        itemStyle: { color: (p) => (p.value >= 40 ? '#34c759' : p.value >= 25 ? '#e58f4f' : '#d05555') },
        label: { show: true, position: 'top', fontSize: 9 },
      },
    ],
  };

  const runAnalyze = () => {
    const nums = rrText
      .split(/[,;\s]+/)
      .map((s) => parseFloat(s))
      .filter((n) => Number.isFinite(n) && n > 200 && n < 2500);
    if (nums.length < 30) {
      setRrResult({ error: '至少需要 30 个有效 RR 间期（毫秒）', n_rri: nums.length });
      return;
    }
    api
      .hrvAnalyze(nums)
      .then(setRrResult)
      .catch((e) => setRrResult({ error: e.message }));
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-title">HRV 恢复监测</div>
        <div className="page-desc">心率变异性 · 自主神经恢复状态 · RR 间期分析（hrvanalysis 引擎）</div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <div className="stat-card">
          <div className="stat-number">{overview.n_measured}</div>
          <div className="stat-label">HRV 测量人数</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{ color: 'var(--green)' }}>{levels['恢复良好'] || 0}</div>
          <div className="stat-label">恢复良好</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{ color: '#e58f4f' }}>{(levels['恢复偏低'] || 0) + (levels['疲劳风险'] || 0)}</div>
          <div className="stat-label">需关注（偏低+风险）</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{overview.stats?.rmssd?.median ?? '—'}</div>
          <div className="stat-label">RMSSD 中位数 (ms)</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginBottom: 14 }}>
        <div className="card">
          <Chart option={levelOption} height="300px" />
          <Hint text="绿色越多 = 全队恢复越好；红色（疲劳风险）队员要降负荷、多睡眠" />
        </div>
        <div className="card">
          <div className="card-title">恢复状态解读</div>
          <div className="note" style={{ lineHeight: 1.8 }}>
            <b>RMSSD</b>（相邻 RR 间期差均方根）是反映副交感神经活性的核心恢复指标：<br />
            · <b style={{ color: '#34c759' }}>≥60ms</b> 恢复良好（副交感主导）<br />
            · <b style={{ color: '#a3b9d6' }}>40–60ms</b> 恢复正常<br />
            · <b style={{ color: '#e58f4f' }}>25–40ms</b> 恢复偏低，注意疲劳累积<br />
            · <b style={{ color: '#d05555' }}>&lt;25ms</b> 疲劳风险，建议降低训练负荷<br /><br />
            <b>LF/HF</b> 反映交感/副交感平衡；<b>SDNN</b> 反映整体变异性（压力/恢复总水平）。
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">个体 RMSSD 分布</div>
        <Chart option={rmssdOption} height="360px" />
        <Hint text="绿柱 = 恢复好，橙柱 = 偏低要留意，红柱 = 疲劳风险；同一个人连续变矮说明累着了" />
      </div>

      <div className="card">
        <div className="card-title">
          RR 间期分析工具
          <span className="hint">粘贴 RR 间期序列（毫秒，逗号/空格分隔）→ 计算全套 HRV 指标</span>
        </div>
        <textarea
          className="textarea"
          rows={4}
          placeholder="例如：1000, 1015, 998, 1032, ...（至少 30 个）"
          value={rrText}
          onChange={(e) => setRrText(e.target.value)}
          style={{ width: '100%', marginBottom: 10, padding: 8, fontFamily: 'monospace', fontSize: 12 }}
        />
        <button className="btn" onClick={runAnalyze}>计算 HRV 指标</button>
        {rrResult && (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            {rrResult.error ? (
              <div className="note">{rrResult.error}</div>
            ) : (
              <table className="data-table">
                <thead><tr><th>指标</th><th>值</th><th>说明</th></tr></thead>
                <tbody>
                  <tr><td>平均 RR (meanNN)</td><td>{rrResult.mean_nni} ms</td><td>静息心率水平</td></tr>
                  <tr><td>SDNN</td><td>{rrResult.sdnn} ms</td><td>整体变异性</td></tr>
                  <tr><td>RMSSD</td><td>{rrResult.rmssd} ms</td><td>副交感活性（恢复核心指标）</td></tr>
                  <tr><td>pNN50</td><td>{rrResult.pnni_50}%</td><td>相邻 RR 差 &gt;50ms 占比</td></tr>
                  <tr><td>LF</td><td>{rrResult.lf} ms²</td><td>低频功率（0.04–0.15Hz）</td></tr>
                  <tr><td>HF</td><td>{rrResult.hf} ms²</td><td>高频功率（0.15–0.4Hz，副交感）</td></tr>
                  <tr><td>LF/HF</td><td>{rrResult.lf_hf_ratio}</td><td>交感/副交感平衡</td></tr>
                  <tr><td>总功率</td><td>{rrResult.total_power} ms²</td><td>HRV 总水平</td></tr>
                  <tr><td>引擎</td><td>{rrResult.engine}</td><td>hrvanalysis 计算</td></tr>
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

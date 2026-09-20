'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';

export default function TeamReportPage() {
  const [overview, setOverview] = useState(null);
  const [exceedance, setExceedance] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.dashboardOverview(), api.analyteExceedance(), api.dashboardAlerts()])
      .then(([ov, exc, al]) => {
        setOverview(ov);
        setExceedance(exc);
        setAlerts(al);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!overview) return <div className="loading">加载中...</div>;

  const timepointOption = {
    title: { text: '时间点样本分布', textStyle: { fontSize: 13 } },
    tooltip: {},
    grid: { left: 50, right: 20, top: 40, bottom: 28 },
    xAxis: { type: 'category', data: ['训练前 BL', '24小时后', '72小时后'] },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: [
          overview.timepoint_counts.BL,
          overview.timepoint_counts['24H'],
          overview.timepoint_counts['72H'],
        ],
        itemStyle: { color: '#1a5c54', borderRadius: [4, 4, 0, 0] },
        barWidth: 52,
        label: { show: true, position: 'top', fontWeight: 600 },
      },
    ],
  };

  const groupOption = {
    title: { text: '组别分布', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['38%', '68%'],
        data: Object.entries(overview.group_counts).map(([name, value]) => ({ name, value })),
        label: { fontSize: 12 },
        color: ['#1a5c54', '#2a7a6f', '#e67e22', '#bdc3c7'],
      },
    ],
  };

  const exceedOption = {
    title: { text: '指标超标率（按参考区间）', textStyle: { fontSize: 13 } },
    tooltip: {},
    legend: { data: ['偏高', '偏低'], top: 26 },
    grid: { left: 60, right: 20, top: 60, bottom: 30 },
    xAxis: { type: 'category', data: exceedance.map((x) => x.name), axisLabel: { fontSize: 11, rotate: 15 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, max: 100 },
    series: [
      {
        name: '偏高',
        type: 'bar',
        data: exceedance.map((x) => ((x.high_rate ?? 0) * 100).toFixed(1)),
        itemStyle: { color: '#c0392b' },
      },
      {
        name: '偏低',
        type: 'bar',
        data: exceedance.map((x) => ((x.low_rate ?? 0) * 100).toFixed(1)),
        itemStyle: { color: '#2980b9' },
      },
    ],
  };

  return (
    <div className="report-page">
      <div className="report-toolbar">
        <div className="page-title">团队血液数据报告</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => window.print()}>
            导出 PDF / 打印
          </button>
          <button className="btn btn-ghost" onClick={() => history.back()}>
            返回
          </button>
        </div>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card stat-card">
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #ccfbf1, #a7f3d0)' }}>🏃</div>
          <div>
            <div className="stat-number">{overview.participant_count}</div>
            <div className="stat-label">在册运动员</div>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #fee2e2, #fecaca)' }}>🩸</div>
          <div>
            <div className="stat-number">{overview.sample_count}</div>
            <div className="stat-label">血样记录</div>
          </div>
        </div>
        <div className="card stat-card">
          <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #fef3c7, #fde68a)' }}>⚠️</div>
          <div>
            <div className="stat-number" style={{ color: alerts.length ? 'var(--accent)' : 'var(--text)' }}>
              {alerts.length}
            </div>
            <div className="stat-label">异常预警</div>
          </div>
        </div>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card"><Chart option={timepointOption} height="260px" /></div>
        <div className="card"><Chart option={groupOption} height="260px" /></div>
        <div className="card"><Chart option={exceedOption} height="260px" /></div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">指标超标率明细</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>指标</th>
              <th>偏高比例</th>
              <th>偏低比例</th>
            </tr>
          </thead>
          <tbody>
            {exceedance.map((x) => (
              <tr key={x.name}>
                <td>{x.name}</td>
                <td>{x.high_rate != null ? `${(x.high_rate * 100).toFixed(1)}%` : '—'}</td>
                <td>{x.low_rate != null ? `${(x.low_rate * 100).toFixed(1)}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-title">
          异常预警列表
          <span className="hint">CK 偏高 / T/C 比值偏低 / 待复核</span>
        </div>
        {alerts.length === 0 ? (
          <div className="empty">暂无异常预警 🎉</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>运动员</th>
                <th>时间点</th>
                <th>组别</th>
                <th>预警内容</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.sample_id}>
                  <td><strong>{a.participant_id}</strong></td>
                  <td>{a.timepoint_label}</td>
                  <td>{a.group || '未分组'}</td>
                  <td>{a.alerts.join('、')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="note" style={{ textAlign: 'center', marginTop: 8 }}>
        本报告由 SpeedTrack Pro 生成 · 数据仅存于本机
      </div>
    </div>
  );
}

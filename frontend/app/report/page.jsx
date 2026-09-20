'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';

const TP_LABELS = ['训练前', '24小时后', '72小时后'];
const TP_COLORS = { BL: '#2ca02c', '24H': '#ff7f0e', '72H': '#d62728' };

export default function ReportPage() {
  const [id, setId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('id') || '';
    setId(q);
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError('');
    api
      .tracking(id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (!id) return <div className="loading">缺少运动员编号</div>;
  if (loading && !data) return <div className="loading">加载中...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <div className="loading">加载中...</div>;

  const recovery = data.recovery;
  const recClass = {
    恢复良好: 'good',
    恢复中: 'mid',
    恢复缓慢: 'slow',
    平稳: 'flat',
    需关注: 'slow',
    信息不足: 'info',
  }[recovery?.level] || 'info';

  const chartOptions = Object.entries(data.series).map(([col, s]) => ({
    key: col,
    option: {
      title: { text: `${s.label} (${s.unit})`, textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 55, right: 20, top: 40, bottom: 28 },
      xAxis: { type: 'category', data: TP_LABELS },
      yAxis: { type: 'value', scale: true },
      series: [
        {
          type: 'line',
          data: s.points.map((p) => p.value),
          smooth: true,
          symbolSize: 8,
          lineStyle: { width: 3, color: '#1a5c54' },
          itemStyle: {
            color: (params) => TP_COLORS[['BL', '24H', '72H'][params.dataIndex]] || '#1a5c54',
          },
        },
      ],
    },
  }));

  const tcOption = {
    title: { text: 'T/C 比值（睾酮/皮质醇 ×100%）', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 55, right: 20, top: 40, bottom: 28 },
    xAxis: { type: 'category', data: TP_LABELS },
    yAxis: { type: 'value', scale: true },
    series: [
      {
        type: 'line',
        data: data.tc_ratio.map((p) => p.value),
        smooth: true,
        symbolSize: 8,
        lineStyle: { width: 3, color: '#8e44ad' },
      },
    ],
  };

  const p = data.participant;

  return (
    <div className="report-page">
      <div className="report-toolbar">
        <div className="page-title">运动员纵向报告</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => window.print()}>
            导出 PDF / 打印
          </button>
          <button className="btn btn-ghost" onClick={() => history.back()}>
            返回
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">基本信息</div>
        <div
          className="grid"
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: 12 }}
        >
          <div>
            <div className="note">编号</div>
            <strong>{p.participant_id}</strong>
          </div>
          <div>
            <div className="note">姓名</div>
            <strong>{p.name || '—'}</strong>
          </div>
          <div>
            <div className="note">性别</div>
            <strong>{p.sex || '—'}</strong>
          </div>
          <div>
            <div className="note">年龄</div>
            <strong>{p.age_years != null ? `${p.age_years} 岁` : '—'}</strong>
          </div>
          <div>
            <div className="note">组别</div>
            <strong>{p.group_name || '未分组'}</strong>
          </div>
          <div>
            <div className="note">教练</div>
            <strong>{p.coach || '—'}</strong>
          </div>
          <div>
            <div className="note">身高/体重</div>
            <strong>
              {p.height_cm != null ? `${p.height_cm}cm` : '—'} /{' '}
              {p.weight_kg != null ? `${p.weight_kg}kg` : '—'}
            </strong>
          </div>
        </div>
      </div>

      <div className={`card recovery-card ${recClass}`} style={{ marginBottom: 16 }}>
        <div className="recovery-level">恢复评估：{recovery?.level || '—'}</div>
        <div className="recovery-msg">{recovery?.message || ''}</div>
        {recovery?.detail?.bl_to_24h_pct != null && (
          <div className="note" style={{ color: 'rgba(255,255,255,0.85)', marginTop: 8 }}>
            CK 变化：BL→24H {recovery.detail.bl_to_24h_pct > 0 ? '+' : ''}
            {recovery.detail.bl_to_24h_pct}%，BL→72H{' '}
            {recovery.detail.bl_to_72h_pct > 0 ? '+' : ''}
            {recovery.detail.bl_to_72h_pct}%
          </div>
        )}
      </div>

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        {chartOptions.map(({ key, option }) => (
          <div className="card" key={key}>
            <Chart option={option} height="240px" />
          </div>
        ))}
        <div className="card">
          <Chart option={tcOption} height="240px" />
        </div>
        <div className="card">
          <div className="card-title">血样明细</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>训练前</th>
                <th>24小时后</th>
                <th>72小时后</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.series).map(([col, s]) => (
                <tr key={col}>
                  <td>{s.label}</td>
                  {s.points.map((pt, i) => (
                    <td key={i} style={{ color: pt.value == null ? 'var(--text-light)' : undefined }}>
                      {pt.value != null
                        ? col === 'testosterone_value' && pt.raw
                          ? pt.raw
                          : pt.value
                        : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="note" style={{ marginTop: 8 }}>
            * 睾酮 &lt;0.0868 为低于检测限，图中按缺失处理，此处显示原始读数。
          </div>
        </div>
      </div>

      <div className="note" style={{ textAlign: 'center', marginTop: 8 }}>
        本报告由 SpeedTrack Pro 生成 · 数据仅存于本机
      </div>
    </div>
  );
}

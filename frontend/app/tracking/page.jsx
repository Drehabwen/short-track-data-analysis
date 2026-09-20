'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import { selectInitialParticipant } from '@/lib/coach-workspace.mjs';

const TIMEPOINT_COLORS = { BL: '#2ca02c', '24H': '#ff7f0e', '72H': '#d62728' };
const TP_LABELS = { BL: '训练前', '24H': '24小时后', '72H': '72小时后' };

export default function TrackingPage() {
  const [participants, setParticipants] = useState([]);
  const [selected, setSelected] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .participants()
      .then((list) => {
        setParticipants(list);
        setSelected(selectInitialParticipant(list, window.location.search));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError('');
    api
      .tracking(selected)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selected]);

  if (loading && !data) return <div className="loading">加载中...</div>;

  const tpLabels = ['训练前', '24小时后', '72小时后'];

  // 每个指标的折线图 option
  const lineOptions = data
    ? Object.entries(data.series).map(([col, s]) => ({
        key: col,
        option: {
          title: { text: `${s.label} (${s.unit})`, textStyle: { fontSize: 13, color: '#13443e' } },
          tooltip: { trigger: 'axis' },
          grid: { left: 50, right: 20, top: 40, bottom: 28 },
          xAxis: { type: 'category', data: tpLabels, axisLabel: { fontSize: 12 } },
          yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
          series: [
            {
              type: 'line',
              data: s.points.map((p) => p.value),
              smooth: true,
              symbolSize: 9,
              lineStyle: { width: 3, color: '#1a5c54' },
              itemStyle: {
                color: (params) =>
                  TIMEPOINT_COLORS[['BL', '24H', '72H'][params.dataIndex]] || '#1a5c54',
              },
              markPoint: {
                data: [
                  { type: 'max', name: '峰值' },
                  { type: 'min', name: '谷值' },
                ],
                label: { fontSize: 10 },
              },
            },
          ],
        },
      }))
    : [];

  const tcOption = data
    ? {
        title: { text: 'T/C 比值 (睾酮/皮质醇 ×100%)', textStyle: { fontSize: 13, color: '#13443e' } },
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 20, top: 40, bottom: 28 },
        xAxis: { type: 'category', data: tpLabels },
        yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
        series: [
          {
            type: 'line',
            data: data.tc_ratio.map((p) => p.value),
            smooth: true,
            symbolSize: 9,
            lineStyle: { width: 3, color: '#8e44ad' },
          },
        ],
      }
    : null;

  const recovery = data?.recovery;
  const recClass = {
    恢复良好: 'good',
    恢复中: 'mid',
    恢复缓慢: 'slow',
    平稳: 'flat',
    需关注: 'slow',
    信息不足: 'info',
  }[recovery?.level] || 'info';

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">个体追踪</div>
          <div className="page-desc">单运动员五指标三时间点趋势与恢复评估</div>
        </div>
        <div>
          <select
            className="select"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            style={{ minWidth: 160 }}
          >
            {participants.map((p) => (
              <option key={p.participant_id} value={p.participant_id}>
                {p.participant_id}
                {p.group_name ? `（${p.group_name}）` : ''}
              </option>
            ))}
          </select>
          <a
            className="btn btn-primary"
            href={`/report?id=${encodeURIComponent(selected)}`}
            style={{ marginLeft: 8 }}
          >
            生成报告
          </a>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {data && (
        <>
          {/* 运动员信息 + 恢复评估 */}
          <div className="grid cols-3" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="card-title">运动员信息</div>
              <table className="data-table">
                <tbody>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>编号</td>
                    <td><strong>{data.participant.participant_id}</strong></td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>姓名</td>
                    <td>{data.participant.name || '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>批次</td>
                    <td>{data.participant.batch_id || '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>性别</td>
                    <td>{data.participant.sex || '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>年龄</td>
                    <td>{data.participant.age_years != null ? `${data.participant.age_years} 岁` : '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>组别</td>
                    <td>{data.participant.group_name || '未分组'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>教练</td>
                    <td>{data.participant.coach || '—'}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-light)' }}>身高/体重</td>
                    <td>
                      {data.participant.height_cm != null ? `${data.participant.height_cm}cm` : '—'}
                      {' / '}
                      {data.participant.weight_kg != null ? `${data.participant.weight_kg}kg` : '—'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className={`card recovery-card ${recClass}`}>
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
            <div className="card">
              <div className="card-title">
                血样记录
                <span className="hint">{data.samples.length} 份</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>时间点</th>
                    <th>采集时间</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {data.samples.map((s) => (
                    <tr key={s.visit_id}>
                      <td>
                        {TP_LABELS[s.timepoint] || s.timepoint}
                      </td>
                      <td>{s.collection_time ? s.collection_time.slice(0, 16) : '—'}</td>
                      <td>
                        <span className={`badge ${s.review_status.includes('复核') ? 'warn' : 'ok'}`}>
                          {s.review_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 五指标趋势图 */}
          <div className="grid cols-2" style={{ marginBottom: 16 }}>
            {lineOptions.map(({ key, option }) => (
              <div className="card" key={key}>
                <Chart option={option} height="260px" />
              </div>
            ))}
            <div className="card">
              {tcOption ? <Chart option={tcOption} height="260px" /> : <div className="empty">数据不足</div>}
            </div>
            <div className="card">
              <div className="card-title">数值明细</div>
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
                      {s.points.map((p, i) => (
                        <td key={i} style={{ color: p.value == null ? 'var(--text-light)' : undefined }}>
                          {p.value != null
                            ? col === 'testosterone_value' && p.raw
                              ? p.raw
                              : p.value
                            : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="note">
                * 睾酮 &lt;0.0868 为低于检测限（censored），图中按缺失处理，此处显示原始读数。
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

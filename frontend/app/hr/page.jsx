'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

export default function HrPage() {
  const [overview, setOverview] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [selected, setSelected] = useState('');
  const [athleteHr, setAthleteHr] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.hrOverview(), api.hrSessions(), api.participants()])
      .then(([ov, ss, ps]) => {
        setOverview(ov);
        setSessions(ss);
        setParticipants(ps);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api
      .hrAthlete(selected)
      .then(setAthleteHr)
      .catch((e) => setError(e.message));
  }, [selected]);

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!overview) return null;

  const typeOption = {
    title: { text: '训练类型场次分布', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        data: Object.entries(overview.by_type || {}).map(([name, value]) => ({ name, value })),
        label: { fontSize: 12 },
      },
    ],
  };

  const zoneOption = {
    title: { text: '心率区间分布（Z1-Z5）', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
    tooltip: {},
    xAxis: { type: 'category', data: ['Z1', 'Z2', 'Z3', 'Z4', 'Z5'] },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        barWidth: 40,
        data: athleteHr
          ? [0, 1, 2, 3, 4].map((i) => {
              const s = athleteHr[i];
              return s ? Math.round(((s.z1 || 0) + (s.z2 || 0) + (s.z3 || 0) + (s.z4 || 0) + (s.z5 || 0)) || 0) : 0;
            })
          : [],
        itemStyle: { color: '#0071e3', borderRadius: [6, 6, 0, 0] },
        label: { show: true, position: 'top' },
      },
    ],
  };

  const athleteZoneOption = athleteHr
    ? {
        title: { text: `${selected} 各场次平均心率`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 16, top: 40, bottom: 28 },
        xAxis: {
          type: 'category',
          data: athleteHr.map((s) => (s.datetime ? s.datetime.slice(5, 16) : s.id)),
          axisLabel: { rotate: 30, fontSize: 10 },
        },
        yAxis: { type: 'value', min: 60 },
        series: [
          {
            type: 'line',
            data: athleteHr.map((s) => s.avg_hr),
            smooth: true,
            lineStyle: { width: 3, color: '#0071e3' },
            itemStyle: { color: '#0071e3' },
            areaStyle: { opacity: 0.08 },
          },
        ],
      }
    : null;

  // ── 教练对比图（按教练聚合：均心 + 高强度%）──
  const coaches = Object.entries(overview.by_coach || {});
  const coachOption = coaches.length
    ? {
        title: { text: '各教练组训练强度对比', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
        tooltip: { trigger: 'axis' },
        legend: { top: 0, data: ['平均心率', '高强度 Z4+Z5%'] },
        grid: { left: 50, right: 55, top: 36, bottom: 30 },
        xAxis: { type: 'category', data: coaches.map(([c]) => c), axisLabel: { fontSize: 11 } },
        yAxis: [
          { type: 'value', name: 'bpm', min: 80 },
          { type: 'value', name: '%', splitLine: { show: false } },
        ],
        series: [
          {
            name: '平均心率',
            type: 'bar',
            barWidth: 26,
            data: coaches.map(([, v]) => v.avg_hr ?? 0),
            itemStyle: { color: '#0071e3', borderRadius: [6, 6, 0, 0] },
            label: { show: true, position: 'top' },
          },
          {
            name: '高强度 Z4+Z5%',
            type: 'line',
            yAxisIndex: 1,
            data: coaches.map(([, v]) => v.z45_pct ?? 0),
            lineStyle: { color: '#ff3b30', width: 2.5 },
            itemStyle: { color: '#ff3b30' },
            label: { show: true, position: 'top' },
          },
        ],
      }
    : null;

  return (
    <div>
      <div className="page-header">
        <div className="page-title">训练心率监测</div>
        <div className="page-desc">逐人次训练心率 · 区间分布 · 运动员追踪</div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <div className="stat-card">
          <div className="stat-number">{overview.rows}</div>
          <div className="stat-label">心率记录</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{overview.athletes}</div>
          <div className="stat-label">监测运动员</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{overview.avg_hr ?? '—'}</div>
          <div className="stat-label">平均心率 bpm</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{ color: 'var(--red)' }}>{overview.max_hr ?? '—'}</div>
          <div className="stat-label">最大心率 bpm</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginBottom: 14 }}>
        <div className="card">
          <Chart option={typeOption} height="240px" />
          <Hint text="冰上 vs 陆地场次占比，看训练结构是否平衡" />
        </div>
        <div className="card">
          <Chart option={coachOption || {}} height="240px" />
          <Hint text="柱子高 = 该教练训练强度大；红线（Z4+Z5%）越高 = 高强度内容越多" />
        </div>
      </div>
      <div className="grid cols-2" style={{ marginBottom: 14 }}>
        <div className="card">
          <div className="card-title">
            运动员心率追踪
            <select className="select" value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">选择运动员</option>
              {participants
                .filter((p) => p.name)
                .map((p) => (
                  <option key={p.participant_id} value={p.participant_id}>
                    {p.participant_id} {p.name}
                  </option>
                ))}
            </select>
          </div>
          {athleteHr && athleteHr.length > 0 ? (
            <>
              <Chart option={athleteZoneOption} height="240px" />
              <Hint text="折线是这个人各场次的平均心率，往上走说明训练强度在加大" />
            </>
          ) : (
            <div className="empty">选择运动员查看心率趋势</div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          心率记录明细
          <span className="hint">共 {sessions.length} 条</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>运动员</th>
                <th>时间</th>
                <th>类型</th>
                <th>教练</th>
                <th>时长(分)</th>
                <th>平均HR</th>
                <th>最大HR</th>
                <th>Z1</th>
                <th>Z2</th>
                <th>Z3</th>
                <th>Z4</th>
                <th>Z5</th>
              </tr>
            </thead>
            <tbody>
              {sessions.slice(0, 60).map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.subject_id}</strong> {s.athlete || ''}</td>
                  <td>{s.datetime ? s.datetime.slice(0, 16) : '—'}</td>
                  <td><span className="badge blue">{s.session_name || s.session_type || '—'}</span></td>
                  <td>{s.coach || '—'}</td>
                  <td>{s.duration_min != null ? Math.round(s.duration_min) : '—'}</td>
                  <td style={{ fontWeight: 600 }}>{s.avg_hr ?? '—'}</td>
                  <td style={{ color: s.max_hr > 190 ? 'var(--red)' : undefined, fontWeight: 600 }}>
                    {s.max_hr ?? '—'}
                  </td>
                  <td>{s.z1 ?? '—'}</td>
                  <td>{s.z2 ?? '—'}</td>
                  <td>{s.z3 ?? '—'}</td>
                  <td>{s.z4 ?? '—'}</td>
                  <td>{s.z5 ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

const PHASE_CLS = {
  维持期: 'badge ok',
  减量期: 'badge warn',
  赛前期: 'badge blue',
  比赛日: 'badge danger',
};

export default function DecisionTaperPage() {
  const [event, setEvent] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.decisionTaper(event || undefined)
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
  }, [event]);

  const option = useMemo(() => {
    if (!data) return null;
    const plan = data.plan ?? [];
    return {
      grid: { left: 46, right: 16, top: 28, bottom: 30 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: plan.map((p) => (p.d_minus === 0 ? '比赛' : `D-${p.d_minus}`)),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', name: '目标负荷 %', max: 120 },
      series: [
        {
          name: '目标负荷',
          type: 'bar',
          data: plan.map((p) => ({
            value: p.target_pct,
            itemStyle: { color: p.d_minus === 0 ? '#c0392b' : p.target_pct >= 80 ? '#9cc3dd' : '#1d6f9e' },
          })),
          label: { show: true, position: 'top', fontSize: 9, formatter: '{c}' },
        },
      ],
    };
  }, [data]);

  const plan = data?.plan ?? [];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">赛前减量</h1>
          <div className="page-sub">
            基准日 {data?.anchor ?? '—'} · 比赛日 {data?.event ?? '—'} · 还剩 {data?.days_to_event ?? '—'} 天
          </div>
        </div>
        <div className="page-actions">
          <input
            type="date"
            value={event}
            onChange={(e) => setEvent(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #dbe3ee', fontSize: 12.5 }}
          />
          <Link className="btn ghost" href="/decision">← 今日卡</Link>
        </div>
      </div>

      {error && <div className="alert danger">{error}</div>}

      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="stat-card" data-tone="danger">
          <div className="stat-label">倒计时</div>
          <div className="stat-number">{data?.days_to_event ?? '—'} 天</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">今日目标负荷</div>
          <div className="stat-number">{plan[0]?.target_pct ?? '—'}%</div>
        </div>
        <div className="stat-card" data-tone="warn">
          <div className="stat-label">比赛日目标</div>
          <div className="stat-number">{plan[plan.length - 1]?.target_pct ?? '—'}%</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">减量幅度</div>
          <div className="stat-number">
            {(plan[0]?.target_pct ?? 100) - (plan[plan.length - 1]?.target_pct ?? 30)}%
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">每日目标负荷（% 基线）</div>
        {option ? <Chart option={option} height="300px" /> : <Hint>加载中…</Hint>}
        <div className="decision-legend">
          <span><i style={{ background: '#9cc3dd' }} />维持期</span>
          <span><i style={{ background: '#1d6f9e' }} />减量期</span>
          <span><i style={{ background: '#c0392b' }} />比赛日</span>
        </div>
      </div>

      <div className="card">
        <div className="card-title">逐日计划</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>日期</th><th>倒计时</th><th>阶段</th><th>目标负荷</th><th>建议</th></tr>
            </thead>
            <tbody>
              {plan.map((p) => (
                <tr key={p.date}>
                  <td>{p.date}</td>
                  <td>{p.d_minus === 0 ? '比赛日' : `D-${p.d_minus}`}</td>
                  <td><span className={PHASE_CLS[p.phase] ?? 'badge gray'}>{p.phase}</span></td>
                  <td>{p.target_pct}%</td>
                  <td className="muted">{p.tip}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Hint>总量按线性衰减到 30%，强度课保留；实际执行由教练在今日卡上确认。</Hint>
      </div>
    </div>
  );
}

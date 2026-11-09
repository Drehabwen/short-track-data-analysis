'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

const LEVEL_TEXT = { red: '停训观察', yellow: '建议减量' };

export default function DecisionWeeklyPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [days, setDays] = useState(14);

  useEffect(() => {
    api.decisionWeekly(days)
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
  }, [days]);

  const option = useMemo(() => {
    if (!data) return null;
    return {
      grid: { left: 44, right: 16, top: 24, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: data.days.map((d) => d.slice(5)),
        axisLabel: { fontSize: 10 },
      },
      yAxis: { type: 'value', name: '负荷' },
      series: [
        {
          name: '全队负荷',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: data.team_load,
          areaStyle: { opacity: 0.12 },
        },
      ],
    };
  }, [data]);

  const alerts = data?.alerts ?? [];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">周负荷与超阈名单</h1>
          <div className="page-sub">基准日 {data?.anchor ?? '—'} · 负荷指数 = 时长 × 心率区间权重</div>
        </div>
        <div className="page-actions">
          <div className="seg">
            {[7, 14, 28].map((d) => (
              <button
                key={d}
                className={`seg-btn ${days === d ? 'active' : ''}`}
                onClick={() => setDays(d)}
              >
                {d} 天
              </button>
            ))}
          </div>
          <Link className="btn ghost" href="/decision">← 今日卡</Link>
        </div>
      </div>

      {error && <div className="alert danger">{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">全队每日负荷</div>
        {option ? <Chart option={option} height="280px" /> : <Hint>加载中…</Hint>}
        <div className="decision-legend">
          <span><i style={{ background: '#1d6f9e' }} />全队合计负荷</span>
          <span>横轴为日期（月-日）</span>
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          <span>超阈名单（{alerts.length}）</span>
          <span className="muted">ACWR ≥ 1.3 或主观疲劳偏高</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>运动员</th>
                <th>建议</th>
                <th>ACWR</th>
                <th>单调性</th>
                <th>本周负荷</th>
                <th>建议负荷</th>
                <th>依据</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.athlete}>
                  <td>
                    <Link href={`/decision/athlete?name=${encodeURIComponent(a.athlete)}`} className="link">
                      {a.athlete}
                    </Link>
                  </td>
                  <td>
                    <span className={a.level === 'red' ? 'badge danger' : 'badge warn'}>
                      {LEVEL_TEXT[a.level] ?? a.level}
                    </span>
                  </td>
                  <td>{a.acwr ?? '—'}</td>
                  <td>{a.monotony ?? '—'}</td>
                  <td>{a.week_load ?? '—'}</td>
                  <td>{a.suggested_pct ?? '—'}%</td>
                  <td className="muted">{a.reason}</td>
                </tr>
              ))}
              {!alerts.length && (
                <tr><td colSpan={7} className="muted">本周无明显超阈运动员</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

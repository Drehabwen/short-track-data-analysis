'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api, API_BASE_URL } from '@/lib/api';
import Hint from '@/components/Hint';

const LEVEL_META = {
  green: { text: '正常训练', cls: 'badge ok', pct: 100 },
  yellow: { text: '建议减量', cls: 'badge warn', pct: 60 },
  red: { text: '停训观察', cls: 'badge danger', pct: 0 },
  under: { text: '负荷偏低', cls: 'badge blue', pct: 110 },
  unknown: { text: '数据不足', cls: 'badge gray', pct: 100 },
};

export default function DecisionPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    api.decisionToday()
      .then(setData)
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const athletes = data?.athletes ?? [];
  const shown = useMemo(
    () => (filter === 'all' ? athletes : athletes.filter((a) => a.level === filter)),
    [athletes, filter],
  );
  const cards = data?.cards ?? {};

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">今日训练决策</h1>
          <div className="page-sub">
            基准日 {data?.anchor ?? '—'} · 数据来自训练心率与主观疲劳
          </div>
        </div>
        <div className="page-actions">
          <button
            className="btn"
            onClick={() => window.open(`${API_BASE_URL}/api/decision/export.csv`, '_blank')}
          >
            导出训练单
          </button>
          <Link className="btn ghost" href="/decision/weekly">周负荷 →</Link>
          <Link className="btn ghost" href="/decision/taper">赛前减量 →</Link>
        </div>
      </div>

      {error && <div className="alert danger">{error}</div>}

      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="stat-card" data-tone="ok">
          <div className="stat-label">正常训练</div>
          <div className="stat-number">{cards.green ?? 0}</div>
        </div>
        <div className="stat-card" data-tone="warn">
          <div className="stat-label">建议减量</div>
          <div className="stat-number">{cards.yellow ?? 0}</div>
        </div>
        <div className="stat-card" data-tone="danger">
          <div className="stat-label">停训观察</div>
          <div className="stat-number">{cards.red ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">负荷偏低 / 数据不足</div>
          <div className="stat-number">{cards.under ?? 0} / {cards.unknown ?? 0}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          <span>运动员名单（{shown.length}）</span>
          <div className="seg">
            {[
              ['all', '全部'],
              ['red', '停训'],
              ['yellow', '减量'],
              ['under', '偏低'],
              ['green', '正常'],
            ].map(([k, label]) => (
              <button
                key={k}
                className={`seg-btn ${filter === k ? 'active' : ''}`}
                onClick={() => setFilter(k)}
              >
                {label}
              </button>
            ))}
          </div>
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
              {shown.map((a) => {
                const meta = LEVEL_META[a.level] ?? LEVEL_META.unknown;
                return (
                  <tr key={a.athlete}>
                    <td>
                      <Link href={`/decision/athlete?name=${encodeURIComponent(a.athlete)}`} className="link">
                        {a.athlete}
                      </Link>
                    </td>
                    <td><span className={meta.cls}>{meta.text}</span></td>
                    <td>{a.acwr ?? '—'}</td>
                    <td>{a.monotony ?? '—'}</td>
                    <td>{a.week_load ?? '—'}</td>
                    <td>{a.suggested_pct ?? '—'}%</td>
                    <td className="muted">{a.reason}</td>
                  </tr>
                );
              })}
              {!shown.length && (
                <tr><td colSpan={7} className="muted">暂无数据</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <Hint>点击姓名查看个人负荷曲线；建议负荷 = 基线负荷 × 建议百分比。</Hint>
      </div>
    </div>
  );
}

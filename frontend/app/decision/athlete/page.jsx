'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

const LEVEL_META = {
  green: { text: '正常训练', cls: 'badge ok' },
  yellow: { text: '建议减量', cls: 'badge warn' },
  red: { text: '停训观察', cls: 'badge danger' },
  under: { text: '负荷偏低', cls: 'badge blue' },
  unknown: { text: '数据不足', cls: 'badge gray' },
};

function AthleteContent() {
  const search = useSearchParams();
  const name = decodeURIComponent(String(search.get('name') ?? ''));
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [pct, setPct] = useState(100);
  const [status, setStatus] = useState({ sleep_hours: '', fatigue: '', morning_hr: '' });
  const [statusMsg, setStatusMsg] = useState('');

  useEffect(() => {
    if (!name) return;
    api.decisionAthlete(name)
      .then((d) => {
        setData(d);
        setPct(d?.summary?.suggested_pct ?? 100);
      })
      .catch((e) => setError(String(e.message || e)));
  }, [name]);

  const option = useMemo(() => {
    if (!data) return null;
    const series = data.series ?? [];
    return {
      grid: { left: 46, right: 52, top: 30, bottom: 30 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: series.map((s) => s.date.slice(5)),
        axisLabel: { fontSize: 10 },
      },
      yAxis: [
        { type: 'value', name: '负荷', nameTextStyle: { fontSize: 10 } },
        { type: 'value', name: 'ACWR', min: 0, max: 2, nameTextStyle: { fontSize: 10 } },
      ],
      series: [
        {
          name: '每日负荷',
          type: 'bar',
          data: series.map((s) => s.load),
          itemStyle: { color: '#1d6f9e', opacity: 0.75 },
        },
        {
          name: 'ACWR',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          data: series.map((s) => s.acwr),
          itemStyle: { color: '#d97706' },
          markLine: {
            symbol: 'none',
            silent: true,
            data: [{ yAxis: 1.3 }, { yAxis: 1.5 }],
            lineStyle: { type: 'dashed', color: '#c0392b', opacity: 0.5 },
            label: { fontSize: 9 },
          },
        },
      ],
    };
  }, [data]);

  const s = data?.summary;
  const meta = LEVEL_META[s?.level] ?? LEVEL_META.unknown;

  const saveStatus = async () => {
    try {
      await api.decisionStatus({
        athlete_name: name,
        sleep_hours: status.sleep_hours === '' ? null : Number(status.sleep_hours),
        fatigue: status.fatigue === '' ? null : Number(status.fatigue),
        morning_hr: status.morning_hr === '' ? null : Number(status.morning_hr),
      });
      setStatusMsg('已保存，正在刷新…');
      const d = await api.decisionAthlete(name);
      setData(d);
      setPct(d?.summary?.suggested_pct ?? 100);
      setStatusMsg('已保存');
    } catch (e) {
      setStatusMsg(`保存失败：${e.message}`);
    }
  };

  const log = async () => {
    if (!s) return;
    try {
      await api.decisionLog({
        athlete_name: name,
        level: s.level,
        suggested_pct: pct,
        reason: s.reason,
        acwr: s.acwr,
        monotony: s.monotony,
        decided_by: 'coach',
      });
      setMsg('已记录本次决策（留痕）');
    } catch (e) {
      setMsg(`记录失败：${e.message}`);
    }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">{name}</h1>
          <div className="page-sub">基准日 {data?.anchor ?? '—'} · 负荷-恢复与 ACWR</div>
        </div>
        <div className="page-actions">
          <Link className="btn ghost" href="/decision">← 返回名单</Link>
        </div>
      </div>

      {error && <div className="alert danger">{error}</div>}

      {s && (
        <div className="grid" style={{ marginBottom: 16, gridTemplateColumns: 'repeat(5, 1fr)' }}>
          <div className="stat-card" data-tone="warn">
            <div className="stat-label">建议</div>
            <div className="stat-number" style={{ fontSize: 20 }}>
              <span className={meta.cls}>{meta.text}</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">ACWR</div>
            <div className="stat-number">{s.acwr ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">单调性</div>
            <div className="stat-number">{s.monotony ?? '—'}</div>
          </div>
          <div className="stat-card" data-tone="warn">
            <div className="stat-label">疲劳指数</div>
            <div className="stat-number">{s.fatigue_index ?? '—'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">本周负荷</div>
            <div className="stat-number">{s.week_load ?? '—'}</div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">负荷与 ACWR 曲线</div>
        {option ? <Chart option={option} height="320px" /> : <Hint>加载中…</Hint>}
        <div className="decision-legend">
          <span><i style={{ background: '#1d6f9e' }} />每日负荷</span>
          <span><i style={{ background: '#d97706' }} />ACWR（虚线为 1.3 / 1.5 阈值）</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">
          <span>今日状态录入</span>
          <span className="muted">
            主观 {s?.subjective ?? '—'} · 晨脉 {s?.morning_hr ?? '—'} · 睡眠 {s?.sleep_hours ?? '—'}h
          </span>
        </div>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ fontSize: 12.5 }}>
            睡眠(h)
            <input type="number" step="0.5" value={status.sleep_hours}
              onChange={(e) => setStatus({ ...status, sleep_hours: e.target.value })}
              style={{ width: 70, marginLeft: 6, padding: '4px 8px', borderRadius: 6, border: '1px solid #dbe3ee' }} />
          </label>
          <label style={{ fontSize: 12.5 }}>
            主观疲劳(1-10)
            <input type="number" min={1} max={10} value={status.fatigue}
              onChange={(e) => setStatus({ ...status, fatigue: e.target.value })}
              style={{ width: 70, marginLeft: 6, padding: '4px 8px', borderRadius: 6, border: '1px solid #dbe3ee' }} />
          </label>
          <label style={{ fontSize: 12.5 }}>
            晨脉(bpm)
            <input type="number" value={status.morning_hr}
              onChange={(e) => setStatus({ ...status, morning_hr: e.target.value })}
              style={{ width: 70, marginLeft: 6, padding: '4px 8px', borderRadius: 6, border: '1px solid #dbe3ee' }} />
          </label>
          <button className="btn" onClick={saveStatus}>保存状态</button>
          <span className="muted">{statusMsg}</span>
        </div>
        <Hint>状态会进入疲劳指数（主观 25 分、晨脉偏移 15 分），与 ACWR、单调性共同决定建议。</Hint>
      </div>

      <div className="card">
        <div className="card-title">
          <span>决策与留痕</span>
          <span className="muted">{s?.reason ?? ''}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ fontSize: 12.5 }}>
            建议负荷：
            <input
              type="number"
              value={pct}
              min={0}
              max={120}
              step={5}
              onChange={(e) => setPct(Number(e.target.value))}
              style={{ width: 76, marginLeft: 6, padding: '4px 8px', borderRadius: 6, border: '1px solid #dbe3ee' }}
            />
            %
          </label>
          <button className="btn" onClick={log}>采纳并记录</button>
          <span className="muted">{msg}</span>
        </div>
        <Hint>记录写入 decision_logs 表，用于赛后复盘“谁被减量、为什么”。</Hint>
      </div>
    </div>
  );
}

export default function DecisionAthletePage() {
  return (
    <Suspense fallback={<div className="loading">加载中…</div>}>
      <AthleteContent />
    </Suspense>
  );
}

'use client';

import dynamic from 'next/dynamic';
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';

// 画像页首屏只需要运动员选择器；图表组件（及 ECharts）在真正选中运动员后再加载。
const Chart = dynamic(() => import('@/components/Chart'), {
  ssr: false,
  loading: () => <div className="note" style={{ minHeight: 200, display: 'grid', placeItems: 'center' }}>图表加载中...</div>,
});

const TP_LABELS = { BL: '训练前', '24H': '24小时后', '72H': '72小时后' };
const TP_ORDER = ['BL', '24H', '72H'];

const num = (v) => (v == null || v === '' ? null : Number(v));

export default function ProfilePage() {
  const [athletes, setAthletes] = useState([]);
  const [selected, setSelected] = useState('');
  const [data, setData] = useState(null);
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.participants().then(setAthletes).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError('');
    Promise.all([api.athletePanorama(selected), api.samples({ participant: selected })])
      .then(([pano, smp]) => {
        setData(pano);
        setSamples(smp || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selected]);

  // 血液趋势（按时间点聚合）
  const bloodTrend = useMemo(() => {
    if (!samples.length) return null;
    const get = (s, k) => {
      if (k !== 'testosterone_value') return num(s[k]);
      const v = num(s.testosterone_value);
      if (v != null) return v;
      const raw = String(s.testosterone_raw || '').replace(/[^\d.]/g, '');
      const pv = parseFloat(raw);
      return Number.isNaN(pv) ? null : pv;
    };
    const metrics = [
      { key: 'testosterone_value', name: '睾酮', unit: 'nmol/L', color: '#c0392b' },
      { key: 'cortisol_ug_dL', name: '皮质醇', unit: 'μg/dL', color: '#e67e22' },
      { key: 'urea_mmol_L', name: '尿素', unit: 'mmol/L', color: '#2980b9' },
      { key: 'creatine_kinase_U_L', name: '肌酸激酶CK', unit: 'U/L', color: '#8e44ad' },
      { key: 'ldh_U_L', name: 'LDH', unit: 'U/L', color: '#16a085' },
    ];
    return metrics.map((m) => ({
      ...m,
      data: TP_ORDER.map((tp) => {
        const vals = samples.filter((s) => s.timepoint === tp).map((s) => get(s, m.key)).filter((v) => v != null && !Number.isNaN(v));
        return vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : null;
      }),
    }));
  }, [samples]);

  const radarOption = useMemo(() => {
    if (!data?.radar || !data.radar.indicators) return null;
    return {
      tooltip: {},
      radar: { indicator: data.radar.indicators.map((name) => ({ name, max: 100 })) },
      series: [{ type: 'radar', data: [{ value: data.radar.values.map((v) => (v == null ? 0 : v)), areaStyle: { opacity: 0.3 }, lineStyle: { color: '#0d9488' }, itemStyle: { color: '#0d9488' } }] }],
    };
  }, [data]);

  const bloodOptions = useMemo(
    () =>
      (bloodTrend || []).map((m) => ({
        tooltip: { trigger: 'axis' },
        grid: { left: 55, right: 16, top: 24, bottom: 26 },
        xAxis: { type: 'category', data: TP_ORDER.map((t) => TP_LABELS[t]) },
        yAxis: { type: 'value', name: m.unit, nameTextStyle: { fontSize: 10 } },
        series: [{ type: 'line', smooth: true, symbolSize: 8, lineStyle: { width: 3, color: m.color }, itemStyle: { color: m.color }, data: m.data, connectNulls: true }],
      })),
    [bloodTrend]
  );

  const p = data?.participant || {};
  const b = data?.blood || {};
  const hr = data?.hr || {};
  const cpet = data?.cpet || {};
  const pre = data?.pretest || {};

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">运动员画像</div>
          <div className="page-desc">一键生成运动员综合画像：血液 · 心率 · 最大摄氧量 · 前测 · 功能雷达</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">选择运动员</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <select className="select" value={selected} onChange={(e) => setSelected(e.target.value)} style={{ minWidth: 220 }}>
            <option value="">— 选择运动员 —</option>
            {athletes.map((a) => (
              <option key={a.participant_id} value={a.participant_id}>
                {a.name}（{a.participant_id}）
              </option>
            ))}
          </select>
          {loading && <span className="note">加载中...</span>}
        </div>
        {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}
      </div>

      {data && (
        <>
          <div className="grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(170px,1fr))', gap: 12, marginBottom: 16 }}>
            <div className="card" style={{ padding: 12 }}>
              <div className="card-title">基本信息</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{p.name}</div>
              <div className="note">{p.sex} · {p.age_years}岁 · {p.height_cm}cm/{p.weight_kg}kg</div>
              <div className="note">{p.group_name || '未分组'} · {p.coach || '—'}</div>
            </div>
            <div className="card" style={{ padding: 12 }}>
              <div className="card-title">心率（近周）</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{hr.avg_hr ?? '—'} <small style={{ fontSize: 12, color: 'var(--muted)' }}>bpm</small></div>
              <div className="note">{hr.sessions ?? 0} 次训练 · 峰值 {hr.max_hr ?? '—'} · Z4+5 {hr.z45_pct ?? '—'}%</div>
            </div>
            <div className="card" style={{ padding: 12 }}>
              <div className="card-title">最大摄氧量</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{num(cpet.best_vo2kg) != null ? cpet.best_vo2kg : '—'} <small style={{ fontSize: 12, color: 'var(--muted)' }}>ml/kg/min</small></div>
              <div className="note">排名 {cpet.ranks?.vo2kg?.rank ?? '—'}/{cpet.ranks?.vo2kg?.total ?? '—'} · 达标{num(cpet.best_pctnorm) != null ? ` ${cpet.best_pctnorm}%` : ''}</div>
            </div>
            <div className="card" style={{ padding: 12 }}>
              <div className="card-title">最新血液（CK）</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{num(b.ck) != null ? b.ck : '—'} <small style={{ fontSize: 12, color: 'var(--muted)' }}>U/L</small></div>
              <div className="note">睾酮 {num(b.testosterone) ?? '—'} · 尿素 {num(b.urea) ?? '—'}</div>
            </div>
            <div className="card" style={{ padding: 12 }}>
              <div className="card-title">前测</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{num(pre.fms_total) != null ? pre.fms_total : '—'} <small style={{ fontSize: 12, color: 'var(--muted)' }}>/36 FMS</small></div>
              <div className="note">CMJ {num(pre.cmj_height_cm) ?? '—'}cm · 血乳酸 {num(pre.lactate_pre) ?? '—'}</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">综合能力雷达（0-100）</div>
            {radarOption ? <Chart option={radarOption} height={280} /> : <div className="note">暂无雷达数据</div>}
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">血液指标恢复趋势（训练前 → 24h → 72h）</div>
            {bloodOptions.length ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 12 }}>
                {bloodOptions.map((opt, i) => (
                  <div key={i} className="card" style={{ padding: 10 }}>
                    <div className="card-title" style={{ fontSize: 12 }}>{bloodTrend[i].name}（{bloodTrend[i].unit}）</div>
                    <Chart option={opt} height={200} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="note">该运动员暂无血液样本记录</div>
            )}
          </div>
        </>
      )}

      {!data && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>
          <p style={{ fontSize: 40 }}>🩺</p>
          <p>请选择运动员查看画像</p>
        </div>
      )}
    </div>
  );
}

'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import Chart from '@/components/Chart';

const TP_LABELS = ['训练前', '24小时后', '72小时后'];

const RECOVERY_TEXT = {
  恢复良好: { title: '你恢复得不错', advice: '今天可以正常训练，注意保持强度节奏。', color: '#16a34a' },
  恢复中: { title: '基本恢复', advice: '今天可以训练，强度先按计划的 80% 来。', color: '#d97706' },
  恢复缓慢: { title: '恢复偏慢', advice: '建议今天降低训练强度，多留时间休息。', color: '#e11d48' },
  需关注: { title: '需要关注', advice: '建议今天以恢复为主，必要时和教练沟通。', color: '#e11d48' },
  平稳: { title: '状态平稳', advice: '状态稳定，按计划正常训练。', color: '#16a34a' },
  信息不足: { title: '数据还不够', advice: '多测几次或配合状态上报，才能给你更准的判断。', color: '#64748b' },
};

function statusOf(value, lo, hi) {
  if (value == null) return { text: '—', tone: 'gray' };
  if (lo != null && value < lo) return { text: '偏低', tone: 'low' };
  if (hi != null && value > hi) return { text: '偏高', tone: 'high' };
  return { text: '正常', tone: 'ok' };
}

export default function MyStatusPage() {
  const { user } = useAuth();
  const athleteId = user?.athlete_id || '';
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!athleteId) return;
    api
      .tracking(athleteId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [athleteId]);

  if (loading) return <div className="loading">正在分析你的状态...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <div className="loading">加载中...</div>;

  const p = data.participant || {};
  const recovery = data.recovery;
  const rec = RECOVERY_TEXT[recovery?.level] || RECOVERY_TEXT.信息不足;

  const get = (col, idx) => {
    const s = data.series?.[col];
    return s?.points?.[idx]?.value ?? null;
  };
  const ck72 = get('creatine_kinase_U_L', 2);
  const cort72 = get('cortisol_ug_dL', 2);
  const tc72 = data.tc_ratio?.[2]?.value ?? null;

  const ckStatus = statusOf(ck72, null, 500);
  const tcStatus = statusOf(tc72, 2.0, null);
  const cortStatus = statusOf(cort72, null, 25);

  const toneColor = { ok: '#16a34a', low: '#2980b9', high: '#e11d48', gray: '#94a3b8' };

  // 72 小时恢复曲线（CK）
  const ckSeries = data.series?.['creatine_kinase_U_L'];
  const ckCurve = ckSeries
    ? {
        title: { text: '', textStyle: { fontSize: 12 } },
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 16, top: 20, bottom: 26 },
        xAxis: { type: 'category', data: TP_LABELS },
        yAxis: { type: 'value', name: ckSeries.unit, nameTextStyle: { fontSize: 10 } },
        series: [
          {
            type: 'line',
            smooth: true,
            symbolSize: 8,
            data: ckSeries.points.map((pt) => pt.value),
            lineStyle: { width: 3, color: '#0d9488' },
            itemStyle: { color: '#0d9488' },
            label: { show: true, position: 'top', fontSize: 10 },
            connectNulls: true,
          },
        ],
      }
    : null;

  // 详细数据：五指标图 + T/C + 明细表
  const detailCharts = Object.entries(data.series || {}).map(([col, s]) => ({
    key: col,
    option: {
      title: { text: `${s.label} (${s.unit})`, textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 16, top: 34, bottom: 26 },
      xAxis: { type: 'category', data: TP_LABELS },
      yAxis: { type: 'value', scale: true },
      series: [
        {
          type: 'line',
          data: s.points.map((pt) => pt.value),
          smooth: true,
          symbolSize: 7,
          lineStyle: { width: 2.5, color: '#1a5c54' },
          itemStyle: { color: '#1a5c54' },
          connectNulls: true,
        },
      ],
    },
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">我的状态</div>
          <div className="page-desc">今天能不能练 · 恢复得怎么样 · 需要注意什么</div>
        </div>
      </div>

      {/* 顶部：结论卡 */}
      <div
        className="card"
        style={{
          marginBottom: 16,
          borderLeft: `6px solid ${rec.color}`,
          padding: '20px 22px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{p.name || p.participant_id}</div>
          <span className="badge" style={{ background: rec.color, color: '#fff', border: 'none' }}>
            {recovery?.level || '信息不足'}
          </span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 800, color: rec.color, margin: '10px 0 4px' }}>
          {rec.title}
        </div>
        <div style={{ color: 'var(--text)' }}>{rec.advice}</div>
        {recovery?.message && (
          <div className="note" style={{ marginTop: 8 }}>{recovery.message}</div>
        )}
        {recovery?.detail?.bl_to_72h_pct != null && (
          <div className="note" style={{ marginTop: 6 }}>
            CK 训练前 → 72小时 变化 {recovery.detail.bl_to_72h_pct > 0 ? '+' : ''}
            {recovery.detail.bl_to_72h_pct}%
          </div>
        )}
      </div>

      {/* 三个关键数字 */}
      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        {[
          { label: '肌肉疲劳', value: ck72, unit: 'U/L', status: ckStatus, hint: '运动后升高正常，72小时还高 = 恢复不足' },
          { label: '恢复储备', value: tc72, unit: '%', status: tcStatus, hint: 'T/C 比值偏低提示过度训练风险' },
          { label: '压力水平', value: cort72, unit: 'μg/dL', status: cortStatus, hint: '皮质醇偏高 = 压力/恢复不足' },
        ].map((card) => (
          <div className="card" key={card.label} style={{ padding: 16 }}>
            <div className="note" style={{ fontSize: 12 }}>{card.label}</div>
            <div style={{ fontSize: 26, fontWeight: 800, margin: '4px 0' }}>
              {card.value ?? '—'}
              <small style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 4 }}>{card.unit}</small>
            </div>
            <span
              className="badge"
              style={{
                background: toneColor[card.status.tone],
                color: '#fff',
                border: 'none',
              }}
            >
              {card.status.text}
            </span>
            <div className="note" style={{ marginTop: 8 }}>{card.hint}</div>
          </div>
        ))}
      </div>

      {/* 72 小时恢复曲线 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">72 小时恢复曲线（肌肉疲劳 CK）</div>
        {ckCurve ? (
          <>
            <Chart option={ckCurve} height="220px" />
            <div className="note">训练后 CK 会升高，72 小时应回落；如果还在高位，说明恢复还没完成。</div>
          </>
        ) : (
          <div className="empty">暂无血液样本数据</div>
        )}
      </div>

      {/* 详细数据 */}
      <details className="card" style={{ marginBottom: 16 }}>
        <summary style={{ cursor: 'pointer', fontWeight: 700, padding: 6, color: '#13443e' }}>
          查看详细数据（指标趋势 · 血样明细）
        </summary>
        <div className="grid cols-2" style={{ marginTop: 10 }}>
          {detailCharts.map(({ key, option }) => (
            <div className="card" key={key}>
              <Chart option={option} height="220px" />
            </div>
          ))}
        </div>
        <div className="card" style={{ marginTop: 10 }}>
          <div className="card-title">血样明细</div>
          <div className="table-wrap">
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
                {Object.entries(data.series || {}).map(([col, s]) => (
                  <tr key={col}>
                    <td>{s.label}</td>
                    {s.points.map((pt, i) => (
                      <td key={i} style={{ color: pt.value == null ? 'var(--text-light)' : undefined }}>
                        {pt.value != null ? (col === 'testosterone_value' && pt.raw ? pt.raw : pt.value) : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            * 睾酮 &lt;0.0868 为低于检测限，按正常处理。
          </div>
        </div>
      </details>
    </div>
  );
}

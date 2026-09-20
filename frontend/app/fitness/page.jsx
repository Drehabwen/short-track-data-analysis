'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';

const TABS = [
  { key: 'cpet', label: '功率自行车 CPET' },
  { key: 'pretest', label: '基础体能 前测' },
  { key: 'fatigue', label: '急性疲劳 恢复' },
  { key: 'daily', label: '日常训练成绩' },
];

const TP_LABELS = ['训练前', '24小时', '72小时'];

export default function FitnessPage() {
  const [tab, setTab] = useState('cpet');
  const [cpet, setCpet] = useState([]);
  const [pretest, setPretest] = useState([]);
  const [fatigue, setFatigue] = useState([]);
  const [daily, setDaily] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.cpetTests().catch(() => []),
      api.pretest().catch(() => []),
      api.fatigue().catch(() => []),
      api.trainingEntries({ limit: 500 }).catch(() => []),
      api.participants().catch(() => []),
    ])
      .then(([cp, pt, ft, dy, ps]) => {
        setCpet(cp);
        setPretest(pt);
        setFatigue(ft);
        setDaily(dy);
        setParticipants(ps);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const nameOf = (pid) =>
    participants.find((p) => p.participant_id === pid)?.name || '—';

  const cmjOption = useMemo(() => {
    const rows = fatigue.filter((f) => f.cmj_pre != null || f.cmj_24h != null || f.cmj_72h != null);
    if (!rows.length) return null;
    const avg = (key) => {
      const vals = rows.map((r) => r[key]).filter((v) => v != null);
      return vals.length ? +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : null;
    };
    return {
      title: { text: `CMJ 跳跃高度恢复趋势（均值，n=${rows.length}）`, textStyle: { fontSize: 13 } },
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 40, bottom: 28 },
      xAxis: { type: 'category', data: TP_LABELS },
      yAxis: { type: 'value', name: 'cm', nameTextStyle: { fontSize: 10 } },
      series: [
        {
          type: 'line',
          smooth: true,
          symbolSize: 9,
          data: [avg('cmj_pre'), avg('cmj_24h'), avg('cmj_72h')],
          lineStyle: { width: 3, color: '#0d9488' },
          itemStyle: { color: '#0d9488' },
          label: { show: true, position: 'top', fontSize: 11 },
          connectNulls: true,
        },
      ],
    };
  }, [fatigue]);

  const dailyByType = useMemo(() => {
    const m = {};
    daily.forEach((d) => {
      const k = d.test_type || '其他';
      if (!m[k]) m[k] = { count: 0, last: null };
      m[k].count += 1;
      if (!m[k].last || d.entry_date > m[k].last) m[k].last = d.entry_date;
    });
    return Object.entries(m);
  }, [daily]);

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const uniqueSubjects = (rows, key) => new Set(rows.map((r) => r[key]).filter(Boolean)).size;
  const cpetValid = cpet.filter((t) => (t.valid_class || '').includes('有效')).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">体能测试中心</div>
          <div className="page-desc">功率自行车 · 基础体能 · 急性疲劳 · 日常成绩</div>
        </div>
      </div>

      <div id="body-composition" className="card body-composition-status" style={{ marginBottom: 16 }}>
        <div>
          <div className="card-title">身体成分</div>
          <div className="note">核心字段已定义：身高、体重、BMI、体脂率、骨骼肌量、去脂体重。</div>
        </div>
        <div className="body-composition-status__state">等待设备导出样例后接入标准化导入</div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`btn ${tab === t.key ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'cpet' && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 14 }}>
            <div className="card stat-card">
              <div className="stat-number">{cpet.length}</div>
              <div className="stat-label">测试总数</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number" style={{ color: 'var(--ok)' }}>{cpetValid}</div>
              <div className="stat-label">有效测试</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">{uniqueSubjects(cpet, 'subject_id')}</div>
              <div className="stat-label">覆盖运动员</div>
            </div>
          </div>
          <div className="card">
            <div className="card-title">
              功率自行车 / 心肺测试记录
              <span className="hint"><a href="/cpet">前往 CPET 详细分析页 →</a></span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>运动员</th>
                    <th>VO₂/kg</th>
                    <th>%预测</th>
                    <th>HR峰</th>
                    <th>RER</th>
                    <th>VT1</th>
                    <th>功率(W)</th>
                    <th>时长(s)</th>
                    <th>分级</th>
                  </tr>
                </thead>
                <tbody>
                  {cpet.map((t) => (
                    <tr key={t.id}>
                      <td>{t.test_start ? t.test_start.slice(0, 10) : '—'}</td>
                      <td><strong>{t.subject_id}</strong> {nameOf(t.subject_id)}</td>
                      <td style={{ fontWeight: 700 }}>{t.vo2kg_peak ?? '—'}</td>
                      <td>{t.vo2kg_pctnorm != null ? `${Math.round(t.vo2kg_pctnorm)}%` : '—'}</td>
                      <td>{t.hr_peak ?? '—'}</td>
                      <td>{t.rer_peak ?? '—'}</td>
                      <td>{t.vo2kg_vt1 ?? '—'}</td>
                      <td>{t.peak_wr ?? '—'}</td>
                      <td>{t.duration_s ?? '—'}</td>
                      <td>
                        <span className={`badge ${(t.valid_class || '').includes('有效') ? 'ok' : (t.valid_class || '').includes('无效') ? 'danger' : 'warn'}`}>
                          {t.valid_class || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {cpet.length === 0 && (
                    <tr><td colSpan={10} className="empty">暂无功率自行车测试数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === 'pretest' && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 14 }}>
            <div className="card stat-card">
              <div className="stat-number">{pretest.length}</div>
              <div className="stat-label">测试记录</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">{uniqueSubjects(pretest, 'subject_id')}</div>
              <div className="stat-label">覆盖运动员</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">
                {pretest.filter((r) => r.fms_total != null).length}
              </div>
              <div className="stat-label">有 FMS 总分</div>
            </div>
          </div>
          <div className="card">
            <div className="card-title">基础体能前测记录（CMJ / YBT / 平衡 / 乳酸）</div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>运动员</th>
                    <th>性别</th>
                    <th>FMS</th>
                    <th>CMJ(cm)</th>
                    <th>单跳右(cm)</th>
                    <th>三级跳右(cm)</th>
                    <th>YBT左前(cm)</th>
                    <th>YBT右前(cm)</th>
                    <th>乳酸pre</th>
                    <th>乳酸post5</th>
                    <th>COP面积</th>
                  </tr>
                </thead>
                <tbody>
                  {pretest.map((r) => (
                    <tr key={r.id}>
                      <td><strong>{r.subject_id}</strong> {nameOf(r.subject_id)}</td>
                      <td>{r.profile_gender || '—'}</td>
                      <td style={{ fontWeight: 700 }}>{r.fms_total ?? '—'}</td>
                      <td>{r.cmj_height_cm ?? '—'}</td>
                      <td>{r.jump_single_r ?? '—'}</td>
                      <td>{r.jump_triple_r ?? '—'}</td>
                      <td>{r.ybt_left_ant ?? '—'}</td>
                      <td>{r.ybt_right_ant ?? '—'}</td>
                      <td>{r.lactate_pre ?? '—'}</td>
                      <td>{r.lactate_post5 ?? '—'}</td>
                      <td>{r.cop_left_ellipse_area ?? '—'}</td>
                    </tr>
                  ))}
                  {pretest.length === 0 && (
                    <tr><td colSpan={11} className="empty">暂无前测数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === 'fatigue' && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 14 }}>
            <div className="card stat-card">
              <div className="stat-number">{fatigue.length}</div>
              <div className="stat-label">测试记录</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">{uniqueSubjects(fatigue, 'subject_id')}</div>
              <div className="stat-label">覆盖运动员</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">
                {fatigue.filter((r) => r.hrv_sdnn != null || r.hrv_rmssd != null).length}
              </div>
              <div className="stat-label">有 HRV 数据</div>
            </div>
          </div>
          {cmjOption && (
            <div className="card" style={{ marginBottom: 14 }}>
              <Chart option={cmjOption} height="260px" />
              <div className="note">CMJ 恢复趋势：72小时应接近训练前水平，未恢复提示疲劳堆积。</div>
            </div>
          )}
          <div className="card">
            <div className="card-title">急性疲劳恢复记录</div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>运动员</th>
                    <th>负荷%</th>
                    <th>干预</th>
                    <th>CMJ前</th>
                    <th>CMJ 24h</th>
                    <th>CMJ 72h</th>
                    <th>VAS 24h</th>
                    <th>RPE 24h</th>
                    <th>HRV SDNN</th>
                    <th>HRV RMSSD</th>
                  </tr>
                </thead>
                <tbody>
                  {fatigue.map((r) => (
                    <tr key={r.id}>
                      <td><strong>{r.subject_id}</strong> {nameOf(r.subject_id)}</td>
                      <td>{r.load_pct ?? '—'}</td>
                      <td>{r.intervention || '—'}</td>
                      <td>{r.cmj_pre ?? '—'}</td>
                      <td>{r.cmj_24h ?? '—'}</td>
                      <td style={{ fontWeight: 700 }}>{r.cmj_72h ?? '—'}</td>
                      <td>{r.vas_24h ?? '—'}</td>
                      <td>{r.rpe_24h ?? '—'}</td>
                      <td>{r.hrv_sdnn ?? '—'}</td>
                      <td>{r.hrv_rmssd ?? '—'}</td>
                    </tr>
                  ))}
                  {fatigue.length === 0 && (
                    <tr><td colSpan={10} className="empty">暂无急性疲劳数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === 'daily' && (
        <>
          <div className="grid cols-3" style={{ marginBottom: 14 }}>
            <div className="card stat-card">
              <div className="stat-number">{daily.length}</div>
              <div className="stat-label">成绩记录</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">{dailyByType.length}</div>
              <div className="stat-label">测试项目</div>
            </div>
            <div className="card stat-card">
              <div className="stat-number">{uniqueSubjects(daily, 'athlete_id')}</div>
              <div className="stat-label">覆盖运动员</div>
            </div>
          </div>
          <div className="card">
            <div className="card-title">
              日常训练成绩
              <span className="hint"><a href="/training">前往训练录入页 →</a></span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>运动员</th>
                    <th>测试项目</th>
                    <th>成绩</th>
                    <th>单位</th>
                    <th>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {daily.map((d) => (
                    <tr key={d.id}>
                      <td>{d.entry_date || '—'}</td>
                      <td><strong>{d.athlete_id}</strong> {d.athlete_name || nameOf(d.athlete_id)}</td>
                      <td><span className="badge blue">{d.test_type}</span></td>
                      <td style={{ fontWeight: 700 }}>{d.value}</td>
                      <td>{d.unit || '—'}</td>
                      <td>{d.note || '—'}</td>
                    </tr>
                  ))}
                  {daily.length === 0 && (
                    <tr>
                      <td colSpan={6} className="empty">
                        暂无日常成绩，前往训练录入页添加（如 30m、500m 计时、CMJ 跳高等）。
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

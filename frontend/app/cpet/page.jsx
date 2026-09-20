'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Guide from '@/components/Guide';
import Hint from '@/components/Hint';

const GUIDE_ROWS = [
  { name: '相对摄氧量 VO2/kg', calc: '峰值摄氧量（L/min）÷ 体重（kg），递增负荷至力竭的最大摄氧速率', read: '越高越好，反映每公斤体重有氧供能上限', color: '#0071e3' },
  { name: 'VE/VCO2 斜率', calc: '运动全程通气量 VE 对 CO2 产量 VCO2 线性回归的斜率', read: '越低越好（<30 优秀），斜率小=呼吸经济性好', color: '#34c759' },
  { name: 'VT1% 耐力储备', calc: '第一通气阈（VE/VO2 开始上升点）摄氧量 ÷ VO2peak ×100%', read: '越高越好（≥70% 良好），无氧启动越晚', color: '#af52de' },
  { name: 'RER 呼吸交换率', calc: 'VCO2 ÷ VO2 峰值', read: '≥1.05 有效测试；1.00-1.05 亚极量（峰值可能低估）', color: '#e58f4f' },
  { name: '有效性分级', calc: '有效=RER≥1.05 且运动≥180s；亚极量=RER 1.00-1.05；无效=无有效 VO2', read: '绿/橙/灰 对应 有效/亚极量/无效' },
  { name: '复测趋势 Δ', calc: '同一人末次 VO2/kg − 首次 VO2/kg', read: 'Δ>2 进步、Δ<-2 退步；反映训练效果与测试熟悉度' },
];

export default function CpetPage() {
  const [tests, setTests] = useState([]);
  const [ranking, setRanking] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [selected, setSelected] = useState('');
  const [athleteCpet, setAthleteCpet] = useState(null);
  const [trends, setTrends] = useState(null);
  const [groupCompare, setGroupCompare] = useState(null);
  const [quality, setQuality] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.cpetTests(),
      api.cpetRanking(),
      api.participants(),
      api.cpetTrends().catch(() => null),
      api.cpetGroupCompare().catch(() => null),
      api.cpetQuality().catch(() => null),
    ])
      .then(([ts, rk, ps, tr, gc, q]) => {
        setTests(ts);
        setRanking(rk);
        setParticipants(ps);
        setTrends(tr);
        setGroupCompare(gc);
        setQuality(q);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api
      .cpetAthlete(selected)
      .then(setAthleteCpet)
      .catch(() => setAthleteCpet(null));
  }, [selected]);

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const validCount = tests.filter((t) => (t.valid_class || '').includes('有效')).length;
  const validTests = tests.filter((t) => t.vo2kg_peak != null && (t.valid_class || '').includes('有效'));
  const bestVo2 = validTests.length ? Math.max(...validTests.map((t) => t.vo2kg_peak)) : null;

  const rankOption = {
    title: { text: '最优 VO₂/kg 排名（Top 15）', textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
    tooltip: {},
    grid: { left: 56, right: 20, top: 36, bottom: 40 },
    xAxis: { type: 'value', name: 'ml/kg/min' },
    yAxis: {
      type: 'category',
      data: ranking.slice(0, 15).map((r) => `${r.subject_id} ${r.name || ''}`),
      inverse: true,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: ranking.slice(0, 15).map((r) => r.vo2kg_peak),
        itemStyle: { color: '#0071e3', borderRadius: [0, 6, 6, 0] },
        label: { show: true, position: 'right', fontSize: 11 },
      },
    ],
  };

  const athleteOption = athleteCpet && athleteCpet.length
    ? {
        title: { text: `${selected} CPET 历史 VO₂/kg`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
        tooltip: {},
        xAxis: { type: 'category', data: athleteCpet.map((t) => (t.test_start ? t.test_start.slice(0, 10) : t.id)) },
        yAxis: { type: 'value' },
        series: [
          {
            type: 'bar',
            data: athleteCpet.map((t) => t.vo2kg_peak),
            itemStyle: { color: '#34c759', borderRadius: [6, 6, 0, 0] },
            label: { show: true, position: 'top', fontSize: 11 },
          },
        ],
      }
    : null;

  // ── 复测趋势图（图）──
  const trendOption =
    trends && trends.trends && trends.trends.length
      ? {
          title: { text: `复测 VO₂/kg 变化（${trends.n_multi} 人多测，${trends.n_progress} 人进步）`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
          tooltip: {
            formatter: (p) => {
              const d = p[0].data;
              return `${d.name}（${d.first_date} → ${d.last_date}）<br>${d.first} → ${d.last} ml/kg/min<br>Δ ${d.delta > 0 ? '+' : ''}${d.delta}`;
            },
          },
          grid: { left: 60, right: 40, top: 36, bottom: 30 },
          xAxis: { type: 'value', name: 'Δ VO2/kg' },
          yAxis: { type: 'category', data: trends.trends.map((t) => t.name), inverse: true },
          series: [
            {
              type: 'bar',
              barWidth: 16,
              data: trends.trends.map((t) => ({
                name: t.name, value: t.delta, first: t.first, last: t.last,
                first_date: t.first_date, last_date: t.last_date,
                itemStyle: { color: t.delta > 0 ? '#34c759' : '#ff3b30' },
              })),
              label: { show: true, position: 'right', formatter: (p) => `${p.value > 0 ? '+' : ''}${p.value}` },
            },
          ],
        }
      : null;

  // ── 干预组箱线图（图）──
  const grpOption =
    groupCompare && groupCompare.groups && groupCompare.groups.length
      ? {
          title: { text: `干预组 VO₂/kg 对比（Kruskal-Wallis p=${groupCompare.kruskal_p != null ? groupCompare.kruskal_p.toFixed(3) : '—'}）`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
          tooltip: {},
          grid: { left: 50, right: 20, top: 36, bottom: 30 },
          xAxis: { type: 'category', data: groupCompare.groups.map((g) => `${g.group} (n=${g.n})`) },
          yAxis: { type: 'value', name: 'VO2/kg' },
          series: [
            {
              type: 'boxplot',
              data: groupCompare.groups.map((g) => [g.min, g.q1, g.median, g.q3, g.max]),
              itemStyle: { color: '#4c72b0' },
            },
          ],
        }
      : null;

  // ── 质量筛查图（图）──
  const qualityOption =
    quality && quality.n_total
      ? {
          title: { text: `数据质量筛查（共 ${quality.n_total} 人，中位 ${quality.median}）`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
          tooltip: {},
          grid: { left: 50, right: 20, top: 36, bottom: 30 },
          xAxis: { type: 'category', data: ['显著偏高 z>1.5', '显著偏低 z<-1.5', '无效测试'] },
          yAxis: { type: 'value', minInterval: 1 },
          series: [
            {
              type: 'bar',
              barWidth: 44,
              data: [
                { value: quality.high.length, itemStyle: { color: '#e58f4f' } },
                { value: quality.low.length, itemStyle: { color: '#8a94a0' } },
                { value: quality.invalid.length, itemStyle: { color: '#ff3b30' } },
              ],
              label: { show: true, position: 'top' },
            },
          ],
        }
      : null;

  return (
    <div>
      <div className="page-header">
        <div className="page-title">最大摄氧量 CPET</div>
        <div className="page-desc">心肺运动试验 · VO₂max 排名 · 有效性分级</div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 14 }}>
        <div className="stat-card">
          <div className="stat-number">{tests.length}</div>
          <div className="stat-label">测试总数</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{ color: 'var(--green)' }}>{validCount}</div>
          <div className="stat-label">有效测试</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{ranking.length}</div>
          <div className="stat-label">有 VO₂ 运动员</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{ color: 'var(--accent)' }}>{bestVo2 ?? '—'}</div>
          <div className="stat-label">最优 VO₂/kg</div>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginBottom: 14 }}>
        <div className="card"><Chart option={rankOption} height="440px" /></div>
        <div className="card">
          <div className="card-title">
            运动员 CPET 详情
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
          {athleteCpet && athleteCpet.length > 0 ? (
            <>
              <Chart option={athleteOption} height="220px" />
              <div className="table-wrap" style={{ marginTop: 8 }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>分级</th>
                      <th>VO₂/kg</th>
                      <th>%预测</th>
                      <th>HR峰</th>
                    </tr>
                  </thead>
                  <tbody>
                    {athleteCpet.map((t) => (
                      <tr key={t.id}>
                        <td>{t.test_start ? t.test_start.slice(0, 10) : '—'}</td>
                        <td>
                          <span className={`badge ${(t.valid_class || '').includes('有效') ? 'ok' : (t.valid_class || '').includes('无效') ? 'danger' : 'warn'}`}>
                            {t.valid_class || '—'}
                          </span>
                        </td>
                        <td style={{ fontWeight: 600 }}>{t.vo2kg_peak ?? '—'}</td>
                        <td>{t.vo2kg_pctnorm != null ? `${Math.round(t.vo2kg_pctnorm)}%` : '—'}</td>
                        <td>{t.hr_peak ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="empty">选择运动员查看 CPET 详情</div>
          )}
        </div>
      </div>

      {/* 图化分析：复测趋势 + 干预组 + 质量 */}
      <div className="grid cols-2" style={{ marginBottom: 14 }}>
        {trendOption && (
          <div className="card">
            <Chart option={trendOption} height="360px" />
            <Hint text="柱子向右（绿）= 复测进步，向左（红）= 退步；橙条说明这次没测出真实水平，数字会偏低" />
          </div>
        )}
        {grpOption && (
          <div className="card">
            <Chart option={grpOption} height="360px" />
            <Hint text="三个箱子重叠越多 = 三组有氧能力越接近；p&lt;0.05 才说明组间真有差距" />
          </div>
        )}
      </div>
      {qualityOption && (
        <div className="card" style={{ marginBottom: 14 }}>
          <Chart option={qualityOption} height="300px" />
          <Hint text="偏高名单先复核设备校准，别急着夸；偏低/无效名单优先安排复测" />
          {quality && (quality.high.length > 0 || quality.low.length > 0 || quality.invalid.length > 0) && (
            <div className="note" style={{ marginTop: 8 }}>
              偏高：{quality.high.map((h) => h.name).join('、') || '无'}（建议复核校准）
              {' · '}偏低：{quality.low.map((l) => l.name).join('、') || '无'}（多为亚极量，建议复测）
              {' · '}无效：{quality.invalid.join('、') || '无'}
            </div>
          )}
        </div>
      )}
      <Guide rows={GUIDE_ROWS} title="CPET 指标计算逻辑与解读指南" />

      <div className="card">
        <div className="card-title">
          VO₂max 排名
          <span className="hint">按每人最优有效测试排序</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>运动员</th>
                <th>姓名</th>
                <th>VO₂/kg</th>
                <th>%预测</th>
                <th>HR峰</th>
                <th>分级</th>
                <th>测试日期</th>
              </tr>
            </thead>
            <tbody>
              {ranking.map((r) => (
                <tr key={r.subject_id}>
                  <td>{r.rank}</td>
                  <td><strong>{r.subject_id}</strong></td>
                  <td>{r.name || '—'}</td>
                  <td style={{ fontWeight: 700, color: 'var(--accent)' }}>{r.vo2kg_peak}</td>
                  <td>{r.vo2kg_pctnorm != null ? `${Math.round(r.vo2kg_pctnorm)}%` : '—'}</td>
                  <td>{r.hr_peak ?? '—'}</td>
                  <td>
                    <span className={`badge ${r.valid ? 'ok' : 'warn'}`}>{r.valid_class || '—'}</span>
                  </td>
                  <td>{r.test_start ? r.test_start.slice(0, 10) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          有效性分级口径：RER≥1.05 且递增负荷运动≥3 分钟 = 有效；RER 1.00–1.05 = 亚极量；未完成运动 = 无效。
        </div>
      </div>
    </div>
  );
}

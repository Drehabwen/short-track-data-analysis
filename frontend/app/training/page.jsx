'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';
import { COACH_TRAINING_TABS } from '@/lib/coach-workspace.mjs';
const PARTS = ['膝', '踝', '腰', '肩', '肘', '腕', '大腿', '小腿', '足', '其他'];
const LEVELS = ['轻', '中', '重'];
const INJ_STATUS = ['治疗中', '康复中', '已恢复'];

const EMPTY = {
  entry_date: new Date().toISOString().slice(0, 10),
  session_name: '',
  test_type: '500m计时',
  athlete_id: '',
  value: '',
  unit: 's',
  note: '',
};
const EMPTY_INJ = {
  injury_date: new Date().toISOString().slice(0, 10),
  athlete_id: '',
  part: '膝',
  injury_level: '轻',
  diagnosis: '',
  status: '治疗中',
  note: '',
};

export default function TrainingPage() {
  const [tab, setTab] = useState('score');
  const [types, setTypes] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [entries, setEntries] = useState([]);
  const [injuries, setInjuries] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [formInj, setFormInj] = useState(EMPTY_INJ);
  const [filters, setFilters] = useState({ athlete_id: '', test_type: '' });
  const [trend, setTrend] = useState(null);
  const [trendAthlete, setTrendAthlete] = useState('');
  const [trendType, setTrendType] = useState('');
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    Promise.all([api.trainingTypes(), api.participants(), api.trainingEntries(filters)])
      .then(([ts, ps, es]) => {
        setTypes(ts);
        setParticipants(ps.filter((p) => p.name));
        setEntries(es);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, []);

  // 当前 Tab 的项目列表
  const catTypes = types.filter((t) => (tab === 'score' ? t.category === '成绩' : t.category === '体能'));
  // 切换 Tab 时更新表单项目
  useEffect(() => {
    if (catTypes.length && !catTypes.some((t) => t.name === form.test_type)) {
      const first = catTypes[0];
      setForm((f) => ({ ...f, test_type: first.name, unit: first.unit }));
    }
  }, [tab]);

  const unitFor = (name) => {
    const t = types.find((x) => x.name === name);
    return t ? t.unit : 's';
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setMsg('');
    if (!form.athlete_id || form.value === '') {
      setError('请选择运动员并填写成绩');
      return;
    }
    try {
      await api.trainingEntriesCreate([
        {
          athlete_id: form.athlete_id,
          entry_date: form.entry_date,
          session_name: form.session_name,
          test_type: form.test_type,
          value: parseFloat(form.value),
          unit: form.unit || unitFor(form.test_type),
          note: form.note,
        },
      ]);
      setMsg('已录入 ✓');
      setForm({ ...EMPTY, entry_date: form.entry_date, test_type: form.test_type, unit: unitFor(form.test_type) });
      api.trainingEntries(filters).then(setEntries).catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  };

  const submitInj = async (e) => {
    e.preventDefault();
    setError('');
    setMsg('');
    if (!formInj.athlete_id) {
      setError('请选择运动员');
      return;
    }
    try {
      await api.injuryCreate(formInj);
      setMsg('伤病已记录 ✓');
      setFormInj({ ...EMPTY_INJ, injury_date: formInj.injury_date });
      api.injuries().then(setInjuries).catch(() => {});
    } catch (err) {
      setError(err.message);
    }
  };

  const updateInjStatus = async (id, status) => {
    await api.injuryUpdate(id, { status });
    api.injuries().then(setInjuries).catch(() => {});
  };

  useEffect(() => {
    if (!trendAthlete) return;
    api.trainingEntriesAthlete(trendAthlete).then(setTrend).catch(() => {});
  }, [trendAthlete]);

  const trendTypes = trend ? Object.keys(trend.by_type) : [];
  const trendOption =
    trend && trendType && trend.by_type[trendType] && trend.by_type[trendType].length
      ? {
          title: { text: `${trendAthlete} ${trendType} 趋势`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
          tooltip: { trigger: 'axis' },
          grid: { left: 50, right: 20, top: 36, bottom: 30 },
          xAxis: { type: 'category', data: trend.by_type[trendType].map((p) => p.date) },
          yAxis: { type: 'value' },
          series: [
            {
              type: 'line',
              data: trend.by_type[trendType].map((p) => p.value),
              smooth: true,
              lineStyle: { width: 2.5, color: '#0071e3' },
              itemStyle: { color: '#0071e3' },
              label: { show: true, position: 'top', fontSize: 10 },
            },
          ],
        }
      : null;

  const LV_COLOR = { 轻: '#ff9500', 中: '#ff3b30', 重: '#8b0000' };
  const ST_COLOR = { 治疗中: '#ff3b30', 康复中: '#ff9500', 已恢复: '#34c759' };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">训练数据录入</div>
          <div className="page-desc">训练后补录：成绩 · 专项体能 · 身体成分</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="note" style={{ color: 'var(--green)', marginBottom: 10 }}>{msg}</div>}

      {/* 教练端首期：成绩 / 体能 */}
      <div className="tabbar" style={{ marginBottom: 14 }}>
        {COACH_TRAINING_TABS.map((t) => (
          <button
            key={t.key}
            className={`tabbtn ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
            <span className="tabbtn-desc">{t.desc}</span>
          </button>
        ))}
      </div>

      {/* ═══ 成绩 / 体能 录入（共用表单，项目不同）═══ */}
      {(tab === 'score' || tab === 'fitness') && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">{tab === 'score' ? '录入训练成绩' : '录入体能数据'}</div>
            <form onSubmit={submit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 10 }}>
                <input className="input" type="date" value={form.entry_date} onChange={(e) => setForm({ ...form, entry_date: e.target.value })} />
                <input className="input" placeholder="课名（如 8.14于教练冰上）" value={form.session_name} onChange={(e) => setForm({ ...form, session_name: e.target.value })} />
                <select className="select" value={form.test_type} onChange={(e) => setForm({ ...form, test_type: e.target.value, unit: unitFor(e.target.value) })}>
                  {catTypes.map((t) => (
                    <option key={t.name} value={t.name}>{t.name}</option>
                  ))}
                </select>
                <select className="select" value={form.athlete_id} onChange={(e) => setForm({ ...form, athlete_id: e.target.value })}>
                  <option value="">选择运动员</option>
                  {participants.map((p) => (
                    <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
                  ))}
                </select>
                <input className="input" placeholder="数值" type="number" step="any" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
                <input className="input" placeholder="单位" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} style={{ width: 70 }} />
                <input className="input" placeholder="备注" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
              </div>
              <div style={{ marginTop: 12 }}>
                <button className="btn btn-primary" type="submit">保存</button>
              </div>
            </form>
            <Hint text={tab === 'score' ? '计时类（500m/冲刺）越小越好；折返跑也越小越好' : '跳远/力量/CMJ 越大越好；FMS≥14 达标；体重/体脂直接记录'} />
          </div>

          <div className="grid cols-2" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="card-title">
                个人趋势
                <select className="select" value={trendAthlete} onChange={(e) => setTrendAthlete(e.target.value)} style={{ marginLeft: 8 }}>
                  <option value="">选择运动员</option>
                  {participants.map((p) => (
                    <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
                  ))}
                </select>
                {trendTypes.length > 0 && (
                  <select className="select" value={trendType} onChange={(e) => setTrendType(e.target.value)} style={{ marginLeft: 8 }}>
                    <option value="">选择项目</option>
                    {trendTypes.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                )}
              </div>
              {trendOption ? (
                <Chart option={trendOption} height="280px" />
              ) : (
                <div className="empty">选择运动员和项目查看趋势</div>
              )}
            </div>

            <div className="card">
              <div className="card-title">
                已录{tab === 'score' ? '成绩' : '体能'}记录
                <select className="select" value={filters.athlete_id} onChange={(e) => setFilters({ ...filters, athlete_id: e.target.value })} style={{ marginLeft: 8 }}>
                  <option value="">全部</option>
                  {participants.map((p) => (
                    <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
                  ))}
                </select>
              </div>
              <div className="table-wrap" style={{ maxHeight: 300, overflowY: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr><th>日期</th><th>运动员</th><th>项目</th><th>成绩</th><th>课名</th></tr>
                  </thead>
                  <tbody>
                    {entries
                      .filter((e) => catTypes.some((t) => t.name === e.test_type))
                      .map((e) => (
                        <tr key={e.id}>
                          <td>{e.entry_date}</td>
                          <td>{e.athlete_name || e.athlete_id}</td>
                          <td>{e.test_type}</td>
                          <td style={{ fontWeight: 600 }}>{e.value} {e.unit}</td>
                          <td style={{ fontSize: 11 }}>{e.session_name || '—'}</td>
                        </tr>
                      ))}
                    {entries.filter((e) => catTypes.some((t) => t.name === e.test_type)).length === 0 && (
                      <tr><td colSpan={5} className="empty">暂无记录</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ═══ 伤病录入 ═══ */}
      {tab === 'injury' && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">伤病记录</div>
            <form onSubmit={submitInj}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
                <input className="input" type="date" value={formInj.injury_date} onChange={(e) => setFormInj({ ...formInj, injury_date: e.target.value })} />
                <select className="select" value={formInj.athlete_id} onChange={(e) => setFormInj({ ...formInj, athlete_id: e.target.value })}>
                  <option value="">运动员</option>
                  {participants.map((p) => (
                    <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
                  ))}
                </select>
                <select className="select" value={formInj.part} onChange={(e) => setFormInj({ ...formInj, part: e.target.value })}>
                  {PARTS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <select className="select" value={formInj.injury_level} onChange={(e) => setFormInj({ ...formInj, injury_level: e.target.value })}>
                  {LEVELS.map((l) => <option key={l} value={l}>{l}度</option>)}
                </select>
                <input className="input" placeholder="诊断（如 髌腱炎/扭伤）" value={formInj.diagnosis} onChange={(e) => setFormInj({ ...formInj, diagnosis: e.target.value })} />
                <select className="select" value={formInj.status} onChange={(e) => setFormInj({ ...formInj, status: e.target.value })}>
                  {INJ_STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input className="input" placeholder="备注" value={formInj.note} onChange={(e) => setFormInj({ ...formInj, note: e.target.value })} />
              </div>
              <div style={{ marginTop: 12 }}>
                <button className="btn btn-primary" type="submit">记录伤病</button>
              </div>
            </form>
            <Hint text="伤病必须记录：部位 + 程度 + 诊断；恢复后把状态改为「已恢复」——伤病史是防伤的重要依据" />
          </div>

          <div className="card">
            <div className="card-title">伤病记录列表（{injuries.length} 条）</div>
            <div className="table-wrap" style={{ maxHeight: 420, overflowY: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr><th>日期</th><th>运动员</th><th>部位</th><th>程度</th><th>诊断</th><th>状态</th><th>备注</th></tr>
                </thead>
                <tbody>
                  {injuries.map((r) => (
                    <tr key={r.id}>
                      <td>{r.injury_date}</td>
                      <td><strong>{r.athlete_name || r.athlete_id}</strong></td>
                      <td>{r.part}</td>
                      <td>
                        <span className="badge" style={{ background: LV_COLOR[r.injury_level] + '22', color: LV_COLOR[r.injury_level], fontWeight: 700 }}>
                          {r.injury_level}
                        </span>
                      </td>
                      <td>{r.diagnosis || '—'}</td>
                      <td>
                        <select
                          className="select"
                          style={{ fontSize: 11, padding: '2px 4px', color: ST_COLOR[r.status] }}
                          value={r.status}
                          onChange={(e) => updateInjStatus(r.id, e.target.value)}
                        >
                          {INJ_STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td style={{ fontSize: 11 }}>{r.note || '—'}</td>
                    </tr>
                  ))}
                  {injuries.length === 0 && (
                    <tr><td colSpan={7} className="empty">暂无伤病记录</td></tr>
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

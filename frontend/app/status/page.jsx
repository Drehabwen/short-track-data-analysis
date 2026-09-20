'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

const EMPTY = {
  athlete_id: '',
  status_date: new Date().toISOString().slice(0, 10),
  sleep_hours: 7,
  fatigue: 5,
  morning_hr: '',
  weight_kg: '',
  muscle_soreness: 3,
  injury: '无',
  self_rating: 5,
  note: '',
};

export default function StatusPage() {
  const { user } = useAuth();
  const isCoach = user?.role === 'coach' || user?.role === 'admin';
  const isAthlete = user?.role === 'athlete';
  const [participants, setParticipants] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [team, setTeam] = useState(null);
  const [history, setHistory] = useState(null);
  const [histId, setHistId] = useState('');
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.participants().then((ps) => setParticipants(ps.filter((p) => p.name))).catch(() => {});
    if (isCoach) {
      api.statusTeam().then(setTeam).catch(() => {});
    }
    if (isAthlete) {
      const myId = user?.athlete_id || '';
      setForm((f) => ({ ...f, athlete_id: myId }));
      setHistId(myId);
    }
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setMsg('');
    if (!form.athlete_id) {
      setError('请选择运动员');
      return;
    }
    try {
      const r = await api.statusReport({
        athlete_id: form.athlete_id,
        status_date: form.status_date,
        sleep_hours: parseFloat(form.sleep_hours) || null,
        fatigue: parseInt(form.fatigue) || null,
        morning_hr: form.morning_hr ? parseInt(form.morning_hr) : null,
        weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : null,
        muscle_soreness: parseInt(form.muscle_soreness) || null,
        injury: form.injury,
        self_rating: parseInt(form.self_rating) || null,
        note: form.note,
      });
      setMsg(`${r.athlete_id} ${r.status_date} 已上报 ✓`);
      if (isCoach) {
        api.statusTeam(form.status_date).then(setTeam).catch(() => {});
      }
      if (isAthlete) {
        api.statusAthlete(user?.athlete_id).then(setHistory).catch(() => {});
      }
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (!histId) return;
    api.statusAthlete(histId).then(setHistory).catch(() => {});
  }, [histId]);

  const trendOption =
    history && history.length > 1
      ? {
          title: { text: `${histId} 近期状态趋势`, textStyle: { fontSize: 13, color: '#1d1d1f', fontWeight: 600 } },
          tooltip: { trigger: 'axis' },
          legend: { top: 0, data: ['睡眠(h)', '疲劳(1-10)', '酸痛(1-10)', '自评(1-10)'] },
          grid: { left: 40, right: 20, top: 36, bottom: 30 },
          xAxis: { type: 'category', data: history.map((h) => h.date) },
          yAxis: { type: 'value' },
          series: [
            { name: '睡眠(h)', type: 'line', data: history.map((h) => h.sleep_hours), smooth: true },
            { name: '疲劳(1-10)', type: 'line', data: history.map((h) => h.fatigue), smooth: true, lineStyle: { color: '#ff3b30' } },
            { name: '酸痛(1-10)', type: 'line', data: history.map((h) => h.muscle_soreness), smooth: true },
            { name: '自评(1-10)', type: 'line', data: history.map((h) => h.self_rating), smooth: true },
          ],
        }
      : null;

  const score = (v) => v ?? '—';

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">每日状态上报</div>
          <div className="page-desc">运动员自评 · 教练全队状态看板（睡眠/疲劳/晨脉/酸痛/伤病）</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="note" style={{ color: 'var(--green)', marginBottom: 10 }}>{msg}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">状态上报（每天 1 次，重复提交=覆盖）</div>
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            {isAthlete ? (
              <label className="input-label">
                运动员
                <input className="input" value={form.athlete_id} disabled />
              </label>
            ) : (
              <select className="select" value={form.athlete_id} onChange={(e) => setForm({ ...form, athlete_id: e.target.value })}>
                <option value="">运动员</option>
                {participants.map((p) => (
                  <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
                ))}
              </select>
            )}
            <input className="input" type="date" value={form.status_date} onChange={(e) => setForm({ ...form, status_date: e.target.value })} />
            <label className="input-label">睡眠(h) <input className="input" type="number" step="0.5" value={form.sleep_hours} onChange={(e) => setForm({ ...form, sleep_hours: e.target.value })} /></label>
            <label className="input-label">疲劳(1-10) <input className="input" type="number" min="1" max="10" value={form.fatigue} onChange={(e) => setForm({ ...form, fatigue: e.target.value })} /></label>
            <label className="input-label">晨脉(bpm) <input className="input" type="number" value={form.morning_hr} onChange={(e) => setForm({ ...form, morning_hr: e.target.value })} /></label>
            <label className="input-label">体重(kg) <input className="input" type="number" step="0.1" value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: e.target.value })} /></label>
            <label className="input-label">肌肉酸痛(1-10) <input className="input" type="number" min="1" max="10" value={form.muscle_soreness} onChange={(e) => setForm({ ...form, muscle_soreness: e.target.value })} /></label>
            <label className="input-label">伤病
              <select className="select" value={form.injury} onChange={(e) => setForm({ ...form, injury: e.target.value })}>
                <option value="无">无</option>
                <option value="轻">轻</option>
                <option value="中">中</option>
                <option value="重">重</option>
              </select>
            </label>
            <label className="input-label">训练自评(1-10) <input className="input" type="number" min="1" max="10" value={form.self_rating} onChange={(e) => setForm({ ...form, self_rating: e.target.value })} /></label>
            <input className="input" placeholder="备注（部位/情况）" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" type="submit">提交今日状态</button>
          </div>
        </form>
        <Hint text="疲劳/酸痛 ≥7 或伤病非「无」→ 会在看板标红，教练据此调整当天训练量" />
      </div>

      {isCoach && (
      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">
            全队今日状态（{team ? `${team.reported} 人上报 · ${team.flagged} 人需关注` : ''}）
            <input className="input" type="date" style={{ marginLeft: 8, width: 140 }} defaultValue={new Date().toISOString().slice(0, 10)}
              onChange={(e) => api.statusTeam(e.target.value).then(setTeam).catch(() => {})} />
          </div>
          <div className="table-wrap" style={{ maxHeight: 380, overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr><th>运动员</th><th>教练</th><th>睡眠</th><th>疲劳</th><th>晨脉</th><th>酸痛</th><th>伤病</th><th>自评</th><th>状态</th></tr>
              </thead>
              <tbody>
                {(team?.rows || []).map((r) => (
                  <tr key={r.athlete_id} style={r.flag ? { background: '#fff5f5' } : undefined}>
                    <td><strong>{r.name}</strong> <span className="note">{r.athlete_id}</span></td>
                    <td style={{ fontSize: 11 }}>{r.coach || '—'}</td>
                    <td>{score(r.sleep_hours)}h</td>
                    <td style={{ color: r.fatigue >= 7 ? '#ff3b30' : undefined, fontWeight: r.fatigue >= 7 ? 700 : 400 }}>{score(r.fatigue)}</td>
                    <td>{score(r.morning_hr)}</td>
                    <td style={{ color: r.muscle_soreness >= 7 ? '#ff3b30' : undefined }}>{score(r.muscle_soreness)}</td>
                    <td style={{ color: r.injury && r.injury !== '无' ? '#ff3b30' : undefined }}>{r.injury || '—'}</td>
                    <td>{score(r.self_rating)}</td>
                    <td>
                      {r.flag ? <span className="badge danger">{r.flag}</span> : <span className="badge ok">正常</span>}
                    </td>
                  </tr>
                ))}
                {team && team.reported === 0 && (
                  <tr><td colSpan={9} className="empty">今日暂无上报</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Hint text="红行 = 需关注（疲劳/酸痛高或伤病），建议降负荷或安排恢复；全队亮绿 = 可以正常练" />
        </div>

        <div className="card">
          <div className="card-title">
            个人状态趋势
            <select className="select" value={histId} onChange={(e) => setHistId(e.target.value)} style={{ marginLeft: 8 }}>
              <option value="">选择运动员</option>
              {participants.map((p) => (
                <option key={p.participant_id} value={p.participant_id}>{p.participant_id} {p.name}</option>
              ))}
            </select>
          </div>
          {trendOption ? (
            <Chart option={trendOption} height="320px" />
          ) : (
            <div className="empty">选择运动员查看状态趋势（需 ≥2 天上报）</div>
          )}
          <Hint text="睡眠下降+疲劳上升 = 疲劳累积信号；晨脉持续偏高 = 恢复不足，建议减量" />
        </div>
      </div>
      )}

      {isAthlete && (
        <div className="card">
          <div className="card-title">我的状态趋势</div>
          {trendOption ? (
            <Chart option={trendOption} height="300px" />
          ) : (
            <div className="empty">连续上报 ≥2 天即可查看趋势</div>
          )}
        </div>
      )}
    </div>
  );
}

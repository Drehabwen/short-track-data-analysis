'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Hint from '@/components/Hint';

const TYPES = ['冰上', '陆地', '力量', '技术', '恢复'];
const INTENSITY = ['低', '中', '高'];
const STATUS = ['计划', '已执行', '取消'];
const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

const INT_COLOR = { 低: '#34c759', 中: '#ff9500', 高: '#ff3b30' };
const STATUS_COLOR = { 计划: '#0071e3', 已执行: '#34c759', 取消: '#8a94a0' };

const emptyForm = {
  plan_date: new Date().toISOString().slice(0, 10),
  coach: '于教练',
  session_type: '冰上',
  content: '',
  duration_min: 90,
  intensity: '中',
};

export default function PlansPage() {
  const [plans, setPlans] = useState([]);
  const [weekStart, setWeekStart] = useState(() => {
    const t = new Date();
    const d = new Date(t.getFullYear(), t.getMonth(), t.getDate() - ((t.getDay() + 6) % 7));
    return d.toISOString().slice(0, 10);
  });
  const [form, setForm] = useState(emptyForm);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = (ws) => {
    api.plans(ws).then((d) => setPlans(d.plans)).catch((e) => setError(e.message));
  };
  useEffect(() => load(weekStart), [weekStart]);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setMsg('');
    if (!form.content) {
      setError('请填写训练内容');
      return;
    }
    try {
      await api.planCreate(form);
      setMsg('已排课 ✓');
      setForm({ ...emptyForm, plan_date: form.plan_date });
      load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  };

  const setStatus = async (id, status) => {
    await api.planUpdate(id, { status });
    load(weekStart);
  };

  const del = async (id) => {
    if (!window.confirm('删除这条计划？')) return;
    await api.planDelete(id);
    load(weekStart);
  };

  // 周日期数组
  const weekDates = [];
  const ws = new Date(weekStart + 'T00:00:00');
  for (let i = 0; i < 7; i++) {
    const d = new Date(ws);
    d.setDate(ws.getDate() + i);
    weekDates.push(d.toISOString().slice(0, 10));
  }
  const shiftWeek = (n) => {
    const d = new Date(weekStart + 'T00:00:00');
    d.setDate(d.getDate() + n * 7);
    setWeekStart(d.toISOString().slice(0, 10));
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">训练计划</div>
          <div className="page-desc">教练排课 · 周视图 · 标记执行情况</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="note" style={{ color: 'var(--green)', marginBottom: 10 }}>{msg}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">排课</div>
        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10 }}>
            <input className="input" type="date" value={form.plan_date} onChange={(e) => setForm({ ...form, plan_date: e.target.value })} />
            <select className="select" value={form.coach} onChange={(e) => setForm({ ...form, coach: e.target.value })}>
              {['于教练', '陈教练', '张教练', '李教练', '姚教练组(尹教练)'].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select className="select" value={form.session_type} onChange={(e) => setForm({ ...form, session_type: e.target.value })}>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input className="input" placeholder="训练内容（如 500m 弯道技术+计时）" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} style={{ minWidth: 180 }} />
            <input className="input" type="number" placeholder="时长(分)" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: parseInt(e.target.value) || 0 })} style={{ width: 80 }} />
            <select className="select" value={form.intensity} onChange={(e) => setForm({ ...form, intensity: e.target.value })}>
              {INTENSITY.map((t) => <option key={t} value={t}>{t}强度</option>)}
            </select>
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" type="submit">排课</button>
          </div>
        </form>
      </div>

      <div className="card">
        <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => shiftWeek(-1)}>‹ 上周</button>
          <span>{weekStart} ~ {weekDates[6]}</span>
          <button className="btn btn-ghost" onClick={() => shiftWeek(1)}>下周 ›</button>
        </div>
        <div className="plan-grid">
          {weekDates.map((date, i) => {
            const dayPlans = plans.filter((p) => p.plan_date === date);
            return (
              <div key={date} className="plan-day">
                <div className="plan-day-head">{WEEKDAYS[i]} <span className="plan-date">{date.slice(5)}</span></div>
                {dayPlans.length === 0 && <div className="plan-empty">—</div>}
                {dayPlans.map((p) => (
                  <div key={p.id} className="plan-item">
                    <div className="plan-item-top">
                      <span className="plan-coach">{p.coach}</span>
                      <span className="plan-type">{p.session_type}</span>
                      <span className="plan-int" style={{ color: INT_COLOR[p.intensity] || '#86868b' }}>{p.intensity}</span>
                      <span className="plan-dur">{p.duration_min}min</span>
                    </div>
                    <div className="plan-content">{p.content}</div>
                    <div className="plan-item-bot">
                      <select
                        className="select"
                        style={{ fontSize: 11, padding: '2px 4px' }}
                        value={p.status}
                        onChange={(e) => setStatus(p.id, e.target.value)}
                      >
                        {STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <button className="btn btn-ghost" style={{ fontSize: 11, padding: '2px 6px' }} onClick={() => del(p.id)}>删</button>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <Hint text="计划 → 训练时 → 练完标记「已执行」，取消则标「取消」；强度红=高 橙=中 绿=低" />
      </div>
    </div>
  );
}

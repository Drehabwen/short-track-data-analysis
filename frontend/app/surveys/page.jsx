'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

export default function SurveysPage() {
  const [list, setList] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [detail, setDetail] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: '每日心理状态',
    target_type: 'all',
    target_value: '',
    deadline: '',
  });
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = () =>
    api
      .surveys()
      .then(setList)
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
    api.participants().then(setParticipants).catch(() => {});
  }, []);

  const groups = [...new Set(participants.map((p) => p.group_name).filter(Boolean))];

  const submit = async () => {
    setError('');
    setMsg('');
    if (form.target_type !== 'all' && !form.target_value) {
      setError('请选择发放对象');
      return;
    }
    try {
      const payload = {
        title: form.title.trim() || '每日心理状态',
        target_type: form.target_type,
        target_value: form.target_type === 'all' ? null : form.target_value,
        deadline: form.deadline ? `${form.deadline}T23:59:59` : null,
      };
      await api.surveysCreate(payload);
      setMsg('问卷已发放 ✓');
      setShowForm(false);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  const openDetail = async (id) => {
    setDetail(null);
    try {
      setDetail(await api.surveyDetail(id));
    } catch (e) {
      setError(e.message);
    }
  };

  const targetLabel = (s) => {
    if (s.target_type === 'group') return `组别：${s.target_value}`;
    if (s.target_type === 'participant') return `指定：${s.target_value}`;
    return '全部运动员';
  };

  const scaleText = (v) => {
    const map = { 1: '很差/低', 2: '较差', 3: '一般', 4: '较好', 5: '很好/高' };
    return map[v] ?? v;
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">心理问卷</div>
          <div className="page-desc">发放心理问卷 · 查看回收与汇总</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? '收起' : '发放问卷'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="note" style={{ color: 'var(--green)', marginBottom: 10 }}>{msg}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title">发放新问卷（内置：每日心理状态 · 情绪/压力/睡眠/疲劳 + 备注）</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
            <input
              className="input"
              placeholder="问卷标题"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <select
              className="select"
              value={form.target_type}
              onChange={(e) => setForm({ ...form, target_type: e.target.value, target_value: '' })}
            >
              <option value="all">全部运动员</option>
              <option value="group">按组别</option>
              <option value="participant">指定运动员</option>
            </select>
            {form.target_type === 'group' && (
              <select
                className="select"
                value={form.target_value}
                onChange={(e) => setForm({ ...form, target_value: e.target.value })}
              >
                <option value="">选择组别</option>
                {groups.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            )}
            {form.target_type === 'participant' && (
              <select
                className="select"
                value={form.target_value}
                onChange={(e) => setForm({ ...form, target_value: e.target.value })}
              >
                <option value="">选择运动员</option>
                {participants.map((p) => (
                  <option key={p.participant_id} value={p.participant_id}>
                    {p.name || p.participant_id}（{p.participant_id}）
                  </option>
                ))}
              </select>
            )}
            <input
              className="input"
              type="date"
              value={form.deadline}
              onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            />
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={submit}>发放</button>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">已发放问卷</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>发放日期</th>
                <th>发放对象</th>
                <th>题目</th>
                <th>回收进度</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.title}</strong></td>
                  <td>{s.assign_date || '—'}</td>
                  <td>{targetLabel(s)}</td>
                  <td>{s.question_count} 题</td>
                  <td>
                    <span style={{ fontWeight: 700 }}>{s.answered}</span>/{s.total}
                    {s.pending_ids.length > 0 && (
                      <span className="note" style={{ marginLeft: 6 }}>
                        未填 {s.pending_ids.length}
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="btn btn-ghost" onClick={() => openDetail(s.id)}>
                      查看回收
                    </button>
                  </td>
                </tr>
              ))}
              {list.length === 0 && (
                <tr><td colSpan={6} className="empty">还没有发放过问卷</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {detail && (
        <div className="card">
          <div className="card-title">
            回收详情：{detail.title}
            <span className="hint">{targetLabel(detail)}</span>
          </div>
          <div className="note" style={{ marginBottom: 8 }}>
            题目：{detail.items.map((it, i) => `${i + 1}. ${it.text}`).join('　')}
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>运动员</th>
                  {detail.items.map((it, i) => (
                    <th key={it.id}>Q{i + 1}</th>
                  ))}
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {detail.respondents.map((r) => {
                  const has = Object.keys(r.answers).length > 0;
                  return (
                    <tr key={r.athlete_id}>
                      <td><strong>{r.name || r.athlete_id}</strong> <span className="note">{r.athlete_id}</span></td>
                      {detail.items.map((it) => {
                        const a = r.answers[it.id];
                        return (
                          <td key={it.id}>
                            {a ? (it.type === 'text' ? (a.text || '—') : scaleText(a.value)) : '—'}
                          </td>
                        );
                      })}
                      <td>
                        {has ? <span className="badge ok">已填</span> : <span className="badge warn">未填</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            Q1 心情 / Q2 压力 / Q3 睡眠 / Q4 疲劳为 1–5 分；Q5 为备注。分数含义见题目说明。
          </div>
        </div>
      )}
    </div>
  );
}

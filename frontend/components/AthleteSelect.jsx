'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export default function AthleteSelect() {
  const { selectAthlete, logout } = useAuth();
  const [list, setList] = useState([]);
  const [q, setQ] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .participants()
      .then((ps) => setList(ps))
      .catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    const kw = q.trim().toLowerCase();
    if (!kw) return list;
    return list.filter(
      (p) =>
        (p.participant_id || '').toLowerCase().includes(kw) ||
        (p.name || '').toLowerCase().includes(kw)
    );
  }, [list, q]);

  return (
    <div className="role-select">
      <div className="role-select-box athlete-select-box">
        <div className="role-brand"><img src="/speedtrack-logo.svg" alt="" aria-hidden="true" /> <span>SpeedTrack Pro</span></div>
        <h1>选择你的身份</h1>
        <p className="role-sub">在花名册中选择你的姓名进入</p>
        <input
          className="input"
          placeholder="搜索姓名或编号"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: '100%', marginBottom: 14 }}
        />
        {error && <div className="error-banner">{error}</div>}
        <div className="athlete-select-list">
          {filtered.map((p) => (
            <button
              key={p.participant_id}
              className="athlete-select-item"
              onClick={() => selectAthlete(p)}
            >
              <strong>{p.name || p.participant_id}</strong>
              <span className="note">
                {p.participant_id}
                {p.group_name ? ` · ${p.group_name}` : ''}
              </span>
            </button>
          ))}
          {!list.length && !error && <div className="empty">花名册加载中...</div>}
        </div>
        <button className="btn btn-ghost" onClick={logout} style={{ marginTop: 14 }}>
          ← 返回角色选择
        </button>
      </div>
    </div>
  );
}

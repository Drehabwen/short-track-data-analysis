'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import AthleteProfile from '@/components/AthleteProfile';

const GROUPS = ['常规恢复', '拔罐+推拿', '艾灸+推拿'];

export default function AthletesPage() {
  const { user } = useAuth();
  const [athletes, setAthletes] = useState([]);
  const [q, setQ] = useState('');
  const [group, setGroup] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [profileId, setProfileId] = useState('');
  const [form, setForm] = useState({
    participant_id: '',
    name: '',
    sex: '',
    birth_date: '',
    batch_id: '',
    group_name: '',
    id_card: '',
  });

  const load = () => {
    setLoading(true);
    setError('');
    api
      .participants({ q: q || undefined, group: group || undefined })
      .then(setAthletes)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
  }, [q, group]);

  const canEdit = user?.role === 'admin' || user?.role === 'coach';

  const openCreate = () => {
    setEditing(null);
    setForm({
      participant_id: '',
      name: '',
      sex: '',
      birth_date: '',
      batch_id: '',
      group_name: '',
      id_card: '',
    });
    setShowForm(true);
  };

  const openEdit = (a) => {
    setEditing(a);
    setForm({
      participant_id: a.participant_id,
      name: a.name || '',
      sex: a.sex || '',
      birth_date: a.birth_date ? a.birth_date.slice(0, 10) : '',
      batch_id: a.batch_id || '',
      group_name: a.group_name || '',
      id_card: a.id_card || '',
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (editing) {
        await api.updateParticipant(editing.participant_id, form);
      } else {
        await api.createParticipant(form);
      }
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (a) => {
    if (!window.confirm(`确定删除运动员 ${a.participant_id}？`)) return;
    try {
      await api.deleteParticipant(a.participant_id);
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">运动员管理</div>
          <div className="page-desc">运动员基本信息维护（共 {athletes.length} 人）</div>
        </div>
        {canEdit && (
          <button className="btn btn-primary" onClick={openCreate}>
            + 新增运动员
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">筛选</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="input"
            placeholder="搜索编号/姓名/证件号"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ width: 220 }}
          />
          <select className="select" value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">全部组别</option>
            {GROUPS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16, background: '#fbfdfc', borderColor: 'var(--primary-light)' }}>
          <div className="card-title">{editing ? `编辑 ${editing.participant_id}` : '新增运动员'}</div>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10 }}>
              <input className="input" placeholder="编号 *（如 Z05）" value={form.participant_id} onChange={(e) => setForm({ ...form, participant_id: e.target.value })} disabled={!!editing} required />
              <input className="input" placeholder="姓名" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <select className="select" value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
                <option value="">性别</option>
                <option value="男">男</option>
                <option value="女">女</option>
              </select>
              <input className="input" type="date" placeholder="出生日期" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} />
              <input className="input" placeholder="批次（如 713）" value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} />
              <select className="select" value={form.group_name} onChange={(e) => setForm({ ...form, group_name: e.target.value })}>
                <option value="">组别</option>
                {GROUPS.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
              <input className="input" placeholder="证件号" value={form.id_card} onChange={(e) => setForm({ ...form, id_card: e.target.value })} />
            </div>
            <div style={{ marginTop: 12, display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" type="submit">{editing ? '保存修改' : '创建'}</button>
              <button className="btn btn-ghost" type="button" onClick={() => setShowForm(false)}>取消</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-title">运动员列表</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>姓名</th>
                <th>性别</th>
                <th>出生日期</th>
                <th>年龄</th>
                <th>批次</th>
                <th>组别</th>
                <th>血样数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {athletes.map((a) => (
                <tr key={a.participant_id}>
                  <td><strong>{a.participant_id}</strong></td>
                  <td>{a.name || '—'}</td>
                  <td>{a.sex || '—'}</td>
                  <td>{a.birth_date ? a.birth_date.slice(0, 10) : '—'}</td>
                  <td>{a.age_years != null ? `${a.age_years} 岁` : '—'}</td>
                  <td>{a.batch_id || '—'}</td>
                  <td><span className="badge blue">{a.group_name || '未分组'}</span></td>
                  <td>{a.samples?.length ?? '—'}</td>
                  <td>
                    <button className="btn btn-primary" style={{ marginRight: 6 }} onClick={() => setProfileId(a.participant_id)}>
                      画像
                    </button>
                    {canEdit && (
                      <>
                        <button className="btn btn-ghost" style={{ marginRight: 6 }} onClick={() => openEdit(a)}>编辑</button>
                        <button className="btn btn-ghost" onClick={() => handleDelete(a)}>删除</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && athletes.length === 0 && (
                <tr>
                  <td colSpan={9} className="empty">暂无运动员</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {profileId && <AthleteProfile subjectId={profileId} onClose={() => setProfileId('')} />}
    </div>
  );
}

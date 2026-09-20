'use client';

import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

const EMPTY_FORM = {
  participant_id: '',
  competition_name: '',
  competition_date: '',
  venue: '',
  event: '', // 由后端 events 字典动态填充
  time_result: '',
  rank: '',
  note: '',
};

export default function CompetitionsPage() {
  const [records, setRecords] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('');
  const [editing, setEditing] = useState(null); // id or 'new'
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .competitions(filter ? { participant_id: filter } : {})
      .then(setRecords)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    load();
    api.participants().then(setAthletes).catch(() => {});
    api.competitionEvents().then((evs) => {
      setEvents(evs || []);
      if (evs?.length) setForm((f) => ({ ...f, event: evs[0].name }));
    }).catch(() => {});
  }, [load]);

  const startNew = () => {
    setEditing('new');
    setForm({ ...EMPTY_FORM, participant_id: filter || '' });
  };
  const startEdit = (r) => {
    setEditing(r.id);
    setForm({
      participant_id: r.participant_id,
      competition_name: r.competition_name || '',
      competition_date: r.competition_date ? r.competition_date.slice(0, 10) : '',
      venue: r.venue || '',
      event: r.event || '500m',
      time_result: r.time_result || '',
      rank: r.rank ?? '',
      note: r.note || '',
    });
  };
  const save = async () => {
    if (!form.participant_id) {
      setError('请选择运动员');
      return;
    }
    const payload = {
      ...form,
      rank: form.rank === '' ? null : Number(form.rank),
      competition_date: form.competition_date || null,
    };
    try {
      if (editing === 'new') await api.competitionCreate(payload);
      else await api.competitionUpdate(editing, payload);
      setEditing(null);
      setError('');
      load();
    } catch (e) {
      setError(`保存失败：${e.message}`);
    }
  };
  const remove = async (id) => {
    if (!window.confirm('确定删除这条参赛记录？')) return;
    try {
      await api.competitionDelete(id);
      load();
    } catch (e) {
      setError(`删除失败：${e.message}`);
    }
  };

  const fmtDate = (d) => (d ? d.slice(0, 10) : '—');
  const rankBadge = (r) =>
    r == null ? '—' : r === 1 ? <span className="badge ok">🥇 冠军</span> : r === 2 ? <span className="badge blue">🥈 亚军</span> : r === 3 ? <span className="badge amber">🥉 季军</span> : <span>{r}</span>;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">参赛记录</div>
          <div className="page-desc">短道速滑比赛成绩登记与查询</div>
        </div>
        <button className="btn btn-primary" onClick={startNew}>
          + 新增记录
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">筛选</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <select className="select" value={filter} onChange={(e) => { setFilter(e.target.value); }}>
            <option value="">全部运动员</option>
            {athletes.map((a) => (
              <option key={a.participant_id} value={a.participant_id}>
                {a.name}（{a.participant_id}）
              </option>
            ))}
          </select>
          <span className="note">共 {records.length} 条记录</span>
        </div>
      </div>

      {editing !== null && (
        <div className="card" style={{ marginBottom: 16, background: '#fdf8ee' }}>
          <div className="card-title">{editing === 'new' ? '新增参赛记录' : '编辑参赛记录'}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(170px,1fr))', gap: 10 }}>
            <label>
              <span className="note">运动员 *</span>
              <select className="select" value={form.participant_id} onChange={(e) => setForm({ ...form, participant_id: e.target.value })} style={{ width: '100%' }}>
                <option value="">— 选择 —</option>
                {athletes.map((a) => (
                  <option key={a.participant_id} value={a.participant_id}>
                    {a.name}（{a.participant_id}）
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="note">赛事名称</span>
              <input className="input" value={form.competition_name} onChange={(e) => setForm({ ...form, competition_name: e.target.value })} placeholder="如 全国短道速滑锦标赛" style={{ width: '100%' }} />
            </label>
            <label>
              <span className="note">比赛日期</span>
              <input className="input" type="date" value={form.competition_date} onChange={(e) => setForm({ ...form, competition_date: e.target.value })} style={{ width: '100%' }} />
            </label>
            <label>
              <span className="note">项目</span>
              <select className="select" value={form.event} onChange={(e) => setForm({ ...form, event: e.target.value })} style={{ width: '100%' }}>
                {events.length === 0 && <option value="">— 无项目配置 —</option>}
                {events.map((ev) => (
                  <option key={ev.name} value={ev.name}>{ev.label || ev.name}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="note">成绩（如 47.80 或 1:23.45）</span>
              <input className="input" value={form.time_result} onChange={(e) => setForm({ ...form, time_result: e.target.value })} placeholder="47.80" style={{ width: '100%' }} />
            </label>
            <label>
              <span className="note">名次</span>
              <input className="input" type="number" min="1" value={form.rank} onChange={(e) => setForm({ ...form, rank: e.target.value })} placeholder="1" style={{ width: '100%' }} />
            </label>
            <label>
              <span className="note">地点</span>
              <input className="input" value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} placeholder="北京" style={{ width: '100%' }} />
            </label>
            <label style={{ gridColumn: 'span 2' }}>
              <span className="note">备注</span>
              <input className="input" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="备注" style={{ width: '100%' }} />
            </label>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" onClick={save}>保存</button>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">记录列表</div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>运动员</th>
                <th>赛事</th>
                <th>项目</th>
                <th>成绩</th>
                <th>名次</th>
                <th>地点</th>
                <th>备注</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>{fmtDate(r.competition_date)}</td>
                  <td><strong>{r.name}</strong> <span className="dim">({r.participant_id})</span></td>
                  <td>{r.competition_name || '—'}</td>
                  <td><span className="badge blue">{r.event || '—'}</span></td>
                  <td><strong>{r.time_result || '—'}</strong></td>
                  <td>{rankBadge(r.rank)}</td>
                  <td>{r.venue || '—'}</td>
                  <td className="dim">{r.note || '—'}</td>
                  <td>
                    <button className="btn btn-ghost" onClick={() => startEdit(r)}>编辑</button>
                    <button className="btn btn-ghost" style={{ color: '#c0392b' }} onClick={() => remove(r.id)}>删除</button>
                  </td>
                </tr>
              ))}
              {!loading && records.length === 0 && (
                <tr>
                  <td colSpan={9} className="empty">暂无参赛记录，点击右上角"新增记录"。</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

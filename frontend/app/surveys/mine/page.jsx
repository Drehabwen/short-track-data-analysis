'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

const SCALE_LABELS = {
  1: '很差',
  2: '较差',
  3: '一般',
  4: '较好',
  5: '很好',
};

export default function MySurveysPage() {
  const { user } = useAuth();
  const athleteId = user?.athlete_id || '';
  const [list, setList] = useState([]);
  const [detail, setDetail] = useState(null);
  const [answers, setAnswers] = useState({});
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    if (!athleteId) return;
    api
      .mySurveys(athleteId)
      .then(setList)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    load();
  }, [athleteId]);

  const openSurvey = async (id) => {
    setError('');
    setMsg('');
    try {
      const d = await api.surveyDetail(id);
      setDetail(d);
      const mine = d.respondents.find((r) => r.athlete_id === athleteId);
      const init = {};
      if (mine) {
        Object.entries(mine.answers).forEach(([itemId, a]) => {
          init[itemId] = a.value ?? a.text ?? '';
        });
      }
      setAnswers(init);
    } catch (e) {
      setError(e.message);
    }
  };

  const submit = async () => {
    if (!detail) return;
    try {
      const payload = {
        athlete_id: athleteId,
        answers: detail.items.map((it) => ({
          item_id: it.id,
          value: it.type === 'text' ? null : answers[it.id] != null ? Number(answers[it.id]) : null,
          text: it.type === 'text' ? answers[it.id] || null : null,
        })),
      };
      await api.surveyRespond(detail.id, payload);
      setMsg('提交成功，感谢填写 ✓');
      setDetail(null);
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">我的问卷</div>
          <div className="page-desc">填写教练发放的心理问卷 · 结果会同步给教练</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="note" style={{ color: 'var(--green)', marginBottom: 10 }}>{msg}</div>}

      {!detail && (
        <div className="card">
          <div className="card-title">待填写 / 已填写问卷</div>
          {list.length === 0 ? (
            <div className="empty">目前没有需要填写的问卷</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {list.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    border: '1px solid #e3ecea',
                    borderRadius: 12,
                    padding: '14px 16px',
                    background: '#f8fbfa',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700 }}>{s.title}</div>
                    <div className="note">
                      {s.deadline ? `截止：${s.deadline.slice(0, 10)}` : '请在今天内填写'}
                      {s.description ? ` · ${s.description}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {s.answered ? (
                      <span className="badge ok">已填写</span>
                    ) : (
                      <span className="badge warn">待填写</span>
                    )}
                    <button className="btn btn-primary" onClick={() => openSurvey(s.id)}>
                      {s.answered ? '查看 / 修改' : '开始填写'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {detail && (
        <div className="card">
          <div className="card-title">
            {detail.title}
            <span className="hint">1=很差/低，5=很好/高</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {detail.items.map((it, idx) => (
              <div key={it.id}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>
                  {idx + 1}. {it.text}
                </div>
                {it.type === 'text' ? (
                  <input
                    className="input"
                    placeholder="写点什么（可选）"
                    value={answers[it.id] || ''}
                    onChange={(e) => setAnswers({ ...answers, [it.id]: e.target.value })}
                    style={{ width: '100%' }}
                  />
                ) : (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {[1, 2, 3, 4, 5].map((v) => (
                      <button
                        key={v}
                        className={`btn ${Number(answers[it.id]) === v ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => setAnswers({ ...answers, [it.id]: v })}
                      >
                        {v} {SCALE_LABELS[v]}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 20, display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" onClick={submit}>提交</button>
            <button className="btn btn-ghost" onClick={() => setDetail(null)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}

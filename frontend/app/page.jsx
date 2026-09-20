'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { COACH_PORTAL_GROUPS, summarizeLatestSession } from '@/lib/coach-workspace.mjs';

const formatValue = (value, suffix = '') => (value == null ? '—' : `${value}${suffix}`);
const displayDate = (value) => {
  if (!value) return '尚无训练日期';
  const [, month, day] = value.split('-');
  return `${Number(month)}月${Number(day)}日`;
};

export default function CoachDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.hrSessions(),
      api.dashboardOverview(),
      api.dashboardAlerts(),
      api.personalizedAlerts(),
    ])
      .then(([sessions, overview, alerts, trendAlerts]) => {
        setData({ sessions, overview, alerts, trendAlerts });
      })
      .catch((err) => setError(err.message));
  }, []);

  const latest = useMemo(() => summarizeLatestSession(data?.sessions), [data?.sessions]);
  const attention = useMemo(() => {
    if (!data) return [];
    const seen = new Set();
    return [...data.trendAlerts, ...data.alerts]
      .filter((item) => {
        const key = `${item.participant_id}-${item.metric || item.alerts?.join('|')}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 6);
  }, [data]);

  if (error) {
    return <div className="error-banner">训练数据加载失败：{error}。请确认本地服务已启动。</div>;
  }
  if (!data) return <div className="loading">正在整理最近一次训练...</div>;

  return (
    <div className="coach-dashboard">
      <header className="review-hero">
        <div>
          <div className="review-kicker">POST-SESSION REVIEW · 训练后复盘</div>
          <h1>{latest ? latest.name : '等待导入训练数据'}</h1>
          <p>
            {latest
              ? `${displayDate(latest.date)} · ${latest.type} · ${latest.coach}`
              : '导入训练后的设备文件，系统将在这里汇总本堂课。'}
          </p>
        </div>
        <div className="review-actions">
          <a className="btn btn-primary" href="/data">查看数据管理</a>
          <a className="btn btn-secondary" href="/training">补录成绩 / 体能</a>
        </div>
      </header>

      {latest ? (
        <>
          <section className="session-lane" aria-label="最近一次训练概况">
            <div className="session-lane__label"><span>本次训练</span><small>同一训练名称与日期自动归组</small></div>
            <div className="session-metric"><strong>{latest.athleteCount}</strong><span>有心率数据人数</span></div>
            <div className="session-metric"><strong>{formatValue(latest.avgDuration, ' min')}</strong><span>平均记录时长</span></div>
            <div className="session-metric"><strong>{formatValue(latest.avgHr, ' bpm')}</strong><span>平均心率</span></div>
            <div className="session-metric"><strong>{formatValue(latest.maxHr, ' bpm')}</strong><span>最高心率</span></div>
          </section>

          <div className="review-grid">
            <section className="card review-panel">
              <div className="card-title">本次负荷排序 <span className="hint">按平均心率排列，仅用于教练复核</span></div>
              <div className="load-list">
                {latest.rows.slice(0, 8).map((row, index) => (
                  <a className="load-row" href="/hr" key={row.id || `${row.subject_id}-${index}`}>
                    <span className="load-rank">{String(index + 1).padStart(2, '0')}</span>
                    <span className="load-person"><strong>{row.athlete || row.subject_id || '未知运动员'}</strong><small>{row.subject_id || '未匹配编号'}</small></span>
                    <span className="load-number"><strong>{formatValue(row.avg_hr)}</strong><small>平均 bpm</small></span>
                    <span className="load-number"><strong>{formatValue(row.max_hr)}</strong><small>最高 bpm</small></span>
                  </a>
                ))}
              </div>
              {latest.rows.length > 8 && <a className="panel-link" href="/hr">查看本次全部 {latest.rows.length} 条记录 →</a>}
            </section>

            <section className="card review-panel">
              <div className="card-title">持续关注 <span className="hint">来自现有检测与恢复趋势</span></div>
              {attention.length ? (
                <div className="attention-list">
                  {attention.map((item, index) => (
                    <a className="attention-row" href={`/tracking?id=${encodeURIComponent(item.participant_id)}`} key={`${item.participant_id}-${index}`}>
                      <span className={`attention-mark ${item.severity === 'high' ? 'high' : ''}`} />
                      <span><strong>{item.name || item.participant_id}</strong><small>{item.message || item.alerts?.join('、') || '存在需要复核的数据'}</small></span>
                      <span>查看 →</span>
                    </a>
                  ))}
                </div>
              ) : (
                <div className="decision-empty"><strong>暂无持续关注项</strong><span>这表示现有规则没有触发提醒，不代表医学结论。</span></div>
              )}
            </section>
          </div>
        </>
      ) : (
        <section className="card first-session-empty">
          <div className="first-session-empty__index">01</div>
          <div><h2>从最近一堂训练开始</h2><p>先导入心率或设备导出文件；专项成绩和体能数据可随后补录。</p></div>
          <a className="btn btn-primary" href="/data">打开数据管理</a>
        </section>
      )}

      <section className="workflow-section">
        <div className="section-heading"><div><span>工作入口</span><h2>围绕下一堂训练组织数据</h2></div><p>低频检测用于解释长期变化，日常训练数据用于课后复盘。</p></div>
        <div className="workflow-grid">
          {COACH_PORTAL_GROUPS.flatMap((group) => group.items).map((item) => (
            <a className="workflow-card" href={item.href} key={`${item.href}-${item.label}`}>
              <span>{item.label}</span><small>进入查看与处理</small><b>→</b>
            </a>
          ))}
        </div>
      </section>

      <footer className="dashboard-footnote">
        当前页面提供数据汇总和关注线索，不替代教练判断或医学诊断。
        {data.overview && ` 当前收录 ${data.overview.participant_count} 名运动员。`}
      </footer>
    </div>
  );
}

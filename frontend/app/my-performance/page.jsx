'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import Chart from '@/components/Chart';

export default function MyPerformancePage() {
  const { user } = useAuth();
  const athleteId = user?.athlete_id || '';
  const [trainingMine, setTrainingMine] = useState(null);
  const [trainingAll, setTrainingAll] = useState([]);
  const [cpetRank, setCpetRank] = useState([]);
  const [cpetHistory, setCpetHistory] = useState([]);
  const [pretestAll, setPretestAll] = useState([]);
  const [fatigueAll, setFatigueAll] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!athleteId) return;
    Promise.all([
      api.trainingEntriesAthlete(athleteId).catch(() => null),
      api.trainingEntries({ limit: 500 }).catch(() => []),
      api.cpetRanking().catch(() => []),
      api.cpetAthlete(athleteId).catch(() => []),
      api.pretest().catch(() => []),
      api.fatigue().catch(() => []),
    ])
      .then(([tm, ta, cr, ch, pt, ft]) => {
        setTrainingMine(tm);
        setTrainingAll(ta);
        setCpetRank(cr);
        setCpetHistory(ch);
        setPretestAll(pt);
        setFatigueAll(ft);
      })
      .catch((e) => setError(e.message));
  }, [athleteId]);

  const rankOf = (rows, key, asc) => {
    const sorted = [...rows]
      .filter((r) => r[key] != null)
      .sort((a, b) => (asc ? a[key] - b[key] : b[key] - a[key]));
    const idx = sorted.findIndex(
      (r) => r.subject_id === athleteId || r.athlete_id === athleteId
    );
    return idx >= 0 ? { rank: idx + 1, total: sorted.length } : null;
  };

  const trainingRanking = useMemo(() => {
    const result = {};
    if (!trainingMine) return result;
    Object.entries(trainingMine.by_type || {}).forEach(([ttype, history]) => {
      const rows = trainingAll.filter((e) => e.test_type === ttype);
      const asc =
        ttype.includes('计时') ||
        ttype.includes('跑') ||
        (rows[0]?.unit || '').toLowerCase() === 's';
      const sorted = [...rows]
        .filter((e) => e.value != null)
        .sort((a, b) => (asc ? a.value - b.value : b.value - a.value));
      const idx = sorted.findIndex((e) => e.athlete_id === athleteId);
      result[ttype] = {
        unit: history[0]?.unit || rows[0]?.unit,
        history,
        latest: history[history.length - 1]?.value,
        rank: idx >= 0 ? idx + 1 : null,
        total: sorted.length,
      };
    });
    return result;
  }, [trainingMine, trainingAll, athleteId]);

  const myPretest = useMemo(
    () => pretestAll.find((r) => r.subject_id === athleteId),
    [pretestAll, athleteId]
  );
  const myFatigue = useMemo(
    () => fatigueAll.find((r) => r.subject_id === athleteId),
    [fatigueAll, athleteId]
  );
  const cmjRank = myPretest ? rankOf(pretestAll, 'cmj_height_cm', false) : null;
  const fmsRank = myPretest ? rankOf(pretestAll, 'fms_total', false) : null;
  const cpetMe = cpetRank.find((r) => r.subject_id === athleteId);

  const trainingOptions = useMemo(
    () =>
      Object.entries(trainingRanking).map(([ttype, info]) => ({
        key: ttype,
        title: `${ttype}${info.unit ? `（${info.unit}）` : ''}`,
        option: {
          title: { text: '', textStyle: { fontSize: 12 } },
          tooltip: { trigger: 'axis' },
          grid: { left: 45, right: 16, top: 20, bottom: 26 },
          xAxis: { type: 'category', data: info.history.map((h) => h.date) },
          yAxis: { type: 'value' },
          series: [
            {
              type: 'line',
              smooth: true,
              symbolSize: 7,
              data: info.history.map((h) => h.value),
              lineStyle: { width: 3, color: '#0d9488' },
              itemStyle: { color: '#0d9488' },
              label: { show: true, position: 'top', fontSize: 10 },
            },
          ],
        },
      })),
    [trainingRanking]
  );

  const cpetOption =
    cpetHistory.length > 0
      ? {
          title: { text: '', textStyle: { fontSize: 12 } },
          tooltip: { trigger: 'axis' },
          grid: { left: 45, right: 16, top: 20, bottom: 26 },
          xAxis: {
            type: 'category',
            data: cpetHistory.map((t) => (t.test_start ? t.test_start.slice(0, 10) : t.id)),
          },
          yAxis: { type: 'value', name: 'ml/kg/min', nameTextStyle: { fontSize: 10 } },
          series: [
            {
              type: 'line',
              smooth: true,
              symbolSize: 8,
              data: cpetHistory.map((t) => t.vo2kg_peak),
              lineStyle: { width: 3, color: '#2563eb' },
              itemStyle: { color: '#2563eb' },
              label: { show: true, position: 'top', fontSize: 10 },
            },
          ],
        }
      : null;

  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">我的成绩</div>
          <div className="page-desc">个人成绩与体能测试 · 趋势与队内排名</div>
        </div>
      </div>

      {/* 日常训练成绩 */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title">日常训练成绩</div>
        {Object.keys(trainingRanking).length === 0 ? (
          <div className="empty">
            还没有日常成绩记录，教练录入后这里会显示你的趋势与排名
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 12,
            }}
          >
            {Object.entries(trainingRanking).map(([ttype, info]) => (
              <div key={ttype} className="card" style={{ padding: 12 }}>
                <div className="card-title">
                  {ttype}
                  <span className="hint">
                    队内第 {info.rank ?? '—'}/{info.total ?? '—'}
                  </span>
                </div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>
                  {info.latest ?? '—'}
                  <small style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 4 }}>
                    {info.unit || ''}
                  </small>
                </div>
                {info.history.length > 1 ? (
                  <Chart
                    option={
                      trainingOptions.find((o) => o.key === ttype)?.option
                    }
                    height="160px"
                  />
                ) : (
                  <div className="note">多次测试后显示趋势</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 最大摄氧量 */}
      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-title">
            最大摄氧量 VO₂/kg
            <span className="hint">
              队内第 {cpetMe?.rank ?? '—'}/{cpetRank.length || '—'}
            </span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {cpetMe?.vo2kg_peak ?? '—'}
            <small style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 4 }}>
              ml/kg/min
            </small>
          </div>
          {cpetOption ? (
            <Chart option={cpetOption} height="200px" />
          ) : (
            <div className="note">暂无 CPET 测试数据</div>
          )}
        </div>

        <div className="card">
          <div className="card-title">基础体能（前测）</div>
          {myPretest ? (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                gap: 10,
              }}
            >
              <div>
                <div className="note">CMJ 跳高</div>
                <div style={{ fontWeight: 700 }}>
                  {myPretest.cmj_height_cm ?? '—'} cm
                  {cmjRank && (
                    <span className="note"> 队内第 {cmjRank.rank}/{cmjRank.total}</span>
                  )}
                </div>
              </div>
              <div>
                <div className="note">FMS 总分</div>
                <div style={{ fontWeight: 700 }}>
                  {myPretest.fms_total ?? '—'} /36
                  {fmsRank && (
                    <span className="note"> 队内第 {fmsRank.rank}/{fmsRank.total}</span>
                  )}
                </div>
              </div>
              <div>
                <div className="note">单跳（右）</div>
                <div style={{ fontWeight: 700 }}>{myPretest.jump_single_r ?? '—'} cm</div>
              </div>
              <div>
                <div className="note">三级跳（右）</div>
                <div style={{ fontWeight: 700 }}>{myPretest.jump_triple_r ?? '—'} cm</div>
              </div>
              <div>
                <div className="note">YBT 左前</div>
                <div style={{ fontWeight: 700 }}>{myPretest.ybt_left_ant ?? '—'} cm</div>
              </div>
              <div>
                <div className="note">乳酸（运动后5min）</div>
                <div style={{ fontWeight: 700 }}>{myPretest.lactate_post5 ?? '—'} mmol/L</div>
              </div>
            </div>
          ) : (
            <div className="empty">暂无前测数据</div>
          )}
        </div>
      </div>

      {/* 急性疲劳 */}
      {myFatigue && (
        <div className="card">
          <div className="card-title">急性疲劳恢复（CMJ 变化）</div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
              gap: 10,
            }}
          >
            <div>
              <div className="note">训练前</div>
              <div style={{ fontWeight: 700 }}>{myFatigue.cmj_pre ?? '—'} cm</div>
            </div>
            <div>
              <div className="note">24 小时</div>
              <div style={{ fontWeight: 700 }}>{myFatigue.cmj_24h ?? '—'} cm</div>
            </div>
            <div>
              <div className="note">72 小时</div>
              <div style={{ fontWeight: 700 }}>{myFatigue.cmj_72h ?? '—'} cm</div>
            </div>
            <div>
              <div className="note">HRV SDNN</div>
              <div style={{ fontWeight: 700 }}>{myFatigue.hrv_sdnn ?? '—'}</div>
            </div>
            <div>
              <div className="note">RPE（24h）</div>
              <div style={{ fontWeight: 700 }}>{myFatigue.rpe_24h ?? '—'}</div>
            </div>
          </div>
          <div className="note" style={{ marginTop: 8 }}>
            CMJ 72 小时接近训练前水平说明恢复良好；差距越大恢复越慢。
          </div>
        </div>
      )}
    </div>
  );
}

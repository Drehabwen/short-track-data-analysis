'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Chart from '@/components/Chart';
import Hint from '@/components/Hint';

const LEVEL_COLOR = { 恢复良好: '#34c759', 恢复正常: '#a3b9d6', 恢复偏低: '#e58f4f', 疲劳风险: '#d05555' };

function DataCell({ label, value, unit, color }) {
  return (
    <div className="profile-cell">
      <div className="profile-cell-label">{label}</div>
      <div className="profile-cell-value" style={{ color: color || 'var(--text)' }}>
        {value ?? '—'}
        {value != null && unit ? <span className="profile-cell-unit"> {unit}</span> : null}
      </div>
    </div>
  );
}

export default function AthleteProfile({ subjectId, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!subjectId) return;
    setData(null);
    setError('');
    api.athletePanorama(subjectId).then(setData).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId]);

  if (!subjectId) return null;
  if (error) {
    return (
      <div className="profile-modal">
        <div className="profile-card">
          <div className="profile-head">
            <span>画像加载失败</span>
            <button className="btn btn-ghost" onClick={onClose}>关闭</button>
          </div>
          <div className="error-banner">{error}</div>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="profile-modal">
        <div className="profile-card">
          <div className="loading">画像加载中...</div>
        </div>
      </div>
    );
  }

  const p = data.participant;
  const radar = data.radar || { indicators: [], values: [] };
  const radarOption = {
    tooltip: {},
    radar: {
      indicator: radar.indicators.map((name) => ({ name, max: 100 })),
      radius: '65%',
      center: ['50%', '55%'],
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            name: p.name,
            value: radar.values,
            areaStyle: { color: 'rgba(0,113,227,0.25)' },
            itemStyle: { color: '#0071e3' },
          },
        ],
      },
    ],
  };

  const cpetHist = data.cpet?.history || [];
  const cpetOption = cpetHist.length
    ? {
        title: { text: 'CPET VO₂/kg 历史', textStyle: { fontSize: 12, color: '#1d1d1f', fontWeight: 600 } },
        tooltip: {},
        grid: { left: 40, right: 16, top: 32, bottom: 24 },
        xAxis: { type: 'category', data: cpetHist.map((c) => c.date) },
        yAxis: { type: 'value' },
        series: [
          {
            type: 'bar',
            data: cpetHist.map((c) => c.vo2kg),
            itemStyle: { color: '#34c759', borderRadius: [6, 6, 0, 0] },
            label: { show: true, position: 'top', fontSize: 10 },
          },
        ],
      }
    : null;

  const hrv = data.hrv;
  const cpet = data.cpet;
  const hr = data.hr;
  const bl = data.blood || {};
  const pt = data.pretest;

  return (
    <div className="profile-modal" onClick={onClose}>
      <div className="profile-card" onClick={(e) => e.stopPropagation()}>
        <div className="profile-head">
          <div>
            <span className="profile-title">
              {p.name || p.participant_id} <span className="profile-id">{p.participant_id}</span>
            </span>
            <div className="profile-meta">
              {p.sex || '—'} · {p.age_years != null ? `${p.age_years}岁` : '—'}
              {p.coach ? ` · ${p.coach}` : ''}
              {p.group_name ? ` · ${p.group_name}` : ''}
              {p.athlete_class ? ` · ${p.athlete_class}` : ''}
            </div>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>关闭 ✕</button>
        </div>

        <div className="profile-body">
          {/* 雷达五维 */}
          <div className="card profile-radar">
            <div className="card-title">能力画像（相对全队百分位）</div>
            <Chart option={radarOption} height="300px" />
            <Hint text="100=全队顶尖，50=中位；某维特别矮 = 该方面是短板，训练往那补" />
          </div>

          {/* 有氧能力 */}
          <div className="card">
            <div className="card-title">最大摄氧量（CPET）</div>
            <div className="profile-grid">
              <DataCell label="VO₂/kg" value={cpet?.best_vo2kg} unit="ml/kg/min" color={cpet?.best_vo2kg != null && cpet.best_vo2kg >= 70 ? '#34c759' : cpet?.best_vo2kg != null && cpet.best_vo2kg < 55 ? '#e58f4f' : null} />
              <DataCell label="预测达成率" value={cpet?.best_pctnorm} unit="%" color={cpet?.best_pctnorm != null && cpet.best_pctnorm >= 100 ? '#34c759' : '#e58f4f'} />
              <DataCell label="VT1 耐力储备" value={cpet?.vt1_pct} unit="%" color={cpet?.vt1_pct != null && cpet.vt1_pct >= 70 ? '#34c759' : '#e58f4f'} />
              <DataCell label="VE/VCO2 斜率" value={cpet?.ve_slope} color={cpet?.ve_slope != null && cpet.ve_slope < 30 ? '#34c759' : '#e58f4f'} />
              <DataCell label="最大心率" value={cpet?.hr_peak} unit="bpm" />
              <DataCell label="最大通气 VE" value={cpet?.ve_peak} unit="L/min" />
              <DataCell label="VO₂ 绝对值" value={cpet?.vo2_abs} unit="L/min" />
              <DataCell label="峰值功率" value={cpet?.peak_wr} unit="W" />
              <DataCell label="运动时长" value={cpet?.duration_s ? (cpet.duration_s / 60).toFixed(0) : null} unit="min" />
              <DataCell label="RER 努力度" value={cpet?.rer} color={cpet?.rer != null && cpet.rer >= 1.05 ? '#34c759' : '#e58f4f'} />
              <DataCell label="测试分级" value={cpet?.valid_class} color={cpet?.valid_class?.includes('有效') ? '#34c759' : '#e58f4f'} />
              <DataCell label="测试次数" value={cpet?.count} unit="次" />
            </div>
            {cpetOption && <Chart option={cpetOption} height="200px" />}
            <Hint text="VO₂/kg 绿≥70 优秀/橙&lt;55 待提高；VE斜率绿&lt;30 呼吸经济；RER 绿≥1.05 才算真测出最大值" />
          </div>

          {/* CPET 全队排名可视化 */}
          {cpet?.ranks?.total ? (
            <div className="card">
              <div className="card-title">全队排名（共 {cpet.ranks.total} 人）</div>
              <div className="rank-bars">
                {[
                  { key: 'vo2kg', label: 'VO₂/kg', desc: '越高越好' },
                  { key: 'pctnorm', label: '预测达成', desc: '越高越好' },
                  { key: 'vt1', label: 'VT1 耐力', desc: '越高越好' },
                  { key: 'slope', label: 'VE斜率', desc: '越低越好' },
                  { key: 'rer', label: 'RER 努力', desc: '越高越好' },
                ].map((m) => {
                  const rk = cpet.ranks[m.key];
                  if (!rk) return null;
                  const top3 = rk.rank <= 3;
                  const bottom = rk.pct >= 80;
                  return (
                    <div key={m.key} className="rank-row">
                      <div className="rank-label">{m.label} <span className="rank-dir">{m.desc}</span></div>
                      <div className="rank-track">
                        <div
                          className={`rank-fill ${top3 ? 'top' : bottom ? 'bottom' : ''}`}
                          style={{ width: `${100 - rk.pct}%` }}
                        />
                        <span className="rank-mark" style={{ left: `${100 - rk.pct}%` }} />
                      </div>
                      <div className="rank-val">
                        {top3 ? `🏆 第 ${rk.rank}` : `第 ${rk.rank} / ${rk.total}`}
                        <span className="rank-pct">前 {rk.pct}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <Hint text="条越长 = 排名越靠前；🏆=全队前3。VO₂/kg 是主排名，其他是辅助维度" />
            </div>
          ) : null}

          {/* 恢复与负荷 */}
          <div className="card">
            <div className="card-title">恢复与训练负荷</div>
            <div className="profile-grid">
              <DataCell label="HRV RMSSD" value={hrv?.rmssd} unit="ms" color={hrv ? LEVEL_COLOR[hrv.level] : null} />
              <DataCell label="恢复状态" value={hrv?.level} color={hrv ? LEVEL_COLOR[hrv.level] : null} />
              <DataCell label="HRV SDNN" value={hrv?.sdnn} unit="ms" />
              <DataCell label="LF/HF" value={hrv?.lf_hf} />
              <DataCell label="心率场次" value={hr?.sessions} unit="次" />
              <DataCell label="平均心率" value={hr?.avg_hr} unit="bpm" />
              <DataCell label="高强度 Z4+Z5" value={hr?.z45_pct} unit="%" color={hr?.z45_pct != null && hr.z45_pct > 10 ? '#e58f4f' : null} />
              <DataCell label="最高心率" value={hr?.max_hr} unit="bpm" />
            </div>
          </div>

          {/* 血液（最近一次） */}
          <div className="card">
            <div className="card-title">血液指标（{bl.collection_time || '最近'}）</div>
            <div className="profile-grid">
              <DataCell label="睾酮" value={bl.testosterone} unit="nmol/L" />
              <DataCell label="皮质醇" value={bl.cortisol} unit="ug/dL" />
              <DataCell label="CK" value={bl.ck} unit="U/L" color={bl.ck != null && bl.ck > 400 ? '#e58f4f' : null} />
              <DataCell label="尿素" value={bl.urea} unit="mmol/L" />
              <DataCell label="LDH" value={bl.ldh} unit="U/L" color={bl.ldh != null && bl.ldh > 300 ? '#e58f4f' : null} />
            </div>
          </div>

          {/* 训练成绩（日常录入） */}
          <div className="card">
            <div className="card-title">训练成绩（{data.training?.count || 0} 条记录）</div>
            {data.training?.recent?.length ? (
              <>
                <div className="profile-grid">
                  {Object.entries(data.training.latest_by_type || {}).slice(0, 6).map(([name, v]) => (
                    <DataCell key={name} label={name} value={v.value} unit={v.unit} />
                  ))}
                </div>
                <div className="table-wrap" style={{ maxHeight: 180, overflowY: 'auto' }}>
                  <table className="data-table">
                    <thead>
                      <tr><th>日期</th><th>项目</th><th>成绩</th><th>课名</th></tr>
                    </thead>
                    <tbody>
                      {data.training.recent.map((r, i) => (
                        <tr key={i}>
                          <td>{r.date}</td>
                          <td>{r.test_type}</td>
                          <td style={{ fontWeight: 600 }}>{r.value} {r.unit}</td>
                          <td style={{ fontSize: 11 }}>{r.session_name || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="note">暂无训练成绩记录，请到「训练录入」添加</div>
            )}
          </div>

          {/* 前测体能 */}
          <div className="card">
            <div className="card-title">前测体能</div>
            <div className="profile-grid">
              <DataCell label="FMS 总分" value={pt?.fms_total} unit="/21" color={pt?.fms_total != null && pt.fms_total < 14 ? '#e58f4f' : null} />
              <DataCell label="CMJ 纵跳" value={pt?.cmj_height_cm} unit="cm" />
              <DataCell label="血乳酸(前)" value={pt?.lactate_pre} unit="mmol/L" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

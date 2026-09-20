export const DEFAULT_LOCAL_USER = Object.freeze({
  id: 2,
  username: 'coach',
  display_name: '教练工作台',
  role: 'coach',
  athlete_id: null,
});

export const COACH_NAV_GROUPS = Object.freeze([
  {
    label: '训练后复盘',
    items: [
      { href: '/', label: '训练复盘' },
      { href: '/training', label: '训练数据' },
      { href: '/hr', label: '心率负荷' },
    ],
  },
  {
    label: '运动表现',
    items: [
      { href: '/fitness', label: '专项体能' },
      { href: '/body-composition', label: '身体成分' },
      { href: '/competitions', label: '成绩记录' },
      { href: '/athletes', label: '运动员' },
    ],
  },
  {
    label: '分析与数据',
    items: [
      { href: '/profile', label: '个人追踪' },
      { href: '/groups', label: '深度分析' },
      { href: '/data', label: '数据管理' },
    ],
  },
]);

export const COACH_PORTAL_GROUPS = COACH_NAV_GROUPS;

export const COACH_TRAINING_TABS = Object.freeze([
  { key: 'score', label: '成绩', desc: '训练成绩（计时/速度）' },
  { key: 'fitness', label: '体能', desc: '体能测试（力量/灵敏/身体成分）' },
]);

export function resolveLocalUser() {
  return DEFAULT_LOCAL_USER;
}

const mean = (values) => {
  const valid = values
    .filter((value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)))
    .map(Number);
  return valid.length ? Math.round((valid.reduce((sum, value) => sum + value, 0) / valid.length) * 10) / 10 : null;
};

export function summarizeLatestSession(sourceRows) {
  if (!Array.isArray(sourceRows) || sourceRows.length === 0) return null;

  const datedRows = sourceRows
    .filter((row) => row?.datetime)
    .slice()
    .sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
  if (!datedRows.length) return null;

  const newest = datedRows[0];
  const date = String(newest.datetime).slice(0, 10);
  const name = newest.session_name || '未命名训练';
  const rows = datedRows
    .filter((row) => String(row.datetime).slice(0, 10) === date && (row.session_name || '未命名训练') === name)
    .sort((a, b) => (Number(b.avg_hr) || 0) - (Number(a.avg_hr) || 0));

  return {
    name,
    date,
    coach: newest.coach || '未记录',
    type: newest.session_type || '未分类',
    athleteCount: new Set(rows.map((row) => row.subject_id || row.athlete).filter(Boolean)).size,
    avgHr: mean(rows.map((row) => row.avg_hr)),
    maxHr: rows.reduce((max, row) => Math.max(max, Number(row.max_hr) || 0), 0) || null,
    avgDuration: mean(rows.map((row) => row.duration_min)),
    rows,
  };
}

export function selectInitialParticipant(participants, search = '') {
  if (!Array.isArray(participants) || participants.length === 0) return '';
  const requested = new URLSearchParams(search).get('id');
  return participants.some((participant) => participant.participant_id === requested)
    ? requested
    : participants[0].participant_id;
}

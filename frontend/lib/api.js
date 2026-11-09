/**
 * API 客户端：所有请求指向本地后端 FastAPI（localhost:8000）。
 * 数据不出网——全部请求发往本机。请求自动携带 JWT token。
 */
const API_BASE =
  typeof window !== 'undefined' && window.__API_BASE__
    ? window.__API_BASE__
    : typeof window !== 'undefined' && window.location.port !== '3000'
      ? window.location.origin
      : process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

export const API_BASE_URL = API_BASE;

const TOKEN_KEY = 'blood_analysis_token';

function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

function handleUnauthorized() {
  // 本地模式已免登录，401 不再跳转登录页
  if (typeof window !== 'undefined') {
    localStorage.removeItem('blood_analysis_token');
    localStorage.removeItem('blood_analysis_user');
  }
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    handleUnauthorized();
    throw new Error('登录已失效，请重新登录');
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} 失败 (${res.status}): ${text}`);
  }
  return res.json();
}

export const api = {
  decisionToday: (day) => request(`/api/decision/today${day ? `?day=${day}` : ''}`),
  decisionWeekly: (days = 14) => request(`/api/decision/weekly?days=${days}`),
  decisionAthlete: (name) => request(`/api/decision/athlete/${encodeURIComponent(name)}`),
  decisionLog: (payload) =>
    request('/api/decision/log', { method: 'POST', body: JSON.stringify(payload) }),
  decisionLogs: (limit = 20) => request(`/api/decision/logs?limit=${limit}`),

  // 认证
  login: (username, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => request('/api/auth/me'),
  changePassword: (old_password, new_password) =>
    request('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password, new_password }),
    }),

  // 总览
  dashboardOverview: () => request('/api/dashboard/overview'),
  dashboardAlerts: () => request('/api/dashboard/alerts'),
  personalizedAlerts: () => request('/api/dashboard/personalized_alerts'),

  // 个体追踪
  participants: () => request('/api/participants'),
  tracking: (id) => request(`/api/tracking/${encodeURIComponent(id)}`),

  // 科研统计
  statsDescriptive: (by = 'timepoint') => request(`/api/stats/descriptive?by=${by}`),
  statsLongitudinal: () => request('/api/stats/longitudinal'),
  statsGroupComparison: () => request('/api/stats/group_comparison'),
  statsCorrelation: () => request('/api/stats/correlation'),
  statsPerformanceCorrelation: () => request('/api/stats/performance_correlation'),
  statsByTimepoint: () => request('/api/stats/by_timepoint'),

  // 指标配置与超标统计
  analytes: () => request('/api/analytes'),
  analyteExceedance: () => request('/api/analytes/exceedance'),
  analyteReference: () => request('/api/analytes/reference'),

  // 运动员管理
  createParticipant: (payload) =>
    request('/api/participants', { method: 'POST', body: JSON.stringify(payload) }),
  updateParticipant: (id, payload) =>
    request(`/api/participants/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteParticipant: (id) =>
    request(`/api/participants/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  // 综合数据（心率/CPET/前测/疲劳/全景）
  hrOverview: () => request('/api/hr/overview'),
  hrSessions: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
    ).toString();
    return request(`/api/hr/sessions${qs ? `?${qs}` : ''}`);
  },
  hrAthlete: (id) => request(`/api/hr/athlete/${encodeURIComponent(id)}`),
  cpetTests: () => request('/api/cpet/tests'),
  cpetRanking: () => request('/api/cpet/ranking'),
  cpetAthlete: (id) => request(`/api/cpet/athlete/${encodeURIComponent(id)}`),
  cpetTrends: () => request('/api/cpet/trends'),
  cpetGroupCompare: () => request('/api/cpet/group_compare'),
  cpetQuality: () => request('/api/cpet/quality'),
  hrvOverview: () => request('/api/hrv/overview'),
  hrvAthlete: (id) => request(`/api/hrv/athlete/${encodeURIComponent(id)}`),
  hrvAnalyze: (rrIntervals) => request('/api/hrv/analyze', { method: 'POST', body: JSON.stringify({ rr_intervals: rrIntervals }) }),
  trainingTypes: () => request('/api/training/types'),
  trainingEntries: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString();
    return request(`/api/training/entries${qs ? `?${qs}` : ''}`);
  },
  trainingEntriesCreate: (entries) => request('/api/training/entries', { method: 'POST', body: JSON.stringify({ entries }) }),
  trainingEntriesAthlete: (id) => request(`/api/training/entries/athlete/${encodeURIComponent(id)}`),
  plans: (weekStart) => request(`/api/plans${weekStart ? `?week_start=${weekStart}` : ''}`),
  planCreate: (data) => request('/api/plans', { method: 'POST', body: JSON.stringify(data) }),
  planUpdate: (id, data) => request(`/api/plans/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  planDelete: (id) => request(`/api/plans/${id}`, { method: 'DELETE' }),
  statusReport: (data) => request('/api/status/report', { method: 'POST', body: JSON.stringify(data) }),
  statusTeam: (date) => request(`/api/status/team${date ? `?status_date=${date}` : ''}`),
  statusAthlete: (id) => request(`/api/status/athlete/${encodeURIComponent(id)}`),
  injuries: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString();
    return request(`/api/injuries${qs ? `?${qs}` : ''}`);
  },
  injuryCreate: (data) => request('/api/injuries', { method: 'POST', body: JSON.stringify(data) }),
  injuryUpdate: (id, data) => request(`/api/injuries/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  pretest: () => request('/api/pretest'),
  fatigue: () => request('/api/fatigue'),
  trainingSessions: () => request('/api/training/sessions'),
  athletePanorama: (id) => request(`/api/athlete/panorama/${encodeURIComponent(id)}`),

  // 数据管理
  samples: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
    ).toString();
    return request(`/api/samples${qs ? `?${qs}` : ''}`);
  },
  updateSample: (id, payload) =>
    request(`/api/samples/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  importSeed: () => request('/api/import/seed', { method: 'POST' }),

  // 参赛记录
  competitionEvents: () => request('/api/competitions/events'),
  competitions: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString();
    return request(`/api/competitions${qs ? `?${qs}` : ''}`);
  },
  competitionCreate: (payload) => request('/api/competitions', { method: 'POST', body: JSON.stringify(payload) }),
  competitionUpdate: (id, payload) => request(`/api/competitions/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  competitionDelete: (id) => request(`/api/competitions/${id}`, { method: 'DELETE' }),

  // 心理问卷
  surveyTemplates: () => request('/api/surveys/templates'),
  surveysCreate: (payload) => request('/api/surveys', { method: 'POST', body: JSON.stringify(payload) }),
  surveys: () => request('/api/surveys'),
  surveyDetail: (id) => request(`/api/surveys/${id}`),
  mySurveys: (athleteId) => request(`/api/surveys/mine?athlete_id=${encodeURIComponent(athleteId)}`),
  surveyRespond: (id, payload) => request(`/api/surveys/${id}/respond`, { method: 'POST', body: JSON.stringify(payload) }),
};

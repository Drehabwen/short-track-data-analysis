import test from 'node:test';
import assert from 'node:assert/strict';

import {
  COACH_NAV_GROUPS,
  COACH_PORTAL_GROUPS,
  COACH_TRAINING_TABS,
  DEFAULT_LOCAL_USER,
  resolveLocalUser,
  selectInitialParticipant,
  summarizeLatestSession,
} from '../lib/coach-workspace.mjs';

const flattenLabels = (groups) => groups.flatMap((group) => group.items.map((item) => item.label));

test('local app opens directly as the coach workspace', () => {
  assert.equal(DEFAULT_LOCAL_USER.role, 'coach');
  assert.equal(DEFAULT_LOCAL_USER.display_name, '教练工作台');
});

test('legacy saved roles cannot reopen deferred athlete or admin modes', () => {
  assert.equal(resolveLocalUser('{"role":"athlete","athlete_id":"A01"}').role, 'coach');
  assert.equal(resolveLocalUser('{"role":"admin"}').role, 'coach');
  assert.equal(resolveLocalUser(null).role, 'coach');
});

test('coach navigation exposes the post-training decision workflow', () => {
  const labels = flattenLabels(COACH_NAV_GROUPS);

  for (const required of ['训练复盘', '训练数据', '心率负荷', '专项体能', '身体成分', '成绩记录', '运动员', '深度分析']) {
    assert.ok(labels.includes(required), `missing core coach entry: ${required}`);
  }
  assert.equal(COACH_NAV_GROUPS.flatMap((group) => group.items).find((item) => item.label === '身体成分').href, '/body-composition');
  assert.ok(labels.includes('数据管理'));
});

test('deferred multi-role services are absent from coach navigation and portal', () => {
  const labels = [...flattenLabels(COACH_NAV_GROUPS), ...flattenLabels(COACH_PORTAL_GROUPS)];

  for (const deferred of ['心理问卷', '状态上报', '训练计划', '伤病管理', '团队报告', '我的问卷', '我的状态']) {
    assert.ok(!labels.includes(deferred), `deferred service is still visible: ${deferred}`);
  }
});

test('training entry keeps performance data but hides injury management', () => {
  assert.deepEqual(COACH_TRAINING_TABS.map((tab) => tab.key), ['score', 'fitness']);
});

test('latest-session summary only uses rows from the newest training session', () => {
  const rows = [
    { athlete: '甲', subject_id: 'A01', datetime: '2026-09-05T15:00:00', session_name: '冰上训练', duration_min: 60, avg_hr: 150, max_hr: 188 },
    { athlete: '乙', subject_id: 'A02', datetime: '2026-09-05T15:00:00', session_name: '冰上训练', duration_min: 62, avg_hr: 160, max_hr: 194 },
    { athlete: '丙', subject_id: 'A03', datetime: '2026-09-04T09:00:00', session_name: '陆地训练', duration_min: 80, avg_hr: 140, max_hr: 180 },
  ];

  const summary = summarizeLatestSession(rows);

  assert.equal(summary.name, '冰上训练');
  assert.equal(summary.date, '2026-09-05');
  assert.equal(summary.athleteCount, 2);
  assert.equal(summary.avgHr, 155);
  assert.equal(summary.maxHr, 194);
  assert.equal(summary.avgDuration, 61);
  assert.deepEqual(summary.rows.map((row) => row.subject_id), ['A02', 'A01']);
});

test('latest-session summary returns an empty state for missing training data', () => {
  assert.equal(summarizeLatestSession([]), null);
  assert.equal(summarizeLatestSession(null), null);
});

test('latest-session averages ignore nullable device fields', () => {
  const summary = summarizeLatestSession([
    { subject_id: 'A01', datetime: '2026-09-05T15:00:00', session_name: '冰上训练', duration_min: 60, avg_hr: 150, max_hr: 188 },
    { subject_id: 'A02', datetime: '2026-09-05T15:00:00', session_name: '冰上训练', duration_min: null, avg_hr: null, max_hr: null },
  ]);

  assert.equal(summary.avgHr, 150);
  assert.equal(summary.avgDuration, 60);
  assert.equal(summary.maxHr, 188);
});

test('tracking links select the requested athlete when it exists', () => {
  const participants = [{ participant_id: 'A01' }, { participant_id: 'A02' }];
  assert.equal(selectInitialParticipant(participants, '?id=A02'), 'A02');
  assert.equal(selectInitialParticipant(participants, '?id=missing'), 'A01');
});

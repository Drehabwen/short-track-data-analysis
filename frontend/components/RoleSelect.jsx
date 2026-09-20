'use client';

import { useAuth } from '@/lib/auth-context';

const ROLES = [
  {
    key: 'admin',
    title: '管理员',
    desc: '全队数据管理 · 分析 · 报告 · 配置',
    account: 'admin / admin123',
  },
  {
    key: 'coach',
    title: '教练',
    desc: '训练监测 · 个体追踪 · 状态看板 · 成绩录入',
    account: 'coach / coach123',
  },
  {
    key: 'athlete',
    title: '运动员',
    desc: '我的数据 · 状态上报 · 个人追踪',
    account: '进入后从花名册选择身份',
  },
];

export default function RoleSelect() {
  const { login } = useAuth();
  return (
    <div className="role-select">
      <div className="role-select-box">
        <div className="role-brand"><img src="/speedtrack-logo.svg" alt="" aria-hidden="true" /> <span>SpeedTrack Pro</span></div>
        <h1>短道速滑训练监测平台</h1>
        <p className="role-sub">请选择你的角色进入</p>
        <div className="role-cards">
          {ROLES.map((r) => (
            <button key={r.key} className="role-card" onClick={() => login(r.key)}>
              <div className="role-title">{r.title}</div>
              <div className="role-desc">{r.desc}</div>
              <div className="role-account">{r.account}</div>
            </button>
          ))}
        </div>
        <p className="role-foot">本地演示版 · 数据仅存于本机</p>
      </div>
    </div>
  );
}

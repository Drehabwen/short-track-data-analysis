'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { COACH_NAV_GROUPS } from '@/lib/coach-workspace.mjs';

function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderGroup = (g) => (
    <div key={g.label} className="side-group">
      {!collapsed && <div className="side-group-label">{g.label}</div>}
      {g.items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={`${item.href}-${item.label}`}
            href={item.href}
            className={`side-item ${active ? 'active' : ''}`}
            title={item.label}
            onClick={() => setMobileOpen(false)}
          >
            <span className="side-dot" />
            {!collapsed && <span className="side-text">{item.label}</span>}
          </Link>
        );
      })}
    </div>
  );

  return (
    <>
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
        <div className="side-brand">
          <img className="side-brand-logo" src="/speedtrack-logo.svg" alt="" aria-hidden="true" />
          {!collapsed && <span className="side-brand-text">SpeedTrack Pro</span>}
        </div>
        <nav className="side-nav">{COACH_NAV_GROUPS.map(renderGroup)}</nav>
        <div className="side-footer">
          <button className="side-collapse" onClick={() => setCollapsed(!collapsed)} title="折叠/展开">
            {collapsed ? '»' : '« 折叠'}
          </button>
          {!collapsed && <div className="side-local-note">本机运行 · 数据不出网</div>}
        </div>
      </aside>
      {mobileOpen && <div className="side-backdrop" onClick={() => setMobileOpen(false)} />}
    </>
  );
}

// 供 TopNav 汉堡按钮调用的折叠/抽屉控制
export function toggleSidebar() {
  const el = document.querySelector('.sidebar');
  if (!el) return;
  if (window.innerWidth <= 900) {
    el.classList.toggle('mobile-open');
  } else {
    el.classList.toggle('collapsed');
  }
}

export default Sidebar;

'use client';

import { toggleSidebar } from './Sidebar';

function TopNav() {
  return (
    <nav className="topnav">
      <button className="hamburger" onClick={toggleSidebar} title="菜单">
        ☰
      </button>
      <div className="brand">
        <img className="brand-logo" src="/speedtrack-logo.svg" alt="" aria-hidden="true" />
        <span>SpeedTrack Pro</span>
        <span className="brand-sub">短道速滑训练监测</span>
      </div>
      <div className="user-area">
        <div className="workspace-chip"><span className="workspace-chip__pulse" />教练端 · 本地模式</div>
      </div>
    </nav>
  );
}

export default TopNav;

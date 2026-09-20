'use client';

import { AuthProvider, useAuth } from '@/lib/auth-context';
import TopNav from '@/components/TopNav';
import Sidebar from '@/components/Sidebar';
import './globals.css';

function AppShell({ children }) {
  const { loading } = useAuth();
  if (loading) return <div className="loading">加载中...</div>;
  return (
    <div className="shell">
      <TopNav />
      <div className="shell-body">
        <Sidebar />
        <main className="main">{children}</main>
      </div>
    </div>
  );
}

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="icon" href="/speedtrack-logo.svg" type="image/svg+xml" />
      </head>
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}

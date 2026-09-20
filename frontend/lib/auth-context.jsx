'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LOCAL_USER, resolveLocalUser } from './coach-workspace.mjs';

const AuthContext = createContext(null);

const STORAGE_KEY = 'blood_analysis_role';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(DEFAULT_LOCAL_USER);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      // localStorage 不可用不影响本地教练端
    }
    setUser(resolveLocalUser());
    setReady(true);
  }, []);

  const value = useMemo(
    () => ({
      user,
      token: null,
      loading: !ready,
      login: () => {
        setUser(DEFAULT_LOCAL_USER);
        return DEFAULT_LOCAL_USER;
      },
      selectAthlete: () => {
        setUser(DEFAULT_LOCAL_USER);
        return DEFAULT_LOCAL_USER;
      },
      logout: () => {
        try {
          localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
          // 忽略
        }
        setUser(DEFAULT_LOCAL_USER);
      },
      changePassword: async () => true,
    }),
    [user, ready]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return ctx;
}

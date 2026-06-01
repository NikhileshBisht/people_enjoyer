import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('access_token') || '');
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const clearSession = useCallback(() => {
    localStorage.removeItem('access_token');
    setToken('');
    setUser(null);
  }, []);

  const fetchMe = useCallback(async (accessToken) => {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      throw new Error('Session expired. Please login again.');
    }
    return response.json();
  }, []);

  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      if (!token) {
        setUser(null);
        setAuthLoading(false);
        return;
      }

      try {
        const profile = await fetchMe(token);
        if (!cancelled) {
          setUser(profile);
        }
      } catch {
        if (!cancelled) {
          clearSession();
        }
      } finally {
        if (!cancelled) {
          setAuthLoading(false);
        }
      }
    };

    setAuthLoading(true);
    restoreSession();

    return () => {
      cancelled = true;
    };
  }, [token, fetchMe, clearSession]);

  const login = useCallback((accessToken) => {
    localStorage.setItem('access_token', accessToken);
    setToken(accessToken);
  }, []);

  const logout = useCallback(async () => {
    const currentToken = localStorage.getItem('access_token');
    if (currentToken) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch {
        // Best effort.
      }
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo(
    () => ({
      token,
      user,
      authLoading,
      login,
      logout,
      isAuthenticated: Boolean(token && user),
    }),
    [token, user, authLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

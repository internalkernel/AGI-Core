import { useState, useCallback } from 'react';

const TOKEN_KEY = 'openclaw_token';
const USER_KEY = 'openclaw_user';

interface AuthUser {
  id: string;
  username: string;
  is_admin: boolean;
}

export function useAuth() {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuthenticated = !!token;

  const setToken = useCallback((t: string | null) => {
    setTokenState(t);
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Login failed');
      }
      const data = await res.json();
      setToken(data.token);

      // Fetch user profile
      const meRes = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${data.token}` },
      });
      if (meRes.ok) {
        const userData = await meRes.json();
        setUser(userData);
        localStorage.setItem(USER_KEY, JSON.stringify(userData));
      }
    } catch (e: any) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [setToken]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  }, [setToken]);

  return { token, user, isAuthenticated, loading, error, login, logout };
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

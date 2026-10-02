import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError } from "./api";
import type { LoginResponse, User } from "./types";

/**
 * The frontend never decides who is authenticated. `user` is whatever the server's /me endpoint
 * says for the session cookie; `lastLogin` only carries the analysis to display.
 */
interface AuthState {
  user: User | null;
  loading: boolean;
  lastLogin: LoginResponse | null;
  setLastLogin: (r: LoginResponse | null) => void;
  refresh: () => Promise<User | null>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastLogin, setLastLogin] = useState<LoginResponse | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api.get<{ user: User }>("/api/auth/me");
      setUser(me.user);
      return me.user;
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 401) console.error(e);
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const logout = useCallback(async () => {
    try { await api.post("/api/auth/logout"); } finally { setUser(null); setLastLogin(null); }
  }, []);

  const value = useMemo(() => ({ user, loading, lastLogin, setLastLogin, refresh, logout }), [user, loading, lastLogin, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

// --- administrator session (completely separate cookie and endpoints) ---------------------------
interface AdminState {
  admin: { username: string } | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}
const AdminContext = createContext<AdminState | null>(null);

export function AdminProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<{ username: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try { setAdmin(await api.get<{ username: string }>("/api/admin/me")); }
    catch { setAdmin(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const logout = useCallback(async () => {
    try { await api.post("/api/admin/logout"); } finally { setAdmin(null); }
  }, []);

  const value = useMemo(() => ({ admin, loading, refresh, logout }), [admin, loading, refresh, logout]);
  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>;
}

export function useAdmin(): AdminState {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error("useAdmin must be used inside AdminProvider");
  return ctx;
}

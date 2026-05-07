import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("scale_token"));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("scale_token");
    localStorage.removeItem("scale_user");
    setUser(null);
    setToken(null);
  }, []);

  const loginWith = (t, username, userId, isAdmin = false) => {
    localStorage.setItem("scale_token", t);
    localStorage.setItem("scale_user", username);
    setToken(t);
    setUser({ username, userId, isAdmin });
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const t = localStorage.getItem("scale_token");
      if (!t) { setLoading(false); return; }
      try {
        const { data } = await api.get("/auth/me");
        if (!cancelled) setUser({ username: data.username, userId: data.userId, isAdmin: !!data.isAdmin });
      } catch {
        if (!cancelled) logout();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [logout]);

  return (
    <AuthCtx.Provider value={{ user, token, loading, loginWith, logout }}>
      {children}
    </AuthCtx.Provider>
  );
};

export const useAuth = () => useContext(AuthCtx);

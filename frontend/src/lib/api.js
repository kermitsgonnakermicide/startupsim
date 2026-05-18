import axios from "axios";

const rawBackendUrl = process.env.REACT_APP_BACKEND_URL;

const localBackendUrl = () => {
  if (typeof window === "undefined") return "";
  const { protocol, hostname, port } = window.location;
  if ((hostname === "localhost" || hostname === "127.0.0.1") && port === "3000") {
    return `${protocol}//${hostname}:8001`;
  }
  return window.location.origin;
};

const BACKEND_URL = rawBackendUrl == null ? localBackendUrl() : rawBackendUrl.trim();
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("scale_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const wsUrl = (token) => {
  let base = BACKEND_URL || localBackendUrl();
  if (!base || base.startsWith("/")) base = window.location.origin;
  const u = new URL(base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  u.pathname = "/api/ws";
  u.searchParams.set("token", token);
  return u.toString();
};

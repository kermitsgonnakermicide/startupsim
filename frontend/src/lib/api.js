import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("scale_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const wsUrl = (token) => {
  let base = BACKEND_URL;
  if (!base || base.startsWith("/")) {
    base = window.location.origin;
  }
  const u = new URL(base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  u.pathname = "/api/ws";
  u.searchParams.set("token", token);
  return u.toString();
};

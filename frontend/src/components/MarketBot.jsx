import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

/**
 * useMarketBot pulls server-side demand pressure and news reasons every 30s
 * and merges them into a `botPrices` map that any tab can consume.
 */
export function useMarketBot() {
  const { user } = useAuth();
  const [demand, setDemand] = useState({});
  const [news, setNews] = useState({});
  const tickRef = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const [d, n] = await Promise.all([
        api.get("/demand"),
        user ? api.get("/marketbot/news").catch(() => ({ data: { news: {} } })) : Promise.resolve({ data: { news: {} } }),
      ]);
      setDemand(d.data?.pressure || {});
      setNews(n.data?.news || {});
      tickRef.current += 1;
    } catch (_) {
      // silent fallback
    }
  }, [user]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [refresh]);

  const botPrices = useMemo(() => {
    const m = {};
    Object.keys(demand).forEach((sym) => {
      m[sym] = { demandPressure: demand[sym], reason: news[sym] || null };
    });
    return m;
  }, [demand, news]);

  return { botPrices, demand, news, refresh };
}

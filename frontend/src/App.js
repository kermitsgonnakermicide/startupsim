import React, { useCallback, useEffect, useMemo, useState } from "react";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AuthPage from "@/pages/AuthPage";
import Navbar from "@/components/Navbar";
import MarketTab from "@/components/MarketTab";
import PortfolioTab from "@/components/PortfolioTab";
import HistoryTab from "@/components/HistoryTab";
import LeaderboardTab from "@/components/LeaderboardTab";
import AdminTab from "@/components/AdminTab";
import WatchlistTab from "@/components/WatchlistTab";
import NewsTab from "@/components/NewsTab";
import IndicesTicker from "@/components/IndicesTicker";
import MarketBotChat, { useMarketBot } from "@/components/MarketBot";
import { api } from "@/lib/api";
import { useMarketFeed } from "@/hooks/useMarketFeed";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

const Shell = () => {
  const { user, token, loading, logout } = useAuth();
  const [tab, setTab] = useState("Market");
  const [stocks, setStocks] = useState([]);
  const [sparks, setSparks] = useState({});
  const [portfolio, setPortfolio] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [highlightSymbol, setHighlightSymbol] = useState(null);
  const { prices, marketStatus, news: wsNews, connected, onTick, onAlert } = useMarketFeed(token);
  const { botPrices: rawBot, news: polledNews } = useMarketBot();

  // Prefer WS-broadcast news (real-time on each cycle) over the 30s poll,
  // but fall back to polled news if WS hasn't delivered yet.
  const news = useMemo(
    () => (Object.keys(wsNews || {}).length ? wsNews : polledNews),
    [wsNews, polledNews]
  );
  // Re-build bot enrichment using the freshest news source
  const botPrices = useMemo(() => {
    const m = { ...rawBot };
    Object.entries(news || {}).forEach(([sym, reason]) => {
      m[sym] = { ...(m[sym] || {}), reason };
    });
    return m;
  }, [rawBot, news]);

  const refreshPortfolio = useCallback(async () => {
    try {
      const { data } = await api.get("/portfolio");
      setPortfolio(data);
    } catch (e) {
      if (e?.response?.status === 401) logout();
    }
  }, [logout]);

  const refreshWatchlist = useCallback(async () => {
    try {
      const { data } = await api.get("/watchlist");
      setWatchlist(data.symbols || []);
    } catch {}
  }, []);

  const toggleWatch = useCallback(async (symbol) => {
    const isWatched = watchlist.includes(symbol);
    setWatchlist((prev) => isWatched ? prev.filter((s) => s !== symbol) : [...prev, symbol]);
    try {
      if (isWatched) {
        await api.delete(`/watchlist/${symbol}`);
        toast.success(`Removed ${symbol} from watchlist`);
      } else {
        await api.post("/watchlist", { symbol });
        toast.success(`Added ${symbol} to watchlist`);
      }
    } catch (e) {
      setWatchlist((prev) => isWatched ? [...prev, symbol] : prev.filter((s) => s !== symbol));
      toast.error(e?.response?.data?.detail || "Watchlist update failed");
    }
  }, [watchlist]);

  // Cross-tab navigation: jump to Market tab and spotlight a symbol.
  const jumpToSymbol = useCallback((sym) => {
    if (!sym) return;
    setTab("Market");
    setHighlightSymbol(sym);
    // clear highlight after 4s so subsequent jumps always retrigger scroll + flash
    setTimeout(() => setHighlightSymbol((cur) => (cur === sym ? null : cur)), 4000);
  }, []);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const [s, p] = await Promise.all([
          api.get("/stocks"),
          api.get("/prices"),
        ]);
        setStocks(s.data.stocks || []);
        setSparks(p.data.sparks || {});
      } catch {}
    })();
    refreshPortfolio();
    refreshWatchlist();
    const id = setInterval(refreshPortfolio, 30000);
    return () => clearInterval(id);
  }, [user, refreshPortfolio, refreshWatchlist]);

  useEffect(() => {
    if (!user) return;
    const id = setInterval(async () => {
      try {
        const { data } = await api.get("/prices");
        setSparks(data.sparks || {});
      } catch {}
    }, 30000);
    return () => clearInterval(id);
  }, [user]);

  const newsTicker = useMemo(() => {
    const items = Object.entries(news || {})
      .filter(([, r]) => r)
      .map(([sym, r]) => `${sym}: ${r}`)
      .slice(0, 8);
    return items;
  }, [news]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ color: "var(--text-secondary)" }}>
        Loading…
      </div>
    );
  }
  if (!user) return <AuthPage />;

  return (
    <div className="min-h-screen pb-24">
      <Navbar portfolio={portfolio} marketStatus={marketStatus} tab={tab} setTab={setTab} onAlert={onAlert} onJumpToSymbol={jumpToSymbol} />
      <IndicesTicker newsItems={newsTicker} />
      {tab === "Market" && (
        <MarketTab
          prices={prices}
          botPrices={botPrices}
          sparks={sparks}
          stocks={stocks}
          portfolio={portfolio}
          marketStatus={marketStatus}
          watchlist={watchlist}
          onToggleWatch={toggleWatch}
          onPortfolioChange={(p) => setPortfolio(p)}
          onTickListener={onTick}
          highlightSymbol={highlightSymbol}
        />
      )}
      {tab === "Watchlist" && (
        <WatchlistTab
          prices={prices}
          botPrices={botPrices}
          sparks={sparks}
          stocks={stocks}
          portfolio={portfolio}
          marketStatus={marketStatus}
          watchlist={watchlist}
          onToggleWatch={toggleWatch}
          onPortfolioChange={(p) => setPortfolio(p)}
          onTickListener={onTick}
        />
      )}
      {tab === "Portfolio" && (
        <PortfolioTab
          portfolio={portfolio}
          prices={prices}
          stocks={stocks}
          marketStatus={marketStatus}
          onPortfolioChange={(p) => setPortfolio(p)}
        />
      )}
      {tab === "History" && <HistoryTab />}
      {tab === "Leaderboard" && <LeaderboardTab />}
      {tab === "News" && <NewsTab onJumpToSymbol={jumpToSymbol} />}
      {tab === "Admin" && user?.isAdmin && <AdminTab />}

      {!connected && (
        <div
          className="fixed left-4 bottom-10 text-xs px-3 py-1.5 rounded-md"
          style={{ background: "var(--amber-dim)", color: "var(--amber)", border: "1px solid var(--amber)" }}
          data-testid="ws-disconnected"
        >
          Live feed reconnecting…
        </div>
      )}

      <div
        data-testid="disclaimer"
        style={{
          background: "var(--amber-dim)",
          border: "1px solid var(--amber)",
          borderRadius: 8,
          margin: "16px 24px",
          padding: "10px 16px",
          fontSize: 12,
          color: "var(--text-secondary)",
          lineHeight: 1.6,
        }}
      >
        ⚠️ <strong>Educational Simulator Only:</strong> SCALE India Investment is a paper-trading simulator using fictional stock units representing 1% of AI-estimated private startup valuations. Prices also respond to real student buy/sell activity on this platform. No real securities, real money, or real trading is involved. Valuations are generated by MarketBot AI and are not financial advice. Not affiliated with SEBI, NSE, BSE, or any startup listed here. Virtual currency (SimRupees ₹S) has no real-world value.
      </div>

      <Toaster />
      <MarketBotChat />
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

export default App;

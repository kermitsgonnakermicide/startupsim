import React, { useEffect, useState } from "react";
import { istClock, countdown } from "../utils/marketTiming";
import { fmtINR, fmtPct } from "../utils/formatters";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import ChangePasswordModal from "./ChangePasswordModal";
import AlertsBell from "./AlertsBell";

const StatusDot = ({ color, pulse }) => (
  <span
    className={pulse ? "dot-pulse" : ""}
    style={{
      display: "inline-block",
      width: 8,
      height: 8,
      borderRadius: 999,
      background: color,
    }}
  />
);

const LogoMark = () => (
  <div
    aria-hidden="true"
    style={{
      width: 32,
      height: 32,
      borderRadius: 6,
      border: "1px solid var(--border)",
      background: "linear-gradient(135deg, rgba(160,30,32,0.22), rgba(37,99,235,0.22))",
      display: "grid",
      placeItems: "center",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
    }}
  >
    <span className="mono" style={{ color: "var(--blue)", fontSize: 13, fontWeight: 700, letterSpacing: "-0.06em" }}>
      SC
    </span>
  </div>
);

const Pill = ({ label, value, tone = "neutral", sub, testid }) => {
  const bg =
    tone === "up" ? "var(--green-dim)" :
    tone === "down" ? "var(--red-dim)" :
    "var(--bg-elevated)";
  const color =
    tone === "up" ? "var(--green)" :
    tone === "down" ? "var(--red)" :
    "var(--text-primary)";
  return (
    <div
      data-testid={testid}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
      style={{ background: bg, border: "1px solid var(--border)" }}
    >
      <span style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
        {label}
      </span>
      <span className="mono" style={{ fontSize: 13, fontWeight: 600, color }}>
        {value}
      </span>
      {sub && <span className="mono" style={{ fontSize: 11, color }}>({sub})</span>}
    </div>
  );
};

const Navbar = ({ portfolio, marketStatus, tab, setTab, onAlert, onJumpToSymbol }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [clock, setClock] = useState(istClock());
  const [cd, setCd] = useState("");
  const [showCp, setShowCp] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      setClock(istClock());
      if (marketStatus?.countdownTo) setCd(countdown(marketStatus.countdownTo));
    }, 1000);
    return () => clearInterval(id);
  }, [marketStatus]);

  const mkt = marketStatus || {};
  const st = mkt.sessionType;
  const holiday = !!mkt.holidayOverride;
  const colorMap = {
    REGULAR: { dot: "var(--green)", label: "MARKET OPEN", pulse: true },
    PRE_OPEN: { dot: "var(--amber)", label: "PRE-OPEN", pulse: true },
    POST_CLOSE: { dot: "var(--blue)", label: "POST-CLOSE", pulse: false },
    CLOSED: { dot: "#64748b", label: holiday ? "MARKET HOLIDAY" : "MARKET CLOSED", pulse: false },
  };
  const mc = colorMap[st] || colorMap.CLOSED;

  const pnl = portfolio?.totalPnl ?? 0;
  const pnlTone = pnl >= 0 ? "up" : "down";
  const day = portfolio?.dayChange ?? 0;
  const dayTone = day >= 0 ? "up" : "down";

  const tabs = ["Market", "Watchlist", "Portfolio", "History", "Leaderboard", "News"];
  if (user?.isAdmin) tabs.push("Admin");

  return (
    <div className="sticky top-0 z-20" style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border)" }}>
      <div className="flex items-center px-6 py-3 gap-4 flex-wrap">
        <div className="flex items-baseline gap-2">
          <LogoMark />
          <span className="mono" style={{ color: "var(--blue)", fontSize: 20, fontWeight: 700, letterSpacing: "-0.03em" }}>SCALE</span>
          <span style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase" }}>
            India Investment
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 ml-2">
          <Pill testid="pill-cash" label="SimRupees ₹S" value={fmtINR(portfolio?.cash)} />
          <Pill testid="pill-value" label="Portfolio" value={fmtINR(portfolio?.totalValue)} />
          <Pill testid="pill-pnl" label="P&L" value={fmtINR(portfolio?.totalPnl)} tone={pnlTone} sub={fmtPct(portfolio?.totalPnlPct)} />
          <Pill testid="pill-day" label="Day" value={fmtINR(day)} tone={dayTone} />
        </div>

        <div className="ml-auto flex items-center gap-3 flex-wrap">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
            data-testid="market-status-badge"
          >
            <StatusDot color={mc.dot} pulse={mc.pulse} />
            <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: mc.dot }}>
              {mc.label}
            </span>
            {cd && mc.label === "MARKET OPEN" && (
              <span className="mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                {mkt.countdownLabel} {cd}
              </span>
            )}
            {holiday && mkt.nseMarketStatusMessage && (
              <span className="mono" style={{ fontSize: 11, color: "var(--text-secondary)" }} data-testid="holiday-msg">
                {mkt.nseMarketStatusMessage}
              </span>
            )}
          </div>
          <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }} data-testid="ist-clock">
            IST {clock}
          </span>
          <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Hello,{" "}
            <span className="mono" style={{ color: "var(--text-primary)" }}>@{user?.username}</span>
            {user?.isAdmin && (
              <span className="pill ml-2" style={{ background: "var(--blue-dim)", color: "var(--blue)", fontWeight: 600 }} data-testid="admin-badge">
                CREATOR
              </span>
            )}
          </span>
          <button
            data-testid="theme-toggle"
            onClick={toggleTheme}
            className="btn-ghost px-3 py-1.5 rounded-md text-xs"
            title="Toggle light/dark mode"
          >
            {theme === "dark" ? "🌙" : "☀️"}
          </button>
          <AlertsBell onAlert={onAlert} onJumpToSymbol={onJumpToSymbol} />
          <button
            data-testid="change-pw-btn"
            onClick={() => setShowCp(true)}
            className="btn-ghost px-3 py-1.5 rounded-md text-xs"
            title="Change password"
          >
            ⚙
          </button>
          <button
            data-testid="logout-btn"
            onClick={logout}
            className="btn-ghost px-3 py-1.5 rounded-md text-xs"
          >
            Log Out
          </button>
        </div>
      </div>

      <div className="flex px-6 gap-1">
        {tabs.map((t) => (
          <button
            key={t}
            data-testid={`tab-${t.toLowerCase()}`}
            onClick={() => setTab(t)}
            className="px-4 py-2.5 text-sm transition"
            style={{
              color: tab === t ? "var(--blue)" : "var(--text-secondary)",
              borderBottom: tab === t ? "2px solid var(--blue)" : "2px solid transparent",
              fontWeight: tab === t ? 600 : 400,
              letterSpacing: "0.04em",
            }}
          >
            {t}
          </button>
        ))}
      </div>
      <ChangePasswordModal open={showCp} onClose={() => setShowCp(false)} />
    </div>
  );
};

export default Navbar;

import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtINR, fmtPct } from "../utils/formatters";

const BADGE_STYLE = {
  BULL: { bg: "var(--green-dim)", color: "var(--green)" },
  TRADER: { bg: "var(--blue-dim)", color: "var(--blue)" },
  HODLER: { bg: "rgba(148,163,184,0.15)", color: "#94a3b8" },
  BEAR: { bg: "var(--red-dim)", color: "var(--red)" },
};

const medalFor = (rank) => (rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : null);

const LeaderboardTab = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get("/leaderboard");
        if (!cancelled) setData(data);
      } catch {
        if (!cancelled) setData({ rows: [], totalPlayers: 0, me: null });
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!data) return <div className="p-8 text-center" style={{ color: "var(--text-muted)" }}>Loading…</div>;

  const me = data.me;
  const myBadge = me?.badge || "HODLER";

  return (
    <div className="px-6 py-5 space-y-4" data-testid="leaderboard-tab">
      <div className="surface rounded-xl p-5 flex flex-wrap items-center gap-4">
        <div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Your Rank</div>
          <div className="mono" style={{ fontSize: 26, fontWeight: 600 }}>
            {me ? `#${me.rank}` : "—"}{" "}
            <span style={{ color: "var(--text-secondary)", fontSize: 14, fontWeight: 400 }}>of {data.totalPlayers}</span>
          </div>
        </div>
        <div className="ml-auto">
          <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Your Badge</div>
          <span
            className="pill"
            style={{
              background: BADGE_STYLE[myBadge].bg,
              color: BADGE_STYLE[myBadge].color,
              fontSize: 14,
              fontWeight: 600,
              padding: "6px 14px",
              marginTop: 4,
              display: "inline-block",
            }}
          >
            {myBadge}
          </span>
        </div>
      </div>

      <div className="surface rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                {["Rank", "Player", "Current Value", "P&L", "Return %", "Badge"].map((h, i) => (
                  <th key={i} className="text-left px-3 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => {
                const medal = medalFor(r.rank);
                const st = BADGE_STYLE[r.badge];
                return (
                  <tr
                    key={`${r.rank}-${r.username}`}
                    data-testid={r.isCurrentUser ? "leaderboard-me" : undefined}
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      background: r.isCurrentUser ? "var(--bg-elevated)" : "transparent",
                      boxShadow: r.isCurrentUser ? "inset 0 0 0 1px var(--blue)" : "none",
                    }}
                  >
                    <td className="px-3 py-2.5 mono" style={{ fontWeight: 600 }}>{medal || `#${r.rank}`}</td>
                    <td className="px-3 py-2.5">
                      <span className="mono" style={{ color: "var(--text-primary)" }}>@{r.username}</span>{" "}
                      {r.isCurrentUser && (
                        <span className="pill" style={{ background: "var(--blue-dim)", color: "var(--blue)", marginLeft: 6 }}>YOU</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 mono" style={{ fontWeight: 600 }}>{fmtINR(r.currentValue)}</td>
                    <td className="px-3 py-2.5 mono" style={{ color: r.pnl >= 0 ? "var(--green)" : "var(--red)" }}>{fmtINR(r.pnl)}</td>
                    <td className="px-3 py-2.5 mono" style={{ color: r.returnPct >= 0 ? "var(--green)" : "var(--red)", fontWeight: 600 }}>
                      {fmtPct(r.returnPct)}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="pill" style={{ background: st.bg, color: st.color, fontWeight: 600 }}>{r.badge}</span>
                    </td>
                  </tr>
                );
              })}
              {data.rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-12 text-center" style={{ color: "var(--text-muted)" }} data-testid="leaderboard-empty">
                    No traders yet — be the first to make a trade! 🚀
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default LeaderboardTab;

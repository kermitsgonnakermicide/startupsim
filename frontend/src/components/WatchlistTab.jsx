import React, { useEffect, useMemo, useRef, useState } from "react";
import { fmtINR, fmtNum, fmtPct, fmtVolume } from "../utils/formatters";
import Sparkline from "./Sparkline";
import TradeModal from "./TradeModal";
import ChartModal from "./ChartModal";
import AlertModal from "./AlertModal";

const WatchlistTab = ({ prices, botPrices, sparks, stocks, portfolio, marketStatus, watchlist, onToggleWatch, onPortfolioChange, onTickListener }) => {
  const [modal, setModal] = useState(null);
  const [chart, setChart] = useState(null);
  const [alertModal, setAlertModal] = useState(null);
  const rowRefs = useRef({});

  // merge bot enrichment onto live prices
  const mergedPrices = useMemo(() => {
    const m = {};
    Object.keys(botPrices || {}).forEach((s) => { m[s] = { ...botPrices[s] }; });
    Object.entries(prices || {}).forEach(([s, p]) => {
      if (p?.price) m[s] = { ...m[s], ...p };
    });
    return m;
  }, [prices, botPrices]);

  useEffect(() => {
    if (!onTickListener) return;
    const off = onTickListener((ev) => {
      const el = rowRefs.current[ev.symbol];
      if (!el) return;
      const cls = (ev.change || 0) >= 0 ? "flash-green" : "flash-red";
      el.classList.remove("flash-green", "flash-red");
      void el.offsetWidth;
      el.classList.add(cls);
    });
    return off;
  }, [onTickListener]);

  const watched = useMemo(() => {
    const set = new Set(watchlist || []);
    return stocks.filter((s) => set.has(s.symbol));
  }, [stocks, watchlist]);

  const holdingsMap = useMemo(() => {
    const m = {};
    (portfolio?.holdings || []).forEach((h) => { m[h.symbol] = h; });
    return m;
  }, [portfolio]);

  const marketClosed = !marketStatus || (marketStatus?.status || "").toUpperCase() !== "OPEN";
  const prevTradedLabel = useMemo(() => {
    const td = marketStatus?.tradeDate;
    if (!td) return "Prev close";
    const datePart = String(td).split(" ")[0];
    const bits = datePart.split("-");
    if (bits.length >= 2) return `Last traded ${bits[0]} ${bits[1]}`;
    return "Prev close";
  }, [marketStatus?.tradeDate]);

  return (
    <div className="px-6 py-5" data-testid="watchlist-tab">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>My Watchlist</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 2 }}>
            {watched.length} {watched.length === 1 ? "stock" : "stocks"} starred · live prices stream in real-time
          </div>
        </div>
      </div>

      {watched.length === 0 ? (
        <div className="surface rounded-xl p-12 text-center" data-testid="watchlist-empty">
          <div style={{ fontSize: 36, marginBottom: 12, color: "var(--text-muted)" }}>☆</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>No watched stocks yet</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>
            Tap the ☆ next to any stock in the <strong style={{ color: "var(--blue)" }}>Market</strong> tab to track it here.
          </div>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden surface">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                  {["", "Symbol", "Name", "Sector", "LTP", "Open", "High", "Low", "Chg", "Chg %", "Vol", "Updated", "Trend", ""].map((h, i) => (
                    <th key={i} className="text-left px-3 py-2.5" style={{ borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {watched.map((r) => {
                  const p = mergedPrices[r.symbol] || {};
                  const held = holdingsMap[r.symbol];
                  const up = (p.changePct || 0) >= 0;
                  return (
                    <tr
                      key={r.symbol}
                      ref={(el) => { if (el) rowRefs.current[r.symbol] = el; }}
                      className={`tr-hover ${held ? "tr-held" : ""}`}
                      style={{ borderTop: "1px solid var(--border-subtle)" }}
                      data-testid={`watch-row-${r.symbol}`}
                    >
                      <td className="px-3 py-2.5">
                        <button
                          data-testid={`watch-unstar-${r.symbol}`}
                          onClick={() => onToggleWatch(r.symbol)}
                          title="Remove from watchlist"
                          className="text-base"
                          style={{ color: "var(--amber)", lineHeight: 1, padding: 2, cursor: "pointer" }}
                        >
                          ★
                        </button>
                      </td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--blue)", fontWeight: 600, fontSize: 13, cursor: "pointer" }} onClick={() => setChart({ symbol: r.symbol, stock: r })}>{r.symbol}</td>
                      <td className="px-3 py-2.5" style={{ color: "var(--text-primary)", maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", cursor: "pointer" }} onClick={() => setChart({ symbol: r.symbol, stock: r })}>
                        {r.name}
                      </td>
                      <td className="px-3 py-2.5" style={{ color: "var(--text-secondary)", fontSize: 12 }}>{r.sector}</td>
                      <td className="px-3 py-2.5 mono" style={{ fontWeight: 600 }}>{p.price ? fmtNum(p.price) : "—"}</td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)" }}>{p.open ? fmtNum(p.open) : "—"}</td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)" }}>{p.high ? fmtNum(p.high) : "—"}</td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)" }}>{p.low ? fmtNum(p.low) : "—"}</td>
                      <td className="px-3 py-2.5 mono" style={{ color: up ? "var(--green)" : "var(--red)" }}>
                        {p.change != null ? (up ? "+" : "") + fmtNum(p.change) : "—"}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="pill mono" style={{ background: up ? "var(--green-dim)" : "var(--red-dim)", color: up ? "var(--green)" : "var(--red)" }}>
                          {p.changePct != null ? fmtPct(p.changePct) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)", fontSize: 12 }}>{fmtVolume(p.volume)}</td>
                      <td className="px-3 py-2.5 mono" style={{ color: "var(--text-muted)", fontSize: 11, whiteSpace: "nowrap" }}>
                        {marketClosed ? prevTradedLabel : (p.lastUpdated ? p.lastUpdated.split(" ").slice(-1)[0] : "—")}
                      </td>
                      <td className="px-3 py-2.5"><Sparkline points={sparks[r.symbol] || []} /></td>
                      <td className="px-3 py-2.5">
                        <div className="flex gap-1.5">
                          <button
                            data-testid={`watch-buy-${r.symbol}`}
                            onClick={() => setModal({ mode: "BUY", symbol: r.symbol, stock: r })}
                            disabled={!p.price || marketClosed}
                            title={marketClosed ? "Market is closed" : ""}
                            className="btn-buy px-2.5 py-1 rounded-md text-xs font-medium"
                            style={{ opacity: (!p.price || marketClosed) ? 0.5 : 1, cursor: marketClosed ? "not-allowed" : "pointer" }}
                          >
                            Buy
                          </button>
                          <button
                            data-testid={`watch-sell-${r.symbol}`}
                            onClick={() => setModal({ mode: "SELL", symbol: r.symbol, stock: r })}
                            disabled={!held || !p.price || marketClosed}
                            title={marketClosed ? "Market is closed" : ""}
                            className="btn-sell px-2.5 py-1 rounded-md text-xs font-medium"
                            style={{ opacity: (!held || !p.price || marketClosed) ? 0.35 : 1, cursor: marketClosed ? "not-allowed" : "pointer" }}
                          >
                            Sell
                          </button>
                          <button
                            data-testid={`watch-alert-${r.symbol}`}
                            onClick={() => setAlertModal({ symbol: r.symbol, stock: r, price: p.price })}
                            disabled={!p.price}
                            title="Set price alert"
                            className="btn-ghost px-2 py-1 rounded-md text-xs"
                            style={{ opacity: !p.price ? 0.4 : 1, cursor: !p.price ? "not-allowed" : "pointer" }}
                          >
                            🔔
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <TradeModal
        open={!!modal}
        onClose={() => setModal(null)}
        mode={modal?.mode}
        symbol={modal?.symbol}
        stock={modal?.stock}
        livePrice={modal ? mergedPrices[modal.symbol]?.price : null}
        portfolio={portfolio}
        marketClosed={marketClosed}
        onDone={(p) => onPortfolioChange(p)}
      />

      <ChartModal
        open={!!chart}
        onClose={() => setChart(null)}
        symbol={chart?.symbol}
        stock={chart?.stock}
        livePrice={chart ? mergedPrices[chart.symbol]?.price : null}
        marketClosed={marketClosed}
        onTrade={(mode) => { setChart(null); setModal({ mode, symbol: chart.symbol, stock: chart.stock }); }}
      />

      <AlertModal
        open={!!alertModal}
        onClose={() => setAlertModal(null)}
        symbol={alertModal?.symbol}
        stock={alertModal?.stock}
        currentPrice={alertModal ? mergedPrices[alertModal.symbol]?.price : null}
      />
    </div>
  );
};

export default WatchlistTab;

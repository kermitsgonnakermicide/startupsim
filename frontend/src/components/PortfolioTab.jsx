import React, { useState } from "react";
import { fmtINR, fmtNum, fmtPct } from "../utils/formatters";
import SectorDonut from "./SectorDonut";
import TradeModal from "./TradeModal";

const Card = ({ label, value, tone }) => {
  const color =
    tone === "up" ? "var(--green)" : tone === "down" ? "var(--red)" : "var(--text-primary)";
  return (
    <div className="surface rounded-xl p-4">
      <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 600, marginTop: 4, color }}>
        {value}
      </div>
    </div>
  );
};

const PortfolioTab = ({ portfolio, prices, stocks, marketStatus, onPortfolioChange }) => {
  const [modal, setModal] = useState(null);
  const holdings = portfolio?.holdings || [];
  const pnlTone = (portfolio?.totalPnl ?? 0) >= 0 ? "up" : "down";
  const marketClosed = marketStatus?.sessionType === "CLOSED" || (marketStatus?.status && marketStatus.status !== "OPEN");

  const stockFor = (sym) => stocks.find((s) => s.symbol === sym);

  return (
    <div className="px-6 py-5 space-y-5" data-testid="portfolio-tab">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card label="Invested" value={fmtINR(portfolio?.totalInvested)} />
        <Card label="Current Value" value={fmtINR(portfolio?.holdingsValue)} />
        <Card label="Unrealized P&L" value={fmtINR(portfolio?.totalPnl)} tone={pnlTone} />
        <Card label="Return %" value={fmtPct(portfolio?.totalPnlPct)} tone={pnlTone} />
      </div>

      <div className="surface rounded-xl overflow-hidden">
        <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.04em" }}>Holdings</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12 }}>{holdings.length} positions</div>
        </div>
        {holdings.length === 0 ? (
          <div className="p-8 text-center" style={{ color: "var(--text-muted)" }} data-testid="holdings-empty">
            No holdings yet. Start trading from the Market tab.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                  {["Symbol", "Name", "Qty", "Avg Cost", "CMP", "Value", "P&L", "P&L %", ""].map((h, i) => (
                    <th key={i} className="text-left px-3 py-2.5" style={{ borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {holdings
                  .slice()
                  .sort((a, b) => b.pnlPct - a.pnlPct)
                  .map((h) => {
                    const up = h.pnl >= 0;
                    return (
                      <tr key={h.symbol} className="tr-hover" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                        <td className="px-3 py-2.5 mono" style={{ color: "var(--blue)", fontWeight: 600 }}>{h.symbol}</td>
                        <td className="px-3 py-2.5" style={{ color: "var(--text-primary)" }}>{h.name}</td>
                        <td className="px-3 py-2.5 mono">{h.qty}</td>
                        <td className="px-3 py-2.5 mono">{fmtNum(h.avgBuyPrice)}</td>
                        <td className="px-3 py-2.5 mono" style={{ fontWeight: 600 }}>{fmtNum(h.ltp)}</td>
                        <td className="px-3 py-2.5 mono">{fmtINR(h.currentValue)}</td>
                        <td className="px-3 py-2.5 mono" style={{ color: up ? "var(--green)" : "var(--red)" }}>{fmtINR(h.pnl)}</td>
                        <td className="px-3 py-2.5">
                          <span className="pill mono" style={{ background: up ? "var(--green-dim)" : "var(--red-dim)", color: up ? "var(--green)" : "var(--red)" }}>
                            {fmtPct(h.pnlPct)}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            data-testid={`holding-sell-${h.symbol}`}
                            onClick={() => setModal({ mode: "SELL", symbol: h.symbol, stock: stockFor(h.symbol) })}
                            disabled={marketClosed}
                            title={marketClosed ? "Market is closed" : ""}
                            className="btn-sell px-2.5 py-1 rounded-md text-xs font-medium"
                            style={{ opacity: marketClosed ? 0.5 : 1, cursor: marketClosed ? "not-allowed" : "pointer" }}
                          >
                            Sell
                          </button>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {holdings.length > 0 && (
        <div className="surface rounded-xl p-5">
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.04em", marginBottom: 12 }}>Sector Allocation</div>
          <SectorDonut holdings={holdings} />
        </div>
      )}

      <TradeModal
        open={!!modal}
        onClose={() => setModal(null)}
        mode={modal?.mode}
        symbol={modal?.symbol}
        stock={modal?.stock}
        livePrice={modal ? prices[modal.symbol]?.price : null}
        portfolio={portfolio}
        marketClosed={marketClosed}
        onDone={(p) => onPortfolioChange(p)}
      />
    </div>
  );
};

export default PortfolioTab;

import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { fmtINR, fmtNum } from "../utils/formatters";
import { toast } from "sonner";

const TradeModal = ({ open, onClose, mode, symbol, stock, livePrice, portfolio, marketClosed, onDone }) => {
  const [qty, setQty] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [byAmount, setByAmount] = useState(false); // toggle: by qty vs by ₹ amount
  const [amount, setAmount] = useState("");

  useEffect(() => { setQty(1); setAmount(""); setByAmount(false); }, [open, symbol, mode]);

  // When user enters amount, compute shares = floor(amount / price)
  useEffect(() => {
    if (!byAmount) return;
    const amt = Number(amount);
    if (!amt || !livePrice || livePrice <= 0) { setQty(0); return; }
    setQty(Math.max(0, Math.floor(amt / livePrice)));
  }, [amount, livePrice, byAmount]);

  const holding = useMemo(
    () => portfolio?.holdings?.find((h) => h.symbol === symbol),
    [portfolio, symbol]
  );
  const sharesHeld = holding?.qty || 0;
  const cash = portfolio?.cash || 0;
  const total = (livePrice || 0) * qty;
  const remainder = byAmount && livePrice ? Math.max(0, Number(amount || 0) - total) : 0;
  const insufficientCash = mode === "BUY" && total > cash;
  const overSell = mode === "SELL" && qty > sharesHeld;
  const invalid = qty <= 0 || !livePrice || insufficientCash || overSell || !!marketClosed;

  if (!open) return null;

  const submit = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.post("/trade", {
        symbol,
        type: mode,
        qty: Number(qty),
        price: livePrice,
      });
      toast.success(
        `${mode === "BUY" ? "Bought" : "Sold"} ${qty} ${symbol} @ ₹${data.fillPrice.toFixed(2)}`
      );
      onDone?.(data.portfolio);
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Trade failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={onClose}
      data-testid="trade-modal"
    >
      <div
        className="w-full max-w-[420px] rounded-2xl p-6 surface"
        onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: "0 32px 80px rgba(0,0,0,0.6)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span
                className="pill"
                style={{
                  background: mode === "BUY" ? "var(--blue-dim)" : "var(--red-dim)",
                  color: mode === "BUY" ? "var(--blue)" : "var(--red)",
                }}
              >
                {mode}
              </span>
              <span className="mono" style={{ fontSize: 18, fontWeight: 600 }}>{symbol}</span>
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 2 }}>
              {stock?.name} · {stock?.sector}
            </div>
          </div>
          <button onClick={onClose} style={{ color: "var(--text-secondary)" }} data-testid="modal-close">✕</button>
        </div>

        <div className="rounded-xl p-4 mb-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            Live Price
          </div>
          <div className="mono" style={{ fontSize: 28, fontWeight: 600, marginTop: 2 }}>
            {livePrice ? fmtINR(livePrice) : "—"}
          </div>
        </div>

        <div className="mb-3 flex gap-1 p-1 rounded-lg" style={{ background: "var(--bg-elevated)" }}>
          <button
            type="button"
            data-testid="mode-qty"
            onClick={() => setByAmount(false)}
            className="flex-1 py-1.5 rounded-md text-xs"
            style={{
              background: !byAmount ? "var(--bg-surface)" : "transparent",
              color: !byAmount ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: !byAmount ? 600 : 400,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            By Quantity
          </button>
          <button
            type="button"
            data-testid="mode-amount"
            onClick={() => setByAmount(true)}
            className="flex-1 py-1.5 rounded-md text-xs"
            style={{
              background: byAmount ? "var(--bg-surface)" : "transparent",
              color: byAmount ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: byAmount ? 600 : 400,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            By ₹ Amount
          </button>
        </div>

        {byAmount ? (
          <div className="mb-4">
            <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
              Invest ₹
            </div>
            <div className="relative">
              <span className="mono absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)", fontSize: 16 }}>₹</span>
              <input
                data-testid="amount-input"
                type="number"
                min={0}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 5000"
                className="mono w-full pl-8 pr-3 py-2.5 rounded-md outline-none"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", fontSize: 16 }}
              />
            </div>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {mode === "BUY" && [1000, 5000, 10000, Math.floor(cash)].map((amt, i) => (
                <button
                  key={i}
                  onClick={() => setAmount(String(amt))}
                  className="btn-ghost px-2.5 py-1 rounded-md text-xs"
                  data-testid={`amount-preset-${i}`}
                >
                  {i === 3 ? "Max" : `₹${amt.toLocaleString("en-IN")}`}
                </button>
              ))}
            </div>
            <div className="mt-2 text-xs mono" style={{ color: "var(--text-secondary)" }}>
              ≈ <span style={{ color: "var(--text-primary)", fontWeight: 600 }} data-testid="computed-qty">{qty}</span> shares
              {qty > 0 && remainder > 0 && (
                <span> · ₹{remainder.toFixed(2)} leftover</span>
              )}
            </div>
          </div>
        ) : (
          <div className="mb-4">
            <div style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
              Quantity
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setQty((q) => Math.max(1, Number(q) - 1))}
                className="btn-ghost w-9 h-9 rounded-md text-lg"
                data-testid="qty-minus"
              >
                −
              </button>
              <input
                data-testid="qty-input"
                type="number"
                min={1}
                value={qty}
                onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                className="mono flex-1 text-center px-3 py-2 rounded-md outline-none"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)", fontSize: 16 }}
              />
              <button
                onClick={() => setQty((q) => Number(q) + 1)}
                className="btn-ghost w-9 h-9 rounded-md text-lg"
                data-testid="qty-plus"
              >
                +
              </button>
              {mode === "SELL" && sharesHeld > 0 && (
                <button
                  onClick={() => setQty(sharesHeld)}
                  className="btn-ghost px-3 h-9 rounded-md text-xs"
                  data-testid="qty-max"
                >
                  MAX
                </button>
              )}
            </div>
          </div>
        )}

        <div className="rounded-xl p-3 mb-4 space-y-1.5 mono text-sm" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
          <Row label={`${qty} × ${livePrice ? fmtNum(livePrice) : "—"}`} value={fmtINR(total)} emphasize />
          <Row label={mode === "BUY" ? "Available SimRupees" : "Shares held"} value={mode === "BUY" ? fmtINR(cash) : `${sharesHeld}`} />
          <Row label={mode === "BUY" ? "SimRupees after trade" : "Shares after trade"} value={mode === "BUY" ? fmtINR(cash - total) : `${sharesHeld - qty}`} />
        </div>

        {insufficientCash && <div className="text-sm mb-3" style={{ color: "var(--red)" }} data-testid="warn-cash">Insufficient SimRupees.</div>}
        {overSell && <div className="text-sm mb-3" style={{ color: "var(--red)" }} data-testid="warn-oversell">You don't hold enough shares.</div>}
        {marketClosed && <div className="text-sm mb-3" style={{ color: "var(--amber)" }} data-testid="warn-market-closed">NSE is currently closed. Trading is disabled.</div>}

        <div className="flex gap-2">
          <button onClick={onClose} className="btn-ghost flex-1 py-2.5 rounded-md text-sm" data-testid="modal-cancel">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={invalid || submitting}
            data-testid="modal-confirm"
            className="flex-1 py-2.5 rounded-md text-sm font-medium"
            style={{
              background: mode === "BUY" ? "var(--blue)" : "var(--red)",
              color: "white",
              opacity: invalid || submitting ? 0.5 : 1,
            }}
          >
            {submitting ? "Processing…" : `Confirm ${mode}`}
          </button>
        </div>
      </div>
    </div>
  );
};

const Row = ({ label, value, emphasize }) => (
  <div className="flex justify-between">
    <span style={{ color: "var(--text-secondary)" }}>{label}</span>
    <span style={{ color: "var(--text-primary)", fontWeight: emphasize ? 600 : 400 }}>{value}</span>
  </div>
);

export default TradeModal;

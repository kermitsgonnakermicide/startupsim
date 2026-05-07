import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { fmtNum } from "../utils/formatters";
import { toast } from "sonner";

/** Modal to create a threshold price alert for a symbol.
 *  Props: open, onClose, symbol, stock, currentPrice, onCreated(alert)
 */
const AlertModal = ({ open, onClose, symbol, stock, currentPrice, onCreated }) => {
  const [direction, setDirection] = useState("above");
  const [target, setTarget] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    // Seed target to +2% / -2% of current
    if (currentPrice) {
      const seed = direction === "above" ? currentPrice * 1.02 : currentPrice * 0.98;
      setTarget(seed.toFixed(2));
    }
    setNote("");
  }, [open, symbol]); // eslint-disable-line

  useEffect(() => {
    if (!open || !currentPrice) return;
    const seed = direction === "above" ? currentPrice * 1.02 : currentPrice * 0.98;
    setTarget(seed.toFixed(2));
  }, [direction]); // eslint-disable-line

  const diff = useMemo(() => {
    const t = parseFloat(target);
    if (!t || !currentPrice) return null;
    const pct = ((t - currentPrice) / currentPrice) * 100;
    return { abs: t - currentPrice, pct };
  }, [target, currentPrice]);

  if (!open) return null;

  const requestNotifyPermission = () => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission().catch(() => {});
    }
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    const t = parseFloat(target);
    if (!t || t <= 0) {
      toast.error("Enter a valid target price");
      return;
    }
    setSubmitting(true);
    try {
      const { data } = await api.post("/alerts", {
        symbol,
        targetPrice: t,
        direction,
        note: note.trim(),
      });
      requestNotifyPermission();
      toast.success(`Alert set for ${symbol} ${direction === "above" ? "≥" : "≤"} ${fmtNum(t)}`);
      onCreated?.(data.alert);
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create alert");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ background: "rgba(5, 8, 16, 0.72)", backdropFilter: "blur(4px)", zIndex: 100 }}
      onClick={onClose}
      data-testid="alert-modal"
    >
      <div
        className="surface rounded-xl p-6 w-full"
        style={{ maxWidth: 460, border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <div style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--text-muted)", textTransform: "uppercase" }}>
              Threshold Alert
            </div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: "var(--blue)", marginTop: 2 }}>
              {symbol}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{stock?.name}</div>
          </div>
          <div className="text-right">
            <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Current
            </div>
            <div className="mono" style={{ fontSize: 16, fontWeight: 600 }}>
              ₹{currentPrice ? fmtNum(currentPrice) : "—"}
            </div>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div className="flex gap-2" data-testid="alert-direction">
            {[
              ["above", "▲ Notify when price rises above"],
              ["below", "▼ Notify when price drops below"],
            ].map(([v, label]) => {
              const active = direction === v;
              const col = v === "above" ? "var(--green)" : "var(--red)";
              return (
                <button
                  key={v}
                  type="button"
                  data-testid={`alert-dir-${v}`}
                  onClick={() => setDirection(v)}
                  className="flex-1 px-3 py-2 rounded-md text-xs transition"
                  style={{
                    background: active ? (v === "above" ? "var(--green-dim)" : "var(--red-dim)") : "var(--bg-elevated)",
                    color: active ? col : "var(--text-secondary)",
                    border: `1px solid ${active ? col : "var(--border)"}`,
                    fontWeight: active ? 600 : 500,
                    textAlign: "left",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <div>
            <label style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Target Price (₹)
            </label>
            <input
              data-testid="alert-target-input"
              type="number"
              step="0.01"
              min="0.01"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="mono w-full px-3 py-2 rounded-md text-sm outline-none mt-1"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              autoFocus
            />
            {diff && (
              <div className="mono mt-1" style={{ fontSize: 11, color: diff.pct >= 0 ? "var(--green)" : "var(--red)" }}>
                {diff.pct >= 0 ? "+" : ""}{diff.pct.toFixed(2)}% from current ({diff.abs >= 0 ? "+" : ""}₹{fmtNum(Math.abs(diff.abs))})
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: 11, color: "var(--text-secondary)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Note (optional)
            </label>
            <input
              data-testid="alert-note-input"
              type="text"
              maxLength={120}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Planning to buy more below this"
              className="w-full px-3 py-2 rounded-md text-sm outline-none mt-1"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            />
          </div>

          <div
            style={{
              background: "var(--blue-dim)",
              border: "1px solid var(--blue)",
              borderRadius: 8,
              padding: "8px 12px",
              fontSize: 11,
              color: "var(--text-secondary)",
              lineHeight: 1.5,
            }}
          >
            You'll receive a browser notification and in-app toast when the price crosses your target. Make sure to allow notifications when prompted.
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              data-testid="alert-cancel"
              className="btn-ghost px-4 py-2 rounded-md text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="alert-submit"
              disabled={submitting || !target}
              className="px-4 py-2 rounded-md text-xs"
              style={{
                background: "var(--blue)",
                color: "#fff",
                fontWeight: 600,
                opacity: submitting ? 0.6 : 1,
                cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              {submitting ? "Setting…" : "Set Alert"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AlertModal;

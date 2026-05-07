import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { fmtNum } from "../utils/formatters";
import { toast } from "sonner";

/** Navbar bell that shows active threshold alerts + recently triggered ones.
 *  Listens to the ALERT WS events via `onAlert` prop and keeps a rolling
 *  list of triggered alerts for the session.
 */
const AlertsBell = ({ onAlert, onJumpToSymbol }) => {
  const [alerts, setAlerts] = useState([]);
  const [triggeredHistory, setTriggeredHistory] = useState([]);
  const [open, setOpen] = useState(false);
  const [perm, setPerm] = useState(typeof Notification !== "undefined" ? Notification.permission : "default");
  const popRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/alerts");
      setAlerts(data.alerts || []);
    } catch {}
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  // WS alert subscription
  useEffect(() => {
    if (!onAlert) return;
    return onAlert((a) => {
      // Remove from active list, push into history
      setAlerts((prev) => prev.filter((x) => x.id !== a.id));
      setTriggeredHistory((prev) => [{ ...a, receivedAt: Date.now() }, ...prev].slice(0, 30));
      // Native browser notification
      try {
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          const dir = a.direction === "above" ? "rose above" : "dropped below";
          const n = new Notification(`${a.symbol} ${dir} ₹${fmtNum(a.targetPrice)}`, {
            body: `Triggered at ₹${fmtNum(a.triggeredPrice)}${a.note ? ` · ${a.note}` : ""}`,
            tag: `alert-${a.id}`,
            icon: "/favicon.ico",
          });
          n.onclick = () => {
            window.focus();
            onJumpToSymbol?.(a.symbol);
            n.close();
          };
        }
      } catch {}
      // In-app toast fallback
      toast.success(
        `🔔 ${a.symbol} ${a.direction === "above" ? "↑ above" : "↓ below"} ₹${fmtNum(a.targetPrice)} · now ₹${fmtNum(a.triggeredPrice)}`,
        { duration: 6000 },
      );
    });
  }, [onAlert, onJumpToSymbol]);

  // close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (popRef.current && !popRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const requestPermission = async () => {
    if (typeof Notification === "undefined") return;
    try {
      const p = await Notification.requestPermission();
      setPerm(p);
      if (p === "granted") toast.success("Browser notifications enabled");
      else toast.info("Notifications not enabled — you'll still see in-app toasts");
    } catch {}
  };

  const remove = async (id) => {
    try {
      await api.delete(`/alerts/${id}`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
      toast.success("Alert removed");
    } catch {}
  };

  const activeCount = alerts.length;
  const recentHits = triggeredHistory.length;
  const badgeCount = activeCount + recentHits;

  return (
    <div className="relative" ref={popRef}>
      <button
        data-testid="alerts-bell"
        onClick={() => setOpen((v) => !v)}
        className="btn-ghost px-3 py-1.5 rounded-md text-xs relative"
        title={`${activeCount} active alert${activeCount === 1 ? "" : "s"}`}
        style={{ display: "flex", alignItems: "center", gap: 6 }}
      >
        <span style={{ fontSize: 14 }}>🔔</span>
        {badgeCount > 0 && (
          <span
            data-testid="alerts-badge"
            className="mono"
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              background: recentHits > 0 ? "var(--red)" : "var(--blue)",
              color: "#fff",
              borderRadius: 999,
              fontSize: 9,
              fontWeight: 700,
              padding: "1px 5px",
              minWidth: 16,
              textAlign: "center",
              lineHeight: "14px",
            }}
          >
            {badgeCount}
          </span>
        )}
      </button>

      {open && (
        <div
          data-testid="alerts-dropdown"
          className="absolute rounded-xl"
          style={{
            top: "calc(100% + 8px)",
            right: 0,
            width: 340,
            maxHeight: 480,
            overflowY: "auto",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            boxShadow: "0 12px 40px rgba(0,0,0,.45)",
            zIndex: 80,
          }}
        >
          <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Price Alerts</div>
            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
              {activeCount} active · {recentHits} triggered this session
            </div>
            {perm !== "granted" && typeof Notification !== "undefined" && (
              <button
                onClick={requestPermission}
                data-testid="alerts-enable-push"
                className="mt-2 w-full px-3 py-1.5 rounded-md text-xs"
                style={{
                  background: "var(--blue-dim)",
                  color: "var(--blue)",
                  border: "1px solid var(--blue)",
                  fontWeight: 600,
                }}
              >
                Enable browser notifications
              </button>
            )}
          </div>

          {recentHits > 0 && (
            <div>
              <div className="px-4 pt-2.5 pb-1" style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                Recently Triggered
              </div>
              {triggeredHistory.map((a) => (
                <div
                  key={a.id + a.receivedAt}
                  className="px-4 py-2"
                  style={{ borderTop: "1px solid var(--border-subtle)" }}
                  data-testid={`alert-triggered-${a.symbol}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--blue)" }}>
                      {a.symbol}
                    </div>
                    <div style={{ fontSize: 10, color: a.direction === "above" ? "var(--green)" : "var(--red)", fontWeight: 600, letterSpacing: "0.06em" }}>
                      {a.direction === "above" ? "▲ ABOVE" : "▼ BELOW"}
                    </div>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                    target ₹{fmtNum(a.targetPrice)} · hit @ ₹{fmtNum(a.triggeredPrice)}
                  </div>
                  {a.note && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{a.note}</div>}
                </div>
              ))}
            </div>
          )}

          <div>
            <div className="px-4 pt-2.5 pb-1" style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Active
            </div>
            {activeCount === 0 ? (
              <div className="px-4 py-5 text-center" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                No active alerts. Click "Set Alert" on a stock to add one.
              </div>
            ) : (
              alerts.map((a) => (
                <div
                  key={a.id}
                  className="px-4 py-2.5 flex items-center justify-between gap-2"
                  style={{ borderTop: "1px solid var(--border-subtle)" }}
                  data-testid={`alert-active-${a.symbol}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => { setOpen(false); onJumpToSymbol?.(a.symbol); }}
                        className="mono"
                        style={{ fontSize: 13, fontWeight: 600, color: "var(--blue)", cursor: "pointer" }}
                        data-testid={`alert-jump-${a.symbol}`}
                      >
                        {a.symbol}
                      </button>
                      <span style={{ fontSize: 10, color: a.direction === "above" ? "var(--green)" : "var(--red)", fontWeight: 600, letterSpacing: "0.06em" }}>
                        {a.direction === "above" ? "▲ ABOVE" : "▼ BELOW"}
                      </span>
                    </div>
                    <div className="mono" style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                      ₹{fmtNum(a.targetPrice)}
                    </div>
                    {a.note && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.note}</div>}
                  </div>
                  <button
                    data-testid={`alert-remove-${a.id}`}
                    onClick={() => remove(a.id)}
                    title="Remove alert"
                    className="btn-ghost px-2 py-1 rounded-md text-xs"
                    style={{ color: "var(--text-muted)" }}
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AlertsBell;

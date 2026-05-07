import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtINR, fmtNum, fmtIST } from "../utils/formatters";

const HistoryTab = () => {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/transactions");
        if (!cancelled) setRows(data.transactions || []);
      } catch {
        if (!cancelled) setRows([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (rows === null) {
    return <div className="p-8 text-center" style={{ color: "var(--text-muted)" }}>Loading…</div>;
  }

  return (
    <div className="px-6 py-5" data-testid="history-tab">
      <div className="surface rounded-xl overflow-hidden">
        <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 13 }}>
          Transaction History
        </div>
        {rows.length === 0 ? (
          <div className="p-8 text-center" style={{ color: "var(--text-muted)" }} data-testid="history-empty">
            No transactions yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase" }}>
                  {["Date & Time (IST)", "Type", "Symbol", "Name", "Qty", "Price", "Total"].map((h, i) => (
                    <th key={i} className="text-left px-3 py-2.5" style={{ borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} className="tr-hover" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                    <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)", fontSize: 12 }}>{fmtIST(t.timestamp)}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className="pill"
                        style={{
                          background: t.type === "BUY" ? "var(--blue-dim)" : "var(--amber-dim)",
                          color: t.type === "BUY" ? "var(--blue)" : "var(--amber)",
                          fontWeight: 600,
                        }}
                      >
                        {t.type}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 mono" style={{ color: "var(--blue)", fontWeight: 600 }}>{t.symbol}</td>
                    <td className="px-3 py-2.5">{t.name}</td>
                    <td className="px-3 py-2.5 mono">{t.qty}</td>
                    <td className="px-3 py-2.5 mono">{fmtNum(t.price)}</td>
                    <td className="px-3 py-2.5 mono" style={{ fontWeight: 600 }}>{fmtINR(t.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryTab;

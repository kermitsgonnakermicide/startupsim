import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { fmtIST } from "../utils/formatters";
import { toast } from "sonner";

const STATUS_STYLE = {
  pending: { bg: "var(--amber-dim)", color: "var(--amber)" },
  approved: { bg: "var(--green-dim)", color: "var(--green)" },
  rejected: { bg: "var(--red-dim)", color: "var(--red)" },
};

const Section = ({ title, count, rows, onAction, actions, onToggleLeaderboard }) => (
  <div className="surface rounded-xl overflow-hidden">
    <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
      <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.04em" }}>{title}</div>
      <div className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>{count} {count === 1 ? "user" : "users"}</div>
    </div>
    {rows.length === 0 ? (
      <div className="p-8 text-center" style={{ color: "var(--text-muted)" }}>None.</div>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.07em", textTransform: "uppercase" }}>
              {["Username", "Email", "Reason", "Applied", "Expires", "Leaderboard", "Actions"].map((h, i) => (
                <th key={i} className="text-left px-3 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const hidden = !!r.leaderboardHidden;
              return (
              <tr key={r.userId} className="tr-hover" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                <td className="px-3 py-2.5 mono" style={{ color: "var(--blue)", fontWeight: 600 }}>@{r.username}</td>
                <td className="px-3 py-2.5" style={{ color: "var(--text-secondary)", fontSize: 12 }}>{r.email || "—"}</td>
                <td className="px-3 py-2.5" style={{ maxWidth: 320, color: "var(--text-primary)", fontSize: 13 }}>
                  <div style={{ whiteSpace: "normal", overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                    {r.reason || "—"}
                  </div>
                  {r.reappliedAt && (
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                      Reapplied {fmtIST(r.reappliedAt)}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)", fontSize: 11 }}>{fmtIST(r.createdAt)}</td>
                <td className="px-3 py-2.5 mono" style={{ color: "var(--text-secondary)", fontSize: 11 }}>{r.approvedUntil ? fmtIST(r.approvedUntil) : "—"}</td>
                <td className="px-3 py-2.5">
                  <button
                    data-testid={`admin-leaderboard-toggle-${r.username}`}
                    onClick={() => onToggleLeaderboard(r, !hidden)}
                    className="px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1.5"
                    style={{
                      background: hidden ? "var(--red-dim)" : "var(--green-dim)",
                      color: hidden ? "var(--red)" : "var(--green)",
                      border: `1px solid ${hidden ? "var(--red)" : "var(--green)"}`,
                    }}
                    title={hidden ? "User is hidden from public leaderboard. Click to show." : "User is visible on leaderboard. Click to hide."}
                  >
                    <span style={{ fontSize: 13, lineHeight: 1 }}>{hidden ? "✕" : "✓"}</span>
                    {hidden ? "Hidden" : "Visible"}
                  </button>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex gap-1.5">
                    {actions.map((a) => (
                      <button
                        key={a.key}
                        data-testid={`admin-${a.key}-${r.username}`}
                        onClick={() => onAction(a.key, r)}
                        className="px-2.5 py-1 rounded-md text-xs font-medium"
                        style={{
                          background:
                            a.key === "approve" ? "var(--green)" :
                            a.key === "reject" ? "var(--red)" :
                            "transparent",
                          color: a.key === "revoke" ? "var(--text-secondary)" : "white",
                          border: a.key === "revoke" ? "1px solid var(--border)" : "none",
                        }}
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

const AdminTab = () => {
  const [data, setData] = useState(null);
  const [active, setActive] = useState("pending");
  const [search, setSearch] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/applications");
      setData(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load applications");
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const act = async (kind, row) => {
    if (!window.confirm(`${kind.toUpperCase()} @${row.username}?`)) return;
    try {
      await api.post(`/admin/${kind}`, { userId: row.userId });
      toast.success(`${kind === "approve" ? "Approved" : kind === "reject" ? "Rejected" : "Revoked"} @${row.username}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${kind} failed`);
    }
  };

  const toggleLeaderboard = async (row, hidden) => {
    try {
      await api.post("/admin/leaderboard-visibility", { userId: row.userId, hidden });
      toast.success(`@${row.username} is now ${hidden ? "hidden from" : "visible on"} the leaderboard`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update leaderboard visibility");
    }
  };

  const bulk = async (kind) => {
    const prompts = {
      "reject-pending": `Reject ALL pending applications (${data?.counts?.pending || 0})? This cannot be undone.`,
      "revoke-approved": `Revoke ALL ${data?.counts?.approved || 0} approved users back to pending? They will need re-approval to log in.`,
      "leaderboard-hide-all": "Hide ALL non-admin users from the public leaderboard?",
      "leaderboard-show-all": "Make ALL non-admin users visible on the public leaderboard?",
    };
    if (!window.confirm(prompts[kind])) return;
    setBulkBusy(true);
    try {
      const { data: res } = await api.post(`/admin/bulk/${kind}`);
      const labels = {
        "reject-pending": `Rejected ${res.count} pending application${res.count === 1 ? "" : "s"}`,
        "revoke-approved": `Revoked ${res.count} approved user${res.count === 1 ? "" : "s"}`,
        "leaderboard-hide-all": `Hidden ${res.count} user${res.count === 1 ? "" : "s"} from leaderboard`,
        "leaderboard-show-all": `Made ${res.count} user${res.count === 1 ? "" : "s"} visible on leaderboard`,
      };
      toast.success(labels[kind]);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Bulk action failed");
    } finally {
      setBulkBusy(false);
    }
  };

  if (!data) return <div className="p-8 text-center" style={{ color: "var(--text-muted)" }}>Loading…</div>;

  const counts = data.counts || { pending: 0, approved: 0, rejected: 0 };
  const tabs = [
    ["pending", "Pending", counts.pending],
    ["approved", "Approved", counts.approved],
    ["rejected", "Rejected", counts.rejected],
  ];

  const q = search.trim().toLowerCase();
  const allRowsActive = data[active] || [];
  const rowsActive = q
    ? allRowsActive.filter((r) =>
        (r.username || "").toLowerCase().includes(q) ||
        (r.email || "").toLowerCase().includes(q) ||
        (r.reason || "").toLowerCase().includes(q)
      )
    : allRowsActive;
  const actionsByTab = {
    pending: [
      { key: "approve", label: "Approve" },
      { key: "reject", label: "Reject" },
    ],
    approved: [
      { key: "revoke", label: "Revoke" },
      { key: "reject", label: "Reject" },
    ],
    rejected: [
      { key: "approve", label: "Approve" },
    ],
  };

  return (
    <div className="px-6 py-5 space-y-4" data-testid="admin-tab">
      <div className="surface rounded-xl p-4 flex items-center gap-3">
        <span
          className="pill"
          style={{ background: "var(--blue-dim)", color: "var(--blue)", fontWeight: 600, padding: "5px 12px" }}
        >
          CREATOR
        </span>
        <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>
          Approve users to grant 10-day access. Toggle <strong>Visible/Hidden</strong> to control who appears on the public leaderboard.
        </div>
        <button
          data-testid="admin-refresh"
          onClick={load}
          className="ml-auto btn-ghost px-3 py-1.5 rounded-md text-xs flex items-center gap-1.5"
          title="Refresh now"
        >
          <span style={{ fontSize: 14 }}>↻</span>
          Refresh
        </button>
      </div>

      <div className="surface rounded-xl p-4 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)", fontSize: 13 }}>⌕</span>
          <input
            data-testid="admin-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by username, email, or reason…"
            className="mono w-full pl-8 pr-3 py-2 rounded-md text-sm outline-none"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
          />
        </div>
        <button
          data-testid="admin-bulk-reject-pending"
          onClick={() => bulk("reject-pending")}
          disabled={bulkBusy || counts.pending === 0}
          className="px-3 py-2 rounded-md text-xs font-medium"
          style={{
            background: "transparent",
            border: "1px solid var(--red)",
            color: "var(--red)",
            opacity: bulkBusy || counts.pending === 0 ? 0.4 : 1,
            cursor: bulkBusy || counts.pending === 0 ? "not-allowed" : "pointer",
          }}
          title="Reject every pending application"
        >
          ✕ Reject All Pending ({counts.pending})
        </button>
        <button
          data-testid="admin-bulk-revoke-approved"
          onClick={() => bulk("revoke-approved")}
          disabled={bulkBusy || counts.approved === 0}
          className="px-3 py-2 rounded-md text-xs font-medium"
          style={{
            background: "transparent",
            border: "1px solid var(--amber)",
            color: "var(--amber)",
            opacity: bulkBusy || counts.approved === 0 ? 0.4 : 1,
            cursor: bulkBusy || counts.approved === 0 ? "not-allowed" : "pointer",
          }}
          title="Revoke every approved user back to pending"
        >
          ↶ Revoke All Approved ({counts.approved})
        </button>
        <button
          data-testid="admin-bulk-leaderboard-hide-all"
          onClick={() => bulk("leaderboard-hide-all")}
          disabled={bulkBusy}
          className="px-3 py-2 rounded-md text-xs font-medium"
          style={{
            background: "transparent",
            border: "1px solid var(--text-secondary)",
            color: "var(--text-secondary)",
            opacity: bulkBusy ? 0.4 : 1,
          }}
          title="Hide every non-admin user from the public leaderboard"
        >
          ✕ Hide All from Leaderboard
        </button>
        <button
          data-testid="admin-bulk-leaderboard-show-all"
          onClick={() => bulk("leaderboard-show-all")}
          disabled={bulkBusy}
          className="px-3 py-2 rounded-md text-xs font-medium"
          style={{
            background: "transparent",
            border: "1px solid var(--green)",
            color: "var(--green)",
            opacity: bulkBusy ? 0.4 : 1,
          }}
          title="Make every non-admin user visible on the public leaderboard"
        >
          ✓ Show All on Leaderboard
        </button>
      </div>

      <div className="flex gap-1.5">
        {tabs.map(([k, l, c]) => (
          <button
            key={k}
            data-testid={`admin-subtab-${k}`}
            onClick={() => setActive(k)}
            className="px-4 py-2 rounded-md text-xs flex items-center gap-2"
            style={{
              background: active === k ? "var(--bg-highlight)" : "var(--bg-elevated)",
              color: active === k ? "var(--text-primary)" : "var(--text-secondary)",
              border: "1px solid",
              borderColor: active === k ? "var(--blue)" : "var(--border)",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              fontWeight: active === k ? 600 : 400,
            }}
          >
            {l}
            <span
              className="pill mono"
              style={{
                background: STATUS_STYLE[k].bg,
                color: STATUS_STYLE[k].color,
                padding: "1px 8px",
                fontSize: 10,
              }}
            >
              {c}
            </span>
          </button>
        ))}
      </div>

      <Section
        title={`${tabs.find(([k]) => k === active)[1]}${q ? ` — search: "${search}"` : ""}`}
        count={rowsActive.length}
        rows={rowsActive}
        actions={actionsByTab[active]}
        onAction={act}
        onToggleLeaderboard={toggleLeaderboard}
      />
    </div>
  );
};

export default AdminTab;

import React, { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";

const ChangePasswordModal = ({ open, onClose }) => {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirmNext, setConfirmNext] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [serverErr, setServerErr] = useState("");

  if (!open) return null;
  const newTooShort = next.length > 0 && next.length < 6;
  const mismatch = confirmNext.length > 0 && confirmNext !== next;
  const sameAsCurrent = next.length > 0 && next === cur;
  const valid = cur.length > 0 && next.length >= 6 && next === confirmNext && next !== cur;

  const submit = async (e) => {
    e.preventDefault();
    setServerErr("");
    setBusy(true);
    try {
      await api.post("/auth/change-password", { currentPassword: cur, newPassword: next });
      toast.success("Password updated");
      setCur(""); setNext(""); setConfirmNext("");
      onClose();
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to update";
      setServerErr(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const inputStyle = {
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    color: "var(--text-primary)",
    fontSize: 14,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.75)" }} onClick={onClose} data-testid="change-pw-modal">
      <div className="w-full max-w-[400px] surface rounded-2xl p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div style={{ fontSize: 16, fontWeight: 600 }}>Change Password</div>
          <button onClick={onClose} style={{ color: "var(--text-secondary)" }}>✕</button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="block text-xs mb-1.5" style={{ color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Current Password
            </label>
            <input data-testid="cp-current" type={show ? "text" : "password"} value={cur} onChange={(e) => setCur(e.target.value)} className="mono w-full px-3 py-2.5 rounded-md outline-none" style={inputStyle} />
          </div>
          <div>
            <label className="block text-xs mb-1.5" style={{ color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              New Password
            </label>
            <input data-testid="cp-new" type={show ? "text" : "password"} value={next} onChange={(e) => setNext(e.target.value)} className="mono w-full px-3 py-2.5 rounded-md outline-none" style={inputStyle} />
            {newTooShort && (
              <div className="text-xs mt-1" data-testid="cp-err-len" style={{ color: "var(--red)" }}>Password must be at least 6 characters.</div>
            )}
            {sameAsCurrent && !newTooShort && (
              <div className="text-xs mt-1" data-testid="cp-err-same" style={{ color: "var(--red)" }}>New password must differ from current password.</div>
            )}
          </div>
          <div>
            <label className="block text-xs mb-1.5" style={{ color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Confirm New Password
            </label>
            <input data-testid="cp-confirm" type={show ? "text" : "password"} value={confirmNext} onChange={(e) => setConfirmNext(e.target.value)} className="mono w-full px-3 py-2.5 rounded-md outline-none" style={inputStyle} />
            {mismatch && (
              <div className="text-xs mt-1" data-testid="cp-err-match" style={{ color: "var(--red)" }}>Passwords don't match.</div>
            )}
          </div>
          {serverErr && (
            <div
              data-testid="cp-server-err"
              className="text-sm p-2.5 rounded-md"
              style={{ background: "var(--red-dim)", color: "var(--red)", border: "1px solid var(--red)" }}
            >
              {serverErr}
            </div>
          )}
          <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
            Show passwords
          </label>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-ghost flex-1 py-2.5 rounded-md text-sm">Cancel</button>
            <button
              type="submit"
              data-testid="cp-submit"
              disabled={!valid || busy}
              className="flex-1 py-2.5 rounded-md text-sm font-medium"
              style={{ background: "var(--blue)", color: "white", opacity: !valid || busy ? 0.5 : 1 }}
            >
              {busy ? "Saving…" : "Update Password"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChangePasswordModal;

import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const LogoMark = ({ size = 64 }) => (
  <div
    aria-hidden="true"
    style={{
      width: size,
      height: size,
      borderRadius: 14,
      border: "1px solid var(--border)",
      background: "linear-gradient(135deg, rgba(160,30,32,0.22), rgba(37,99,235,0.22))",
      display: "grid",
      placeItems: "center",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
    }}
  >
    <span className="mono" style={{ color: "var(--blue)", fontSize: size * 0.36, fontWeight: 700, letterSpacing: "-0.06em" }}>
      SC
    </span>
  </div>
);

const Eye = ({ open }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    {open ? (
      <>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ) : (
      <>
        <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-6.5 0-10-7-10-7a18.9 18.9 0 0 1 4.17-5.33" />
        <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c6.5 0 10 7 10 7a18.6 18.6 0 0 1-2.16 3.19" />
        <path d="M1 1l22 22" />
      </>
    )}
  </svg>
);

const Check = ({ ok }) => (
  <span style={{ color: ok ? "var(--green)" : "var(--red)", fontFamily: "JetBrains Mono", fontSize: 13 }}>
    {ok ? "OK" : "X"}
  </span>
);

const Field = ({ label, children }) => (
  <div>
    <label className="block text-xs mb-1.5" style={{ color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
      {label}
    </label>
    {children}
  </div>
);

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  color: "var(--text-primary)",
  fontSize: 14,
};

const AuthPage = () => {
  const { loginWith } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [email, setEmail] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [pendingNotice, setPendingNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const usernameLen = username.length >= 3 && username.length <= 20;
  const usernameChars = /^[a-zA-Z0-9_]*$/.test(username) && username.length > 0;
  const pwOk = password.length >= 6;
  const pwMatch = confirm.length > 0 && confirm === password;
  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const signupValid = usernameLen && usernameChars && pwOk && pwMatch && emailOk;

  const switchMode = (m) => { setMode(m); setErr(""); setInfo(""); setPendingNotice(""); };

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setInfo(""); setPendingNotice("");
    setLoading(true);
    try {
      if (mode === "login") {
        const { data } = await api.post("/auth/login", { username, password });
        loginWith(data.token, data.username, data.userId, data.isAdmin);
      } else {
        const { data } = await api.post("/auth/signup", { username, password, email });
        setInfo(data.message);
        setUsername(""); setPassword(""); setConfirm(""); setEmail("");
        setMode("login");
      }
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      
      if (!e.response) {
        setErr("Network error: Cannot reach the server. Check your connection or the backend status.");
      } else if (mode === "login" && status === 403) {
        setPendingNotice(detail || "Your account is not active.");
      } else {
        setErr(detail || "Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg px-4 py-8" data-testid="auth-page">
      <div className="w-full max-w-[440px] rounded-2xl p-8 surface" style={{ boxShadow: "0 32px 80px rgba(0,0,0,0.5)" }}>
        <div className="flex items-center gap-3 mb-2">
          <LogoMark />
          <div>
            <div className="mono" style={{ color: "var(--blue)", fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1 }}>
              SCALE
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: 11, letterSpacing: "0.18em", textTransform: "uppercase", marginTop: 4 }}>
              India Investment
            </div>
          </div>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 10, fontStyle: "italic" }}>
          Paper trading. AI-estimated valuations. Zero risk. Access by invitation.
        </div>

        <div className="flex gap-1 my-6 p-1 rounded-lg" style={{ background: "var(--bg-elevated)" }}>
          {[["login","Log In"],["signup","Apply"]].map(([m,l]) => (
            <button
              key={m}
              data-testid={`tab-${m}`}
              onClick={() => switchMode(m)}
              className="flex-1 py-2 rounded-md text-xs transition"
              style={{
                background: mode === m ? "var(--bg-surface)" : "transparent",
                color: mode === m ? "var(--text-primary)" : "var(--text-secondary)",
                fontWeight: mode === m ? 600 : 400,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {l}
            </button>
          ))}
        </div>

        {info && (
          <div className="mb-4 p-3 rounded-md text-sm" style={{ background: "var(--green-dim)", color: "var(--green)", border: "1px solid var(--green)" }} data-testid="auth-info">
            {info}
          </div>
        )}

        {pendingNotice && (
          <div className="mb-4 p-3 rounded-md text-sm" style={{ background: "var(--amber-dim)", color: "var(--amber)", border: "1px solid var(--amber)" }} data-testid="auth-pending">
            {pendingNotice}
            {(pendingNotice.toLowerCase().includes("expired") || pendingNotice.toLowerCase().includes("rejected")) && (
              <div className="mt-2">
                <button onClick={() => switchMode("signup")} className="underline" style={{ color: "var(--amber)" }}>
                  Submit a new application via Apply ->
                </button>
              </div>
            )}
          </div>
        )}

        <form onSubmit={submit} className="space-y-3.5">
          <Field label="Username">
            <input
              data-testid="input-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="mono w-full px-3 py-2.5 rounded-md outline-none"
              style={inputStyle}
            />
            {mode === "signup" && username.length > 0 && (
              <div className="flex flex-col gap-0.5 mt-2 text-[12px]" style={{ color: "var(--text-secondary)" }}>
                <span><Check ok={usernameLen} /> 3-20 characters</span>
                <span><Check ok={usernameChars} /> Letters, numbers, underscores only</span>
              </div>
            )}
          </Field>

          <Field label="Password">
            <div className="relative">
              <input
                data-testid="input-password"
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className="mono w-full px-3 py-2.5 rounded-md outline-none pr-10"
                style={inputStyle}
              />
              <button
                type="button"
                data-testid="toggle-password"
                onClick={() => setShowPw((s) => !s)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2"
                style={{ color: "var(--text-muted)" }}
              >
                <Eye open={showPw} />
              </button>
            </div>
            {mode === "signup" && password.length > 0 && (
              <div className="mt-1.5 text-[12px]" style={{ color: "var(--text-secondary)" }}>
                <Check ok={pwOk} /> At least 6 characters
              </div>
            )}
          </Field>

          {mode === "signup" && (
            <>
              <Field label="Confirm Password">
                <input
                  data-testid="input-confirm"
                  type={showPw ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="mono w-full px-3 py-2.5 rounded-md outline-none"
                  style={inputStyle}
                />
                {confirm.length > 0 && (
                  <div className="mt-1.5 text-[12px]">
                    <Check ok={pwMatch} />{" "}
                    <span style={{ color: pwMatch ? "var(--green)" : "var(--red)" }}>
                      {pwMatch ? "Passwords match" : "Passwords do not match"}
                    </span>
                  </div>
                )}
              </Field>

              <Field label="Email">
                <input
                  data-testid="input-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-md outline-none"
                  style={inputStyle}
                />
                {email.length > 0 && (
                  <div className="mt-1.5 text-[12px]">
                    <Check ok={emailOk} />{" "}
                    <span style={{ color: emailOk ? "var(--green)" : "var(--red)" }}>
                      {emailOk ? "Looks valid" : "Invalid email"}
                    </span>
                  </div>
                )}
              </Field>
            </>
          )}

          {err && (
            <div data-testid="auth-error" className="text-sm" style={{ color: "var(--red)" }}>
              {err}
            </div>
          )}

          <button
            type="submit"
            data-testid="submit-auth"
            disabled={loading || (mode === "signup" && !signupValid)}
            className="w-full py-2.5 rounded-md font-medium text-sm transition"
            style={{
              background: "var(--blue)",
              color: "white",
              opacity: loading || (mode === "signup" && !signupValid) ? 0.55 : 1,
            }}
          >
            {loading ? "Please wait..." : mode === "login" ? "Log In" : "Submit Application"}
          </button>
        </form>

        <div className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          {mode === "login" ? (
            <>New here, or been rejected/expired?{" "}
              <button data-testid="link-signup" onClick={() => switchMode("signup")} style={{ color: "var(--blue)" }}>
                Apply for access ->
              </button>
            </>
          ) : (
            <>Already approved?{" "}
              <button data-testid="link-login" onClick={() => switchMode("login")} style={{ color: "var(--blue)" }}>
                Log in ->
              </button>
            </>
          )}
        </div>

        <p style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center", marginTop: 16, lineHeight: 1.5 }}>
          By signing up, you confirm this is an educational simulator. No real money is involved. Your trades affect startup prices for all students on the platform.
        </p>
      </div>
    </div>
  );
};

export default AuthPage;

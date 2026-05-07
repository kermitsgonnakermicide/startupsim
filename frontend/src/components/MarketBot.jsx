import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

/**
 * useMarketBot pulls server-side demand pressure and news reasons every 30s
 * and merges them into a `botPrices` map that any tab can consume.
 */
export function useMarketBot() {
  const { user } = useAuth();
  const [demand, setDemand] = useState({});
  const [news, setNews] = useState({});
  const tickRef = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const [d, n] = await Promise.all([
        api.get("/demand"),
        user ? api.get("/marketbot/news").catch(() => ({ data: { news: {} } })) : Promise.resolve({ data: { news: {} } }),
      ]);
      setDemand(d.data?.pressure || {});
      setNews(n.data?.news || {});
      tickRef.current += 1;
    } catch (_) {
      // silent fallback
    }
  }, [user]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [refresh]);

  const botPrices = useMemo(() => {
    const m = {};
    Object.keys(demand).forEach((sym) => {
      m[sym] = { demandPressure: demand[sym], reason: news[sym] || null };
    });
    return m;
  }, [demand, news]);

  return { botPrices, demand, news, refresh };
}

const Bubble = ({ role, children }) => {
  const me = role === "user";
  return (
    <div className="flex" style={{ justifyContent: me ? "flex-end" : "flex-start" }}>
      <div
        style={{
          maxWidth: "82%",
          padding: "8px 12px",
          borderRadius: 10,
          background: me ? "var(--blue)" : "var(--bg-elevated)",
          color: me ? "#fff" : "var(--text-primary)",
          fontSize: 13,
          lineHeight: 1.45,
          whiteSpace: "pre-wrap",
          border: me ? "none" : "1px solid var(--border)",
        }}
      >
        {children}
      </div>
    </div>
  );
};

const Typing = () => (
  <div className="flex" style={{ justifyContent: "flex-start" }}>
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 10,
        background: "var(--bg-elevated)",
        border: "1px solid var(--border)",
        display: "inline-flex",
        gap: 4,
      }}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="dot-pulse"
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            background: "var(--text-secondary)",
            animationDelay: `${i * 0.15}s`,
          }}
        />
      ))}
    </div>
  </div>
);

export const MarketBotChat = () => {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi! I'm MarketBot. Ask me about any startup on this market, investment concepts, or why a price moved today. Remember: this is a simulator for learning only!",
    },
  ]);
  const scrollRef = useRef(null);
  const sessionId = useMemo(() => `mb-${user?.userId || "anon"}-${Date.now()}`, [user]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, busy]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const { data } = await api.post("/marketbot/chat", {
        message: text,
        sessionId,
        history: messages,
      });
      setMessages((m) => [...m, { role: "assistant", content: data.reply }]);
    } catch (_) {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "MarketBot is taking a break. Try again shortly!" },
      ]);
    } finally {
      setBusy(false);
    }
  };

  if (!user) return null;

  return (
    <>
      <button
        data-testid="marketbot-toggle"
        onClick={() => setOpen((v) => !v)}
        title="Ask MarketBot"
        style={{
          position: "fixed",
          right: 20,
          bottom: 56,
          width: 52,
          height: 52,
          borderRadius: 999,
          background: "var(--blue)",
          color: "#fff",
          fontSize: 24,
          border: "none",
          boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
          cursor: "pointer",
          zIndex: 50,
        }}
      >
        AI
      </button>

      {open && (
        <div
          data-testid="marketbot-panel"
          className="surface"
          style={{
            position: "fixed",
            right: 20,
            bottom: 116,
            width: "min(360px, calc(100vw - 32px))",
            height: "min(480px, calc(100vh - 160px))",
            borderRadius: 14,
            display: "flex",
            flexDirection: "column",
            zIndex: 51,
            boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
            overflow: "hidden",
          }}
        >
          <div
            className="flex items-center justify-between"
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid var(--border)",
              background: "var(--bg-elevated)",
            }}
          >
            <div className="flex items-center gap-2">
              <span style={{ fontSize: 18 }}>AI</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>MarketBot</div>
                <div style={{ fontSize: 10, color: "var(--text-secondary)" }}>
                  OpenAI or offline mode · educational use only
                </div>
              </div>
            </div>
            <button
              data-testid="marketbot-close"
              onClick={() => setOpen(false)}
              className="btn-ghost"
              style={{ padding: "4px 10px", borderRadius: 6, fontSize: 14 }}
            >
              X
            </button>
          </div>

          <div
            ref={scrollRef}
            data-testid="marketbot-messages"
            style={{
              flex: 1,
              overflowY: "auto",
              padding: 12,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {messages.map((m, i) => (
              <Bubble key={i} role={m.role}>{m.content}</Bubble>
            ))}
            {busy && <Typing />}
          </div>

          <div
            className="flex gap-2"
            style={{
              padding: 10,
              borderTop: "1px solid var(--border)",
              background: "var(--bg-surface)",
            }}
          >
            <input
              data-testid="marketbot-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") send(); }}
              placeholder="Ask about a startup, valuation, or trade..."
              disabled={busy}
              className="mono flex-1 px-3 py-2 rounded-md outline-none"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
                fontSize: 13,
              }}
            />
            <button
              data-testid="marketbot-send"
              onClick={send}
              disabled={busy || !input.trim()}
              className="px-3 py-2 rounded-md text-xs font-medium"
              style={{
                background: "var(--blue)",
                color: "#fff",
                opacity: busy || !input.trim() ? 0.5 : 1,
                border: "none",
                cursor: busy || !input.trim() ? "not-allowed" : "pointer",
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
};

export default MarketBotChat;

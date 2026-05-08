import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

const SECTORS = [
  "All",
  "Fintech",
  "Edtech",
  "Healthtech",
  "Agritech",
  "Logistics",
  "SaaS",
  "Consumer",
  "EV & Cleantech",
  "Gaming",
  "Deeptech",
];

const SECTOR_COLOR = {
  Fintech: "#60a5fa",
  Edtech: "#f472b6",
  Healthtech: "#4ade80",
  Agritech: "#a3e635",
  Logistics: "#fbbf24",
  SaaS: "#c084fc",
  Consumer: "#fb923c",
  "EV & Cleantech": "#2dd4bf",
  Gaming: "#f87171",
  Deeptech: "#38bdf8",
};

const relTime = (iso) => {
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch {
    return "";
  }
};

const NewsTab = ({ onJumpToSymbol }) => {
  const [data, setData] = useState(null);
  const [matchedOnly, setMatchedOnly] = useState(true);
  const [filter, setFilter] = useState("All");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/news/headlines?limit=500&matchedOnly=${matchedOnly}&minPerSector=8`);
      setData(data);
    } finally {
      setLoading(false);
    }
  }, [matchedOnly]);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  const counts = useMemo(() => {
    const c = { All: 0 };
    SECTORS.forEach((s) => { if (s !== "All") c[s] = 0; });
    (data?.headlines || []).forEach((a) => {
      c.All += 1;
      a.matchedSectors.forEach((s) => { if (c[s] != null) c[s] += 1; });
    });
    return c;
  }, [data]);

  const filtered = useMemo(() => {
    const list = data?.headlines || [];
    if (filter === "All") return list;
    return list.filter((a) => a.matchedSectors.includes(filter));
  }, [data, filter]);

  return (
    <div className="px-6 py-5 space-y-4" data-testid="news-tab">
      <div className="surface rounded-xl p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Live Market News</div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 2 }}>
            {data?.status?.articleCount ?? "…"} headlines from {data?.status?.sourceCount ?? "…"} verified Indian publications ·
            {" "}updated {data?.status?.lastRefresh ? relTime(data.status.lastRefresh) : "…"}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setMatchedOnly(!matchedOnly)}>
            <div
              className="flex items-center justify-center"
              style={{
                width: 36,
                height: 20,
                borderRadius: 20,
                background: matchedOnly ? "var(--blue)" : "var(--bg-highlight)",
                position: "relative",
                transition: "background 0.2s",
                border: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: "#fff",
                  position: "absolute",
                  left: matchedOnly ? 19 : 3,
                  transition: "left 0.2s",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                }}
              />
            </div>
            <span style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }}>
              Matched Only
            </span>
          </div>
          <button
            data-testid="news-refresh"
            onClick={load}
            className="btn-ghost px-3 py-1.5 rounded-md text-xs flex items-center gap-1.5"
          >
            <span style={{ fontSize: 14 }}>↻</span> Refresh
          </button>
        </div>
      </div>

      {/* Sector filter chips */}
      <div className="flex flex-wrap gap-1.5" data-testid="news-filters">
        {SECTORS.map((s) => {
          const active = filter === s;
          const col = s === "All" ? "var(--blue)" : SECTOR_COLOR[s] || "var(--text-secondary)";
          return (
            <button
              key={s}
              data-testid={`news-filter-${s.replace(/[^a-z0-9]/gi, "").toLowerCase()}`}
              onClick={() => setFilter(s)}
              className="px-3 py-1.5 rounded-md text-xs flex items-center gap-2"
              style={{
                background: active ? "var(--bg-highlight)" : "var(--bg-elevated)",
                border: `1px solid ${active ? col : "var(--border)"}`,
                color: active ? col : "var(--text-secondary)",
                fontWeight: active ? 600 : 500,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {s}
              <span
                className="mono"
                style={{
                  fontSize: 10,
                  color: active ? col : "var(--text-muted)",
                  background: active ? "transparent" : "var(--bg-surface)",
                  padding: "1px 6px",
                  borderRadius: 4,
                }}
              >
                {counts[s] ?? 0}
              </span>
            </button>
          );
        })}
      </div>

      {/* Article list */}
      {loading && !data ? (
        <div className="p-12 text-center" style={{ color: "var(--text-muted)" }}>Loading headlines…</div>
      ) : filtered.length === 0 ? (
        <div className="surface rounded-xl p-12 text-center" data-testid="news-empty">
          <div style={{ fontSize: 36, marginBottom: 10, color: "var(--text-muted)" }}>📰</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            No {filter === "All" ? "" : filter + " "}headlines found
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 4, maxWidth: 300, margin: "4px auto 0" }}>
            {matchedOnly 
              ? "Try turning off 'Matched Only' to see general market news from verified Indian publications."
              : "The scraper refreshes every 5 minutes. Check back shortly."}
          </div>
          {matchedOnly && (
            <button 
              onClick={() => setMatchedOnly(false)}
              className="btn-ghost mt-4 px-4 py-2 rounded-md text-xs font-semibold"
              style={{ color: "var(--blue)", border: "1px solid var(--blue)" }}
            >
              Show All News
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2" data-testid="news-list">
          {filtered.map((a, i) => (
            <a
              key={`${a.link}-${i}`}
              href={a.link}
              target="_blank"
              rel="noopener noreferrer"
              className="surface rounded-xl p-4 flex gap-4 transition-colors"
              style={{ display: "flex", textDecoration: "none", color: "inherit" }}
              data-testid={`news-article-${i}`}
            >
              <div className="flex-shrink-0" style={{ width: 68 }}>
                <div
                  className="mono"
                  style={{
                    fontSize: 10,
                    color: "var(--text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                  }}
                >
                  {relTime(a.publishedAt)}
                </div>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: "var(--blue)",
                    marginTop: 6,
                    letterSpacing: "0.05em",
                    lineHeight: 1.2,
                  }}
                >
                  {a.source}
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", lineHeight: 1.35 }}>
                  {a.title}
                </div>
                {a.summary && (
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-secondary)",
                      marginTop: 6,
                      lineHeight: 1.5,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {a.summary}
                  </div>
                )}
                {(a.matchedSymbols.length > 0 || a.matchedSectors.length > 0) && (
                  <div className="flex flex-wrap gap-1.5 mt-2 items-center">
                    {a.matchedSymbols.map((sym) => (
                      <button
                        key={sym}
                        type="button"
                        data-testid={`news-jump-${sym}-${i}`}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onJumpToSymbol?.(sym);
                        }}
                        title={`View ${sym} on the Market tab`}
                        className="pill mono"
                        style={{
                          background: "var(--blue-dim)",
                          color: "var(--blue)",
                          fontSize: 10,
                          fontWeight: 600,
                          padding: "3px 10px",
                          letterSpacing: "0.04em",
                          border: "1px solid var(--blue)",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <span>{sym}</span>
                        <span style={{ opacity: 0.7, fontSize: 9 }}>→</span>
                      </button>
                    ))}
                    {a.matchedSectors.map((s) => (
                      <span
                        key={s}
                        className="pill"
                        style={{
                          background: "transparent",
                          border: `1px solid ${SECTOR_COLOR[s] || "var(--border)"}`,
                          color: SECTOR_COLOR[s] || "var(--text-secondary)",
                          fontSize: 10,
                          padding: "1px 8px",
                          letterSpacing: "0.04em",
                          textTransform: "uppercase",
                        }}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default NewsTab;

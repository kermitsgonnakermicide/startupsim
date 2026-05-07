import React, { useEffect, useMemo, useState } from "react";

const DEFAULTS = [
  "MarketBot scanning startup news…",
  "Prices are AI-estimated simulations",
  "Market open: 9:15 AM – 3:30 PM IST weekdays",
  "Prices move with real student buy/sell activity",
];

const NewsTicker = ({ newsItems }) => {
  // Marquee animation by sliding via animationName
  const items = useMemo(() => {
    const arr = (newsItems && newsItems.length > 0) ? newsItems : DEFAULTS;
    // duplicate for seamless loop
    return [...arr, ...arr];
  }, [newsItems]);

  const [paused, setPaused] = useState(false);

  useEffect(() => {
    // inject keyframes once
    if (!document.getElementById("mbot-ticker-kf")) {
      const s = document.createElement("style");
      s.id = "mbot-ticker-kf";
      s.innerHTML = `@keyframes mbot-marquee {
        0% { transform: translateX(0); }
        100% { transform: translateX(-50%); }
      }`;
      document.head.appendChild(s);
    }
  }, []);

  return (
    <div
      className="flex items-center gap-3 px-6 py-2"
      style={{ background: "var(--bg-base)", borderBottom: "1px solid var(--border)", overflow: "hidden" }}
      data-testid="news-ticker"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <span
        style={{
          fontSize: 9,
          color: "var(--amber)",
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          fontWeight: 700,
          whiteSpace: "nowrap",
          flexShrink: 0,
          padding: "3px 8px",
          background: "var(--amber-dim)",
          border: "1px solid var(--amber)",
          borderRadius: 4,
        }}
      >
        MARKETBOT LIVE
      </span>
      <div style={{ overflow: "hidden", flex: 1 }}>
        <div
          style={{
            display: "inline-flex",
            gap: 24,
            whiteSpace: "nowrap",
            animation: "mbot-marquee 60s linear infinite",
            animationPlayState: paused ? "paused" : "running",
          }}
        >
          {items.map((t, i) => (
            <span key={i} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              <span style={{ color: "var(--blue)", marginRight: 6 }}>·</span>
              {t}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default NewsTicker;

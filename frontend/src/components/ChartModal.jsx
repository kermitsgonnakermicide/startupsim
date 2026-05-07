import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { fmtINR, fmtNum, fmtPct, fmtVolume } from "../utils/formatters";
import AlertModal from "./AlertModal";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Cell,
  LineChart,
} from "recharts";

const RANGES = [
  ["1d", "1D"],
  ["5d", "5D"],
  ["1mo", "1M"],
  ["3mo", "3M"],
  ["6mo", "6M"],
  ["1y", "1Y"],
];

const fmtTime = (t, range) => {
  const d = new Date(t);
  if (range === "1d" || range === "5d") {
    return d.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return d.toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short" });
};

/** Simple moving average over `period` close prices. Returns array aligned to input (nulls for <period). */
const sma = (closes, period) => {
  const out = new Array(closes.length).fill(null);
  if (closes.length < period) return out;
  let sum = 0;
  for (let i = 0; i < period; i++) sum += closes[i];
  out[period - 1] = sum / period;
  for (let i = period; i < closes.length; i++) {
    sum += closes[i] - closes[i - period];
    out[i] = sum / period;
  }
  return out;
};

/** Classic Wilder RSI over `period` closes. Returns array aligned to input. */
const rsi = (closes, period = 14) => {
  const out = new Array(closes.length).fill(null);
  if (closes.length <= period) return out;
  let gain = 0, loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  const rsAt = (ag, al) => (al === 0 ? 100 : 100 - 100 / (1 + ag / al));
  out[period] = rsAt(avgGain, avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const g = diff >= 0 ? diff : 0;
    const l = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
    out[i] = rsAt(avgGain, avgLoss);
  }
  return out;
};

const Candle = ({ x, y, width, height, payload }) => {
  if (!payload || height == null) return null;
  const { o, c, h, l } = payload;
  const rng = h - l || 1;
  const yOpen = y + ((h - o) / rng) * height;
  const yClose = y + ((h - c) / rng) * height;
  const up = c >= o;
  const color = up ? "#00d4aa" : "#f03e3e";
  const cx = x + width / 2;
  const bodyTop = Math.min(yOpen, yClose);
  const bodyH = Math.max(1, Math.abs(yClose - yOpen));
  const bw = Math.max(2, width * 0.7);
  const bx = cx - bw / 2;
  return (
    <g>
      <line x1={cx} x2={cx} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={bx} y={bodyTop} width={bw} height={bodyH} fill={color} />
    </g>
  );
};

const TooltipBox = ({ active, payload, range }) => {
  if (!active || !payload || !payload.length) return null;
  const p = payload[0]?.payload;
  if (!p) return null;
  const up = p.c >= p.o;
  return (
    <div className="rounded-md p-2.5 mono text-xs" style={{ background: "#0a0e1a", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
      <div style={{ color: "var(--text-secondary)", marginBottom: 4 }}>{fmtTime(p.t, range)}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        <span style={{ color: "var(--text-secondary)" }}>O</span><span>{fmtNum(p.o)}</span>
        <span style={{ color: "var(--text-secondary)" }}>H</span><span style={{ color: "var(--green)" }}>{fmtNum(p.h)}</span>
        <span style={{ color: "var(--text-secondary)" }}>L</span><span style={{ color: "var(--red)" }}>{fmtNum(p.l)}</span>
        <span style={{ color: "var(--text-secondary)" }}>C</span><span style={{ color: up ? "var(--green)" : "var(--red)" }}>{fmtNum(p.c)}</span>
        <span style={{ color: "var(--text-secondary)" }}>V</span><span style={{ color: "var(--text-secondary)" }}>{fmtVolume(p.v)}</span>
        {p.sma20 != null && (<><span style={{ color: "#f59e0b" }}>SMA20</span><span>{fmtNum(p.sma20)}</span></>)}
        {p.sma50 != null && (<><span style={{ color: "#a78bfa" }}>SMA50</span><span>{fmtNum(p.sma50)}</span></>)}
      </div>
    </div>
  );
};

const Stat = ({ label, value, tone }) => (
  <div className="surface-elevated rounded-lg p-3">
    <div style={{ fontSize: 10, color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>{label}</div>
    <div className="mono" style={{ fontSize: 16, fontWeight: 600, marginTop: 4, color: tone === "up" ? "var(--green)" : tone === "down" ? "var(--red)" : "var(--text-primary)" }}>{value}</div>
  </div>
);

const IndicatorToggle = ({ label, active, color, onClick, testid }) => (
  <button
    data-testid={testid}
    onClick={onClick}
    className="px-2.5 py-1 rounded-md text-xs font-medium flex items-center gap-1.5"
    style={{
      background: active ? "var(--bg-highlight)" : "var(--bg-elevated)",
      color: active ? "var(--text-primary)" : "var(--text-secondary)",
      border: "1px solid",
      borderColor: active ? color : "var(--border)",
    }}
  >
    <span style={{ width: 10, height: 2, background: color, borderRadius: 1, display: "inline-block" }} />
    {label}
  </button>
);

const ChartModal = ({ open, onClose, symbol, stock, livePrice, marketClosed, onTrade }) => {
  const [range, setRange] = useState("1d");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [showSMA20, setShowSMA20] = useState(() => {
    const v = localStorage.getItem("scale_ind_sma20");
    return v == null ? true : v === "1";
  });
  const [showSMA50, setShowSMA50] = useState(() => {
    const v = localStorage.getItem("scale_ind_sma50");
    return v == null ? true : v === "1";
  });
  const [showRSI, setShowRSI] = useState(() => {
    const v = localStorage.getItem("scale_ind_rsi");
    return v == null ? false : v === "1";
  });
  const [showAlert, setShowAlert] = useState(false);

  useEffect(() => { localStorage.setItem("scale_ind_sma20", showSMA20 ? "1" : "0"); }, [showSMA20]);
  useEffect(() => { localStorage.setItem("scale_ind_sma50", showSMA50 ? "1" : "0"); }, [showSMA50]);
  useEffect(() => { localStorage.setItem("scale_ind_rsi", showRSI ? "1" : "0"); }, [showRSI]);

  useEffect(() => {
    if (!open || !symbol) { setData(null); return; }
    let cancelled = false;
    setLoading(true);
    setErr("");
    (async () => {
      try {
        const { data } = await api.get(`/chart/${encodeURIComponent(symbol)}`, { params: { range } });
        if (!cancelled) setData(data);
      } catch (e) {
        if (!cancelled) setErr(e?.response?.data?.detail || "Chart unavailable");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, symbol, range]);

  // Compute indicators, attach to each candle
  const enriched = useMemo(() => {
    const cs = data?.candles || [];
    if (!cs.length) return [];
    const closes = cs.map((c) => c.c);
    const s20 = sma(closes, 20);
    const s50 = sma(closes, 50);
    const r14 = rsi(closes, 14);
    return cs.map((c, i) => ({
      ...c,
      hl: [c.l, c.h],
      sma20: s20[i],
      sma50: s50[i],
      rsi: r14[i],
    }));
  }, [data]);

  if (!open) return null;

  const last = enriched[enriched.length - 1];
  const first = enriched[0];
  const change = last && first ? last.c - first.o : 0;
  const changePct = last && first && first.o ? (change / first.o) * 100 : 0;
  const up = change >= 0;
  const rsiLast = last?.rsi;
  const chartH = showRSI ? 260 : 380;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.78)" }}
      onClick={onClose}
      data-testid="chart-modal"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[940px] surface rounded-2xl p-5 max-h-[95vh] overflow-y-auto"
        style={{ boxShadow: "0 32px 80px rgba(0,0,0,0.65)" }}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="mono" style={{ color: "var(--blue)", fontSize: 22, fontWeight: 700 }}>{symbol}</span>
              <span className="pill" style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}>{stock?.sector}</span>
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 2 }}>{stock?.name}</div>
          </div>
          <div className="text-right">
            <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>{livePrice ? fmtINR(livePrice) : "—"}</div>
            {last && first && (
              <div className="mono text-sm" style={{ color: up ? "var(--green)" : "var(--red)" }}>
                {up ? "+" : ""}{fmtNum(change)} ({fmtPct(changePct)})
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 mb-2 flex-wrap">
          {RANGES.map(([k, l]) => (
            <button
              key={k}
              data-testid={`range-${k}`}
              onClick={() => setRange(k)}
              className="px-3 py-1 rounded-md text-xs font-medium"
              style={{
                background: range === k ? "var(--blue)" : "var(--bg-elevated)",
                color: range === k ? "white" : "var(--text-secondary)",
                border: "1px solid",
                borderColor: range === k ? "var(--blue)" : "var(--border)",
              }}
            >
              {l}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <button data-testid="chart-buy" onClick={() => onTrade?.("BUY")} disabled={!!marketClosed} title={marketClosed ? "Market is closed" : ""} className="btn-buy px-3 py-1 rounded-md text-xs font-medium" style={{ opacity: marketClosed ? 0.5 : 1, cursor: marketClosed ? "not-allowed" : "pointer" }}>Buy</button>
            <button data-testid="chart-sell" onClick={() => onTrade?.("SELL")} disabled={!!marketClosed} title={marketClosed ? "Market is closed" : ""} className="btn-sell px-3 py-1 rounded-md text-xs font-medium" style={{ opacity: marketClosed ? 0.5 : 1, cursor: marketClosed ? "not-allowed" : "pointer" }}>Sell</button>
            <button data-testid="chart-alert" onClick={() => setShowAlert(true)} disabled={!livePrice} title="Set price alert" className="btn-ghost px-3 py-1 rounded-md text-xs font-medium" style={{ opacity: !livePrice ? 0.5 : 1 }}>🔔 Alert</button>
            <button onClick={onClose} className="btn-ghost px-3 py-1 rounded-md text-xs" data-testid="chart-close">Close</button>
          </div>
        </div>

        <div className="flex items-center gap-1.5 mb-3 flex-wrap">
          <span style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.1em", textTransform: "uppercase", marginRight: 4 }}>
            Indicators
          </span>
          <IndicatorToggle label="SMA 20" color="#f59e0b" active={showSMA20} onClick={() => setShowSMA20((v) => !v)} testid="ind-sma20" />
          <IndicatorToggle label="SMA 50" color="#a78bfa" active={showSMA50} onClick={() => setShowSMA50((v) => !v)} testid="ind-sma50" />
          <IndicatorToggle label="RSI 14" color="#22d3ee" active={showRSI} onClick={() => setShowRSI((v) => !v)} testid="ind-rsi" />
          {showSMA20 && showSMA50 && last?.sma20 != null && last?.sma50 != null && (
            <span className="ml-2 pill mono" style={{
              background: last.sma20 > last.sma50 ? "var(--green-dim)" : "var(--red-dim)",
              color: last.sma20 > last.sma50 ? "var(--green)" : "var(--red)",
              fontSize: 10,
            }} data-testid="sma-signal">
              {last.sma20 > last.sma50 ? "SMA20 > SMA50 · bullish" : "SMA20 < SMA50 · bearish"}
            </span>
          )}
          {showRSI && rsiLast != null && (
            <span className="pill mono" style={{
              background: rsiLast >= 70 ? "var(--red-dim)" : rsiLast <= 30 ? "var(--green-dim)" : "var(--bg-highlight)",
              color: rsiLast >= 70 ? "var(--red)" : rsiLast <= 30 ? "var(--green)" : "var(--text-secondary)",
              fontSize: 10,
            }} data-testid="rsi-signal">
              RSI {rsiLast.toFixed(1)} {rsiLast >= 70 ? "· overbought" : rsiLast <= 30 ? "· oversold" : "· neutral"}
            </span>
          )}
        </div>

        <div className="rounded-lg p-2" style={{ background: "#0a0e1a", border: "1px solid var(--border)", height: chartH }}>
          {loading && <div className="h-full flex items-center justify-center" style={{ color: "var(--text-muted)" }}>Loading chart…</div>}
          {err && !loading && <div className="h-full flex items-center justify-center" style={{ color: "var(--red)" }}>{err}</div>}
          {!loading && !err && enriched.length > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={enriched} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                <XAxis
                  dataKey="t"
                  tickFormatter={(t) => fmtTime(t, range)}
                  stroke="#475569"
                  fontSize={10}
                  minTickGap={48}
                />
                <YAxis
                  yAxisId="price"
                  domain={["dataMin - 1", "dataMax + 1"]}
                  stroke="#475569"
                  fontSize={10}
                  width={56}
                  tickFormatter={(v) => v.toFixed(0)}
                  orientation="right"
                />
                <YAxis yAxisId="vol" hide domain={[0, "dataMax"]} />
                <Tooltip content={<TooltipBox range={range} />} cursor={{ stroke: "#475569", strokeDasharray: "3 3" }} />
                {data?.previousClose && (
                  <ReferenceLine
                    yAxisId="price"
                    y={data.previousClose}
                    stroke="#475569"
                    strokeDasharray="4 4"
                    label={{ value: `Prev ${data.previousClose.toFixed(2)}`, fill: "#94a3b8", fontSize: 10, position: "right" }}
                  />
                )}
                <Bar yAxisId="vol" dataKey="v" maxBarSize={6} isAnimationActive={false} fillOpacity={0.25}>
                  {enriched.map((d, i) => (
                    <Cell key={i} fill={d.c >= d.o ? "#00d4aa" : "#f03e3e"} />
                  ))}
                </Bar>
                <Bar yAxisId="price" dataKey="hl" shape={<Candle />} isAnimationActive={false} />
                {showSMA20 && (
                  <Line yAxisId="price" type="monotone" dataKey="sma20" stroke="#f59e0b" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                )}
                {showSMA50 && (
                  <Line yAxisId="price" type="monotone" dataKey="sma50" stroke="#a78bfa" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>

        {showRSI && enriched.length > 0 && !loading && !err && (
          <div
            className="rounded-lg p-2 mt-2"
            style={{ background: "#0a0e1a", border: "1px solid var(--border)", height: 110 }}
            data-testid="rsi-panel"
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={enriched} margin={{ top: 10, right: 12, left: 0, bottom: 4 }}>
                <XAxis
                  dataKey="t"
                  tickFormatter={(t) => fmtTime(t, range)}
                  stroke="#475569"
                  fontSize={10}
                  minTickGap={48}
                  hide
                />
                <YAxis
                  domain={[0, 100]}
                  stroke="#475569"
                  fontSize={10}
                  width={56}
                  ticks={[30, 50, 70]}
                  orientation="right"
                />
                <ReferenceLine y={70} stroke="var(--red)" strokeDasharray="3 3" label={{ value: "70", fill: "#f03e3e", fontSize: 10, position: "right" }} />
                <ReferenceLine y={30} stroke="var(--green)" strokeDasharray="3 3" label={{ value: "30", fill: "#00d4aa", fontSize: 10, position: "right" }} />
                <Line type="monotone" dataKey="rsi" stroke="#22d3ee" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
                <Tooltip
                  contentStyle={{ background: "#0a0e1a", border: "1px solid var(--border)", color: "var(--text-primary)", fontSize: 12 }}
                  labelFormatter={(t) => fmtTime(t, range)}
                  formatter={(v) => [v?.toFixed?.(1) ?? "—", "RSI"]}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {data && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
              <Stat label="Prev Close" value={data.previousClose ? fmtNum(data.previousClose) : "—"} />
              <Stat label="52w High" value={data.fiftyTwoWeekHigh ? fmtNum(data.fiftyTwoWeekHigh) : "—"} tone="up" />
              <Stat label="52w Low" value={data.fiftyTwoWeekLow ? fmtNum(data.fiftyTwoWeekLow) : "—"} tone="down" />
              <Stat label="Valuation (₹ cr)" value={data.valuation ? fmtNum(data.valuation) : "—"} />
              <Stat label="Shares Outstanding" value={data.sharesOutstanding ? fmtNum(data.sharesOutstanding) : "—"} />
              <Stat label="Market Cap (₹)" value={data.regularMarketPrice && data.sharesOutstanding ? fmtNum(data.regularMarketPrice * data.sharesOutstanding) : "—"} />
            </div>
            {(() => {
              const dp = typeof data.demandPressure === "number" ? data.demandPressure : 0;
              const pct = (dp * 100).toFixed(1);
              const tone = dp > 0.05 ? "var(--green)" : dp < -0.05 ? "var(--red)" : "var(--text-secondary)";
              const arrow = dp > 0.05 ? "▲" : dp < -0.05 ? "▼" : "→";
              return (
                <div className="mt-3 p-3 rounded-lg" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }} data-testid="chart-demand-card">
                  <div style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-muted)" }}>
                    Demand Pressure
                  </div>
                  <div className="mono mt-1" style={{ fontSize: 22, fontWeight: 600, color: tone }}>
                    {arrow} {pct}%
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>
                    This reflects buying and selling activity by all students on SCALE India Investment today.
                  </div>
                  {data.narrative && (
                    <div style={{ fontSize: 12, color: "var(--text-primary)", marginTop: 6, padding: 8, borderLeft: "3px solid var(--blue)", background: "var(--bg-surface)" }}>
                      <span style={{ color: "var(--blue)", fontWeight: 600 }}>MarketBot:</span> {data.narrative}
                    </div>
                  )}
                </div>
              );
            })()}
          </>
        )}
      </div>
      <AlertModal
        open={showAlert}
        onClose={() => setShowAlert(false)}
        symbol={symbol}
        stock={stock}
        currentPrice={livePrice}
      />
    </div>
  );
};

export default ChartModal;

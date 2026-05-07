import React, { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = [
  "#a01e20", "#00d4aa", "#f59e0b", "#a78bfa", "#f472b6",
  "#22d3ee", "#fb7185", "#10b981", "#e879f9", "#94a3b8",
  "#fbbf24", "#60a5fa", "#34d399", "#fb923c", "#c084fc",
];

const SectorDonut = ({ holdings }) => {
  const data = useMemo(() => {
    const map = {};
    (holdings || []).forEach((h) => {
      const key = h.sector || "Other";
      map[key] = (map[key] || 0) + (h.currentValue || 0);
    });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [holdings]);

  const total = data.reduce((a, b) => a + b.value, 0);
  if (data.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              stroke="#111827"
            >
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: "#111827", border: "1px solid #1e293b", borderRadius: 8, color: "#e2e8f0", fontSize: 12 }}
              formatter={(v, n) => [`₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`, n]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-1.5">
        {data.map((d, i) => (
          <div key={d.name} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span style={{ width: 10, height: 10, borderRadius: 3, background: COLORS[i % COLORS.length], display: "inline-block" }} />
              <span style={{ color: "var(--text-primary)" }}>{d.name}</span>
            </div>
            <div className="mono" style={{ color: "var(--text-secondary)" }}>
              ₹{d.value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}{" "}
              <span style={{ color: "var(--text-muted)" }}>({((d.value / total) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SectorDonut;

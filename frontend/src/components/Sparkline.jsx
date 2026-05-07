import React from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";

const Sparkline = ({ points = [], color }) => {
  if (!points || points.length < 2) {
    return <div style={{ width: 60, height: 28, color: "var(--text-muted)", fontSize: 10 }}>—</div>;
  }
  const data = points.map((v, i) => ({ i, v }));
  const up = points[points.length - 1] >= points[0];
  const stroke = color || (up ? "var(--green)" : "var(--red)");
  return (
    <div style={{ width: 60, height: 28 }}>
      <ResponsiveContainer width={60} height={28}>
        <LineChart data={data}>
          <Line type="monotone" dataKey="v" stroke={stroke} dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default Sparkline;

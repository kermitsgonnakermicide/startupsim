// Frontend-side IST countdown helpers
export const istNow = () => {
  const s = new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" });
  return new Date(s);
};

export const istClock = () => {
  return new Date().toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
  });
};

export const countdown = (targetIso) => {
  if (!targetIso) return "";
  const target = new Date(targetIso).getTime();
  const now = istNow().getTime();
  let diff = Math.max(0, target - now);
  const h = Math.floor(diff / 3_600_000);
  diff -= h * 3_600_000;
  const m = Math.floor(diff / 60_000);
  diff -= m * 60_000;
  const s = Math.floor(diff / 1000);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

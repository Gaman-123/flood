// Risk ramp: cyan/blue -> yellow -> orange -> red
// Kept perceptually distinct from UI-state colors (green/amber/red).
export function riskColor(s) {
  const stops = [
    [0.00, [30, 100, 180]],   // deep blue
    [0.25, [70, 170, 200]],   // cyan
    [0.50, [240, 220, 90]],   // yellow
    [0.75, [240, 140, 50]],   // orange
    [1.00, [220, 40, 40]],    // red
  ];
  const v = Math.max(0, Math.min(1, s));
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i], [b, cb] = stops[i + 1];
    if (v >= a && v <= b) {
      const t = (v - a) / (b - a || 1e-9);
      return [
        Math.round(ca[0] + (cb[0] - ca[0]) * t),
        Math.round(ca[1] + (cb[1] - ca[1]) * t),
        Math.round(ca[2] + (cb[2] - ca[2]) * t),
      ];
    }
  }
  return [220, 40, 40];
}

export function riskColorCss(s, alpha = 1) {
  const [r, g, b] = riskColor(s);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// UI state colors
export const STATE = {
  safe:   "#22c55e",
  watch:  "#f59e0b",
  danger: "#ef4444",
};

export function stateColor(T) {
  if (T < 0.2) return STATE.safe;
  if (T < 0.5) return STATE.watch;
  return STATE.danger;
}

export function stateLabel(T) {
  if (T < 0.2) return "SAFE";
  if (T < 0.5) return "WATCH";
  return "DANGER";
}

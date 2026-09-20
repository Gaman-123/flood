import { stateColor } from "../lib/colors";

export default function TriggerGauge({ value = 0, size = 140, label = "T" }) {
  const v = Math.max(0, Math.min(1, value));
  const color = stateColor(v);
  const r = (size - 20) / 2;
  const c = size / 2;
  const circ = 2 * Math.PI * r;
  const arc = circ * 0.75; // 3/4 sweep
  const filled = arc * v;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }} data-testid="trigger-gauge">
      <svg width={size} height={size * 0.85}>
        <g transform={`translate(${c}, ${c})`}>
          <circle
            r={r}
            fill="none"
            stroke="var(--shadow-dark)"
            strokeWidth="10"
            strokeDasharray={`${arc} ${circ}`}
            strokeLinecap="round"
            transform="rotate(135)"
          />
          <circle
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeDasharray={`${filled} ${circ}`}
            strokeLinecap="round"
            transform="rotate(135)"
            style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.4s ease" }}
          />
          <text y="4" textAnchor="middle" fill="var(--text)" style={{ font: "600 30px 'JetBrains Mono', monospace" }}>
            {v.toFixed(2)}
          </text>
          <text y="24" textAnchor="middle" fill="var(--text-dim)" style={{ font: "500 10px 'IBM Plex Sans'" }}>
            trigger {label}(t)
          </text>
        </g>
      </svg>
    </div>
  );
}

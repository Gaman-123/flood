import { useEffect, useState } from "react";
import { useAppStore } from "../lib/store";
import { SCENARIOS } from "../lib/scenarios";
import { stateColor, stateLabel } from "../lib/colors";
import { Radio } from "lucide-react";

export default function TopBar() {
  const scenarioId = useAppStore((s) => s.scenarioId);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const iv = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  const sc = SCENARIOS[scenarioId];
  const T = sc.T;
  const color = stateColor(T);
  const label = stateLabel(T);

  const time = now.toLocaleTimeString("en-IN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    timeZone: "Asia/Kolkata",
  });

  return (
    <header
      data-testid="top-bar"
      style={{
        height: 56,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 20px",
        borderBottom: "none",
        background: "var(--surface)",
        boxShadow: "0 4px 14px -6px var(--shadow-dark)",
        zIndex: 10, position: "relative",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 38, height: 38, borderRadius: "50%",
            background: "var(--surface)",
            boxShadow: "var(--neo-out-sm)",
            display: "grid", placeItems: "center",
          }}
          aria-hidden
        >
          {/* Orion's belt — three stars */}
          <svg width="19" height="19" viewBox="0 0 20 20" fill="none">
            <circle cx="5.5" cy="13.5" r="1.7" fill="var(--accent)" />
            <circle cx="10" cy="10" r="1.9" fill="var(--accent)" />
            <circle cx="14.5" cy="6.5" r="1.7" fill="var(--accent)" />
            <path d="M5.5 13.5 L10 10 L14.5 6.5" stroke="var(--accent)"
                  strokeWidth="0.8" strokeOpacity="0.45" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <div style={{ fontSize: 17, fontWeight: 600, letterSpacing: 1.2, color: "var(--text)" }}>
            ORION
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)" }}>
            Flood risk &amp; emergency response · Dakshina Kannada
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div className="chip" data-testid="live-clock">
          <Radio size={11} style={{ color: "var(--safe)" }} />
          <span className="mono">{time} IST</span>
        </div>
        <div
          data-testid="scenario-badge"
          className="chip"
          style={{
            background: `${color}18`,
            border: `1px solid ${color}55`,
            color,
          }}
        >
          <span style={{
            display: "inline-block", width: 8, height: 8, borderRadius: 4,
            background: color, boxShadow: `0 0 8px ${color}`,
          }} />
          <span style={{ fontWeight: 600 }}>{label}</span>
          <span style={{ color: "var(--text-dim)", fontWeight: 400 }}>·</span>
          <span style={{ color: "var(--text)" }}>{sc.label}</span>
          <span className="mono" style={{ color: "var(--text-dim)" }}>T={T.toFixed(2)}</span>
        </div>
      </div>
    </header>
  );
}

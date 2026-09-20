import { useAppStore } from "../lib/store";
import { Map, Activity, Play, BarChart3, Info, Crosshair } from "lucide-react";

const TABS = [
  { id: "risk",     label: "Risk Map",  Icon: Map },
  { id: "live",     label: "Live",      Icon: Activity },
  { id: "simulate", label: "Simulate",  Icon: Play },
  { id: "emergency", label: "Pinpoint",  Icon: Crosshair },
  { id: "results",  label: "Results",   Icon: BarChart3 },
  { id: "about",    label: "About",     Icon: Info },
];

export default function LeftRail() {
  const activeTab = useAppStore((s) => s.activeTab);
  const setTab = useAppStore((s) => s.setTab);

  return (
    <nav
      data-testid="left-rail"
      style={{
        width: 76,
        display: "flex", flexDirection: "column",
        gap: 4, padding: "12px 8px",
        borderRight: "none",
        boxShadow: "6px 0 16px -10px var(--shadow-dark)",
        zIndex: 5,
        background: "var(--surface)",
      }}
      aria-label="Primary sections"
    >
      {TABS.map(({ id, label, Icon }) => (
        <button
          key={id}
          data-testid={`rail-tab-${id}`}
          onClick={() => setTab(id)}
          className={`rail-btn ${activeTab === id ? "active" : ""}`}
          aria-current={activeTab === id ? "page" : undefined}
        >
          <Icon size={20} strokeWidth={1.8} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

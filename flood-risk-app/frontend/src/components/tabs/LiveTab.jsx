import { useEffect, useState } from "react";
import axios from "axios";
import TriggerGauge from "../TriggerGauge";
import { stateColor, stateLabel } from "../../lib/colors";
import { CloudRain, Waves, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LiveTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  async function fetchTrigger() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/trigger`);
      setData(r.data);
    } catch (e) {
      console.error("trigger fetch failed", e);
    }
    setLoading(false);
  }

  useEffect(() => {
    fetchTrigger();
    const iv = setInterval(fetchTrigger, 10 * 60 * 1000);
    return () => clearInterval(iv);
  }, []);

  if (!data) {
    return <div style={{ color: "var(--text-dim)", fontSize: 13 }}>Loading live conditions…</div>;
  }

  const T = data.T;
  const color = stateColor(T);
  const label = stateLabel(T);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="tab-live">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>Live monitor</div>
          <div style={{ fontSize: 12, color: "var(--text-dim)" }}>Five-site district rainfall trigger for R = S(x) · T(now)</div>
        </div>
        <button data-testid="refresh-live" onClick={fetchTrigger} className="chip" style={{ cursor: "pointer" }}>
          <RefreshCw size={11} className={loading ? "spin" : ""} /> refresh
        </button>
      </div>

      <div className="card-panel" style={{ padding: 16, display: "flex", alignItems: "center", gap: 14 }}>
        <TriggerGauge value={T} size={130} />
        <div style={{ flex: 1 }}>
          <div style={{
            display: "inline-block", padding: "3px 10px", borderRadius: 999,
            background: `${color}22`, color, border: `1px solid ${color}55`,
            fontSize: 11, fontWeight: 700, letterSpacing: 0.6,
          }}>{label}</div>
          <div data-testid="live-headline" style={{ fontSize: 14, marginTop: 8, lineHeight: 1.4, color: "var(--text)" }}>
            {data.headline}
          </div>
        </div>
      </div>

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, color: "var(--text-dim)", fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
          <CloudRain size={13} /> Rainfall
        </div>
        <Row label="24-hour total" value={`${data.rain_24h} mm`} />
        <Row label="72-hour total" value={`${data.rain_72h} mm`} />
        <Row label="IMD category"  value={data.imd_category} accent={color} />
        <Row label="Highest-trigger site" value={data.critical_site || "Mangaluru"} accent={color} />
      </div>

      {data.sites?.length > 0 && (
        <div className="card-panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 12, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 8 }}>
            District sample
          </div>
          {data.sites.map((s) => <Row key={s.id} label={s.name} value={`T=${Number(s.T).toFixed(3)} · ${s["24h"]} mm/24h`} />)}
          <div style={{ fontSize: 10, color: "var(--text-dim)", marginTop: 8, lineHeight: 1.45 }}>
            Operational T uses the maximum sampled value. Tide is shown separately and is not yet part of T.
          </div>
        </div>
      )}

      <div className="card-panel" style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, color: "var(--text-dim)", fontSize: 12, letterSpacing: 0.4, textTransform: "uppercase" }}>
          <Waves size={13} /> Coastal tide
        </div>
        <Row label="Current height" value={`${data.tide_m} m`} />
        <Row label="Trend" value={data.tide_trend} />
      </div>

      <div style={{ fontSize: 11, color: "var(--text-dim)" }} data-testid="live-updated">
        Updated {new Date(data.updated).toLocaleTimeString("en-IN", { hour12: false })} · auto-refresh every 10 min
      </div>
    </div>
  );
}

function Row({ label, value, accent = "var(--text)" }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid var(--surface-sunken)" }}>
      <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 13, color: accent, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

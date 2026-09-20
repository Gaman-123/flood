import { useEffect, useState } from "react";
import { X, Loader2, Info, Satellite, Hospital, Layers } from "lucide-react";

// Click anywhere on the map -> full readout for that location.
// Every number comes from /api/explain, which samples the real predictor raster and
// decomposes the trained model's prediction with SHAP. Nothing here is generated
// prose: the summary is assembled from the attributions.

const API = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8000") + "/api";

const BAND_COLOR = {
  Low: "var(--safe)", Moderate: "#7fb23f", Elevated: "var(--watch)",
  High: "#e07b3c", "Very High": "var(--danger)",
};

// label + unit + short meaning for every conditioning factor
const FACTOR = {
  elevation: ["Elevation", "m", "height above sea level"],
  hand: ["Height above drainage", "m", "vertical clearance to nearest channel"],
  dist_river: ["Distance to river", "m", "proximity to a watercourse"],
  twi: ["Wetness index", "", "how strongly terrain concentrates flow"],
  rain_annual: ["Annual rainfall", "mm", "long-term climatology"],
  drainage_density: ["Drainage density", "", "channel network density nearby"],
  slope: ["Slope", "°", "steeper ground drains faster"],
  curvature: ["Curvature", "", "concave collects, convex sheds"],
  aspect: ["Aspect", "°", "slope facing direction"],
};

const Section = ({ icon: Icon, title, children }) => (
  <div style={{ marginTop: 14 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10,
                  color: "var(--text-mute)", letterSpacing: 0.5, marginBottom: 7 }}>
      <Icon size={11} /> {title}
    </div>
    {children}
  </div>
);

export default function ExplainPanel({ point, scenario, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!point) return;
    let cancelled = false;
    setLoading(true); setErr(null); setData(null); setShowAll(false);
    fetch(`${API}/explain?lat=${point.lat}&lon=${point.lon}&scenario=${scenario}`)
      .then(async (r) => {
        if (r.status === 404) throw new Error("Outside the analysed Mangaluru area.");
        if (!r.ok) throw new Error(`Explanation unavailable (${r.status})`);
        return r.json();
      })
      .then((j) => { if (!cancelled) setData(j); })
      .catch((e) => { if (!cancelled) setErr(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [point, scenario]);

  if (!point) return null;
  const accent = BAND_COLOR[data?.risk_band] || "var(--accent)";
  const near = data?.nearest_place;
  const isAtPlace = near && near.km <= 0.6;
  const allDrivers = data?.all_drivers ?? data?.drivers ?? [];
  const topDrivers = data?.drivers ?? [];
  const drivers = showAll ? allDrivers : topDrivers;

  return (
    <div className="card-panel" data-testid="explain-panel"
      style={{ position: "absolute", left: 16, bottom: 16, width: 366, zIndex: 7,
               padding: 16, maxHeight: "calc(100% - 32px)", overflowY: "auto" }}>

      {/* header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}>
            {isAtPlace ? near.name : "Selected location"}
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--text-mute)", marginTop: 3 }}>
            {point.lat.toFixed(4)}, {point.lon.toFixed(4)}
            {near && !isAtPlace && ` · ${near.km} km from ${near.name}`}
          </div>
        </div>
        <button onClick={onClose} aria-label="Close"
          style={{ background: "none", border: "none", color: "var(--text-dim)", cursor: "pointer", padding: 2 }}>
          <X size={15} />
        </button>
      </div>

      {loading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14,
                      color: "var(--text-dim)", fontSize: 12 }}>
          <Loader2 size={13} className="spin" /> analysing terrain…
        </div>
      )}
      {err && <div style={{ marginTop: 14, fontSize: 12, color: "var(--danger)" }}>{err}</div>}

      {data && (
        <>
          {/* headline risk */}
          <div className="panel-sunken" style={{ marginTop: 12, padding: "12px 14px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 9 }}>
              <span className="hero-stat" style={{ fontSize: 30, color: accent }}>
                {(data.susceptibility * 100).toFixed(0)}%
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: accent }}>{data.risk_band}</span>
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--text)", marginTop: 7 }}>
              {data.summary}
            </div>
            <div style={{ display: "flex", gap: 16, marginTop: 10, fontSize: 11 }}>
              <div>
                <div style={{ color: "var(--text-mute)", fontSize: 9.5 }}>CALIBRATED</div>
                <div className="mono" style={{ color: "var(--text)" }}>
                  {(data.calibrated_probability * 100).toFixed(0)}%
                </div>
              </div>
              {data.dynamic_risk != null && (
                <div>
                  <div style={{ color: "var(--text-mute)", fontSize: 9.5 }}>
                    NOW (T={data.trigger_T})
                  </div>
                  <div className="mono" style={{ color: accent }}>
                    {(data.dynamic_risk * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* observed evidence */}
          <Section icon={Satellite} title="SATELLITE EVIDENCE">
            <div style={{ fontSize: 11.5, color: "var(--text)", lineHeight: 1.45 }}>
              {data.sar_observed === true && (
                <><b style={{ color: "var(--danger)" }}>Water observed here.</b>{" "}
                Sentinel-1 detected standing water at this location during the monsoon record.</>
              )}
              {data.sar_observed === false && (
                <><b>Not captured in the SAR record.</b>{" "}
                <span style={{ color: "var(--text-dim)" }}>
                  Sentinel-1 passes every ~12 days, so short flash-flood peaks are
                  routinely missed — this is not evidence the location is safe.
                </span></>
              )}
              {data.sar_observed == null && (
                <span style={{ color: "var(--text-dim)" }}>SAR extent layer unavailable.</span>
              )}
            </div>
          </Section>

          {/* every conditioning factor */}
          <Section icon={Layers} title={`TERRAIN & CLIMATE (${drivers.length} OF ${allDrivers.length})`}>
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              {drivers.map((d) => {
                const [label, unit, meaning] = FACTOR[d.feature] || [d.feature, "", ""];
                const w = Math.min(100, Math.abs(d.shap) * 45);
                return (
                  <div key={d.feature}>
                    <div style={{ display: "flex", justifyContent: "space-between",
                                  fontSize: 11.5, color: "var(--text)" }}>
                      <span>{label}</span>
                      <span className="mono">{d.value}{unit}</span>
                    </div>
                    <div style={{ height: 3, background: "var(--shadow-dark)", borderRadius: 2,
                                  marginTop: 3, overflow: "hidden" }}>
                      <div style={{ width: `${w}%`, height: "100%",
                                    background: d.shap > 0 ? "var(--danger)" : "var(--safe)",
                                    transition: "width .35s cubic-bezier(.22,1,.36,1)" }} />
                    </div>
                    <div style={{ fontSize: 9.5, color: "var(--text-mute)", marginTop: 2 }}>
                      {d.shap > 0 ? "raises" : "reduces"} risk · {meaning}
                    </div>
                  </div>
                );
              })}
            </div>
            {allDrivers.length > topDrivers.length && (
            <button className="chip" onClick={() => setShowAll((v) => !v)}
              style={{ cursor: "pointer", marginTop: 9, fontSize: 10.5 }}>
              {showAll ? "Show top factors" : `Show all ${allDrivers.length} factors`}
            </button>
            )}
          </Section>

          {/* emergency access */}
          {!!data.nearest_hospitals?.length && (
            <Section icon={Hospital} title="NEAREST HOSPITALS">
              {data.nearest_hospitals.map((h) => (
                <div key={h.name} style={{ display: "flex", justifyContent: "space-between",
                                           fontSize: 11.5, color: "var(--text)", padding: "2px 0" }}>
                  <span>{h.name}</span>
                  <span className="mono" style={{ color: "var(--text-dim)" }}>{h.km} km</span>
                </div>
              ))}
              <div style={{ fontSize: 9.5, color: "var(--text-mute)", marginTop: 4 }}>
                Straight-line distance. Routed ambulance ETAs are computed between
                hospitals and defined incident sites, not arbitrary points.
              </div>
            </Section>
          )}

          <div style={{ marginTop: 14, paddingTop: 9, borderTop: "1px solid var(--shadow-dark)",
                        fontSize: 10, color: "var(--text-mute)", display: "flex", gap: 5 }}>
            <Info size={11} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>{data.caveat}</span>
          </div>
        </>
      )}
    </div>
  );
}

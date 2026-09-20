// Scenario metadata mirrors backend /api/scenarios; kept client-side for instant switching.
export const SCENARIOS = {
  dry:     { id: "dry",     label: "Dry / calm",                       T: 0.00, kind: "data-driven" },
  live:    { id: "live",    label: "Live now",                         T: 0.13, kind: "data-driven" },
  aug2024: { id: "aug2024", label: "Aug 2024 — Nethravathi river",     T: 0.39, kind: "data-driven" },
  may2025: { id: "may2025", label: "May 2025 — Mangaluru urban flood", T: 0.70, kind: "data-driven" },
  flash5:  { id: "flash5",  label: "Flash flood in 5 minutes",         T: 0.85, kind: "illustrative" },
};

export const SCENARIO_ORDER = ["dry", "live", "aug2024", "may2025", "flash5"];

// Model fallback used only while the live metrics endpoint is loading.
export const MODEL = {
  auc: 0.9625,
};

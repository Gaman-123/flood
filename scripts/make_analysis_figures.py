"""Figures for the analyses added for the journal manuscript.

Every panel reads a committed JSON artifact produced by the corresponding script:
  sensitivity_sweep.json   -> scripts/sensitivity_sweep.py
  spatial_validation.json  -> scripts/spatial_validation.py
  sar_validation.json      -> scripts/sar_validation.py
  trigger_table.json       -> scripts/trigger_table.py
  qaoa_depth_study.json    -> scripts/qaoa_depth_study.py

No value is hard-coded here; changing an upstream script and re-running changes
these figures.
"""
import json
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

FIG = "paper/figures"
P = "data/processed"

mpl.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42,
})


def load(name):
    return json.load(open(os.path.join(P, name)))


# ------------------------------------------------------------------ sensitivity

def fig_sensitivity():
    d = load("sensitivity_sweep.json")
    ks, bs = d["kappas"], d["blocks"]
    shape = (len(ks), len(bs))

    def grid(key):
        g = np.full(shape, np.nan)
        for c in d["cells"]:
            g[ks.index(c["kappa"]), bs.index(c["block"])] = (
                np.nan if c[key] is None else c[key])
        return g

    # Panels (a) and (b) MUST use the survivorship-corrected statistics: cells
    # with severed pairs would otherwise average over an easier, self-selected
    # subset and make an aggressive threshold look beneficial.
    exposure = grid("mean_exposure_common")
    detour = grid("mean_detour_min_common")
    unreach = grid("unreachable")
    base = d["baseline_risk_blind_common"]["mean_exposure"]
    op_k, op_b = d["operating_point"]["kappa"], d["operating_point"]["block"]

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    n_common = d["n_common_pairs"]
    n_pairs = d["n_pairs"]
    panels = [
        (exposure, "viridis", f"(a) Mean exposure (common {n_common} pairs)", "{:.3f}"),
        (detour, "magma", f"(b) Mean detour, min (common {n_common})", "{:.2f}"),
        (unreach, "cividis", f"(c) Severed pairs (of {n_pairs})", "{:.0f}"),
    ]
    for ax, (g, cmap, title, fmt) in zip(axes, panels):
        im = ax.imshow(g, cmap=cmap, aspect="auto", origin="lower")
        ax.set_xticks(range(len(bs))); ax.set_xticklabels([f"{b:.2f}" for b in bs], fontsize=6)
        ax.set_yticks(range(len(ks))); ax.set_yticklabels(ks, fontsize=6)
        ax.set_xlabel("Impassability threshold")
        if ax is axes[0]:
            ax.set_ylabel("Penalty weight $\\kappa$")
        ax.set_title(title, loc="left", fontsize=7.5)
        for i in range(shape[0]):
            for j in range(shape[1]):
                if np.isfinite(g[i, j]):
                    v = g[i, j]
                    rel = (v - np.nanmin(g)) / max(np.nanmax(g) - np.nanmin(g), 1e-9)
                    ax.text(j, i, fmt.format(v), ha="center", va="center",
                            fontsize=4.6, color="white" if rel < 0.55 else "black")
        # mark the operating point
        ax.add_patch(plt.Rectangle((bs.index(op_b) - 0.5, ks.index(op_k) - 0.5), 1, 1,
                                   fill=False, edgecolor="#ff2d00", linewidth=1.6))
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.ax.tick_params(labelsize=5.5)

    fig.suptitle(f"(a)-(b) over the {n_common} pairs routable in every cell "
                 f"(risk-blind baseline exposure {base:.3f}); "
                 f"operating point $\\kappa$={op_k:g}, $\\tau$={op_b:g} (red box)",
                 fontsize=7.0, y=1.05)
    fig.tight_layout()
    fig.savefig(f"{FIG}/sensitivity_sweep.pdf")
    plt.close(fig)
    print("   sensitivity_sweep.pdf")


# ------------------------------------------------------- spatial CV + ablation

def fig_spatial_validation():
    d = load("spatial_validation.json")
    order = ["full_12", "vif_11", "primary_9"]
    # Short axis labels: the full feature-set definitions live in the caption and
    # in Table "ablation", so the tick labels only need to disambiguate.
    labels = {"full_12": "12F", "vif_11": "11F", "primary_9": "9F"}

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))

    # (a) ablation: test AUC and F1
    ax = axes[0]
    x = np.arange(len(order)); w = 0.36
    auc = [d["ablation"][k]["test"]["roc_auc"] for k in order]
    f1 = [d["ablation"][k]["test"]["f1"] for k in order]
    ax.bar(x - w / 2, auc, w, label="Test ROC-AUC", color="#3b6ea5")
    ax.bar(x + w / 2, f1, w, label="Test $F_1$", color="#c1666b")
    for xi, (a, f) in enumerate(zip(auc, f1)):
        ax.text(xi - w / 2, a + 0.004, f"{a:.3f}", ha="center", fontsize=5.6)
        ax.text(xi + w / 2, f + 0.004, f"{f:.3f}", ha="center", fontsize=5.6)
    ax.set_xticks(x); ax.set_xticklabels([labels[k] for k in order], fontsize=7)
    ax.set_xlabel("Feature set")
    ax.set_ylim(0.85, 1.02); ax.set_title("(a) Feature-set ablation", loc="left")
    ax.legend(fontsize=6, loc="lower left")

    # (b) random vs spatial-block CV
    ax = axes[1]
    r = [d["spatial_cv"][k]["random_kfold_auc_mean"] for k in order]
    rs = [d["spatial_cv"][k]["random_kfold_auc_std"] for k in order]
    s = [d["spatial_cv"][k]["spatial_block_auc_mean"] for k in order]
    ss = [d["spatial_cv"][k]["spatial_block_auc_std"] for k in order]
    ax.bar(x - w / 2, r, w, yerr=rs, capsize=2, label="Random 5-fold", color="#8fb8de")
    ax.bar(x + w / 2, s, w, yerr=ss, capsize=2, label="Spatial-block 5-fold", color="#2f4b7c")
    for xi, (a, b) in enumerate(zip(r, s)):
        ax.text(xi + w / 2, b - 0.035, f"$-${100*(a-b)/a:.1f}%", ha="center",
                fontsize=5.6, color="white")
    ax.set_xticks(x); ax.set_xticklabels([labels[k] for k in order], fontsize=7)
    ax.set_xlabel("Feature set")
    ax.set_ylim(0.85, 1.02)
    ax.set_title("(b) Spatial-autocorrelation test", loc="left")
    ax.legend(fontsize=6, loc="lower left")

    # (c) SHAP ranking shift between the full and primary models
    ax = axes[2]
    top_full = d["ablation"]["full_12"]["shap_ranking"][:6][::-1]
    top_prim = d["ablation"]["primary_9"]["shap_ranking"][:6][::-1]
    y = np.arange(6)
    ax.barh(y + 0.2, [t["mean_abs_shap"] for t in top_full], 0.38,
            color="#c1666b", label="12 factors")
    ax.barh(y - 0.2, [t["mean_abs_shap"] for t in top_prim], 0.38,
            color="#3b6ea5", label="9 factors")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{a['feature']} / {b['feature']}"
                        for a, b in zip(top_prim, top_full)], fontsize=5.4)
    ax.set_xlabel("mean $|$SHAP$|$")
    ax.set_title("(c) SHAP top-6 (9-factor / 12-factor)", loc="left", fontsize=7.5)
    ax.legend(fontsize=6, loc="lower right")

    fig.tight_layout()
    fig.savefig(f"{FIG}/spatial_validation.pdf")
    plt.close(fig)
    print("   spatial_validation.pdf")


# ------------------------------------------------------------- SAR validation

def fig_sar_validation():
    d = load("sar_validation.json")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))

    ax = axes[0]
    fpr, tpr = d["roc_curve"]["fpr"], d["roc_curve"]["tpr"]
    ax.plot(fpr, tpr, color="#2f4b7c", lw=1.6,
            label=f"Geographic transfer (AUC = {d['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="#888888", label="No skill")
    ax.set_xlabel("False-positive rate"); ax.set_ylabel("True-positive rate")
    ax.set_title("(a) ROC against SAR-observed flooding", loc="left")
    ax.legend(fontsize=6, loc="lower right")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)

    ax = axes[1]
    src = d["success_rate_curve"]
    pts = sorted((int(k.split("_")[1].replace("pct", "")), v) for k, v in src.items())
    xs = [0] + [p for p, _ in pts]
    ys = [0] + [100 * v for _, v in pts]
    ax.plot(xs, ys, marker="o", ms=3.5, lw=1.6, color="#0b6e4f",
            label="Susceptibility ranking")
    ax.plot([0, 100], [0, 100], ls="--", lw=0.8, color="#888888", label="Random ranking")
    for p, v in pts[:3]:
        ax.annotate(f"{100*v:.0f}%", (p, 100 * v), textcoords="offset points",
                    xytext=(4, -8), fontsize=6)
    ax.set_xlabel("Landscape ranked by susceptibility (% of area)")
    ax.set_ylabel("Observed flooding captured (%)")
    ax.set_title("(b) Success-rate curve", loc="left")
    ax.set_xlim(0, 55); ax.set_ylim(0, 100)
    ax.legend(fontsize=6, loc="lower right")

    fig.tight_layout()
    fig.savefig(f"{FIG}/sar_validation.pdf")
    plt.close(fig)
    print("   sar_validation.pdf")


# ------------------------------------------------------------- trigger anatomy

def fig_trigger_anatomy():
    d = load("trigger_table.json")
    rows = d["scenarios"]
    short = {"documented flood": None, "heavy non-flood": "Heavy\nno flood",
             "ordinary wet": "Ordinary\nwet", "dry": "Dry"}
    names = [short[r["kind"]] or r["scenario"].split()[0] + " " +
             r["scenario"].split()[1][:4] + "\nflood" for r in rows]
    x = np.arange(len(rows))

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7))

    # (a) stacked decomposition of T
    ax = axes[0]
    daily = [r["daily_weighted"] for r in rows]
    sat = [r["saturation_weighted"] for r in rows]
    burst = [r["burst_weighted"] for r in rows]
    ax.bar(x, daily, 0.6, label="0.5 x daily (24 h)", color="#2f4b7c")
    ax.bar(x, sat, 0.6, bottom=daily, label="0.3 x saturation (72 h)", color="#3b8ea5")
    ax.bar(x, burst, 0.6, bottom=np.array(daily) + np.array(sat),
           label="0.2 x burst (6 h)", color="#a5c8d6")
    for xi, r in enumerate(rows):
        ax.text(xi, r["trigger_T"] + 0.02, f"T={r['trigger_T']:.3f}",
                ha="center", fontsize=6)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=5.2)
    ax.set_ylabel("Trigger $T(t)$"); ax.set_ylim(0, 0.85)
    ax.set_title("(a) Trigger decomposition", loc="left")
    ax.legend(fontsize=5.8, loc="upper right")

    # (b) the raw rainfall inputs behind it
    ax = axes[1]
    w = 0.26
    ax.bar(x - w, [r["rain_6h_mm"] for r in rows], w, label="6 h", color="#a5c8d6")
    ax.bar(x, [r["rain_24h_mm"] for r in rows], w, label="24 h", color="#3b8ea5")
    ax.bar(x + w, [r["rain_72h_mm"] for r in rows], w, label="72 h", color="#2f4b7c")
    for lvl, lab in ((d["imd_thresholds_mm"]["heavy"], "IMD Heavy"),
                     (d["imd_thresholds_mm"]["very_heavy"], "IMD Very Heavy")):
        ax.axhline(lvl, ls="--", lw=0.7, color="#c1121f")
        ax.text(len(rows) - 0.4, lvl + 3, lab, fontsize=5.4, color="#c1121f", ha="right")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=5.2)
    ax.set_ylabel("Antecedent rainfall (mm)")
    ax.set_title("(b) Measured rainfall inputs", loc="left")
    ax.legend(fontsize=6, loc="upper right")

    # (c) how the adversarial margin depends on the saturation weight
    ax = axes[2]
    sw = load("trigger_sweep.json")
    trend = sw["mean_adversarial_margin_by_w_sat_at_theta200"]
    xs = [float(k) for k in trend]
    ys = [trend[k] for k in trend]
    ax.plot(xs, ys, lw=1.8, color="#2f4b7c", label="mean over weight simplex")
    ax.axhline(0, ls="--", lw=0.8, color="#888888")
    op = sw["operating_point"]
    ax.plot([op["w_sat"]], [op["margin_adversarial"]], marker="o", ms=5,
            color="#c1121f", zorder=5,
            label=f"operating point ({op['margin_adversarial']:+.3f})")
    ax.set_xlabel("Weight on the 72 h saturation term")
    ax.set_ylabel("Flood vs heavy-non-flood margin")
    ax.set_title("(c) Trigger weight sensitivity", loc="left")
    ax.legend(fontsize=5.6, loc="upper left")

    fig.tight_layout()
    fig.savefig(f"{FIG}/trigger_anatomy.pdf")
    plt.close(fig)
    print("   trigger_anatomy.pdf")


# ---------------------------------------------------------------- QAOA depth

def fig_qaoa_depth():
    d = load("qaoa_depth_study.json")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    colors = {"drycalm": "#2f4b7c", "may2025_flood": "#c1666b"}
    label = {"drycalm": "Dry (T = 0)", "may2025_flood": "May 2025 flood (T = 0.70)"}

    ax = axes[0]
    for k, s in d["scenarios"].items():
        ps = [r["p"] for r in s["depths"]]
        m = np.array([r["approx_ratio_mean"] for r in s["depths"]])
        sd = np.array([r["approx_ratio_std"] for r in s["depths"]])
        ax.plot(ps, m, marker="o", ms=3.5, lw=1.5, color=colors[k], label=label[k])
        ax.fill_between(ps, m - sd, m + sd, color=colors[k], alpha=0.18)
    ax.set_xlabel("Circuit depth $p$"); ax.set_ylabel("Approximation ratio")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_title(f"(a) Solution quality vs depth "
                 f"({d['scenarios']['drycalm']['depths'][0]['n_seeds']} seeds, "
                 f"mean $\\pm$ 1 s.d.)", loc="left", fontsize=7.2)
    ax.legend(fontsize=6, loc="lower right")

    ax = axes[1]
    for k, s in d["scenarios"].items():
        ps = [r["p"] for r in s["depths"]]
        m = np.array([r["prob_optimal_mean"] for r in s["depths"]])
        sd = np.array([r["prob_optimal_std"] for r in s["depths"]])
        ax.errorbar(ps, m, yerr=sd, marker="s", ms=3.5, lw=1.5, capsize=2,
                    color=colors[k], label=label[k])
    base = d["scenarios"]["drycalm"]["random_sampling_baseline"]
    ax.axhline(base, ls="--", lw=0.8, color="#888888")
    ax.text(1.05, base * 1.25, "uniform random over $2^9$ states",
            fontsize=5.6, color="#666666")
    ax.set_yscale("log")
    ax.set_xlabel("Circuit depth $p$"); ax.set_ylabel("P(sampling the optimum)")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_title("(b) Optimum-sampling probability", loc="left")
    ax.legend(fontsize=6, loc="lower right")

    fig.tight_layout()
    fig.savefig(f"{FIG}/qaoa_depth.pdf")
    plt.close(fig)
    print("   qaoa_depth.pdf")


def main():
    os.makedirs(FIG, exist_ok=True)
    print(">> Building analysis figures")
    fig_sensitivity()
    fig_spatial_validation()
    fig_sar_validation()
    fig_trigger_anatomy()
    fig_qaoa_depth()
    print(">> Done")


if __name__ == "__main__":
    main()

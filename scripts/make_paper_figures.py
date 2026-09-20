"""Generate every figure used in paper/main.tex from real, on-disk artifacts.

No synthetic numbers: every figure reads data/processed/*.json or web_assets/*
produced by the actual pipeline (training, dynamic-risk, routing, quantum,
benchmark scripts). Run the relevant upstream scripts first if a file is missing.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROC = "data/processed"
OUT = "paper/figures"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.titlesize": 10,
    "axes.labelsize": 9, "legend.fontsize": 8, "figure.dpi": 200,
    "savefig.bbox": "tight",
})
C_D, C_A, C_SAFE, C_DANGER, C_ACCENT = "#cf8f1c", "#3f74c9", "#2aa96b", "#d94459", "#4a5a72"


def fig_shap():
    rows = [line.strip().split(",") for line in open(f"{PROC}/feature_importance.csv")][1:]
    feats = [r[0] for r in rows][::-1]
    vals = [float(r[1]) for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    ax.barh(feats, vals, color=C_ACCENT)
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title("Feature attribution (primary model)")
    fig.savefig(f"{OUT}/shap_importance.pdf")
    plt.close(fig)
    print("  shap_importance.pdf")


def fig_model_metrics():
    d = json.load(open(f"{PROC}/model_metrics.json"))
    metrics = ["accuracy", "precision", "recall", "f1", "roc_auc"]
    labels = ["Acc.", "Prec.", "Recall", "F1", "ROC-AUC"]
    rf = [d["results"]["RandomForest"]["test"][m] * 100 for m in metrics]
    xgb = [d["results"]["XGBoost"]["test"][m] * 100 for m in metrics]
    x = np.arange(len(labels)); w = 0.35
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    ax.bar(x - w/2, rf, w, label="RandomForest", color=C_D)
    ax.bar(x + w/2, xgb, w, label="XGBoost", color=C_A)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Score (%)"); ax.set_ylim(0, 100)
    ax.legend(loc="lower right")
    ax.set_title("Susceptibility model test-set performance")
    fig.savefig(f"{OUT}/model_metrics.pdf")
    plt.close(fig)
    print("  model_metrics.pdf")


def fig_calibration():
    d = json.load(open(f"{PROC}/model_metrics.json"))["calibration"]
    mp, fp = d["reliability_curve"]["mean_predicted"], d["reliability_curve"]["fraction_positive"]
    fig, ax = plt.subplots(figsize=(2.9, 2.7))
    ax.plot([0, 1], [0, 1], "--", color="#999", lw=1, label="Perfect calibration")
    ax.plot(mp, fp, "o-", color=C_ACCENT, lw=1.4, ms=4, label="Isotonic-calibrated model")
    ax.set_xlabel("Mean predicted probability"); ax.set_ylabel("Observed frequency")
    ax.set_title(f"Reliability diagram (Brier {d['brier_raw']}$\\to${d['brier_calibrated']})")
    ax.legend(loc="upper left", fontsize=7)
    fig.savefig(f"{OUT}/calibration.pdf")
    plt.close(fig)
    print("  calibration.pdf")


def fig_trigger():
    d = json.load(open(f"{PROC}/trigger_table.json"))
    order = ["Dry-season baseline", "Ordinary monsoon wet day",
             "Heavy rain, no reported flooding",
             "Aug 2024 Nethravathi river flood",
             "May 2025 Mangaluru urban flood"]
    by_name = {s["scenario"]: s for s in d["scenarios"]}
    scenarios = ["Dry", "Ordinary\nwet", "Heavy\nnon-flood",
                 "Aug 2024\nflood", "May 2025\nflood"]
    T = [by_name[name]["trigger_T"] for name in order]
    colors = [C_SAFE, C_SAFE, "#e8a33c", C_DANGER, C_DANGER]
    fig, ax = plt.subplots(figsize=(4.2, 2.4))
    ax.bar(scenarios, T, color=colors)
    ax.set_ylabel("Trigger $T(t)$"); ax.set_ylim(0, 0.85)
    ax.set_title("Dynamic rainfall/tide trigger by scenario")
    for i, t in enumerate(T):
        ax.text(i, t + 0.02, f"{t:.2f}", ha="center", fontsize=8)
    fig.savefig(f"{OUT}/trigger_validation.pdf")
    plt.close(fig)
    print("  trigger_validation.pdf")


def fig_routing_exposure():
    focus = json.load(open("web_assets/coverage.json"))["scenarios"]["may2025"]["focus_pair"]
    labels = ["Risk-blind", "Flood-aware"]
    eta = [focus["blind"]["minutes"], focus["aware"]["minutes"]]
    mean_exp = [focus["blind"]["mean_exposure"], focus["aware"]["mean_exposure"]]
    fig, axes = plt.subplots(1, 2, figsize=(4.6, 2.3))
    axes[0].bar(labels, eta, color=[C_DANGER, C_SAFE])
    axes[0].set_ylabel("ETA (min)"); axes[0].set_title("(a) Response time")
    for i, v in enumerate(eta):
        axes[0].text(i, v + 0.3, f"{v}", ha="center", fontsize=8)
    axes[1].bar(labels, mean_exp, color=[C_DANGER, C_SAFE])
    axes[1].set_ylabel("Mean flood exposure"); axes[1].set_title("(b) Route risk")
    for i, v in enumerate(mean_exp):
        axes[1].text(i, v + 0.006, f"{v}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{OUT}/routing_exposure.pdf")
    plt.close(fig)
    print("  routing_exposure.pdf")


def fig_routing_benchmark():
    d = json.load(open(f"{PROC}/routing_benchmark.json"))
    rows = d["pairs"]
    dj = [r["dijkstra_explored"] for r in rows]
    a = [r["astar_explored"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(5.4, 2.5))

    lim = max(max(dj), max(a)) * 1.05
    axes[0].plot([0, lim], [0, lim], "--", color="#999", lw=1)
    axes[0].scatter(dj, a, s=14, color=C_ACCENT, alpha=0.75)
    axes[0].set_xlabel("Dijkstra: nodes explored")
    axes[0].set_ylabel("A*: nodes explored")
    axes[0].set_title(f"(a) Per-pair search cost (n={len(rows)})")

    reductions = sorted(100 * (1 - r["astar_explored"] / r["dijkstra_explored"]) for r in rows)
    axes[1].hist(reductions, bins=14, color=C_A, edgecolor="white")
    axes[1].axvline(np.median(reductions), color=C_DANGER, ls="--", lw=1.2,
                    label=f"median {np.median(reductions):.0f}%")
    axes[1].set_xlabel("Node-exploration reduction (%)")
    axes[1].set_ylabel("Pairs")
    axes[1].set_title("(b) Distribution across routes")
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(f"{OUT}/routing_benchmark.pdf")
    plt.close(fig)
    print("  routing_benchmark.pdf")


def fig_qaoa():
    d = json.load(open(f"{PROC}/qaoa_depth_study.json"))["scenarios"]
    depths = [r["p"] for r in d["drycalm"]["depths"]]
    dry = [r["approx_ratio_mean"] for r in d["drycalm"]["depths"]]
    flood = [r["approx_ratio_mean"] for r in d["may2025_flood"]["depths"]]
    fig, ax = plt.subplots(figsize=(3.2, 2.4))
    ax.plot(depths, dry, "o-", color=C_SAFE, label="Dry / calm")
    ax.plot(depths, flood, "s-", color=C_DANGER, label="May 2025 flood")
    ax.axhline(1.0, color="#999", ls=":", lw=1, label="Classical optimum")
    ax.set_xticks(depths); ax.set_xlabel("QAOA depth $p$")
    ax.set_ylabel("Approximation ratio")
    ax.set_ylim(0.8, 1.03)
    ax.set_title("QAOA depth study (five-seed mean)")
    ax.legend(fontsize=7, loc="lower right")
    fig.savefig(f"{OUT}/qaoa_convergence.pdf")
    plt.close(fig)
    print("  qaoa_convergence.pdf")


def fig_road_network():
    coverage = json.load(open("web_assets/coverage.json"))["graph"]
    fig, ax = plt.subplots(figsize=(2.6, 2.6))
    prone = coverage["flood_prone_pct"]
    safe = 100.0 - prone
    ax.pie([prone, safe], labels=[f"Flood-prone\n{prone}%", f"Not flood-prone\n{safe}%"],
          colors=[C_DANGER, C_SAFE], autopct=None, startangle=90,
          textprops={"fontsize": 8})
    ax.set_title(f"Dakshina Kannada road network\n({coverage['edges']:,} directed edges)")
    fig.savefig(f"{OUT}/road_network.pdf")
    plt.close(fig)
    print("  road_network.pdf")


if __name__ == "__main__":
    print(">> Generating paper figures from real artifacts")
    fig_shap()
    fig_model_metrics()
    fig_calibration()
    fig_trigger()
    fig_routing_exposure()
    fig_routing_benchmark()
    fig_qaoa()
    fig_road_network()
    print(f">> Done. Figures in {OUT}/")

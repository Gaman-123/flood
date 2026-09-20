"""Compare training runs from data/processed/experiments.jsonl.

Turns the ablation history into a table you can paste into the paper, instead of
metrics being silently overwritten on every run.
"""
import json
import os
import sys

LOG = "data/processed/experiments.jsonl"


def main():
    if not os.path.exists(LOG):
        sys.exit(f"no run history yet at {LOG} — run `make train`")

    runs = [json.loads(line) for line in open(LOG) if line.strip()]
    if not runs:
        sys.exit("run history is empty")

    print(f"\n{len(runs)} run(s) — {LOG}\n")
    hdr = f"{'#':>2}  {'date':16}  {'model':13}  {'feats':>5}  {'rows':>5}  " \
          f"{'test AUC':>8}  {'CV AUC':>14}  {'Brier(cal)':>10}  {'commit':>8}"
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(runs, 1):
        cv = f"{r.get('cv_roc_auc_mean', 0):.4f}±{r.get('cv_roc_auc_std', 0):.3f}"
        print(f"{i:>2}  {r['timestamp'][:16]:16}  {r['model']:13}  "
              f"{r.get('n_features', 0):>5}  {r.get('n_rows', 0):>5}  "
              f"{r.get('test_roc_auc', 0):>8.4f}  {cv:>14}  "
              f"{r.get('brier_calibrated', float('nan')):>10.4f}  "
              f"{str(r.get('git_commit') or '-'):>8}")

    best = max(runs, key=lambda r: r.get("test_roc_auc", 0))
    print(f"\nbest test AUC: {best['test_roc_auc']:.4f} ({best['model']}, "
          f"{best.get('n_features')} features, {best['timestamp'][:16]})")
    print(f"top predictors: {', '.join(best.get('top_features', [])[:5])}")

    if len(runs) > 1:
        first, last = runs[0], runs[-1]
        d = last.get("test_roc_auc", 0) - first.get("test_roc_auc", 0)
        print(f"change since first run: {d:+.4f} AUC")


if __name__ == "__main__":
    main()

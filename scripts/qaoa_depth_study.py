"""QAOA depth study: how solution quality scales with circuit depth p (multi-seed).

The conference paper reported approximation ratio at p=1..3 in a figure only.
This extends the study to p=1..5 and publishes the full per-depth record a
reviewer needs to judge it: approximation ratio, the probability of directly
sampling the true optimum, the probability of landing in the feasible (one-hot
valid assignment) subspace, the COBYLA function-evaluation count, and wall time.

Two reference lines make the numbers interpretable rather than merely reported:
  * random baseline  -- probability of sampling the optimum by chance from the
                        uniform superposition over 2^9 states.
  * feasible baseline -- probability of sampling the optimum given a uniform
                        draw restricted to the 3! = 6 valid assignments.

The ETA cost matrices are read from the committed dispatch artifact so this
study reproduces exactly without re-running the routing or Earth Engine stages.
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from floodrisk import quantum  # noqa: E402

IN = "data/processed/quantum_dispatch.json"
OUT = "data/processed/qaoa_depth_study.json"

MAX_P = 5
RESTARTS = 32
# QAOA parameter optimization is a non-convex classical problem solved by COBYLA,
# a local method. A single seed therefore reports one draw from a distribution,
# not "the" performance at depth p. Repeating over seeds is what makes the
# depth trend (and its non-monotonicity) a measurement rather than an anecdote.
SEEDS = [7, 13, 29, 41, 97]


def main():
    src = json.load(open(IN))
    print(f">> QAOA depth study to p={MAX_P} (exact statevector, 9 qubits)")

    out = {"max_p": MAX_P, "restarts": RESTARTS, "seeds": SEEDS, "scenarios": {}}

    for scenario in ("drycalm", "may2025_flood"):
        s = src[scenario]
        C = np.array(s["eta_min"], dtype=float)
        n = C.size
        print(f"\n   === {scenario} (T={s['trigger']}) ===")
        print(f"   cost matrix (min):\n{np.round(C, 2)}")

        # classical reference: Hungarian on the raw cost matrix
        r, c = linear_sum_assignment(C)
        hungarian_cost = float(C[r, c].sum())

        Q, offset = quantum.build_assignment_qubo(C)
        bf = quantum.brute_force(Q, offset)
        agrees = abs(bf["energy"] - hungarian_cost) < 1e-6
        print(f"   Hungarian optimum {hungarian_cost:.4f} min | "
              f"QUBO ground state {bf['energy']:.4f} | agree: {agrees}")

        # baselines for interpreting prob_optimal
        n_states = 2 ** n
        n_feasible = 6                      # 3! permutation matrices
        rand_baseline = 1.0 / n_states
        feas_baseline = 1.0 / n_feasible

        # per-seed INTERP chains: each seed carries its own warm start up the ladder
        warm = {s: None for s in SEEDS}
        rows = []
        for p in range(1, MAX_P + 1):
            ratios, popts, pfeas, walls = [], [], [], []
            for sd in SEEDS:
                t0 = time.perf_counter()
                res = quantum.qaoa_run(Q, offset, p=p, restarts=RESTARTS,
                                       seed=sd, init=warm[sd])
                walls.append(time.perf_counter() - t0)
                warm[sd] = quantum.interp_params(res["params"])
                ratios.append(res["approx_ratio"])
                popts.append(res["prob_optimal"])
                pfeas.append(res["prob_feasible"])

            rows.append({
                "p": p,
                "n_params": 2 * p,
                "n_seeds": len(SEEDS),
                "approx_ratio_mean": round(float(np.mean(ratios)), 4),
                "approx_ratio_std": round(float(np.std(ratios)), 4),
                "approx_ratio_best": round(float(np.max(ratios)), 4),
                "prob_optimal_mean": round(float(np.mean(popts)), 5),
                "prob_optimal_std": round(float(np.std(popts)), 5),
                "prob_feasible_mean": round(float(np.mean(pfeas)), 5),
                "lift_over_random": round(float(np.mean(popts)) / rand_baseline, 1),
                "lift_over_feasible_uniform": round(float(np.mean(popts)) / feas_baseline, 3),
                "wall_seconds_mean": round(float(np.mean(walls)), 2),
            })
            q = rows[-1]
            print(f"   p={p}: ratio {q['approx_ratio_mean']:.4f}+/-{q['approx_ratio_std']:.4f} "
                  f"(best {q['approx_ratio_best']:.4f}) | "
                  f"P(opt) {q['prob_optimal_mean']:.4f}+/-{q['prob_optimal_std']:.4f} "
                  f"({q['lift_over_random']}x random) | "
                  f"P(feas) {q['prob_feasible_mean']:.4f} | {q['wall_seconds_mean']}s")

        means = [r["approx_ratio_mean"] for r in rows]
        monotone = all(b >= a for a, b in zip(means, means[1:]))
        print(f"   approximation ratio monotone in p: {monotone}")

        out["scenarios"][scenario] = {
            "trigger": s["trigger"],
            "cost_matrix_min": C.tolist(),
            "stations": s["stations"],
            "incidents": s["incidents"],
            "hungarian_cost_min": round(hungarian_cost, 4),
            "qubo_ground_energy": round(bf["energy"], 4),
            "qubo_matches_hungarian": bool(agrees),
            "n_states": n_states,
            "n_feasible_states": n_feasible,
            "random_sampling_baseline": rand_baseline,
            "feasible_uniform_baseline": feas_baseline,
            "approx_ratio_monotone_in_p": bool(monotone),
            "depths": rows,
        }

    # does the optimal plan change between dry and flood?
    a = out["scenarios"]["drycalm"]
    b = out["scenarios"]["may2025_flood"]
    Ca, Cb = np.array(a["cost_matrix_min"]), np.array(b["cost_matrix_min"])
    ra, ca_ = linear_sum_assignment(Ca)
    rb, cb_ = linear_sum_assignment(Cb)
    out["assignment_changes_under_flood"] = bool(list(ca_) != list(cb_))
    out["assignment_dry"] = [[a["stations"][i], a["incidents"][j]] for i, j in zip(ra, ca_)]
    out["assignment_flood"] = [[b["stations"][i], b["incidents"][j]] for i, j in zip(rb, cb_)]
    print(f"\n   optimal assignment changes under flood: "
          f"{out['assignment_changes_under_flood']}")

    os.makedirs("data/processed", exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f">> Saved -> {OUT}")


if __name__ == "__main__":
    main()

"""Invariants for the QUBO / QAOA dispatch layer.

The paper's quantum claim rests on one thing: the QUBO encoding of the ambulance
assignment problem must have the *same* optimum as the classical Hungarian
algorithm on the raw cost matrix. `floodrisk/quantum.py` asserts this informally
at runtime; these tests pin it down so a refactor cannot silently break it.
"""
import json
import os

import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from floodrisk import quantum

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPATCH_JSON = os.path.join(REPO, "web_assets", "dispatch.json")


def hungarian_cost(C):
    C = np.asarray(C, dtype=float)
    r, c = linear_sum_assignment(C)
    return float(C[r, c].sum())


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_qubo_optimum_equals_hungarian(seed):
    """The QUBO ground state must be the true assignment optimum."""
    rng = np.random.default_rng(seed)
    C = rng.uniform(1, 25, size=(3, 3))
    Q, offset = quantum.build_assignment_qubo(C)
    best = quantum.brute_force(Q, offset)
    assert best["energy"] == pytest.approx(hungarian_cost(C), rel=1e-9)


@pytest.mark.parametrize("n", [2, 3])
def test_qubo_ground_state_is_a_permutation(n):
    """The penalty terms must make the optimum a valid one-to-one assignment."""
    rng = np.random.default_rng(42)
    C = rng.uniform(1, 20, size=(n, n))
    Q, offset = quantum.build_assignment_qubo(C)
    bits = np.array(quantum.brute_force(Q, offset)["bits"]).reshape(n, n)
    assert (bits.sum(axis=0) == 1).all(), "each incident served exactly once"
    assert (bits.sum(axis=1) == 1).all(), "each ambulance used exactly once"


def test_penalty_large_enough_to_forbid_infeasible():
    """An infeasible state must never beat the feasible optimum."""
    C = np.array([[1.0, 50.0], [50.0, 1.0]])
    Q, offset = quantum.build_assignment_qubo(C)
    E, B = quantum.enumerate_energies(Q, offset)
    n = int(np.sqrt(Q.shape[0]))
    X = B.reshape(-1, n, n)
    feasible = (X.sum(1) == 1).all(1) & (X.sum(2) == 1).all(1)
    assert E[feasible].min() < E[~feasible].min()


def test_qaoa_improves_with_depth():
    """Deeper QAOA (with INTERP warm start) should not degrade the approx ratio."""
    C = np.array([[5.3, 7.0, 13.6], [6.3, 9.4, 9.8], [8.7, 5.8, 17.0]])
    Q, offset = quantum.build_assignment_qubo(C)
    prev, ratios = None, []
    for p in (1, 2):
        res = quantum.qaoa_run(Q, offset, p=p, restarts=6, maxiter=250, seed=7, init=prev)
        ratios.append(res["approx_ratio"])
        prev = quantum.interp_params(res["params"])
    assert all(0.0 <= r <= 1.0 for r in ratios)
    assert ratios[-1] >= ratios[0] - 0.05, f"depth hurt the solution: {ratios}"


def test_interp_warm_start_extends_depth():
    params_p1 = [0.1, 1.2]                       # p=1 -> [gamma, beta]
    out = quantum.interp_params(params_p1)
    assert len(out) == 4, "p=1 params must stretch to p=2 (2*p values)"
    assert np.all(np.isfinite(out))


@pytest.mark.skipif(not os.path.exists(DISPATCH_JSON), reason="run `make assets` first")
def test_published_dispatch_matches_hungarian():
    """The committed research artifact must still agree with the classical optimum."""
    data = json.load(open(DISPATCH_JSON))
    for key in ("drycalm", "may2025_flood"):
        if key not in data:
            continue
        s = data[key]
        assert hungarian_cost(s["eta_min"]) == pytest.approx(s["optimal_cost_min"], rel=1e-6), (
            f"{key}: stored optimum disagrees with Hungarian"
        )

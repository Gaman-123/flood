"""Hybrid quantum module: QUBO formulation + QAOA on an exact statevector simulator.

Completes the architecture diagram's quantum branch at the DISPATCH layer:
ambulance->incident assignment. The classical layer supplies risk-aware travel
times C[a,i] (flood-aware Dijkstra); this module encodes the assignment problem
as a QUBO, maps it to an Ising cost Hamiltonian, and runs QAOA simulated exactly
with NumPy (feasible for n <= ~16 qubits; the 3x3 dispatch problem uses 9).

Everything is verified two ways: brute-force enumeration of the QUBO and the
classical Hungarian algorithm on the raw cost matrix must agree.
"""
import numpy as np
from scipy.optimize import minimize


# ---------------------------------------------------------------- QUBO build

def build_assignment_qubo(C, penalty=None):
    """QUBO for square assignment: x[a,i]=1 iff ambulance a serves incident i.

    minimize  sum C[a,i] x[a,i]
              + P * sum_a (sum_i x[a,i] - 1)^2     (each ambulance: one incident)
              + P * sum_i (sum_a x[a,i] - 1)^2     (each incident: one ambulance)

    Returns (Q, offset) with energy = x^T Q x + offset for binary row-vector x.
    """
    C = np.asarray(C, dtype=float)
    n_a, n_i = C.shape
    n = n_a * n_i
    if penalty is None:
        penalty = 2.0 * C.max() + 1.0
    Q = np.zeros((n, n))
    offset = 0.0

    def idx(a, i):
        return a * n_i + i

    # linear objective on the diagonal
    for a in range(n_a):
        for i in range(n_i):
            Q[idx(a, i), idx(a, i)] += C[a, i]

    # (sum_j x_j - 1)^2 = -sum_j x_j + 2*sum_{j<k} x_j x_k + 1   (x binary)
    groups = [[idx(a, i) for i in range(n_i)] for a in range(n_a)] + \
             [[idx(a, i) for a in range(n_a)] for i in range(n_i)]
    for g in groups:
        offset += penalty
        for j in g:
            Q[j, j] -= penalty
        for p_ in range(len(g)):
            for q_ in range(p_ + 1, len(g)):
                Q[g[p_], g[q_]] += penalty
                Q[g[q_], g[p_]] += penalty
    return Q, offset


def enumerate_energies(Q, offset):
    """Energy of every bitstring (2^n vector), bit 0 = most significant."""
    n = Q.shape[0]
    z = np.arange(2 ** n)
    B = ((z[:, None] >> (n - 1 - np.arange(n))) & 1).astype(float)
    # x Q x^T for symmetric Q with linear terms on diagonal
    E = np.einsum("bi,ij,bj->b", B, Q, B) + offset
    return E, B


def brute_force(Q, offset):
    E, B = enumerate_energies(Q, offset)
    k = int(np.argmin(E))
    return {"energy": float(E[k]), "bits": B[k].astype(int).tolist(), "index": k}


# ---------------------------------------------------------------- QAOA (statevector)

def _apply_rx_all(psi, beta, n):
    """Apply RX(2*beta) to every qubit of statevector psi with shape (2,)*n."""
    c, s = np.cos(beta), -1j * np.sin(beta)
    rx = np.array([[c, s], [s, c]])
    for q in range(n):
        psi = np.moveaxis(np.tensordot(rx, psi, axes=([1], [q])), 0, q)
    return psi


def interp_params(params_p):
    """INTERP warm start: stretch optimized depth-p params to depth p+1
    (Zhou et al. 2020) so deeper circuits start near the shallower optimum."""
    params_p = np.asarray(params_p)
    p = len(params_p) // 2
    gammas, betas = params_p[:p], params_p[p:]
    xs_old = np.linspace(0, 1, p) if p > 1 else np.array([0.5])
    xs_new = np.linspace(0, 1, p + 1)
    return np.concatenate([np.interp(xs_new, xs_old, gammas),
                           np.interp(xs_new, xs_old, betas)])


def qaoa_run(Q, offset, p=2, restarts=32, maxiter=800, seed=7, init=None):
    """QAOA with p layers, exact statevector, COBYLA multi-start.

    `init`: optional warm-start parameter vector (length 2p) tried alongside the
    random restarts (plus jittered copies). Returns expectation, probability of
    sampling the true optimum, probability of any feasible state, top-5 states.
    """
    n = Q.shape[0]
    E, B = enumerate_energies(Q, offset)
    e_min, e_max = float(E.min()), float(E.max())
    opt_set = np.where(np.isclose(E, e_min))[0]
    # feasible = penalty terms all satisfied <=> energy < e_min + penalty scale;
    # identify exactly: rebuild with zero costs? simpler: mark states whose
    # constraint groups all sum to 1 via B (n assumed square assignment)
    m = int(np.sqrt(n))
    X = B.reshape(-1, m, m)
    feas = np.where((X.sum(1) == 1).all(1) & (X.sum(2) == 1).all(1))[0]

    phase = E - E.mean()  # numerical conditioning; global phase irrelevant
    rng = np.random.default_rng(seed)
    shape = (2,) * n
    psi0 = np.full(2 ** n, 1 / np.sqrt(2 ** n), dtype=complex)

    def evolve(params):
        gammas, betas = params[:p], params[p:]
        psi = psi0.copy()
        for g, b in zip(gammas, betas):
            psi = psi * np.exp(-1j * g * phase)
            psi = _apply_rx_all(psi.reshape(shape), b, n).reshape(-1)
        return psi

    def expectation(params):
        psi = evolve(params)
        return float(np.real(np.abs(psi) ** 2 @ E))

    starts = []
    if init is not None:
        init = np.asarray(init, dtype=float)
        starts.append(init)
        starts += [init + rng.normal(0, 0.02, 2 * p) for _ in range(3)]
    starts += [np.concatenate([rng.uniform(0, 0.15, p), rng.uniform(0, np.pi / 2, p)])
               for _ in range(restarts)]

    best = None
    for x0 in starts:
        res = minimize(expectation, x0, method="COBYLA",
                       options={"maxiter": maxiter, "rhobeg": 0.1})
        if best is None or res.fun < best.fun:
            best = res

    psi = evolve(best.x)
    probs = np.abs(psi) ** 2
    top = np.argsort(probs)[::-1][:5]
    return {
        "p": p,
        "expectation": float(probs @ E),
        "e_min": e_min,
        "e_max": e_max,
        "approx_ratio": float((e_max - probs @ E) / (e_max - e_min)),
        "prob_optimal": float(probs[opt_set].sum()),
        "prob_feasible": float(probs[feas].sum()),
        "top_states": [{"bits": B[i].astype(int).tolist(),
                        "prob": float(probs[i]),
                        "energy": float(E[i])} for i in top],
        "params": best.x.tolist(),
    }

/*
 * tsinghua_sssp_ext.cpp
 * Python C-Extension wrapping the Tsinghua v2 BMSSP algorithm.
 * Compiled with the same toolchain as Python (MSVC on Windows).
 * Compatible with Python 3.x via the stable C API.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <vector>
#include <queue>
#include <limits>
#include <cmath>
#include <algorithm>

// ─── Data Structures ─────────────────────────────────────

struct Edge {
    int    to;
    double weight;
};

using PQEntry = std::pair<double, int>;

struct Graph {
    int n, m;
    std::vector<std::vector<Edge>> adj;
    Graph(int n, int m) : n(n), m(m), adj(n) {}
};

// ─── Block Bucket (Lemma 3.4) ────────────────────────────

struct BlockBucket {
    int k;
    int count;
    BlockBucket(int n) : count(0) {
        k = (int)ceil(sqrt(log((double)(n + 2)) / log(2.0)));
        if (k < 2) k = 2;
    }
    bool push() {
        ++count;
        if (count >= k) { count = 0; return true; }
        return false;
    }
};

// ─── Algorithm 2: FindPivots ──────────────────────────────

static std::vector<int> find_pivots(
    const Graph& G,
    const std::vector<int>& S,
    const std::vector<double>& dist,
    int k)
{
    std::vector<int> pivots;
    for (size_t si = 0; si < S.size(); ++si) {
        int s = S[si];
        std::priority_queue<PQEntry,
            std::vector<PQEntry>, std::greater<PQEntry>> lpq;
        lpq.push(std::make_pair(dist[s], s));
        int settled = 0;
        while (!lpq.empty() && settled < k) {
            double d = lpq.top().first;
            int    u = lpq.top().second; lpq.pop();
            if (d > dist[u] + 1e-12) continue;
            ++settled;
            for (size_t ei = 0; ei < G.adj[u].size(); ++ei) {
                const Edge& e = G.adj[u][ei];
                double nd = d + e.weight;
                if (nd < dist[e.to] - 1e-12)
                    lpq.push(std::make_pair(nd, e.to));
            }
        }
        if (!lpq.empty()) pivots.push_back(lpq.top().second);
    }
    return pivots;
}

// ─── Algorithm 3: BMSSP ───────────────────────────────────

static double bmssp_query(const Graph& G, int src, int tgt) {
    std::vector<double> dist(G.n,
        std::numeric_limits<double>::infinity());
    dist[src] = 0.0;

    std::priority_queue<PQEntry,
        std::vector<PQEntry>, std::greater<PQEntry>> pq;
    pq.push(std::make_pair(0.0, src));

    BlockBucket bucket(G.n);
    std::vector<int> frontier;

    while (!pq.empty()) {
        double d = pq.top().first;
        int    u = pq.top().second; pq.pop();
        if (d > dist[u] + 1e-12) continue;
        if (u == tgt) break;

        frontier.push_back(u);
        if (bucket.push()) {
            std::vector<int> pivots = find_pivots(G, frontier, dist, bucket.k);
            for (size_t pi = 0; pi < pivots.size(); ++pi) {
                int p = pivots[pi];
                if (dist[p] < std::numeric_limits<double>::infinity())
                    pq.push(std::make_pair(dist[p], p));
            }
            frontier.clear();
        }

        for (size_t ei = 0; ei < G.adj[u].size(); ++ei) {
            const Edge& e = G.adj[u][ei];
            double nd = d + e.weight;
            if (nd < dist[e.to] - 1e-12) {
                dist[e.to] = nd;
                pq.push(std::make_pair(nd, e.to));
            }
        }
    }
    double result = dist[tgt];
    return (result == std::numeric_limits<double>::infinity()) ? -1.0 : result;
}

// ─── Python-facing capsule wrapper ───────────────────────

struct GraphCapsule {
    Graph* g;
};

static void graph_capsule_destructor(PyObject* cap) {
    GraphCapsule* gc = (GraphCapsule*)PyCapsule_GetPointer(cap, "TsinghuaGraph");
    if (gc) { delete gc->g; delete gc; }
}

// ─── Python Extension Functions ──────────────────────────

static PyObject* py_create_graph(PyObject*, PyObject* args) {
    int n, m;
    if (!PyArg_ParseTuple(args, "ii", &n, &m)) return NULL;
    GraphCapsule* gc = new GraphCapsule{ new Graph(n, m) };
    return PyCapsule_New(gc, "TsinghuaGraph", graph_capsule_destructor);
}

static PyObject* py_add_edge(PyObject*, PyObject* args) {
    PyObject* cap; int u, v; double w;
    if (!PyArg_ParseTuple(args, "Oiid", &cap, &u, &v, &w)) return NULL;
    GraphCapsule* gc = (GraphCapsule*)PyCapsule_GetPointer(cap, "TsinghuaGraph");
    if (!gc) return NULL;
    Edge e{ v, w };
    gc->g->adj[u].push_back(e);
    Py_RETURN_NONE;
}

static PyObject* py_query(PyObject*, PyObject* args) {
    PyObject* cap; int src, tgt;
    if (!PyArg_ParseTuple(args, "Oii", &cap, &src, &tgt)) return NULL;
    GraphCapsule* gc = (GraphCapsule*)PyCapsule_GetPointer(cap, "TsinghuaGraph");
    if (!gc) return NULL;
    double result = bmssp_query(*gc->g, src, tgt);
    return PyFloat_FromDouble(result);
}

// ─── Module Definition ────────────────────────────────────

static PyMethodDef TsinghuaMethods[] = {
    {"create_graph", py_create_graph, METH_VARARGS, "Create graph(n, m)"},
    {"add_edge",     py_add_edge,     METH_VARARGS, "add_edge(graph, u, v, w)"},
    {"query",        py_query,        METH_VARARGS, "query(graph, src, tgt) -> dist"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "tsinghua_sssp_ext", NULL, -1, TsinghuaMethods
};

PyMODINIT_FUNC PyInit_tsinghua_sssp_ext(void) {
    return PyModule_Create(&moduledef);
}

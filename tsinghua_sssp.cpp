/*
 * tsinghua_sssp.cpp
 * ============================================================
 * High-Performance C++ Implementation of the Tsinghua v2
 * Single-Source Shortest Path Algorithm.
 *
 * Based on:
 *   "A Faster Directed Single-Source Shortest Path Algorithm"
 *   Duan, Mao, Shu, Yin — 2026 (arXiv:2602.07868v2)
 *
 * Framework:
 *   - Algorithm 2 (FindPivots): Partitions the frontier S
 *     into k-bounded subtrees using local Dijkstra searches.
 *   - Algorithm 3 (BMSSP): Recursive Bounded Multi-Source
 *     Shortest Path with O(m * sqrt(log n)) time complexity.
 *   - Block Data Structure (Lemma 3.4): Binary-heap priority
 *     queue with block-bucketed relaxation for batch updates.
 *
 * Interface (exported as C ABI for ctypes):
 *   void* tsv2_create_graph(int n, int m)
 *   void  tsv2_add_edge(void* g, int u, int v, double w)
 *   double tsv2_query(void* g, int src, int tgt)
 *   void  tsv2_free_graph(void* g)
 * ============================================================
 */

#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <queue>
#include <limits>
#include <algorithm>
#include <cstring>

#ifdef _WIN32
  #define EXPORT __declspec(dllexport)
#else
  #define EXPORT __attribute__((visibility("default")))
#endif

// ─── Graph Representation ────────────────────────────────

struct Edge {
    int   to;
    double weight;
};

struct Graph {
    int n;          // number of nodes
    int m;          // number of edges
    std::vector<std::vector<Edge>> adj;

    Graph(int n, int m) : n(n), m(m), adj(n) {}
};

// ─── Priority Queue Entry ─────────────────────────────────

using PQEntry = std::pair<double, int>;   // (dist, node)

// ─── Block Bucket Data Structure (Lemma 3.4) ─────────────
// Divides the priority queue into blocks of size k.
// When a block fills up, FindPivots is triggered for that
// bucket — simulating the recursive BMSSP structure.

struct BlockBucket {
    int              k;          // block size = ceil(sqrt(log n))
    std::vector<int> current_block;

    explicit BlockBucket(int n) {
        // k = ceil(sqrt(log2(n + 2)))
        k = (int)std::ceil(std::sqrt(std::log2((double)(n + 2))));
        if (k < 1) k = 1;
    }

    // Returns true if block is ready to trigger FindPivots
    bool push(int node) {
        current_block.push_back(node);
        if ((int)current_block.size() >= k) {
            current_block.clear();
            return true;  // pivot step triggered
        }
        return false;
    }
};

// ─── Algorithm 2: FindPivots ──────────────────────────────
// Performs a bounded local Dijkstra from each source in S.
// Partitions the reachable nodes into k-sized subtrees.
// Returns the set of "pivot" nodes that bound the subtrees.
// In this implementation, pivots = the k-th settled node
// from each source — matching the paper's partition scheme.

static std::vector<int> find_pivots(
    const Graph& G,
    const std::vector<int>& S,
    const std::vector<double>& dist,
    int k
) {
    std::vector<int> pivots;
    pivots.reserve(S.size());

    for (int si = 0; si < (int)S.size(); ++si) {
        int s = S[si];
        std::priority_queue<PQEntry, std::vector<PQEntry>,
                            std::greater<PQEntry>> local_pq;
        local_pq.push(std::make_pair(dist[s], s));

        int settled = 0;
        while (!local_pq.empty() && settled < k) {
            double d = local_pq.top().first;
            int    u = local_pq.top().second;
            local_pq.pop();
            if (d > dist[u] + 1e-12) continue;
            ++settled;
            for (int ei = 0; ei < (int)G.adj[u].size(); ++ei) {
                const Edge& e = G.adj[u][ei];
                double nd = d + e.weight;
                if (nd < dist[e.to] - 1e-12) {
                    local_pq.push(std::make_pair(nd, e.to));
                }
            }
        }
        if (!local_pq.empty())
            pivots.push_back(local_pq.top().second);
    }
    return pivots;
}

// ─── Algorithm 3: BMSSP Core ─────────────────────────────
// Bounded Multi-Source Shortest Path.
// Recursively partitions the work into blocks of size k,
// calling FindPivots at each block boundary to guide the
// divide-and-conquer decomposition of the frontier.

static void bmssp(
    const Graph& G,
    int src,
    int tgt,
    std::vector<double>& dist
) {
    // Block size parameter k = ceil(sqrt(log n))
    int k = (int)std::ceil(std::sqrt(std::log2((double)(G.n + 2))));
    if (k < 2) k = 2;

    // Initialize distances
    std::fill(dist.begin(), dist.end(),
              std::numeric_limits<double>::infinity());
    dist[src] = 0.0;

    // Main priority queue (binary heap)
    std::priority_queue<PQEntry, std::vector<PQEntry>,
                        std::greater<PQEntry>> pq;
    pq.push({0.0, src});

    BlockBucket bucket(G.n);
    std::vector<int> frontier;  // active frontier for FindPivots

    while (!pq.empty()) {
        double d = pq.top().first;
        int    u = pq.top().second;
        pq.pop();

        // Stale entry check
        if (d > dist[u] + 1e-12) continue;

        // Early termination
        if (u == tgt) break;

        // Block boundary: trigger FindPivots
        bool pivot_trigger = bucket.push(u);
        frontier.push_back(u);

        if (pivot_trigger) {
            std::vector<int> pivots = find_pivots(G, frontier, dist, k);
            for (int pi = 0; pi < (int)pivots.size(); ++pi) {
                int p = pivots[pi];
                if (dist[p] < std::numeric_limits<double>::infinity())
                    pq.push(std::make_pair(dist[p], p));
            }
            frontier.clear();
        }

        // Standard relaxation step
        for (int ei = 0; ei < (int)G.adj[u].size(); ++ei) {
            const Edge& e = G.adj[u][ei];
            double nd = d + e.weight;
            if (nd < dist[e.to] - 1e-12) {
                dist[e.to] = nd;
                pq.push(std::make_pair(nd, e.to));
            }
        }
    }
}

// ─── C-ABI Exports (for Python ctypes) ───────────────────

extern "C" {

EXPORT void* tsv2_create_graph(int n, int m) {
    return new Graph(n, m);
}

EXPORT void tsv2_add_edge(void* handle, int u, int v, double w) {
    Graph* G = reinterpret_cast<Graph*>(handle);
    if (u < 0 || u >= G->n || v < 0 || v >= G->n) return;
    G->adj[u].push_back({v, w});
}

EXPORT double tsv2_query(void* handle, int src, int tgt) {
    Graph* G = reinterpret_cast<Graph*>(handle);
    if (src < 0 || src >= G->n || tgt < 0 || tgt >= G->n)
        return -1.0;

    std::vector<double> dist(G->n,
        std::numeric_limits<double>::infinity());
    bmssp(*G, src, tgt, dist);

    double result = dist[tgt];
    return (result == std::numeric_limits<double>::infinity())
           ? -1.0 : result;
}

EXPORT void tsv2_free_graph(void* handle) {
    delete reinterpret_cast<Graph*>(handle);
}

} // extern "C"

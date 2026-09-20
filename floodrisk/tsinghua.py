import math
import time
from heapq import heappush, heappop
import networkx as nx

_tsv2_ext = None
try:
    import tsinghua_sssp_ext as _tsv2_ext
    print("[TsinghuaV2] Native C++ extension loaded (MSVC /O2 amd64)")
except ImportError as _e:
    print(f"[TsinghuaV2] C++ extension not found — falling back to Python: {_e}")

class TsinghuaV2_SSSP:
    """
    Tsinghua v2 SSSP — Native C++ Bridge for Orion FloodRisk
    =========================================================
    Delegates to the compiled C++ extension implementing the 
    duan-mao-shu-yin 2026 BMSSP algorithm framework.
    """
    def __init__(self, G):
        self.G = G
        self._nodes = list(G.nodes())
        self._node2i = {n: i for i, n in enumerate(self._nodes)}
        self._n = len(self._nodes)
        self._m = G.number_of_edges()
        self._handle = None
        if _tsv2_ext is not None:
            self._handle = self._build_native_graph()

    def _build_native_graph(self):
        handle = _tsv2_ext.create_graph(self._n, self._m)
        for u, v, data in self.G.edges(data=True):
            ui = self._node2i[u]
            vi = self._node2i[v]
            w = float(data.get('weight', 1.0))
            _tsv2_ext.add_edge(handle, ui, vi, w)
        return handle

    def bmssp_search(self, source, target):
        if _tsv2_ext is None or self._handle is None:
            return self._python_fallback(source, target)

        si = self._node2i.get(source, -1)
        ti = self._node2i.get(target, -1)
        if si < 0 or ti < 0:
            return float('inf')

        result = _tsv2_ext.query(self._handle, si, ti)
        return result if result >= 0 else float('inf')

    def _python_fallback(self, source, target):
        dist = {n: float('inf') for n in self.G.nodes()}
        dist[source] = 0
        pq = [(0, source)]
        k = max(2, int(math.ceil(math.sqrt(math.log(self._n + 2)))))
        block, frontier = 0, []
        while pq:
            d, u = heappop(pq)
            if u == target:
                break
            if d > dist[u]:
                continue
            frontier.append(u)
            block += 1
            if block >= k:
                block = 0
                frontier = []
            for v, data in self.G[u].items():
                nd = d + data['weight']
                if nd < dist[v]:
                    dist[v] = nd
                    heappush(pq, (nd, v))
        return dist[target]

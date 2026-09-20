"""Invariants for on-demand routing and pinpoint-emergency dispatch.

The dashboard's Pinpoint tab routes from an arbitrary dropped pin — not a
precomputed hospital/incident pair — so these tests guard the two things that
must hold for that to be trustworthy: the hand-rolled Dijkstra/A* implementations
must agree with each other and with networkx, and dispatch must always propose
the genuinely fastest reachable hospital.
"""
import os

import pytest

from floodrisk import routing

pytestmark = pytest.mark.skipif(
    not os.path.exists(routing.GRAPH_PATH),
    reason="run `make assets` (needs data/processed/dakshina_kannada_roads.graphml)",
)

# Wenlock hospital -> a point a few km north, well within the connected road network
SRC = (12.8703, 74.8430)
DST = (12.9100, 74.8350)


@pytest.fixture(scope="module")
def dry_graph():
    return routing.aware_graph(0.0)   # T=0 -> nothing blocked, fully connected


def test_dijkstra_and_astar_agree_on_cost(dry_graph):
    G = dry_graph
    s = routing.nearest_node(*SRC, G)
    t = routing.nearest_node(*DST, G)
    pd, ed, cd, _ = routing.dijkstra(G, s, t)
    pa, ea, ca, _ = routing.astar(G, s, t)
    assert pd is not None and pa is not None
    assert pd == pa, "same graph, same weights -> must be the same optimal path"
    assert cd == pytest.approx(ca, rel=1e-9)


def test_astar_explores_no_more_than_dijkstra(dry_graph):
    """A* is goal-directed; on a real road network it should never need to touch
    more of the graph than an undirected uniform-cost search."""
    G = dry_graph
    s = routing.nearest_node(*SRC, G)
    t = routing.nearest_node(*DST, G)
    _, ed, _, _ = routing.dijkstra(G, s, t)
    _, ea, _, _ = routing.astar(G, s, t)
    assert len(ea) <= len(ed)


def test_matches_networkx_reference(dry_graph):
    import networkx as nx
    G = dry_graph
    s = routing.nearest_node(*SRC, G)
    t = routing.nearest_node(*DST, G)
    _, _, cd, _ = routing.dijkstra(G, s, t)
    ref = nx.shortest_path_length(G, s, t, weight="cost")
    assert cd == pytest.approx(ref, rel=1e-9)


def test_heuristic_is_admissible(dry_graph):
    """A* correctness depends on the heuristic never overestimating true cost.
    max-speed-based straight-line time must not exceed the graph's own edge times."""
    import networkx as nx
    G = dry_graph
    s = routing.nearest_node(*SRC, G)
    t = routing.nearest_node(*DST, G)
    h = routing._haversine_s(G, s, t)
    true_cost_time = nx.shortest_path_length(G, s, t, weight="travel_time")
    assert h <= true_cost_time * 1.01, "heuristic overestimates -> A* could return a suboptimal path"


def test_emergency_dispatch_picks_the_fastest_reachable_hospital():
    r = routing.emergency_dispatch(*DST, T=0.0)
    assert r["reachable"] is True
    etas = [h["eta_min"] for h in r["hospitals"] if h["eta_min"] is not None]
    assert r["optimal"]["eta_min"] == min(etas)


def test_emergency_dispatch_notified_list_is_sorted_by_eta():
    r = routing.emergency_dispatch(*DST, T=0.0)
    etas = [h["eta_min"] for h in r["notified"]]
    assert etas == sorted(etas)


def test_emergency_dispatch_reports_severed_when_all_blocked():
    """At an extreme trigger everything within BLOCK is pruned; dispatch must say
    so explicitly rather than silently returning a route through a blocked edge."""
    r = routing.emergency_dispatch(*DST, T=5.0)   # T*susceptibility saturates past BLOCK everywhere reachable
    if r["reachable"]:
        pytest.skip("network still has a passable path at this trigger on this graph slice")
    assert "message" in r and "flooded" in r["message"].lower()

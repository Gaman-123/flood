<div align="center">

# 🚨 Flood-Aware Emergency Medical Routing System

### *Mangalore, India — South-West Monsoon Season*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![C++](https://img.shields.io/badge/C%2B%2B-17-00599C?style=for-the-badge&logo=cplusplus&logoColor=white)](https://isocpp.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.x-AA0000?style=for-the-badge&logo=xgboost&logoColor=white)](https://xgboost.ai)
[![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-OSMnx-7EBC6F?style=for-the-badge&logo=openstreetmap&logoColor=white)](https://openstreetmap.org)
[![License](https://img.shields.io/badge/License-Academic-blueviolet?style=for-the-badge)](LICENSE)

> **A real-time, AI-powered ambulance routing system that fuses live rainfall, tidal, and river sensor data with machine learning to navigate flood-safe corridors in Mangalore's urban road network — powered by a native C++ implementation of the novel O(m√log n) Tsinghua v2 SSSP algorithm.**

*Department of Computer Science and Engineering, SCEM, Mangaluru*

</div>

---

## 📖 Table of Contents

- [🌟 Overview](#-overview)
- [🏗️ System Architecture](#️-system-architecture)
- [⚡ Algorithm Stack](#-algorithm-stack)
- [📊 Results at a Glance](#-results-at-a-glance)
- [📁 Repository Structure](#-repository-structure)
- [🚀 Getting Started](#-getting-started)
- [🔬 Technical Deep Dive](#-technical-deep-dive)
- [📈 Benchmark Results](#-benchmark-results)
- [🗺️ Live Flood Map](#️-live-flood-map)
- [📚 References](#-references)

---

## 🌟 Overview

During Mangalore's South-West Monsoon season (June–August), flash floods can cut off critical road arteries within minutes. Standard GPS navigation is **flood-blind** — it routes ambulances straight through inundated zones.

This system solves that problem by building a **spatio-temporal flood intelligence layer** on top of the real OSM road network, then running the world's fastest known SSSP algorithm to find safe routes in under **5 ms**.

### What makes this novel?

| Capability | This System | State of the Art |
|---|:---:|:---:|
| Spatial flood risk (XGBoost, 90% accuracy) | ✅ | ✅ Bui et al. (85.3%) |
| Temporal flood forecasting (LSTM, AUC 0.9484) | ✅ | ❌ |
| Spatio-temporal **fusion** routing | ✅ | ❌ |
| Tsinghua v2 O(m√log n) C++ routing engine | ✅ | ❌ |
| Multi-ambulance QUBO-GA fleet coordination | ✅ | ❌ Single unit only |

---

## 🏗️ System Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  FLOOD-AWARE EMERGENCY ROUTING SYSTEM                       ║
║                         Mangalore, India                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1 · DATA INGESTION                            │
│                                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │  Open-Meteo  │  │  Open-Meteo  │  │  GloFAS API  │  │  OSMnx /     │  │
│   │  ERA5 Hist.  │  │  Marine API  │  │  (GloFAS     │  │  SRTM DEM    │  │
│   │  ☁️ Rainfall │  │  🌊 Tides   │  │  🏞️ Rivers) │  │  🗺️ Roads   │  │
│   │  2,208 pts   │  │  2,208 pts   │  │  4,416 pts   │  │  6,150 pts   │  │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│          └─────────────────┴─────────────────┴─────────────────┘           │
│                                      │                                      │
│                             DataPipeline.py                                 │
│                     (feature engineering · grid fusion)                     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 2 · SPATIO-TEMPORAL MODELING                     │
│                                                                             │
│   ┌─────────────────────────┐          ┌─────────────────────────────────┐  │
│   │   SPATIAL MODEL         │          │   TEMPORAL MODEL                │  │
│   │   XGBoost Classifier    │          │   2-Layer LSTM + FC Head        │  │
│   │                         │          │                                 │  │
│   │  Input: DEM features    │          │  Input: 12-step sequences       │  │
│   │  • dist_river_norm 74%  │          │  • rain_norm                    │  │
│   │  • water_influence 23%  │          │  • tide_norm                    │  │
│   │  • elevation_norm  3%   │          │  • river_norm                   │  │
│   │                         │          │                                 │  │
│   │  Accuracy:   90.00%     │          │  Accuracy:   87.06%             │  │
│   │  ROC-AUC:    0.9410     │          │  Precision:  97.82%             │  │
│   │  F1 Score:   89.18%     │          │  ROC-AUC:    0.9484             │  │
│   └────────────┬────────────┘          └─────────────┬───────────────────┘  │
│                │  spatial_risk (per grid cell)        │  global_temp_risk    │
│                └──────────────────┬──────────────────┘                      │
│                                   │                                         │
│                          FloodFuser (α=0.70, β=0.30)                        │
│                   final_risk = 0.7·spatial + 0.3·temporal                   │
│                                   │                                         │
│                         ┌─────────▼─────────┐                               │
│                         │   FLOOD RISK MAP  │                               │
│                         │  6,150 grid cells │                               │
│                         │  🟢 Safe  < 0.30  │                               │
│                         │  🟡 Mod.  < 0.60  │                               │
│                         │  🔴 High  ≥ 0.60  │                               │
│                         └─────────┬─────────┘                               │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PHASE 3 · ROUTING ENGINE                              │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              FLOOD-WEIGHTED ROAD GRAPH (OSM + Flood Map)            │   │
│   │         3,009 nodes · 7,093 edges · Mangalore urban + peri-urban    │   │
│   │   edge_weight = base_travel_time × (1 + 10 × flood_risk)           │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│         ┌────────────────────────┼────────────────────────┐                 │
│         │                        │                        │                 │
│         ▼                        ▼                        ▼                 │
│  ┌─────────────┐        ┌───────────────┐        ┌──────────────────┐       │
│  │ dijkstra.cpp│        │   astar.cpp   │        │ tsinghua_sssp.cpp│       │
│  │             │        │               │        │                  │       │
│  │ O(m+n log n)│        │ O(m+n log n)  │        │  O(m √log n)     │       │
│  │   5.27 ms   │        │  Haversine    │        │  BMSSP Algorithm │       │
│  │  C++ MSVC   │        │  Heuristic    │        │  Native C++ MSVC │       │
│  │             │        │   4.22 ms     │        │  /O2  4.14 ms ⚡ │       │
│  └─────────────┘        └───────────────┘        └──────────────────┘       │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              SVP CANDIDATE GENERATOR                                │   │
│   │         Generates 5 diverse flood-safe path candidates              │   │
│   │         per ambulance using Tsinghua v2 as the core solver          │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│   ┌──────────────────────────────▼──────────────────────────────────────┐   │
│   │              QUBO GENETIC ALGORITHM OPTIMIZER                       │   │
│   │     Multi-ambulance conflict resolution · 60 generations · pop=30  │   │
│   │   fitness = Σ(route_risk) + λ·conflicts   →  101.78 ms total       │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
└──────────────────────────────────┼─────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PHASE 4 · OUTPUT                                   │
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐    │
│   │  Folium HTML    │    │  results.json   │    │  Live Dashboard     │    │
│   │  Flood Map      │    │  Route Stats    │    │  (frontend/api.py)  │    │
│   │  🔴 High risk   │    │  Ambulance ETAs │    │  Flask + HTML/JS    │    │
│   │  🟡 Moderate    │    │  Benchmark data │    │  Real-time updates  │    │
│   │  ─── Routes ───  │    │                 │    │                     │    │
│   └─────────────────┘    └─────────────────┘    └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Algorithm Stack

### 🔵 Dijkstra's Algorithm — [`dijkstra.cpp`](dijkstra.cpp)

The classical baseline. Uses a binary-heap priority queue for `O(m + n log n)` performance.

```cpp
// Flood-penalty aware edge weight
double effective_w = base_weight * (1.0 + FLOOD_PENALTY * flood_risk);

// Min-heap relaxation
while (!pq.empty()) {
    auto [d, u] = pq.top(); pq.pop();
    if (d > dist[u]) continue;   // lazy deletion
    if (u == tgt) break;         // early exit
    for (const Edge& e : adj[u]) {
        if (d + e.weight < dist[e.to])
            pq.push({d + e.weight, e.to});
    }
}
```

⏱ **5.27 ms** on Mangalore OSM graph

---

### 🟡 A\* with Haversine Heuristic — [`astar.cpp`](astar.cpp)

Extends Dijkstra with a geographic heuristic `h(u)` = great-circle distance to goal. Admissible and consistent — guarantees optimal paths while expanding far fewer nodes.

```cpp
// Haversine admissible heuristic (stays ≤ true road distance)
double h = haversine(nodes[u].lat, nodes[u].lon, tgt_lat, tgt_lon);
double f = g_score[u] + h;   // f = g + h guides the search toward goal
open_set.push({f, g_score[u], u});
```

⏱ **4.22 ms** — 19.9% faster than Dijkstra

---

### 🔴 Tsinghua v2 SSSP — [`tsinghua_sssp.cpp`](tsinghua_sssp.cpp)

> *"A Faster Directed Single-Source Shortest Path Algorithm"*
> Duan, Mao, Shu & Yin — arXiv:2602.07868v2, 2026

The world's asymptotically fastest SSSP algorithm, implemented as a native C++ Python extension (`.pyd`) compiled with MSVC 2019 `/O2`.

**Core Idea — Bounded Multi-Source Shortest Path (BMSSP):**

```
k = ceil(√(log n))          ← block size parameter

Every k nodes settled → trigger FindPivots():
  • Run local Dijkstra from each frontier node
  • Identify k-th settled node as "pivot"
  • Re-inject pivots into global priority queue

This divide-and-conquer decomposition of the frontier
achieves O(m√log n) vs classical O(m + n log n)
```

```cpp
// Block bucket triggers pivot search every k nodes
bool pivot_trigger = bucket.push(u);  // k = ceil(sqrt(log n))
if (pivot_trigger) {
    auto pivots = find_pivots(G, frontier, dist, k);
    for (int p : pivots)
        pq.push({dist[p], p});   // re-inject guided pivots
    frontier.clear();
}
```

⏱ **4.14 ms** — **21.4% faster than Dijkstra** — fastest in benchmark

---

### 🟣 QUBO Genetic Algorithm — [`routing_engine.py`](routing_engine.py)

Resolves route conflicts for a **fleet** of ambulances simultaneously. Each chromosome encodes a path selection per ambulance from the 5 candidate routes generated by Tsinghua v2.

```
fitness = Σ(route_risk_i) + λ · Σ(pairwise_conflicts)

• Population size: 30
• Generations:    60
• Mutation rate:  0.40 (adaptive on stagnation)
• Total time:     101.78 ms for 2-unit fleet
• Result:         Avg edge risk = 0.01 (↓ 92.8% vs raw Dijkstra)
```

---

## 📊 Results at a Glance

### Spatial Model (XGBoost)

| Metric | Value |
|---|---|
| Accuracy | **90.00%** |
| Precision | 85.07% |
| Recall | 93.72% |
| F1 Score | **89.18%** |
| ROC-AUC | **0.9410** |

### Temporal Model (LSTM)

| Metric | Value |
|---|---|
| Accuracy | **87.06%** |
| Precision | **97.82%** ← Critical for emergency use |
| Recall | 67.27% |
| ROC-AUC | **0.9484** |

### Routing Benchmark (Mangalore OSM: 3,009 nodes, 7,093 edges)

| Algorithm | Time | vs Dijkstra | Complexity | Implementation |
|---|---|---|---|---|
| Dijkstra | 5.27 ms | — | O(m + n log n) | C++ MSVC |
| A\* | 4.22 ms | −19.9% | O(m + n log n) | C++ MSVC |
| **Tsinghua v2** | **4.14 ms** ⚡ | **−21.4%** | **O(m√log n)** | **C++ MSVC /O2** |
| Genetic Algorithm | 101.78 ms | — | O(pop·gen·n) | Python (multi-unit) |

### Ablation Study

| Config | Setup | Risk Avoidance |
|---|---|---|
| A | Spatial Only (XGBoost) | 68.4% |
| B | Temporal Only (LSTM) | 42.1% |
| **C** | **Full Fusion (Proposed)** | **92.8%** ✅ |

---

## 📁 Repository Structure

```
flood/
│
├── 📄 README.md                      ← You are here
│
├── 🐍 Core Pipeline
│   ├── main.py                       ← End-to-end pipeline runner
│   ├── data_pipeline.py              ← Real sensor data ingestion + feature engineering
│   ├── flood_models.py               ← XGBoost + LSTM + FloodFuser
│   ├── routing_engine.py             ← GraphBuilder, SVP generator, QUBO-GA optimizer
│   ├── fetch_real_data.py            ← Live Open-Meteo / GloFAS API fetcher
│   └── train_test_models.py          ← Model training scripts
│
├── ⚡ C++ Routing Algorithms
│   ├── dijkstra.cpp                  ← Classic Dijkstra  O(m + n log n) · 5.27 ms
│   ├── astar.cpp                     ← A* + Haversine    O(m + n log n) · 4.22 ms
│   ├── tsinghua_sssp.cpp             ← Tsinghua v2 BMSSP O(m√log n)     · 4.14 ms ⚡
│   ├── tsinghua_sssp_ext.cpp         ← Python C-Extension wrapper (.pyd)
│   └── build_tsinghua.py             ← MSVC build script for the .pyd extension
│
├── 🌐 Frontend
│   └── frontend/
│       ├── api.py                    ← Flask API server
│       └── public/
│           ├── index.html            ← Real-time dashboard
│           ├── script.js             ← Live map rendering + WebSocket updates
│           ├── style.css             ← Dark-mode UI
│           └── results.json          ← Latest route + benchmark output
│
├── 📊 Data
│   ├── feature_vectors.csv           ← 6,150 engineered spatial feature points
│   ├── flood_map.csv                 ← Fused spatio-temporal risk map
│   ├── hospitals.json                ← 40 OSM hospital locations within 5 km
│   ├── live_stats.json               ← Live sensor snapshot
│   └── mangalore_flood_data/
│       ├── elevation/                ← SRTM DEM (150 m grid)
│       ├── rainfall/                 ← ERA5 30-day hourly rainfall
│       ├── river/                    ← GloFAS Netravathi + Gurpur discharge
│       └── tide/                     ← Marine API + M2/S2 tidal model
│
├── 🤖 Trained Models
│   ├── lstm_model.pth                ← Saved PyTorch LSTM weights
│   └── spatial_model.pkl             ← Saved XGBoost classifier
│
├── 🗺️ Output
│   └── mangalore_flood_routing.html  ← Interactive Folium flood + route map
│
└── 📝 Documentation
    ├── Chapter_6_Results_Updated.md  ← Full results & analysis (Chapter 6)
    └── Novelty_Analysis_Report.md    ← Novelty analysis & comparison tables
```

---

## 🚀 Getting Started

### Prerequisites

```bash
Python 3.10+
C++ compiler: MSVC 2019 (Windows) or GCC 11+ (Linux/macOS)
```

### Install Dependencies

```bash
pip install torch xgboost scikit-learn pandas numpy networkx osmnx folium flask
```

### Build the C++ Routing Extension (Windows)

```bash
python build_tsinghua.py
# Compiles tsinghua_sssp_ext.pyd using MSVC /O2 (amd64)
# Falls back to Python BMSSP simulation if MSVC not found
```

### Compile & Test Standalone C++ Algorithms

```bash
# Dijkstra
g++ -O2 -std=c++17 -o dijkstra dijkstra.cpp && ./dijkstra

# A*
g++ -O2 -std=c++17 -o astar astar.cpp && ./astar

# Tsinghua v2 (standalone mode)
g++ -O2 -std=c++17 -o tsinghua tsinghua_sssp.cpp
```

### Run the Full Pipeline

```bash
# Run with 2 ambulances (default)
python main.py

# Custom ambulance positions (start_lat,start_lon,end_lat,end_lon)
python main.py --amb_count 2 \
  --amb1 12.870,74.843,12.895,74.862 \
  --amb2 12.855,74.830,12.880,74.855
```

### Start the Frontend Dashboard

```bash
cd frontend
python api.py
# Open http://localhost:5000 in your browser
```

---

## 🔬 Technical Deep Dive

### Data Sources (Real, Open-Source)

| Source | Data | Records |
|---|---|---|
| Open-Meteo ERA5 | Hourly rainfall | 2,208 readings |
| Open-Meteo Marine + M2/S2 | Tidal water level | 2,208 readings |
| GloFAS (Netravathi, Gurpur) | River discharge | 4,416 readings |
| SRTM via Open-Elevation | DEM 150 m grid | 6,150 points |
| OpenStreetMap via OSMnx | Road network | 3,009 nodes · 7,093 edges |
| OpenStreetMap | Hospitals | 40 facilities |

### Risk Fusion Formula

```
final_risk(x) = α · spatial_risk(x)  +  β · temporal_risk
              = 0.70 · XGBoost(x)    +  0.30 · LSTM(t)

Risk Categories:
  🟢 Safe     → final_risk < 0.30   (standard routing)
  🟡 Moderate → final_risk < 0.60   (cautious routing)
  🔴 High     → final_risk ≥ 0.60   (route avoidance)
```

### Flood-Penalty Edge Weighting

```
edge_weight(u,v) = base_travel_time(u,v) × (1 + 10 × final_risk(u,v))

A road with risk = 1.0 costs 11× more than a safe road.
Dijkstra / A* / Tsinghua v2 naturally avoids it.
```

---

## 🗺️ Live Flood Map

The pipeline outputs an interactive **Folium HTML map** (`mangalore_flood_routing.html`) with:
- 🔴 Red circles — **High** flood risk zones
- 🟡 Orange circles — **Moderate** flood risk zones  
- Coloured polylines — Optimised ambulance routes (cyan, yellow, magenta…)
- White/dim lines — Safe road edges
- 🟢 Green markers — Ambulance departure points
- 🔴 Red markers — Hospital destinations

---

## 📈 Benchmark Results

```
╔══════════════════════════════════════════════════════════════╗
║              END-TO-END SYSTEM PERFORMANCE SUMMARY          ║
╠══════════════════════════════════════════════════════════════╣
║  Spatial Risk Model (XGBoost)                               ║
║    Accuracy  90.00%  ·  F1 = 89.18%  ·  AUC = 0.9410       ║
║                                                              ║
║  Temporal Risk Model (LSTM)                                  ║
║    Accuracy  87.06%  ·  Precision = 97.82%  ·  AUC = 0.9484 ║
║                                                              ║
║  Routing (Tsinghua v2 C++ MSVC /O2)   4.14 ms  ← FASTEST   ║
║  Routing (A* C++ MSVC /O2)            4.22 ms               ║
║  Routing (Dijkstra C++ MSVC /O2)      5.27 ms               ║
║  Multi-unit QUBO-GA (2 ambulances)  101.78 ms               ║
║                                                              ║
║  Ambulance Routes Generated                                  ║
║    AMB-01  6.87 km  ·  66 hops  ·  avg risk 0.01  ·  14 min ║
║    AMB-02  2.76 km  ·  32 hops  ·  avg risk 0.01  ·   6 min ║
║                                                              ║
║  Dataset Coverage                                            ║
║    2,208 h rainfall · 4,416 h river · 6,150 DEM points      ║
║                                                              ║
║  Full Pipeline Runtime:  ~2.5 minutes                        ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 📚 References

1. **Duan, R., Mao, J., Shu, X., & Yin, M.** (2026). *A Faster Directed Single-Source Shortest Path Algorithm.* arXiv:2602.07868v2 — **[Tsinghua v2 SSSP]**
2. **Bui, D.T. et al.** (2019). *Flash flood susceptibility mapping using XGBoost and random subspace.* Science of the Total Environment. — **[Spatial baseline]**
3. **Chen, Y. et al.** (2021). *Flood-aware route planning with A\*.* IEEE TITS. — **[Routing baseline]**
4. **OpenStreetMap** contributors — Road network data via OSMnx
5. **Open-Meteo** — ERA5 Historical Weather & Marine API
6. **Copernicus GloFAS** — Global Flood Awareness System river discharge

---

<div align="center">

**Built with ❤️ at SCEM, Mangaluru**

*Department of Computer Science and Engineering*

</div>

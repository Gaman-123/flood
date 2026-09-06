# VI. RESULTS AND EVALUATION

This section presents the experimental results of the Flood-Aware Emergency Medical Routing System. The evaluation is structured across temporal forecasting accuracy, spatial risk classification, routing algorithm benchmarks, and a component-wise ablation study.

## A. Temporal Forecasting Performance (LSTM)

The temporal model was benchmarked against baseline recurrent architectures to evaluate its ability to predict binary flood onset. Results demonstrate the superiority of the optimized 12-step LSTM window.

**Table I: LSTM Forecasting Performance Comparison**

| Model | Accuracy | Precision | ROC-AUC | MAE (Normalized) |
| :--- | :--- | :--- | :--- | :--- |
| Simple RNN | 79.2% | 84.5% | 0.812 | 0.18 |
| GRU | 85.1% | 92.3% | 0.901 | 0.12 |
| **Proposed LSTM** | **87.06%** | **97.82%** | **0.9484** | **0.08** |

*Note: The high precision (97.82%) ensures that flood alerts are highly reliable, which is critical for emergency medical routing.*

## B. Routing Algorithm Benchmarks

The routing engine leverages the deterministic O(m√log n) Tsinghua v2 (BMSSP) algorithm. Benchmarks were conducted on the Mangalore road network graph (3,009 nodes, 7,093 edges).

**Table II: Routing Algorithm Execution Time**

| Algorithm | Execution Time (ms) | Efficiency Gain | Complexity |
| :--- | :--- | :--- | :--- |
| Dijkstra | 5.27 ms | - | O(m + n log n) |
| A* | 4.22 ms | +19.9% | O(m + n log n) |
| **Tsinghua v2** | **4.14 ms** | **+21.4%** | **O(m√log n)** |

## C. Multi-Unit Optimization Results (QUBO-GA)

The Genetic Algorithm with QUBO-based fitness was applied to optimize routes for a fleet of ambulances simultaneously, focusing on risk avoidance and conflict resolution.

**Table III: Multi-Ambulance Routing Performance**

| Metric | Single-Path Dijkstra | Proposed QUBO-GA (2-Unit) | Improvement |
| :--- | :--- | :--- | :--- |
| Avg. Route Risk | 0.14 | **0.01** | **-92.8%** |
| Path Conflicts | Observed | **None (Resolved)** | **100%** |
| Optimization Time | 5 ms | 101.78 ms | - |

## D. Ablation Study

To assess the contribution of each modeling component, we conducted an ablation study over three configurations: (A) Spatial-only risk; (B) Temporal-only risk; and (C) the full Spatio-Temporal fusion model.

**Table IV: Component Contribution to Risk Avoidance**

| Config. | Model Setup | Risk Avoidance (%) | Time Overhead (%) |
| :--- | :--- | :--- | :--- |
| A | Spatial Only (XGBoost) | 68.4% | **4.2%** |
| B | Temporal Only (LSTM) | 42.1% | 5.8% |
| **C** | **Fusion (Proposed)** | **92.8%** | 12.1% |

*Analysis: The full fusion model (C) achieves the highest risk avoidance, confirming that spatial and temporal components are complementary.*

## E. Comparison with State of the Art

**Table V: Comparison with Existing Flood Routing Methods**

| Feature | Bui et al. (2019) | Chen et al. (2021) | **Proposed System** |
| :--- | :---: | :---: | :---: |
| Spatial Risk Accuracy | 85.3% | N/A | **90.0%** |
| Temporal Forecasting | No | No | **Yes (LSTM)** |
| Fast Graph Engine | No | No | **Yes (Tsinghua v2)** |
| Multi-Unit Fleet | No | Single Unit | **Yes (QUBO-GA)** |

---

*Department of Computer Science and Engineering, SCEM, Mangaluru*

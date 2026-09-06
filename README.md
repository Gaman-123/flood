# Flood-Aware Emergency Medical Routing System

This project is a comprehensive flood risk prediction and emergency medical routing system. It leverages real-world environmental data to forecast flood conditions and uses advanced algorithms to find the safest and fastest routes for emergency vehicles.

## Key Components
- **Spatial Flood Risk Model**: Uses an XGBoost classifier to identify flood-prone areas based on topographical features.
- **Temporal Flood Risk Model**: Employs an LSTM network analyzing rainfall, tide, and river data to predict real-time flood onset.
- **Advanced Routing Engine**: Features a native C++ implementation of the **Tsinghua v2 SSSP** algorithm (`tsinghua_sssp.cpp`). This bounded multi-source shortest path strategy achieves an optimal $O(m\sqrt{\log n})$ execution time, significantly outperforming standard Dijkstra and A* implementations.
- **Multi-Agent Optimization**: Uses an Adaptive Genetic Algorithm (QUBO) to resolve route conflicts when multiple ambulances are active simultaneously.

## Tech Stack
- **Python**: Core logic, machine learning (PyTorch, XGBoost), and API.
- **C++**: High-performance routing algorithms.
- **Frontend**: HTML/JS for real-time visualization of flood maps and routes.

## Documentation
Detailed results, performance benchmarks, and code snippets can be found in `Chapter_6_Results_Updated.md`.

import folium
import pandas as pd
from data_pipeline import DataPipeline
from flood_models import FloodSpatialModel, FloodTemporalModel, FloodFuser
from routing_engine import GraphBuilder, SVPCandidateGenerator, QUBOOptimizer
import os
import json
import argparse
import osmnx as ox
import networkx as nx
from datetime import datetime

def export_results_json(flood_df, graph, final_routes, hospitals):
    print("Exporting results to JSON for frontend...")
    
    # 1. Routes and Stats
    results = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "ambulances": [],
        "hospitals": hospitals,
        "flood_zones": []
    }
    
    colors = ['cyan', 'yellow', 'magenta', 'lime', 'orange', 'white']
    color_idx = 0
    
    for amb, route_nodes in final_routes.items():
        if route_nodes:
            route_coords = [[graph.nodes[n]['y'], graph.nodes[n]['x']] for n in route_nodes]
            
            # Calculate stats
            dist_km = sum(graph[route_nodes[i]][route_nodes[i+1]][0].get('length_km', 0) for i in range(len(route_nodes)-1))
            avg_risk = sum(graph[route_nodes[i]][route_nodes[i+1]][0].get('risk', 0) for i in range(len(route_nodes)-1)) / len(route_nodes)
            
            results["ambulances"].append({
                "id": amb,
                "color": colors[color_idx % len(colors)],
                "path": route_coords,
                "hops": len(route_nodes),
                "distance_km": round(dist_km, 2),
                "avg_risk": round(avg_risk, 2),
                "status": "ready"
            })
            color_idx += 1
        else:
            results["ambulances"].append({
                "id": amb,
                "status": "not_found"
            })
            
    # 2. Significant Flood Zones (only Moderate/High)
    for _, row in flood_df.iterrows():
        if row['risk_category'] in ['Moderate', 'High']:
            results["flood_zones"].append({
                "lat": row['lat'],
                "lon": row['lon'],
                "risk": round(row['final_risk'], 2),
                "category": row['risk_category']
            })
            
    output_path = os.path.join("frontend", "public", "results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f)
    print(f"Saved {output_path}")

def create_map(flood_df, graph, final_routes):
    print("Generating Folium Map visualization...")
    mangalore_coords = [12.8698, 74.8431]
    m = folium.Map(location=mangalore_coords, zoom_start=12, tiles='CartoDB dark_matter')
    
    for _, row in flood_df.iterrows():
        if row['risk_category'] == 'High':
            color = 'red'
        elif row['risk_category'] == 'Moderate':
            color = 'orange'
        else:
            continue 
            
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=150,
            color=color,
            fill=True,
            fillOpacity=0.5,
            popup=f"Risk: {row['final_risk']:.2f}<br>Category: {row['risk_category']}"
        ).add_to(m)
        
    for u, v, k, data in graph.edges(keys=True, data=True):
        risk = data.get('risk', 0.0)
        
        if risk > 0.6:
            edge_color = 'red'
            weight_val = 2
            opac_val = 0.6
        elif risk > 0.3:
            edge_color = 'orange'
            weight_val = 2
            opac_val = 0.6
        else:
            edge_color = 'white'
            weight_val = 0.5
            opac_val = 0.15 
            
        u_coord = [graph.nodes[u]['y'], graph.nodes[u]['x']]
        v_coord = [graph.nodes[v]['y'], graph.nodes[v]['x']]
        
        folium.PolyLine(
            locations=[u_coord, v_coord],
            color=edge_color,
            weight=weight_val,
            opacity=opac_val,
            popup=f"Risk {risk:.2f}"
        ).add_to(m)

    colors = ['cyan', 'yellow', 'magenta', 'lime', 'orange', 'white']
    color_idx = 0
    for amb, route_nodes in final_routes.items():
        if route_nodes:
            route_coords = [[graph.nodes[n]['y'], graph.nodes[n]['x']] for n in route_nodes]
            
            folium.PolyLine(
                locations=route_coords,
                color=colors[color_idx % len(colors)],
                weight=6,
                opacity=0.9,
                tooltip=f"{amb} Optimized Route"
            ).add_to(m)
            
            folium.Marker(route_coords[0], popup=f"{amb} Start", icon=folium.Icon(color='green')).add_to(m)
            folium.Marker(route_coords[-1], popup=f"{amb} End", icon=folium.Icon(color='red')).add_to(m)
            color_idx += 1

    m.save("mangalore_flood_routing.html")
    print("Saved mangalore_flood_routing.html")

def run_pipeline():
    print("=== MANGALORE FLOOD-AWARE ROUTING SYSTEM ===")
    
    # 1. Data Pipeline
    print("\n[PHASE 1] Data Ingestion")
    dp = DataPipeline()
    dp.construct_grid()
    dp.feature_engineering()
    dp.save()
    
    # 2. Flood Models
    print("\n[PHASE 2] Spatio-Temporal Modeling")
    spatial_model = FloodSpatialModel("feature_vectors.csv")
    spatial_df = spatial_model.train()
    
    temporal_model = FloodTemporalModel()
    temporal_model.prepare_data()
    global_temp_risk = temporal_model.train()
    
    fuser = FloodFuser(spatial_df, global_temp_risk)
    flood_map = fuser.fuse()
    
    # 3. Routing Engine
    print("\n[PHASE 3] Graph & Optimization")
    gb = GraphBuilder(flood_map_path="flood_map.csv")
    G = gb.build_graph()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--amb_count', type=int, default=2, help='Number of ambulances')
    for _i in range(1, 11):
        parser.add_argument(f'--amb{_i}', type=str, default=None)
    args = parser.parse_args()

    N = args.amb_count

    # Largest strongly connected component for routing
    largest_cc = max(nx.strongly_connected_components(G), key=len)
    G_sub = G.subgraph(largest_cc).copy()
    nodes_sub = list(G_sub.nodes())

    def parse_coords(arg_str):
        parts = list(map(float, arg_str.split(',')))
        # Format: start_lat,start_lon,end_lat,end_lon
        start_node = ox.distance.nearest_nodes(G_sub, X=parts[1], Y=parts[0])
        end_node   = ox.distance.nearest_nodes(G_sub, X=parts[3], Y=parts[2])
        return start_node, end_node

    # Spread N default nodes evenly across the graph for variety
    step = max(1, len(nodes_sub) // (N + 1))
    ambulances = {}
    for i in range(N):
        amb_id = f"AMB-{i+1:02d}"
        arg_val = getattr(args, f'amb{i+1}', None)
        if arg_val:
            src, tgt = parse_coords(arg_val)
            print(f"{amb_id}: Custom coordinates used.")
        else:
            src = nodes_sub[i * step % len(nodes_sub)]
            tgt = nodes_sub[(i * step + len(nodes_sub) // 2) % len(nodes_sub)]
            print(f"{amb_id}: Default coordinates.")
        ambulances[amb_id] = (src, tgt)

    gen = SVPCandidateGenerator(G_sub)
    dict_cands = {
        amb_id: gen.generate_candidates(src, tgt, num_candidates=5)
        for amb_id, (src, tgt) in ambulances.items()
    }

    qubo = QUBOOptimizer(G_sub, list(ambulances.keys()), dict_cands)
    best_routes = qubo.optimize(pop_size=30, gens=60)

    print(f"\n[FINAL RESULTS] Optimal Routes ({N} ambulances)")
    for a, r in best_routes.items():
        if r:
            print(f"  {a}: Path found with {len(r)} hops.")
        else:
            print(f"  {a}: No feasible path.")

    # 4. Map and Data Export
    create_map(flood_map, G, best_routes)
    export_results_json(flood_map, G, best_routes, dp.hospitals)
    print("\n=== PIPELINE SUCCESSFUL ===")

if __name__ == "__main__":
    run_pipeline()

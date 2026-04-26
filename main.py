import folium
import pandas as pd
from data_pipeline import DataPipeline
from flood_models import FloodSpatialModel, FloodTemporalModel, FloodFuser
from routing_engine import GraphBuilder, SVPCandidateGenerator, QUBOOptimizer
import os

def create_map(flood_df, graph, final_routes):
    print("Generating Folium Map visualization...")
    mangalore_coords = [12.8698, 74.8431]
    m = folium.Map(location=mangalore_coords, zoom_start=12, tiles='CartoDB dark_matter')
    
    # 1. Plot Rivers removed - coarse dataset was interfering with CartoDB's native water masking.

    # 2. Plot Flood Grid Nodes (Exclude Safe / Green Nodes)
    for _, row in flood_df.iterrows():
        if row['risk_category'] == 'High':
            color = 'red'
        elif row['risk_category'] == 'Moderate':
            color = 'orange'
        else:
            continue # Skip safe areas to avoid map clutter!
            
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=150,
            color=color,
            fill=True,
            fillOpacity=0.5,
            popup=f"Risk: {row['final_risk']:.2f}<br>Category: {row['risk_category']}"
        ).add_to(m)
        
    # 3. Plot Roads Grid Links
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
            opac_val = 0.15  # Make safe roads a subtle background mesh!
            
        u_coord = [graph.nodes[u]['y'], graph.nodes[u]['x']]
        v_coord = [graph.nodes[v]['y'], graph.nodes[v]['x']]
        
        folium.PolyLine(
            locations=[u_coord, v_coord],
            color=edge_color,
            weight=weight_val,
            opacity=opac_val,
            popup=f"Risk {risk:.2f}"
        ).add_to(m)

    # 3. Plot Final Selected Routes for Ambulances
    colors = ['cyan', 'yellow', 'magenta', 'lime']
    color_idx = 0
    for amb, route_nodes in final_routes.items():
        if route_nodes:
            # Route nodes are OSM node IDs. Convert to [lat, lon]
            route_coords = [[graph.nodes[n]['y'], graph.nodes[n]['x']] for n in route_nodes]
            
            folium.PolyLine(
                locations=route_coords,
                color=colors[color_idx % len(colors)],
                weight=6,
                opacity=0.9,
                tooltip=f"{amb} Optimized Route"
            ).add_to(m)
            
            # Start and End Markers
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
    
    import argparse
    import osmnx as ox
    import networkx as ox_nx

    parser = argparse.ArgumentParser()
    parser.add_argument('--amb_count', type=int, default=2, help='Number of ambulances')
    # Accept up to 10 ambulance coordinate pairs
    for _i in range(1, 11):
        parser.add_argument(f'--amb{_i}', type=str, default=None)
    args = parser.parse_args()

    N = args.amb_count

    # Largest strongly connected component for routing
    largest_cc = max(ox_nx.strongly_connected_components(G), key=len)
    G_sub = G.subgraph(largest_cc).copy()
    nodes_sub = list(G_sub.nodes())

    def parse_coords(arg_str):
        parts = list(map(float, arg_str.split(',')))
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
        amb_id: gen.generate_candidates(src, tgt, num_candidates=3)
        for amb_id, (src, tgt) in ambulances.items()
    }

    qubo = QUBOOptimizer(G, list(ambulances.keys()), dict_cands)
    best_routes = qubo.optimize(pop_size=20, gens=50)

    print(f"\n[FINAL RESULTS] Optimal Routes ({N} ambulances)")
    for a, r in best_routes.items():
        if r:
            print(f"  {a}: Path found with {len(r)} hops.")
        else:
            print(f"  {a}: No feasible path.")

    # 4. Map Generation
    create_map(flood_map, G, best_routes)
    print("\n=== PIPELINE SUCCESSFUL ===")

if __name__ == "__main__":
    run_pipeline()

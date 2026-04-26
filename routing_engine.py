import osmnx as ox
import pandas as pd
import networkx as nx
import numpy as np
import random
import math
from itertools import combinations
import json
from heapq import heappush, heappop

class GraphBuilder:
    def __init__(self, flood_map_path="flood_map.csv"):
        self.flood_nodes = pd.read_csv(flood_map_path)
        self.G = None
        
    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _get_edge_risk(self, lat1, lon1, lat2, lon2):
        mid_lat = (lat1 + lat2) / 2
        mid_lon = (lon1 + lon2) / 2
        
        dists = (self.flood_nodes['lat'] - mid_lat)**2 + (self.flood_nodes['lon'] - mid_lon)**2
        idx = dists.idxmin()
        return self.flood_nodes.loc[idx, 'final_risk']

    def build_graph(self):
        print("Fetching Live OpenStreetMap Data for Mangalore...")
        # Try to load cached graph first for huge speedup
        import os
        cache_path = "mangalore_drive_graph.graphml"
        if os.path.exists(cache_path):
            print("Loading OSM graph from cache...")
            self.G = ox.load_graphml(cache_path)
        else:
            try:
                self.G = ox.graph_from_point((12.8698, 74.8431), dist=3000, network_type='drive')
                self.G = ox.add_edge_speeds(self.G)
                self.G = ox.add_edge_travel_times(self.G)
                ox.save_graphml(self.G, cache_path)
            except Exception as e:
                print("OSMnx fetch failed, reverting to basic mock fallback:", e)
                self.G = nx.DiGraph()
                return self.G
                
        print(f"OSM Live Graph Fetched: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        print("Baking Flood Penalties into Live Geometry...")
        
        for u, v, k, data in self.G.edges(keys=True, data=True):
            lat1, lon1 = self.G.nodes[u]['y'], self.G.nodes[u]['x']
            lat2, lon2 = self.G.nodes[v]['y'], self.G.nodes[v]['x']
            
            dist = data.get('length', self._haversine(lat1, lon1, lat2, lon2)*1000) / 1000.0 # to km
            # If OSM provided travel time from speed limits, use it as baseline, else use dist
            base_cost = data.get('travel_time', dist * 60) # roughly proxy time
            
            risk = self._get_edge_risk(lat1, lon1, lat2, lon2)
            
            penalty = risk * 200 # Heavy risk penalty
            if risk > 0.6: penalty += 5000 # Absolute bottleneck
            
            data['weight'] = base_cost + penalty
            data['risk'] = risk
            data['length_km'] = dist
            
        # Convert MultiDiGraph to DiGraph to support Yen's Algorithm (shortest_simple_paths)
        print("Converting to DiGraph for optimization compatibility...")
        self.G = nx.DiGraph(self.G)
        return self.G

class SVPCandidateGenerator:
    def __init__(self, G):
        self.G = G

    def generate_candidates(self, source, target, num_candidates=5):
        """
        Tsinghua SV2 Style: Single-Via Path generation.
        Efficiently finds diverse alternative paths using intermediate via nodes.
        """
        candidates = []
        try:
            # 1. First, always include the baseline global shortest path
            base_path = nx.dijkstra_path(self.G, source, target, weight='weight')
            candidates.append(base_path)
            
            # 2. Select Via Candidates
            # Tsinghua SV2 often uses nodes near the shortest path but with diversity.
            # We'll sample nodes from the graph that are NOT in the base path.
            all_nodes = list(self.G.nodes())
            # Sample 30 via candidates to find the best num_candidates
            via_pool = random.sample(all_nodes, min(50, len(all_nodes)))
            
            via_paths = []
            for via in via_pool:
                if via == source or via == target or via in base_path:
                    continue
                    
                try:
                    p1 = nx.dijkstra_path(self.G, source, via, weight='weight')
                    p2 = nx.dijkstra_path(self.G, via, target, weight='weight')
                    full_path = p1[:-1] + p2
                    
                    # Calculate total weight
                    cost = sum(self.G[full_path[i]][full_path[i+1]]['weight'] for i in range(len(full_path)-1))
                    
                    # Ensure path is simple (no loops)
                    if len(set(full_path)) == len(full_path):
                        via_paths.append((full_path, cost))
                except nx.NetworkXNoPath:
                    continue
            
            # Sort via paths by cost
            via_paths.sort(key=lambda x: x[1])
            
            # Filter for diversity
            for path, cost in via_paths:
                if len(candidates) >= num_candidates:
                    break
                    
                is_distinct = True
                for c in candidates:
                    intersection = len(set(path).intersection(set(c)))
                    union = len(set(path).union(set(c)))
                    # Jaccard logic: if > 75% similar nodes, reject for diversity
                    if union > 0 and intersection / union > 0.75:
                        is_distinct = False
                        break
                
                if is_distinct:
                    candidates.append(path)
                    
        except nx.NetworkXNoPath:
            print("No baseline path found between source and target.")
            
        return candidates

class QUBOOptimizer:
    def __init__(self, G, ambulances, candidates_dict):
        self.G = G
        self.ambulances = ambulances
        self.candidates_dict = candidates_dict
        
    def fitness(self, chromosome):
        total_cost = 0
        overlap_penalty = 0
        used_edges = {}
        
        for amb in self.ambulances:
            p_idx = chromosome[amb]
            if p_idx == -1:
                total_cost += 10000 
                continue
            path = self.candidates_dict[amb][p_idx]
            
            cost = sum(self.G[path[i]][path[i+1]]['weight'] for i in range(len(path)-1))
            total_cost += cost
            
            for i in range(len(path)-1):
                edge = (path[i], path[i+1])
                reversed_edge = (path[i+1], path[i])
                
                if edge in used_edges or reversed_edge in used_edges:
                    overlap_penalty += 300.0 # High penalty for collision
                else:
                    used_edges[edge] = True
                    
        return total_cost + overlap_penalty

    def optimize(self, pop_size=30, gens=60):
        print("Running Adaptive GA Optimization for Route Entanglement...")
        population = []
        for _ in range(pop_size):
            chrom = {}
            for amb in self.ambulances:
                c_len = len(self.candidates_dict[amb])
                chrom[amb] = random.randint(0, c_len-1) if c_len > 0 else -1
            population.append(chrom)
            
        best_fitness_history = []
        base_mutation_rate = 0.1
        
        for gen in range(gens):
            scored_pop = [(chrom, self.fitness(chrom)) for chrom in population]
            scored_pop.sort(key=lambda x: x[1])
            best_fit = scored_pop[0][1]
            best_fitness_history.append(best_fit)
            
            mutation_rate = base_mutation_rate
            # Adaptive mutation: If fitness hasn't improved in 5 generations, ramp it up!
            if len(best_fitness_history) > 5 and len(set(best_fitness_history[-5:])) == 1:
                mutation_rate = 0.4
            
            if (gen+1) % 10 == 0:
                print(f"Gen {gen+1} Best Fitness: {best_fit:.2f} | Mutate: {mutation_rate:.2f}")
                
            elites = [x[0] for x in scored_pop[:int(pop_size*0.2)]]
            new_pop = list(elites)
            
            while len(new_pop) < pop_size:
                p1, p2 = random.sample(elites, 2)
                child = {}
                for amb in self.ambulances:
                    # Crossover
                    child[amb] = p1[amb] if random.random() > 0.5 else p2[amb]
                    # Mutation
                    if random.random() < mutation_rate:
                        c_len = len(self.candidates_dict[amb])
                        child[amb] = random.randint(0, c_len-1) if c_len > 0 else -1
                new_pop.append(child)
                
            population = new_pop
            
        best_chrom = scored_pop[0][0]
        final_routes = {amb: self.candidates_dict[amb][best_chrom[amb]] if best_chrom[amb] != -1 else [] for amb in self.ambulances}
        return final_routes

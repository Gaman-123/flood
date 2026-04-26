import osmnx as ox
import pandas as pd
import networkx as nx
import numpy as np
import random
import math
from itertools import combinations
import json

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
        # Restrict to a tight 3km radius to keep nodes manageable (~2000-3000 nodes) for real-time SV2 pathing
        try:
            self.G = ox.graph_from_point((12.8698, 74.8431), dist=3000, network_type='drive')
            print(f"OSM Live Graph Fetched: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")
        except Exception as e:
            print("OSMnx fetch failed, reverting to basic mock fallback:", e)
            self.G = nx.DiGraph()
            return self.G
            
        print("Baking Flood Penalties into Live Geometry...")
        for u, v, k, data in self.G.edges(keys=True, data=True):
            lat1, lon1 = self.G.nodes[u]['y'], self.G.nodes[u]['x']
            lat2, lon2 = self.G.nodes[v]['y'], self.G.nodes[v]['x']
            
            dist = data.get('length', self._haversine(lat1, lon1, lat2, lon2)*1000) / 1000.0 # to km
            risk = self._get_edge_risk(lat1, lon1, lat2, lon2)
            
            penalty = risk * 10
            if risk > 0.6: penalty += 1000
            
            data['weight'] = dist + penalty
            data['risk'] = risk
            data['length_km'] = dist
            
        return self.G

class SVPCandidateGenerator:
    """Single-Via Path generator referencing Tsinghua SV2 style algorithms for candidate routes"""
    def __init__(self, G):
        self.G = G
        
    def generate_candidates(self, source, target, num_candidates=3):
        candidates = []
        try:
            # 1. Base Shortest Path
            base_path = nx.dijkstra_path(self.G, source, target, weight='weight')
            candidates.append(base_path)
            
            # 2. Single-Via Paths
            # Select random via nodes that are not in the base path
            nodes = list(self.G.nodes())
            via_nodes = random.sample([n for n in nodes if n not in base_path], min(10, len(nodes)-len(base_path)))
            
            paths_dict = {}
            for via in via_nodes:
                try:
                    p1 = nx.dijkstra_path(self.G, source, via, weight='weight')
                    p2 = nx.dijkstra_path(self.G, via, target, weight='weight')
                    # merge path
                    full_path = p1[:-1] + p2
                    # calc cost
                    cost = sum(min(self.G[full_path[i]][full_path[i+1]].values(), key=lambda d: d.get('weight', 9999))['weight'] for i in range(len(full_path)-1))
                    paths_dict[tuple(full_path)] = cost
                except nx.NetworkXNoPath:
                    continue
                    
            # Sort by cost and get top alternative distinct paths
            sorted_vias = sorted(paths_dict.items(), key=lambda x: x[1])
            
            for p, cost in sorted_vias:
                if len(candidates) >= num_candidates:
                    break
                # Only add if it's somewhat structurally different (Jaccard distance)
                is_distinct = True
                for c in candidates:
                    intersection = len(set(p).intersection(set(c)))
                    union = len(set(p).union(set(c)))
                    if intersection / union > 0.8: # Too similar
                        is_distinct = False
                        break
                if is_distinct:
                    candidates.append(list(p))
                    
        except nx.NetworkXNoPath:
            print("No path found between source and target.")
            
        return candidates

class QUBOOptimizer:
    def __init__(self, G, ambulances, candidates_dict):
        """
        ambulances: list of amb_ids
        candidates_dict: dict {amb_id: [path1, path2, ...]}
        """
        self.G = G
        self.ambulances = ambulances
        self.candidates_dict = candidates_dict
        
    def fitness(self, chromosome):
        # chromosome is a dict {amb_id: path_index}
        total_cost = 0
        overlap_penalty = 0
        used_edges = {}
        
        for amb in self.ambulances:
            p_idx = chromosome[amb]
            if p_idx == -1:
                total_cost += 10000  # Massive penalty for no path
                continue
            path = self.candidates_dict[amb][p_idx]
            # Add base travel + risk cost
            cost = sum(min(self.G[path[i]][path[i+1]].values(), key=lambda d: d.get('weight', 9999))['weight'] for i in range(len(path)-1))
            total_cost += cost
            
            # Check edge usage
            for i in range(len(path)-1):
                edge = (path[i], path[i+1])
                reversed_edge = (path[i+1], path[i])
                
                if edge in used_edges or reversed_edge in used_edges:
                    overlap_penalty += 50.0 # High penalty for shared roads (Traffic Entanglement / QUBO constraint)
                else:
                    used_edges[edge] = True
                    
        return total_cost + overlap_penalty

    def optimize(self, pop_size=20, gens=50):
        print("Running GA Optimization for Route Entanglement...")
        population = []
        for _ in range(pop_size):
            chrom = {}
            for amb in self.ambulances:
                c_len = len(self.candidates_dict[amb])
                chrom[amb] = random.randint(0, c_len-1) if c_len > 0 else -1
            population.append(chrom)
            
        for gen in range(gens):
            # Evaluate
            scored_pop = [(chrom, self.fitness(chrom)) for chrom in population]
            scored_pop.sort(key=lambda x: x[1])
            
            if (gen+1) % 10 == 0:
                print(f"Gen {gen+1} Best Fitness: {scored_pop[0][1]:.2f}")
                
            # Selection
            elites = [x[0] for x in scored_pop[:int(pop_size*0.2)]]
            
            # Crossover & Mutation
            new_pop = list(elites)
            while len(new_pop) < pop_size:
                p1, p2 = random.sample(elites, 2)
                child = {}
                for amb in self.ambulances:
                    # Crossover
                    child[amb] = p1[amb] if random.random() > 0.5 else p2[amb]
                    # Mutation
                    if random.random() < 0.1:
                        c_len = len(self.candidates_dict[amb])
                        child[amb] = random.randint(0, c_len-1) if c_len > 0 else -1
                new_pop.append(child)
                
            population = new_pop
            
        best_chrom = scored_pop[0][0]
        final_routes = {amb: self.candidates_dict[amb][best_chrom[amb]] if best_chrom[amb] != -1 else [] for amb in self.ambulances}
        return final_routes

if __name__ == "__main__":
    gb = GraphBuilder()
    G = gb.build_graph()
    
    # Test Generation
    nodes = list(G.nodes())
    if len(nodes) > 2:
        s = nodes[0]
        # Pick a target reasonably far
        t = nodes[-1]
        
        gen = SVPCandidateGenerator(G)
        cands = gen.generate_candidates(s, t)
        print(f"Generated {len(cands)} candidates for {s} -> {t}")
        
        ambs = ["A1", "A2"]
        cdict = {
            "A1": cands,
            "A2": gen.generate_candidates(nodes[1], nodes[-2])
        }
        
        qubo = QUBOOptimizer(G, ambs, cdict)
        best = qubo.optimize()
        print("Optimal assigned paths:", best)

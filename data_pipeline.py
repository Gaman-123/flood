import pandas as pd
import numpy as np
import json
import math
from pathlib import Path
import os
from datetime import datetime
import osmnx as ox

class DataPipeline:
    def __init__(self, data_dir="mangalore_flood_data"):
        self.data_dir = Path(data_dir)
        self.lat_min = 12.80
        self.lat_max = 12.93
        self.lon_min = 74.81
        self.lon_max = 74.91
        self.grid_res = 0.01

        # Load raw data
        self.load_datasets()

    def load_datasets(self):
        import requests
        print("Fetching Live Data from APIs...")
        # Live Rainfall
        try:
            weather_resp = requests.get("https://api.open-meteo.com/v1/forecast?latitude=12.8698&longitude=74.8431&current=precipitation")
            self.current_rain = weather_resp.json()['current']['precipitation']
            print(f"Live Rain: {self.current_rain} mm")
        except Exception as e:
            print("Weather API failed, fallback to 5.0", e)
            self.current_rain = 5.0

        # Live Tide
        try:
            tide_resp = requests.get("https://marine-api.open-meteo.com/v1/marine?latitude=12.8698&longitude=74.8431&current=sea_surface_elevation")
            self.current_sea = tide_resp.json()['current']['sea_surface_elevation']
            print(f"Live Sea Level: {self.current_sea} m")
        except Exception as e:
            print("Marine API failed, fallback to 1.0", e)
            self.current_sea = 1.0
            
        # Live River Discharge (Flood API)
        try:
            river_resp = requests.get("https://flood-api.open-meteo.com/v1/flood?latitude=12.8698&longitude=74.8431&daily=river_discharge&forecast_days=1")
            self.current_river = river_resp.json()['daily']['river_discharge'][0]
            print(f"Live River Discharge: {self.current_river} m³/s")
        except Exception as e:
            print("River API failed, fallback to 20.0", e)
            self.current_river = 20.0
            
        # Export live stats to json for frontend
        with open('live_stats.json', 'w') as f:
            json.dump({
                "rain_mm": self.current_rain,
                "sea_level_m": self.current_sea,
                "river_discharge_m3s": self.current_river,
                "timestamp": datetime.now().isoformat()
            }, f)

        # Elevation
        self.dem_df = pd.read_csv(self.data_dir / "elevation/mangalore_dem_150m.csv")
        
        # Roads (for drainage proxy)
        self.roads_df = pd.read_csv(self.data_dir / "roads/mangalore_roads.csv")

        # River geometry
        with open(self.data_dir / "river/mangalore_river_geometry.json", 'r') as f:
            self.rivers_data = json.load(f)

        # Hospitals (new) - Try to fetch from OSM or use fallback
        self.hospitals = self.fetch_hospitals()
            
    def fetch_hospitals(self):
        print("Fetching hospital locations from OSM...")
        try:
            # Search for hospitals in Mangalore
            tags = {"amenity": "hospital"}
            hospitals_gdf = ox.features_from_point((12.8698, 74.8431), tags, dist=5000)
            hospitals_list = []
            for _, row in hospitals_gdf.iterrows():
                if row.geometry.geom_type == 'Point':
                    hospitals_list.append({"name": row.get('name', 'Hospital'), "lat": row.geometry.y, "lon": row.geometry.x})
                else:
                    # centroid for polygons
                    centroid = row.geometry.centroid
                    hospitals_list.append({"name": row.get('name', 'Hospital'), "lat": centroid.y, "lon": centroid.x})
            print(f"Found {len(hospitals_list)} hospitals.")
            # Save for inspection
            with open('hospitals.json', 'w') as f:
                json.dump(hospitals_list, f)
            return hospitals_list
        except Exception as e:
            print("Failed to fetch hospitals from OSM:", e)
            # Fallback
            return [{"name": "A.J. Hospital", "lat": 12.8906, "lon": 74.8406}, 
                    {"name": "Father Muller", "lat": 12.8690, "lon": 74.8475},
                    {"name": "KMC Hospital", "lat": 12.8722, "lon": 74.8398}]

    def _haversine(self, lat1, lon1, lat2, lon2):
        # Distance in km
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _get_elevation(self, lat, lon):
        # Nearest neighbor interpolation
        dists = ((self.dem_df['latitude'] - lat)**2 + (self.dem_df['longitude'] - lon)**2)
        idx = dists.idxmin()
        return self.dem_df.loc[idx, 'elevation_m']

    def _get_dist_to_river(self, lat, lon):
        min_dist = float('inf')
        for river in self.rivers_data:
            path = river.get('path', [])
            for pt in path:
                d = self._haversine(lat, lon, pt['lat'], pt['lon'])
                if d < min_dist:
                    min_dist = d
        if min_dist == float('inf'):
            return min(self._haversine(lat, lon, 12.85, 74.83), self._haversine(lat, lon, 12.91, 74.85))
        return min_dist

    def _get_dist_to_road(self, lat, lon):
        min_dist = float('inf')
        for _, road in self.roads_df.iterrows():
            d1 = self._haversine(lat, lon, road['start_lat'], road['start_lon'])
            d2 = self._haversine(lat, lon, road['end_lat'], road['end_lon'])
            
            mid_lat = getattr(road, 'mid_lat', (road['start_lat'] + road['end_lat'])/2)
            mid_lon = getattr(road, 'mid_lon', (road['start_lon'] + road['end_lon'])/2)
            d3 = self._haversine(lat, lon, mid_lat, mid_lon)
            
            min_dist = min(min_dist, d1, d2, d3)
        return min_dist

    def construct_grid(self):
        print("Constructing grid and engineering features...")
        nodes = []
        lats = np.arange(self.lat_min, self.lat_max + self.grid_res, self.grid_res)
        lons = np.arange(self.lon_min, self.lon_max + self.grid_res, self.grid_res)
        
        node_id = 0
        for lat in lats:
            for lon in lons:
                el = self._get_elevation(lat, lon)
                dist_riv = self._get_dist_to_river(lat, lon)
                dist_road = self._get_dist_to_road(lat, lon)
                
                nodes.append({
                    'id': f"N_{node_id}",
                    'lat': round(lat, 4),
                    'lon': round(lon, 4),
                    'rain': self.current_rain,
                    'sea': self.current_sea,
                    'elevation': el,
                    'dist_river': dist_riv,
                    'dist_drainage': dist_road
                })
                node_id += 1
                
        self.nodes_df = pd.DataFrame(nodes)
        print(f"Generated {len(self.nodes_df)} nodes.")
        
    def feature_engineering(self):
        print("Normalizing features...")
        df = self.nodes_df.copy()
        
        # Max-min normalization (global bounds approximate)
        df['rain_norm'] = df['rain'] / 50.0 # max 50mm/hr
        df['sea_norm'] = df['sea'] / 3.0    # max 3m 
        df['elevation_norm'] = np.clip(df['elevation'] / 100.0, 0, 1) # max 100m consideration
        df['dist_river_norm'] = np.clip(df['dist_river'] / 10.0, 0, 1) # max 10km
        df['drainage_norm'] = np.clip(df['dist_drainage'] / 5.0, 0, 1) # max 5km
        
        # Derived
        df['flood_index_base'] = df['rain_norm'] + df['sea_norm']
        df['water_influence'] = 1.0 / (df['dist_river'] + 0.1) # Add epsilon
        
        # We need a risk proxy for training
        # Target: 1 if (rain+sea is high, ele is low, dist_riv is low)
        conditions = (
            ((df['rain_norm'] * 0.4 + df['sea_norm'] * 0.3) > 0.3) | 
            ((df['elevation'] < 10) & (df['dist_river'] < 2.0))
        )
        
        # Give nodes a synthetic target score 0-1 based on physical formulas
        risk_score = (
            df['rain_norm'] * 0.35 + 
            df['sea_norm'] * 0.25 + 
            (1 - df['elevation_norm']) * 0.25 + 
            df['water_influence'] * 0.15
        )
        
        df['target_risk'] = np.clip(risk_score, 0, 1)
        df['is_flooded'] = (df['target_risk'] > 0.55).astype(int)
        
        self.features_df = df
        
    def save(self):
        self.features_df.to_csv("feature_vectors.csv", index=False)
        print("Saved feature_vectors.csv")

if __name__ == "__main__":
    dp = DataPipeline()
    dp.construct_grid()
    dp.feature_engineering()
    dp.save()

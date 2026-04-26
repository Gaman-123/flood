import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import pickle
import os

class FloodSpatialModel:
    def __init__(self, data_path="feature_vectors.csv"):
        self.data_path = data_path
        self.model = xgb.XGBClassifier(eval_metric='logloss', objective='binary:logistic')
        
    def train(self):
        print("Training Spatial Risk Model (XGBoost)...")
        df = pd.read_csv(self.data_path)
        
        # Features: rain_norm, sea_norm, elevation_norm, dist_river_norm, drainage_norm, water_influence
        features = ['rain_norm', 'sea_norm', 'elevation_norm', 'dist_river_norm', 'drainage_norm', 'water_influence']
        X = df[features]
        y = df['is_flooded']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model.fit(X_train, y_train)
        
        preds = self.model.predict(X_test)
        acc = accuracy_score(y_test, preds)
        print(f"XGBoost Model Accuracy: {acc:.4f}")
        
        # Predict spatial risk score
        df['spatial_risk'] = self.model.predict_proba(X)[:, 1]
        self.df = df
        
        with open("spatial_model.pkl", "wb") as f:
            pickle.dump(self.model, f)
            
        print("Saved Spatial Model.")
        return df

class TemporalRiskModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size):
        super(TemporalRiskModel, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)
        
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return torch.sigmoid(out)

class FloodTemporalModel:
    def __init__(self, rain_path="mangalore_flood_data/rainfall/mangalore_rainfall_30days.csv",
                 tide_path="mangalore_flood_data/tide/mangalore_tide_30days.csv"):
        self.rain_path = rain_path
        self.tide_path = tide_path
        self.seq_length = 6 # Last 6 timesteps (e.g., 2 hours if 20-min intervals)
        self.model = TemporalRiskModel(input_size=2, hidden_size=16, num_layers=1, output_size=1)
        self.criterion = nn.BCELoss()
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.01)

    def prepare_data(self):
        print("Preparing Temporal Data...")
        # Since intervals are different (20m rain, 30m tide), we should resample or merge on nearest.
        rain_df = pd.read_csv(self.rain_path, parse_dates=['timestamp'])
        tide_df = pd.read_csv(self.tide_path, parse_dates=['timestamp'])
        
        rain_df.set_index('timestamp', inplace=True)
        tide_df.set_index('timestamp', inplace=True)
        
        # Resample to 30 min and merge
        rain_resampled = rain_df[['rain_1h_mm']].resample('30min').mean()
        tide_resampled = tide_df[['total_water_level_m']].resample('30min').mean()
        
        df = rain_resampled.join(tide_resampled, how='inner').ffill().fillna(0)
        df['rain_norm'] = df['rain_1h_mm'] / df['rain_1h_mm'].max()
        df['tide_norm'] = df['total_water_level_m'] / df['total_water_level_m'].max()
        
        # Synthetic risk target based on high rain and high tide
        df['risk_target'] = ((df['rain_norm'] + df['tide_norm']) > 1.0).astype(float)
        
        X, y = [], []
        data = df[['rain_norm', 'tide_norm']].values
        targets = df['risk_target'].values
        
        for i in range(len(data) - self.seq_length):
            X.append(data[i:i+self.seq_length])
            y.append(targets[i+self.seq_length])
            
        self.X = torch.tensor(np.array(X), dtype=torch.float32)
        self.y = torch.tensor(np.array(y), dtype=torch.float32).unsqueeze(1)
        
    def train(self, epochs=20):
        print("Training Temporal Risk Model (LSTM)...")
        dataset = TensorDataset(self.X, self.y)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        for epoch in range(epochs):
            total_loss = 0
            for batch_X, batch_y in loader:
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()
            if (epoch+1) % 5 == 0:
                print(f"Epoch [{epoch+1}/{epochs}], Loss: {total_loss/len(loader):.4f}")
                
        # Predict current global temporal risk based on last seq_length readings
        self.model.eval()
        with torch.no_grad():
            last_seq = self.X[-1].unsqueeze(0)
            self.current_temporal_risk = self.model(last_seq).item()
        print(f"Current Global Temporal Risk: {self.current_temporal_risk:.4f}")
        torch.save(self.model.state_dict(), "lstm_model.pth")
        return self.current_temporal_risk

class FloodFuser:
    def __init__(self, spatial_df, temporal_risk):
        self.df = spatial_df
        self.temporal_risk = temporal_risk
        
    def fuse(self):
        print("Fusing Spatial and Temporal Risks...")
        alpha = 0.7  # weight for spatial (local specific)
        beta = 0.3   # weight for temporal (global future state)
        
        self.df['final_risk'] = (alpha * self.df['spatial_risk']) + (beta * self.temporal_risk)
        
        # Categorize risk
        def map_risk(val):
            if val < 0.3: return 'Safe'
            elif val < 0.6: return 'Moderate'
            else: return 'High'
            
        self.df['risk_category'] = self.df['final_risk'].apply(map_risk)
        
        self.df.to_csv("flood_map.csv", index=False)
        print("Generated flood_map.csv")
        return self.df

if __name__ == "__main__":
    # 1. Train Spatial (XGBoost)
    spatial_model = FloodSpatialModel()
    spatial_df = spatial_model.train()
    
    # 2. Train Temporal (LSTM)
    temporal_model = FloodTemporalModel()
    temporal_model.prepare_data()
    global_temporal_risk = temporal_model.train()
    
    # 3. Fuse
    fuser = FloodFuser(spatial_df, global_temporal_risk)
    flood_map = fuser.fuse()

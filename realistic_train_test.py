"""
realistic_train_test.py
===================================================
Realistic Training & Evaluation Script using ACTUAL
Mangalore local datasets:
  - mangalore_dem_150m.csv       (elevation, slope)
  - mangalore_flood_zones_lt5m.csv (ground-truth zones)
  - mangalore_rainfall_30days.csv  (20-min rainfall)
  - mangalore_tide_30days.csv      (30-min tidal readings)
  - mangalore_river_levels.csv     (hourly river levels)
  - feature_vectors.csv            (existing spatial grid)

Models:
  1. XGBoost Spatial Flood Risk Classifier
  2. LSTM Temporal Flood Risk Predictor
===================================================
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
import math
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
    classification_report
)
import pickle
import warnings
warnings.filterwarnings('ignore')

np.random.seed(42)
torch.manual_seed(42)

# ─────────────────────────────────────────────────────────
# SECTION 1 — BUILD SPATIAL DATASET FROM REAL DEM + RAINFALL
# ─────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def build_spatial_dataset():
    print("\n[DATA] Loading real DEM, flood zones and rainfall data...")

    # 1. Real elevation grid (150m resolution over Mangalore)
    dem = pd.read_csv("mangalore_flood_data/elevation/mangalore_dem_150m.csv")
    # 2. Ground-truth flood zones (elevation < 5m = confirmed high risk)
    flood_zones = pd.read_csv("mangalore_flood_data/elevation/mangalore_flood_zones_lt5m.csv")
    # 3. Rainfall — take mean rain across the 30-day period
    rain_df = pd.read_csv("mangalore_flood_data/rainfall/mangalore_rainfall_30days.csv",
                          parse_dates=['timestamp'])
    # 4. Tidal — take mean tide
    tide_df = pd.read_csv("mangalore_flood_data/tide/mangalore_tide_30days.csv",
                          parse_dates=['timestamp'])

    avg_rain = rain_df['rain_1h_mm'].mean()
    max_rain  = rain_df['rain_1h_mm'].max()
    avg_tide  = tide_df['total_water_level_m'].mean()
    max_tide  = tide_df['total_water_level_m'].max()

    print(f"  Avg rain: {avg_rain:.2f} mm/h | Max rain: {max_rain:.2f} mm/h")
    print(f"  Avg tide: {avg_tide:.2f} m    | Max tide: {max_tide:.2f} m")
    print(f"  DEM grid points: {len(dem)} | Flood zone points: {len(flood_zones)}")

    # Build set of confirmed flood coordinates for label lookup
    flood_coords = set(
        zip(flood_zones['latitude'].round(4), flood_zones['longitude'].round(4))
    )

    rows = []
    for _, r in dem.iterrows():
        lat, lon = round(r['latitude'], 4), round(r['longitude'], 4)
        el   = r['elevation_m']
        slop = r['slope_deg']

        # Distance to nearest flood zone centroid (rough water influence proxy)
        if len(flood_zones) > 0:
            dists = flood_zones.apply(
                lambda fz: haversine(lat, lon, fz['latitude'], fz['longitude']), axis=1
            )
            dist_flood_zone = dists.min()
        else:
            dist_flood_zone = 10.0

        # Normalise features
        rain_norm        = min(avg_rain / 50.0, 1.0)
        rain_peak_norm   = min(max_rain / 100.0, 1.0)
        sea_norm         = min(avg_tide / 3.5, 1.0)
        sea_peak_norm    = min(max_tide / 4.0, 1.0)
        elev_norm        = min(el / 200.0, 1.0)
        slope_norm       = min(slop / 45.0, 1.0)
        dist_flood_norm  = min(dist_flood_zone / 5.0, 1.0)
        water_influence  = 1.0 / (dist_flood_zone + 0.1)

        # Physical risk score
        risk_score = (
            rain_norm      * 0.25 +
            rain_peak_norm * 0.15 +
            sea_norm       * 0.20 +
            sea_peak_norm  * 0.10 +
            (1 - elev_norm)  * 0.20 +
            water_influence  * 0.10
        )
        risk_score = float(np.clip(risk_score, 0, 1))

        # Ground-truth label: confirmed flood zone OR risk score above threshold
        is_flooded = int((lat, lon) in flood_coords or risk_score > 0.52)

        rows.append({
            'lat': lat, 'lon': lon,
            'rain_norm':       rain_norm,
            'sea_norm':        sea_norm,
            'elevation_norm':  elev_norm,
            'slope_norm':      slope_norm,
            'dist_river_norm': dist_flood_norm,
            'drainage_norm':   slope_norm,        # slope proxy for drainage
            'water_influence': water_influence,
            'risk_score':      risk_score,
            'is_flooded':      is_flooded,
        })

    df = pd.DataFrame(rows)
    print(f"  Spatial dataset: {len(df)} points | "
          f"Flooded: {df['is_flooded'].sum()} ({df['is_flooded'].mean()*100:.1f}%)")
    return df


# ─────────────────────────────────────────────────────────
# SECTION 2 — BUILD TEMPORAL DATASET FROM REAL TIME SERIES
# ─────────────────────────────────────────────────────────

def build_temporal_dataset():
    print("\n[DATA] Loading real rainfall, tide & river level time-series...")

    rain_df  = pd.read_csv("mangalore_flood_data/rainfall/mangalore_rainfall_30days.csv",
                           parse_dates=['timestamp'])
    tide_df  = pd.read_csv("mangalore_flood_data/tide/mangalore_tide_30days.csv",
                           parse_dates=['timestamp'])
    river_df = pd.read_csv("mangalore_flood_data/river/mangalore_river_levels.csv",
                           parse_dates=['timestamp'])

    # Use only Netravathi river (primary) 
    river_df = river_df[river_df['river_name'] == 'Netravathi'].copy()

    # Resample everything to 30-min
    rain_df  = rain_df.set_index('timestamp')[['rain_1h_mm']].resample('30min').mean().ffill()
    tide_df  = tide_df.set_index('timestamp')[['total_water_level_m']].resample('30min').mean().ffill()
    river_df = river_df.set_index('timestamp')[['water_level_m', 'discharge_cumecs']].resample('30min').mean().ffill()

    df = rain_df.join(tide_df, how='inner').join(river_df, how='inner').ffill().dropna()

    # Normalise
    df['rain_norm']  = np.clip(df['rain_1h_mm']          / df['rain_1h_mm'].max(),          0, 1)
    df['tide_norm']  = np.clip(df['total_water_level_m']  / df['total_water_level_m'].max(), 0, 1)
    df['river_norm'] = np.clip(df['water_level_m']        / df['water_level_m'].max(),       0, 1)

    # Risk label — composite threshold on actual measured levels
    rain_thresh  = df['rain_1h_mm'].quantile(0.75)
    tide_thresh  = df['total_water_level_m'].quantile(0.75)
    river_thresh = df['water_level_m'].quantile(0.80)

    df['risk_target'] = np.clip(
        df['rain_norm']  * 0.40 +
        df['tide_norm']  * 0.30 +
        df['river_norm'] * 0.30, 0, 1
    )
    df['is_flooded'] = (
        (df['rain_1h_mm']         > rain_thresh)  |
        (df['total_water_level_m'] > tide_thresh)  |
        (df['water_level_m']       > river_thresh)
    ).astype(float)

    print(f"  Temporal timesteps : {len(df)}")
    print(f"  Rain thresh  : {rain_thresh:.2f} mm/h")
    print(f"  Tide thresh  : {tide_thresh:.2f} m")
    print(f"  River thresh : {river_thresh:.2f} m")
    print(f"  Flood steps  : {df['is_flooded'].sum():.0f} / {len(df)} "
          f"({df['is_flooded'].mean()*100:.1f}%)")
    return df


# ─────────────────────────────────────────────────────────
# SECTION 3 — XGBOOST SPATIAL MODEL
# ─────────────────────────────────────────────────────────

SPATIAL_FEATURES = [
    'rain_norm', 'sea_norm', 'elevation_norm', 'slope_norm',
    'dist_river_norm', 'drainage_norm', 'water_influence'
]

def train_eval_xgboost(df):
    print("\n" + "═"*58)
    print("  XGBOOST SPATIAL FLOOD RISK MODEL  (Realistic Data)")
    print("═"*58)

    X = df[SPATIAL_FEATURES].values
    y = df['is_flooded'].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # Class weight to handle imbalance
    scale = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.06,
        subsample=0.85,
        colsample_bytree=0.85,
        scale_pos_weight=scale,
        eval_metric='logloss',
        objective='binary:logistic',
        random_state=42,
        verbosity=0
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(f"\n  ── Test Set Results ──")
    print(f"  Accuracy :  {accuracy_score(y_test, y_pred)*100:.2f}%")
    print(f"  Precision:  {precision_score(y_test, y_pred, zero_division=0)*100:.2f}%")
    print(f"  Recall   :  {recall_score(y_test, y_pred, zero_division=0)*100:.2f}%")
    print(f"  F1 Score :  {f1_score(y_test, y_pred, zero_division=0)*100:.2f}%")
    print(f"  ROC-AUC  :  {roc_auc_score(y_test, y_proba):.4f}")

    cm = confusion_matrix(y_test, y_pred)
    print(f"\n  Confusion Matrix:")
    print(f"         Pred Safe  Pred Flood")
    print(f"  Safe    {cm[0][0]:6d}      {cm[0][1]:6d}")
    print(f"  Flood   {cm[1][0]:6d}      {cm[1][1]:6d}")

    print(f"\n  Classification Report:")
    for line in classification_report(y_test, y_pred, target_names=['Safe','Flooded']).splitlines():
        print('    ' + line)

    importances = model.feature_importances_
    print("  Feature Importances (from real DEM + rainfall features):")
    for feat, imp in sorted(zip(SPATIAL_FEATURES, importances), key=lambda x: -x[1]):
        bar = '█' * int(imp * 40)
        print(f"    {feat:<22} {bar:<40} {imp:.4f}")

    with open("spatial_model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("\n  ✅ Saved: spatial_model.pkl")
    return model


# ─────────────────────────────────────────────────────────
# SECTION 4 — LSTM TEMPORAL MODEL
# ─────────────────────────────────────────────────────────

class TemporalRiskModel(nn.Module):
    def __init__(self, input_size=3, hidden_size=64, num_layers=2, dropout=0.25):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                            batch_first=True, dropout=dropout)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32), nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1), nn.Sigmoid()
        )
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def build_sequences(df, seq_len=12):
    data = df[['rain_norm', 'tide_norm', 'river_norm']].values
    tgts = df['is_flooded'].values
    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i: i + seq_len])
        y.append(tgts[i + seq_len])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train_eval_lstm(df):
    print("\n" + "═"*58)
    print("  LSTM TEMPORAL FLOOD RISK MODEL  (Realistic Data)")
    print("═"*58)

    SEQ_LEN, EPOCHS, BS, LR = 12, 50, 64, 5e-3

    X, y = build_sequences(df, seq_len=SEQ_LEN)
    split = int(len(X) * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    X_tr_t = torch.tensor(X_train)
    y_tr_t = torch.tensor(y_train).unsqueeze(1)
    X_te_t = torch.tensor(X_test)
    y_te_t = torch.tensor(y_test).unsqueeze(1)

    # Weighted sampler to handle class imbalance
    pos = float(y_train.sum())
    neg = float(len(y_train) - pos)
    weights = torch.tensor([neg/pos if v == 1 else 1.0 for v in y_train])
    sampler = torch.utils.data.WeightedRandomSampler(weights, len(weights))

    train_loader = DataLoader(TensorDataset(X_tr_t, y_tr_t), batch_size=BS, sampler=sampler)
    test_loader  = DataLoader(TensorDataset(X_te_t, y_te_t), batch_size=BS)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model  = TemporalRiskModel(input_size=3, hidden_size=64, num_layers=2).to(device)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.4)

    print(f"\n  Device: {device.upper()} | "
          f"Train seqs: {len(X_train)} | Test seqs: {len(X_test)}")
    print(f"  Seq Length: {SEQ_LEN} steps = {SEQ_LEN//2}h look-back | "
          f"Features: rain, tide, river\n")

    best_loss = float('inf')
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            loss = criterion(model(bx), by)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()
        avg = total_loss / len(train_loader)
        if avg < best_loss:
            best_loss = avg
            torch.save(model.state_dict(), "lstm_model.pth")
        if epoch % 10 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{EPOCHS} | Loss: {avg:.4f} | "
                  f"LR: {scheduler.get_last_lr()[0]:.5f}")

    model.load_state_dict(torch.load("lstm_model.pth"))
    model.eval()

    all_preds, all_probs, all_true = [], [], []
    with torch.no_grad():
        for bx, by in test_loader:
            probs = model(bx.to(device)).cpu().numpy().flatten()
            all_probs.extend(probs)
            all_preds.extend((probs > 0.5).astype(int))
            all_true.extend(by.numpy().flatten().astype(int))

    all_true  = np.array(all_true)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    print(f"\n  ── Test Set Results ──")
    print(f"  Accuracy :  {accuracy_score(all_true, all_preds)*100:.2f}%")
    print(f"  Precision:  {precision_score(all_true, all_preds, zero_division=0)*100:.2f}%")
    print(f"  Recall   :  {recall_score(all_true, all_preds, zero_division=0)*100:.2f}%")
    print(f"  F1 Score :  {f1_score(all_true, all_preds, zero_division=0)*100:.2f}%")
    print(f"  ROC-AUC  :  {roc_auc_score(all_true, all_probs):.4f}")

    cm = confusion_matrix(all_true, all_preds)
    print(f"\n  Confusion Matrix:")
    print(f"         Pred Safe  Pred Flood")
    print(f"  Safe    {cm[0][0]:6d}      {cm[0][1]:6d}")
    print(f"  Flood   {cm[1][0]:6d}      {cm[1][1]:6d}")

    print(f"\n  Classification Report:")
    for line in classification_report(all_true, all_preds, target_names=['Safe','Flooded']).splitlines():
        print('    ' + line)

    with torch.no_grad():
        last_seq = torch.tensor(X_test[-1:]).to(device)
        current_risk = model(last_seq).item()
    print(f"  Current Forecasted Global Temporal Risk: {current_risk:.4f}")
    print(f"\n  ✅ Saved: lstm_model.pth")
    return model, current_risk


# ─────────────────────────────────────────────────────────
# SECTION 5 — REAL-WORLD SCENARIO STRESS TESTS
# ─────────────────────────────────────────────────────────

def run_scenario_tests(xgb_model, lstm_model):
    print("\n" + "═"*58)
    print("  REAL-WORLD SCENARIO STRESS TESTS")
    print("═"*58)

    # XGBoost scenarios based on actual Mangalore geography
    # Features: rain_norm, sea_norm, elevation_norm, slope_norm,
    #           dist_river_norm, drainage_norm, water_influence
    xgb_scenarios = [
        ("🌧️  Cyclone landfall (Kutch-like, coastal)",  [0.98, 0.92, 0.03, 0.05, 0.04, 0.90, 9.0]),
        ("🌊  High tide + monsoon surge (June peak)",   [0.82, 0.90, 0.06, 0.08, 0.06, 0.85, 8.0]),
        ("🏙️  Mangalore city core (poor drainage)",     [0.70, 0.55, 0.18, 0.12, 0.25, 0.88, 3.5]),
        ("🏔️  Kadri Hills safe zone",                   [0.30, 0.20, 0.72, 0.55, 0.70, 0.20, 0.4]),
        ("⛅  Post-monsoon (Oct calm)",                  [0.18, 0.35, 0.45, 0.30, 0.55, 0.30, 0.8]),
        ("🌀  Extreme cyclone SSCS (rare event)",       [1.00, 1.00, 0.02, 0.04, 0.02, 1.00, 10.0]),
        ("🏖️  Panambur beach zone (low elev, tidal)",   [0.60, 0.80, 0.04, 0.10, 0.05, 0.75, 7.5]),
    ]

    print("\n  XGBoost Spatial Predictions (real geography features):")
    print(f"  {'Scenario':<44} {'Risk%':>8}  {'Label':>12}")
    print("  " + "-"*68)
    for name, feats in xgb_scenarios:
        prob  = xgb_model.predict_proba([feats])[0][1]
        label = "🔴 HIGH" if prob > 0.6 else ("🟡 MODERATE" if prob > 0.3 else "🟢 SAFE")
        print(f"  {name:<44} {prob*100:>7.1f}%  {label:>12}")

    # LSTM scenarios using actual measured signal levels from the dataset
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    lstm_model.eval()

    # Values calibrated from actual dataset quantiles
    lstm_scenarios = [
        ("🌧️  June monsoon burst (peak rain+tide)",
            [[0.90, 0.85, 0.80]] * 12),
        ("🌊  Tidal surge — Mangalore port zone",
            [[0.55, 0.95, 0.70]] * 6 + [[0.60, 0.90, 0.65]] * 6),
        ("💧  River Netravathi flood warning level",
            [[0.70, 0.60, 0.90]] * 12),
        ("⛅  Post-storm drain-down (Oct lull)",
            [[0.75, 0.65, 0.60]] * 4 + [[0.25, 0.40, 0.20]] * 8),
        ("☀️  Dry season baseline (Jan-Mar)",
            [[0.05, 0.35, 0.12]] * 12),
        ("🌀  Extreme cyclone surge (all sensors maxed)",
            [[1.00, 1.00, 0.98]] * 12),
    ]

    print("\n  LSTM Temporal Predictions (12-step / 6h window, real signal values):")
    print(f"  {'Scenario':<46} {'Risk%':>8}  {'Label':>12}")
    print("  " + "-"*68)
    with torch.no_grad():
        for name, seq in lstm_scenarios:
            inp  = torch.tensor([seq], dtype=torch.float32).to(device)
            prob = lstm_model(inp).item()
            label = "🔴 HIGH" if prob > 0.6 else ("🟡 MODERATE" if prob > 0.3 else "🟢 SAFE")
            print(f"  {name:<46} {prob*100:>7.1f}%  {label:>12}")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("╔" + "═"*56 + "╗")
    print("║   FLOOD-AWARE ML — REALISTIC DATA TRAINING & EVAL     ║")
    print("║   Mangalore Flood Routing System                       ║")
    print("╚" + "═"*56 + "╝")

    # 1. Build real datasets
    spatial_df  = build_spatial_dataset()
    temporal_df = build_temporal_dataset()

    # 2. Train & evaluate XGBoost (spatial)
    xgb_model = train_eval_xgboost(spatial_df)

    # 3. Train & evaluate LSTM (temporal)
    lstm_model, current_risk = train_eval_lstm(temporal_df)

    # 4. Stress-test with real Mangalore scenarios
    run_scenario_tests(xgb_model, lstm_model)

    print("\n" + "═"*58)
    print("  ALL MODELS TRAINED ON REALISTIC DATA ✅")
    print(f"  Current temporal flood risk: {current_risk:.4f}")
    print("  Saved: spatial_model.pkl | lstm_model.pth")
    print("═"*58)

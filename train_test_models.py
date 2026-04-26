"""
train_test_models.py
===================================================
Comprehensive Training & Evaluation Script for:
  1. XGBoost Spatial Flood Risk Classifier
  2. LSTM Temporal Flood Risk Predictor

Uses realistic mock data simulating Mangalore's
actual geography, monsoon patterns, and tidal behaviour.
===================================================
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import pandas as pd
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
from sklearn.preprocessing import StandardScaler
import pickle
import warnings
warnings.filterwarnings('ignore')

np.random.seed(42)
torch.manual_seed(42)

# ═══════════════════════════════════════════════════════════
# SECTION 1 — REALISTIC MOCK DATA GENERATION
# ═══════════════════════════════════════════════════════════

def generate_spatial_mock_data(n_samples=2000):
    """
    Generates spatially diverse node samples mimicking Mangalore's coastal geography.
    
    Scenario classes:
      - Coastal low-lying zone (high risk)
      - River delta confluence (high risk)
      - Mid-elevation inland (moderate)
      - Elevated plateau zones (safe)
      - Dense urban drainage-poor zones (moderate-high)
    """
    print("\n[DATA GEN] Generating spatial mock dataset ...")

    data = []

    # ── Scenario A: Coastal Low-Lying (High Risk) ──────────
    n = n_samples // 5
    data.append(pd.DataFrame({
        'scenario': 'Coastal Low-Lying',
        'rain_norm':        np.random.uniform(0.6, 1.0, n),
        'sea_norm':         np.random.uniform(0.7, 1.0, n),
        'elevation_norm':   np.random.uniform(0.0, 0.1, n),
        'dist_river_norm':  np.random.uniform(0.0, 0.2, n),
        'drainage_norm':    np.random.uniform(0.7, 1.0, n),
        'water_influence':  np.random.uniform(3.0, 8.0, n),
    }))

    # ── Scenario B: River Delta / Confluence (High Risk) ──
    data.append(pd.DataFrame({
        'scenario': 'River Delta',
        'rain_norm':        np.random.uniform(0.5, 0.9, n),
        'sea_norm':         np.random.uniform(0.4, 0.8, n),
        'elevation_norm':   np.random.uniform(0.0, 0.15, n),
        'dist_river_norm':  np.random.uniform(0.0, 0.1, n),
        'drainage_norm':    np.random.uniform(0.6, 1.0, n),
        'water_influence':  np.random.uniform(4.0, 10.0, n),
    }))

    # ── Scenario C: Urban Core with Poor Drainage ─────────
    data.append(pd.DataFrame({
        'scenario': 'Urban Drainage-Poor',
        'rain_norm':        np.random.uniform(0.5, 0.85, n),
        'sea_norm':         np.random.uniform(0.3, 0.6, n),
        'elevation_norm':   np.random.uniform(0.1, 0.3, n),
        'dist_river_norm':  np.random.uniform(0.1, 0.4, n),
        'drainage_norm':    np.random.uniform(0.7, 1.0, n),
        'water_influence':  np.random.uniform(1.5, 4.0, n),
    }))

    # ── Scenario D: Mid-Elevation Inland (Moderate) ───────
    data.append(pd.DataFrame({
        'scenario': 'Mid-Elevation Inland',
        'rain_norm':        np.random.uniform(0.2, 0.6, n),
        'sea_norm':         np.random.uniform(0.1, 0.4, n),
        'elevation_norm':   np.random.uniform(0.3, 0.6, n),
        'dist_river_norm':  np.random.uniform(0.3, 0.6, n),
        'drainage_norm':    np.random.uniform(0.4, 0.7, n),
        'water_influence':  np.random.uniform(0.5, 2.0, n),
    }))

    # ── Scenario E: High Plateau / Safe Zone ──────────────
    data.append(pd.DataFrame({
        'scenario': 'High Plateau',
        'rain_norm':        np.random.uniform(0.0, 0.4, n),
        'sea_norm':         np.random.uniform(0.0, 0.2, n),
        'elevation_norm':   np.random.uniform(0.6, 1.0, n),
        'dist_river_norm':  np.random.uniform(0.5, 1.0, n),
        'drainage_norm':    np.random.uniform(0.0, 0.3, n),
        'water_influence':  np.random.uniform(0.0, 0.8, n),
    }))

    df = pd.concat(data, ignore_index=True).sample(frac=1, random_state=42)

    # Compute a physically-grounded risk score
    df['risk_score'] = (
        df['rain_norm']     * 0.30 +
        df['sea_norm']      * 0.25 +
        (1 - df['elevation_norm']) * 0.20 +
        (1 - df['dist_river_norm']) * 0.10 +
        df['drainage_norm'] * 0.05 +
        np.clip(df['water_influence'] / 10.0, 0, 1) * 0.10
    )

    # Add realistic noise
    df['risk_score'] = np.clip(df['risk_score'] + np.random.normal(0, 0.03, len(df)), 0, 1)

    # Binary label
    df['is_flooded'] = (df['risk_score'] > 0.50).astype(int)

    print(f"  Total samples: {len(df)}")
    print(f"  Flooded: {df['is_flooded'].sum()} | Safe: {(df['is_flooded']==0).sum()}")
    print(f"  Class balance: {df['is_flooded'].mean()*100:.1f}% flooded")

    return df


def generate_temporal_mock_data(days=90):
    """
    Generates 90-day realistic time-series of rainfall + tide
    for Mangalore — including monsoon surges, tidal peaks, and
    post-monsoon calm sequences.
    """
    print(f"\n[DATA GEN] Generating {days}-day temporal sequence ...")
    timestamps = pd.date_range(start='2024-06-01', periods=days * 48, freq='30min')
    n = len(timestamps)

    # Base monsoon cycle (June peak → Oct tail)
    t = np.linspace(0, 2 * np.pi, n)
    monsoon_base = 0.5 + 0.4 * np.sin(t - np.pi / 4)

    # Random storm events (12 spikes over 90 days)
    rain = monsoon_base * np.random.uniform(0.4, 0.9, n)
    for _ in range(12):
        center = np.random.randint(200, n - 200)
        width = np.random.randint(20, 80)
        intensity = np.random.uniform(0.8, 1.5)
        spike = intensity * np.exp(-0.5 * ((np.arange(n) - center) / width)**2)
        rain += spike

    rain = np.clip(rain, 0, 1)

    # Semi-diurnal tidal signal (two cycles per day ≈ 24h period)
    hours = np.arange(n) * 0.5
    tide = 0.5 + 0.35 * np.sin(2 * np.pi * hours / 12.4) + \
           0.1 * np.sin(2 * np.pi * hours / 24.8) + \
           np.random.normal(0, 0.03, n)
    tide = np.clip(tide, 0, 1)

    # River discharge proxy: lagged + scaled rainfall
    river_lag = np.roll(rain, 6)  # 3-hour lag
    river = 0.4 * river_lag + 0.3 * rain + np.random.normal(0, 0.02, n)
    river = np.clip(river, 0, 1)

    df = pd.DataFrame({
        'timestamp':    timestamps,
        'rain_norm':    rain,
        'tide_norm':    tide,
        'river_norm':   river,
    })

    # Composite risk target
    df['risk_target'] = np.clip(
        df['rain_norm'] * 0.45 + df['tide_norm'] * 0.30 + df['river_norm'] * 0.25
        + np.random.normal(0, 0.02, n), 0, 1
    )
    df['is_flooded'] = (df['risk_target'] > 0.55).astype(float)

    print(f"  Timesteps: {len(df)}")
    print(f"  Flood hours: {df['is_flooded'].sum():.0f} / {len(df)}")

    return df


# ═══════════════════════════════════════════════════════════
# SECTION 2 — XGBOOST SPATIAL MODEL
# ═══════════════════════════════════════════════════════════

FEATURES = ['rain_norm', 'sea_norm', 'elevation_norm',
            'dist_river_norm', 'drainage_norm', 'water_influence']

def train_eval_xgboost(df):
    print("\n" + "═"*55)
    print("  XGBOOST SPATIAL FLOOD RISK MODEL")
    print("═"*55)

    X = df[FEATURES].values
    y = df['is_flooded'].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        use_label_encoder=False,
        eval_metric='logloss',
        objective='binary:logistic',
        random_state=42,
        verbosity=0
    )

    # Training with eval set
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(f"\n  ── Test Set Results ──")
    print(f"  Accuracy :  {accuracy_score(y_test, y_pred)*100:.2f}%")
    print(f"  Precision:  {precision_score(y_test, y_pred)*100:.2f}%")
    print(f"  Recall   :  {recall_score(y_test, y_pred)*100:.2f}%")
    print(f"  F1 Score :  {f1_score(y_test, y_pred)*100:.2f}%")
    print(f"  ROC-AUC  :  {roc_auc_score(y_test, y_proba):.4f}")

    cm = confusion_matrix(y_test, y_pred)
    print(f"\n  Confusion Matrix:")
    print(f"         Pred Safe  Pred Flood")
    print(f"  Safe    {cm[0][0]:6d}      {cm[0][1]:6d}")
    print(f"  Flood   {cm[1][0]:6d}      {cm[1][1]:6d}")

    print(f"\n  Classification Report:")
    report = classification_report(y_test, y_pred, target_names=['Safe','Flooded'])
    for line in report.splitlines():
        print('    ' + line)

    # Feature importances
    importances = model.feature_importances_
    print("  Feature Importances:")
    for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
        bar = '█' * int(imp * 40)
        print(f"    {feat:<22} {bar:<40} {imp:.4f}")

    with open("spatial_model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("\n  ✅ Saved: spatial_model.pkl")

    return model


# ═══════════════════════════════════════════════════════════
# SECTION 3 — LSTM TEMPORAL MODEL
# ═══════════════════════════════════════════════════════════

class TemporalRiskModel(nn.Module):
    def __init__(self, input_size=3, hidden_size=64, num_layers=2, dropout=0.25):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def build_sequences(df, seq_len=12):
    """Build sliding-window sequences over the time-series."""
    data = df[['rain_norm', 'tide_norm', 'river_norm']].values
    tgts = df['is_flooded'].values

    X, y = [], []
    for i in range(len(data) - seq_len):
        X.append(data[i: i + seq_len])
        y.append(tgts[i + seq_len])

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def train_eval_lstm(df):
    print("\n" + "═"*55)
    print("  LSTM TEMPORAL FLOOD RISK MODEL")
    print("═"*55)

    SEQ_LEN = 12   # 6-hour look-back window (12 × 30min)
    EPOCHS   = 40
    BS       = 64
    LR       = 5e-3

    X, y = build_sequences(df, seq_len=SEQ_LEN)

    # 80/20 chronological split (no shuffle — temporal order matters)
    split = int(len(X) * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    X_tr_t = torch.tensor(X_train)
    y_tr_t = torch.tensor(y_train).unsqueeze(1)
    X_te_t = torch.tensor(X_test)
    y_te_t = torch.tensor(y_test).unsqueeze(1)

    train_loader = DataLoader(TensorDataset(X_tr_t, y_tr_t), batch_size=BS, shuffle=True)
    test_loader  = DataLoader(TensorDataset(X_te_t, y_te_t), batch_size=BS)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = TemporalRiskModel(input_size=3, hidden_size=64, num_layers=2).to(device)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

    print(f"\n  Device: {device.upper()} | Sequences: {len(X_train)} train / {len(X_test)} test")
    print(f"  Seq Length: {SEQ_LEN} steps (= {SEQ_LEN//2}h look-back) | Features: rain, tide, river\n")

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

        if epoch % 8 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{EPOCHS} | Loss: {avg:.4f} | LR: {scheduler.get_last_lr()[0]:.5f}")

    # ── Evaluation ────────────────────────────────────────
    model.load_state_dict(torch.load("lstm_model.pth"))
    model.eval()

    all_preds, all_probs, all_true = [], [], []
    with torch.no_grad():
        for bx, by in test_loader:
            bx = bx.to(device)
            probs = model(bx).cpu().numpy().flatten()
            preds = (probs > 0.5).astype(int)
            all_probs.extend(probs)
            all_preds.extend(preds)
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
    report = classification_report(all_true, all_preds, target_names=['Safe','Flooded'])
    for line in report.splitlines():
        print('    ' + line)

    # Current global temporal risk (last window)
    with torch.no_grad():
        last_seq = torch.tensor(X_test[-1:]).to(device)
        current_risk = model(last_seq).item()
    print(f"  Current Forecasted Global Temporal Risk: {current_risk:.4f}")
    print(f"\n  ✅ Saved: lstm_model.pth")

    return model, current_risk


# ═══════════════════════════════════════════════════════════
# SECTION 4 — SCENARIO STRESS TESTS
# ═══════════════════════════════════════════════════════════

def run_scenario_tests(xgb_model, lstm_model):
    print("\n" + "═"*55)
    print("  SCENARIO STRESS TESTS")
    print("═"*55)

    xgb_scenarios = [
        ("🌧️  Heavy monsoon, coastal zone",  [0.95, 0.90, 0.05, 0.08, 0.85, 7.5]),
        ("🌊  Tidal surge, river delta",      [0.70, 0.95, 0.08, 0.05, 0.80, 9.0]),
        ("🏙️  Urban flood, poor drainage",   [0.75, 0.50, 0.20, 0.30, 0.90, 3.2]),
        ("⛅  Moderate rain, mid-elevation", [0.45, 0.35, 0.40, 0.45, 0.55, 1.5]),
        ("🏔️  Light rain, high plateau",     [0.10, 0.05, 0.85, 0.80, 0.10, 0.3]),
        ("🌀  Cyclone approach (extreme)",   [1.00, 1.00, 0.03, 0.02, 1.00, 10.0]),
    ]

    print("\n  XGBoost Spatial Predictions:")
    print(f"  {'Scenario':<38} {'Risk Prob':>10}  {'Label':>8}")
    print("  " + "-"*60)
    for name, feats in xgb_scenarios:
        prob = xgb_model.predict_proba([feats])[0][1]
        label = "🔴 HIGH" if prob > 0.6 else ("🟡 MODERATE" if prob > 0.3 else "🟢 SAFE")
        print(f"  {name:<38} {prob:>9.3f}  {label:>10}")

    lstm_scenarios = [
        ("🌧️  Monsoon surge (6h window)",
            [[0.9, 0.8, 0.75]] * 12),
        ("🌊  Tidal peak with rain",
            [[0.6, 0.95, 0.70]] * 6 + [[0.7, 0.90, 0.65]] * 6),
        ("⛅  Post-storm calm",
            [[0.8, 0.7, 0.60]] * 4 + [[0.3, 0.4, 0.25]] * 8),
        ("☀️  Dry season (safe)",
            [[0.05, 0.3, 0.10]] * 12),
        ("🌀  Cyclone (extreme surge)",
            [[1.0, 1.0, 0.95]] * 12),
    ]

    print("\n  LSTM Temporal Predictions (12-step / 6h window):")
    print(f"  {'Scenario':<40} {'Risk Prob':>10}  {'Label':>8}")
    print("  " + "-"*60)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    lstm_model.eval()
    with torch.no_grad():
        for name, seq in lstm_scenarios:
            inp = torch.tensor([seq], dtype=torch.float32).to(device)
            prob = lstm_model(inp).item()
            label = "🔴 HIGH" if prob > 0.6 else ("🟡 MODERATE" if prob > 0.3 else "🟢 SAFE")
            print(f"  {name:<40} {prob:>9.3f}  {label:>10}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔" + "═"*53 + "╗")
    print("║   FLOOD-AWARE ML MODEL TRAINING & EVALUATION      ║")
    print("║   Mangalore Flood Routing System                   ║")
    print("╚" + "═"*53 + "╝")

    # 1. Generate realistic mock datasets
    spatial_df  = generate_spatial_mock_data(n_samples=2000)
    temporal_df = generate_temporal_mock_data(days=90)

    # 2. Train & evaluate XGBoost
    xgb_model = train_eval_xgboost(spatial_df)

    # 3. Train & evaluate LSTM
    lstm_model, current_risk = train_eval_lstm(temporal_df)

    # 4. Stress test with extreme real-world scenarios
    run_scenario_tests(xgb_model, lstm_model)

    print("\n" + "═"*55)
    print("  ALL MODELS TRAINED AND EVALUATED SUCCESSFULLY ✅")
    print("  Files saved: spatial_model.pkl | lstm_model.pth")
    print("═"*55)

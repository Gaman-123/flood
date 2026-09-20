"""Invariants for the dynamic rainfall trigger T(t).

T(t) modulates the static susceptibility: R(x,t) = S(x)·T(t). If the trigger
stops being monotone or escapes [0,1] the whole dynamic-risk claim breaks, so
these are pinned. Pure functions only — no network.
"""
import pytest

from floodrisk import live


def ant(r1=0.0, r6=0.0, r24=0.0, r72=0.0):
    return {"1h": r1, "6h": r6, "24h": r24, "72h": r72}


def test_trigger_is_bounded():
    for a in (ant(), ant(r24=1e4, r72=1e4, r6=1e4), ant(r24=64.5), ant(r72=500)):
        assert 0.0 <= live.rainfall_trigger(a) <= 1.0


def test_dry_conditions_give_zero_trigger():
    assert live.rainfall_trigger(ant()) == 0.0


def test_trigger_monotone_in_24h_rainfall():
    vals = [live.rainfall_trigger(ant(r24=r)) for r in (0, 20, 60, 120, 200, 300)]
    assert vals == sorted(vals), f"trigger must not decrease with more rain: {vals}"


def test_trigger_monotone_in_72h_saturation():
    vals = [live.rainfall_trigger(ant(r72=r)) for r in (0, 50, 100, 200, 400)]
    assert vals == sorted(vals)


def test_documented_events_rank_correctly():
    """The real May-2025 and Aug-2024 events must outrank an ordinary wet day."""
    may2025 = live.rainfall_trigger(ant(r1=2.3, r6=7.6, r24=87.2, r72=205.6))
    aug2024 = live.rainfall_trigger(ant(r1=3.1, r6=10.1, r24=53.4, r72=216.9))
    ordinary = live.rainfall_trigger(ant(r1=0.2, r6=3.6, r24=13.6, r72=37.6))
    dry = live.rainfall_trigger(ant())
    assert may2025 > aug2024 > ordinary > dry, (
        f"event ordering broken: may={may2025} aug={aug2024} ord={ordinary} dry={dry}")
    assert may2025 > 0.5, "a major flood event must produce a strong trigger"


def test_imd_thresholds_are_the_official_values():
    """Trigger normalization depends on IMD daily-rainfall bands (mm/24h)."""
    assert live.IMD_HEAVY == 64.5
    assert live.IMD_VERY_HEAVY == 115.6
    assert live.IMD_EXTREME == 204.5


def test_secrets_path_is_cwd_independent():
    """Keys must resolve from any working directory (regression: tide returned None)."""
    import os
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        keys = live._load_keys()
        assert isinstance(keys, dict)
        # If the secrets file exists at all, it must be found from a foreign CWD.
        repo_secret = os.path.join(live._REPO_ROOT, ".secrets", "live_api.env")
        if os.path.exists(repo_secret):
            assert "WORLDTIDES_API_KEY" in keys or "OPENWEATHER_API_KEY" in keys
    finally:
        os.chdir(cwd)


@pytest.mark.network
def test_live_openmeteo_returns_real_data():
    times, precip = live.fetch_openmeteo_rainfall(12.87, 74.84, past_days=2, forecast_days=1)
    assert len(times) == len(precip) > 24
    assert all(p >= 0 for p in precip)

"""
Test cases for the prediction model.

Critical tests to verify:
1. Unknown player → 400 PLAYER_NOT_FOUND
2. Ambiguous player → 400 with suggestions  
3. Large ranking gap (tier gap ≥3) with no H2H → Underdog ≤ 0.15
4. Event lookup with date → Event block present
5. Upstream failure → 503 UPSTREAM_UNAVAILABLE
"""

import pytest
from datetime import datetime
import pandas as pd
from predict import model, features


def test_ranking_prior_large_gap():
    """Test that large ranking gap produces appropriate prior."""
    # Top-3 vs #180 (tier gap = 4)
    p_a, p_b = model.ranking_prior(rank_a=2, rank_b=180)
    
    # Favorite (A) should be >= 0.85
    assert p_a >= 0.85, f"Expected p_a >= 0.85, got {p_a}"
    
    # Underdog (B) should be <= 0.15
    assert p_b <= 0.15, f"Expected p_b <= 0.15, got {p_b}"
    
    # Should sum to 1
    assert abs(p_a + p_b - 1.0) < 0.001


def test_hapers_vs_farag_critical():
    """
    Critical test case: Joeri Hapers (~#180) vs Ali Farag (top-3).
    With no H2H, underdog must be <= 0.15, favorite >= 0.85.
    """
    # Minimal features (no H2H, minimal history)
    minimal_features = {
        "elo_a": 1500,  # Hapers
        "elo_b": 2000,  # Farag (higher Elo)
        "elo_diff": -500,  # Hapers disadvantage
        "rank_a": 180,
        "rank_b": 2,
        "form_a": {"win_rate": 0.5, "avg_game_diff": 0, "matches_played": 5},
        "form_b": {"win_rate": 0.75, "avg_game_diff": 1.5, "matches_played": 15},
        "fatigue_a": {"matches_last_14d": 0, "matches_last_30d": 2},
        "fatigue_b": {"matches_last_14d": 2, "matches_last_30d": 5},
        "h2h": {
            "n_matches": 0,
            "n_effective": 0.0,
            "a_win_rate": 0.5,
            "avg_game_diff_a": 0.0,
            "days_since_last": 9999
        }
    }
    
    # Run prediction (A=Hapers, B=Farag)
    prediction = model.predict_match(
        minimal_features,
        rank_a=180,
        rank_b=2,
        seed=42
    )
    
    # Hapers (A, underdog) should be <= 0.15
    assert prediction["proba"]["A"] <= 0.15, \
        f"Underdog (Hapers) probability {prediction['proba']['A']} exceeds 0.15"
    
    # Farag (B, favorite) should be >= 0.85
    assert prediction["proba"]["B"] >= 0.85, \
        f"Favorite (Farag) probability {prediction['proba']['B']} below 0.85"
    
    # Winner should be B (Farag)
    assert prediction["winner"] == "B"
    
    print(f"✓ Critical test passed: Hapers {prediction['proba']['A']:.3f} vs Farag {prediction['proba']['B']:.3f}")


def test_never_fifty_fifty():
    """Test that unequal ranks never produce 50/50 prediction."""
    test_cases = [
        (1, 50),   # T1 vs T3
        (10, 150), # T2 vs T5
        (25, 250), # T3 vs T6
    ]
    
    for rank_a, rank_b in test_cases:
        p_a, p_b = model.ranking_prior(rank_a, rank_b)
        
        # Should never be exactly 0.5
        assert p_a != 0.5, f"Ranks {rank_a} vs {rank_b} produced 0.5 prior"
        assert p_b != 0.5, f"Ranks {rank_a} vs {rank_b} produced 0.5 prior"
        
        # Better rank should be favorite
        if rank_a < rank_b:
            assert p_a > 0.5, f"Better rank {rank_a} not favored vs {rank_b}"
        else:
            assert p_b > 0.5, f"Better rank {rank_b} not favored vs {rank_a}"


def test_tier_identification():
    """Test tier classification."""
    assert model.get_tier(1) == 0   # T1
    assert model.get_tier(3) == 0   # T1
    assert model.get_tier(10) == 1  # T2
    assert model.get_tier(25) == 2  # T3
    assert model.get_tier(75) == 3  # T4
    assert model.get_tier(150) == 4 # T5
    assert model.get_tier(250) == 5 # T6


def test_h2h_adjustment():
    """Test H2H adjustment calculation."""
    # Test with significant H2H advantage
    features_h2h = {
        "h2h": {
            "n_matches": 5,
            "n_effective": 4.5,
            "a_win_rate": 0.8,  # A dominates
            "avg_game_diff_a": 1.5,
            "days_since_last": 90
        },
        "elo_diff": 0,
        "rank_a": 50,
        "rank_b": 50,
        "form_a": {"win_rate": 0.5, "matches_played": 10},
        "form_b": {"win_rate": 0.5, "matches_played": 10},
        "fatigue_a": {},
        "fatigue_b": {}
    }
    
    delta = model.h2h_adjustment(features_h2h, rank_a=50, rank_b=50)
    
    # Should favor A (positive adjustment)
    assert delta > 0, "H2H advantage should produce positive adjustment"
    
    # Should be bounded (not too extreme)
    assert abs(delta) < 2.0, "H2H adjustment should be bounded"


def test_bootstrap_ci():
    """Test bootstrap confidence interval generation."""
    ci_a, ci_b = model.bootstrap_ci(p_a=0.7, p_b=0.3, n_bootstrap=500, seed=42)
    
    # CI should be valid ranges
    assert ci_a[0] < ci_a[1], "CI lower bound should be less than upper"
    assert ci_b[0] < ci_b[1], "CI lower bound should be less than upper"
    
    # Should be centered around the point estimate
    assert 0.6 < ci_a[0] < 0.8, f"CI for 0.7 looks wrong: {ci_a}"
    assert 0.2 < ci_b[0] < 0.4, f"CI for 0.3 looks wrong: {ci_b}"


def test_explanation_generation():
    """Test that explanation is generated in plain English."""
    features = {
        "elo_diff": 200,
        "rank_a": 10,
        "rank_b": 50,
        "form_a": {"win_rate": 0.7, "matches_played": 15},
        "form_b": {"win_rate": 0.5, "matches_played": 12},
        "h2h": {
            "n_matches": 3,
            "n_effective": 2.5,
            "a_win_rate": 0.67
        }
    }
    
    explain = model.generate_explanation(features, rank_a=10, rank_b=50, p_final_a=0.75, tier_gap=1)
    
    # Should have drivers
    assert "drivers" in explain
    assert len(explain["drivers"]) >= 3
    
    # Each driver should have required fields
    for driver in explain["drivers"]:
        assert "feature" in driver
        assert "impact" in driver
        assert "note" in driver
        # Note should be descriptive (no technical jargon)
        assert len(driver["note"]) > 10


if __name__ == "__main__":
    # Run critical test
    print("Running critical test: Hapers vs Farag")
    test_hapers_vs_farag_critical()
    
    print("\nRunning other tests...")
    test_ranking_prior_large_gap()
    test_never_fifty_fifty()
    test_tier_identification()
    test_h2h_adjustment()
    test_bootstrap_ci()
    test_explanation_generation()
    
    print("\n✓ All tests passed!")

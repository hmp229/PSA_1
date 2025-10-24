"""Ranking-aware prediction model with strict guardrails (no 50/50 fallback)."""
import numpy as np
from typing import Dict, Any, List, Tuple
from scipy.special import expit as sigmoid
from scipy.special import logit


# Ranking tiers
TIERS = [
    (1, 5),      # T1
    (6, 20),     # T2
    (21, 50),    # T3
    (51, 100),   # T4
    (101, 200),  # T5
    (201, 9999)  # T6+
]


def get_tier(rank: int) -> int:
    """Get tier index (0-5) for a given rank."""
    for i, (low, high) in enumerate(TIERS):
        if low <= rank <= high:
            return i
    return 5  # Default to lowest tier


def ranking_prior(rank_a: int, rank_b: int) -> Tuple[float, float]:
    """
    Calculate ranking-based prior probabilities.
    
    Returns:
        (p_a, p_b) where p_a is probability that player A (favorite) wins
        
    Never returns (0.5, 0.5) for unequal ranks.
    """
    tier_a = get_tier(rank_a)
    tier_b = get_tier(rank_b)
    
    # Determine favorite (lower rank = better)
    if rank_a < rank_b:
        favorite_tier = tier_a
        underdog_tier = tier_b
        a_is_favorite = True
    elif rank_b < rank_a:
        favorite_tier = tier_b
        underdog_tier = tier_a
        a_is_favorite = False
    else:
        # Equal ranks - slight edge based on other factors
        # Default to 0.52/0.48 to avoid exact 50/50
        return (0.52, 0.48)
    
    tier_gap = underdog_tier - favorite_tier
    
    # Underdog cap based on tier gap
    underdog_caps = {
        0: 0.45,  # Same tier
        1: 0.40,
        2: 0.35,
        3: 0.25,
        4: 0.15,
    }
    underdog_cap = underdog_caps.get(tier_gap, 0.10)  # 5+ gaps
    
    p_fav = 1 - underdog_cap
    p_und = underdog_cap
    
    if a_is_favorite:
        return (p_fav, p_und)
    else:
        return (p_und, p_fav)


def evidence_probability(features: Dict[str, Any]) -> float:
    """
    Enhanced probability calculation using all available features.
    """
    elo_diff = features["elo_diff"]

    # Base Elo probability
    p_elo = 1 / (1 + 10 ** (-elo_diff / 400))

    # Enhanced form adjustment with backward compatibility
    form_a = features["form_a"]
    form_b = features["form_b"]

    # Use quality-adjusted win rate if available, otherwise fall back to regular win rate
    form_a_win_rate = form_a.get("quality_adjusted_win_rate", form_a["win_rate"])
    form_b_win_rate = form_b.get("quality_adjusted_win_rate", form_b["win_rate"])
    form_factor = (form_a_win_rate - form_b_win_rate) * 0.15

    # Momentum adjustment (if available)
    momentum_a = form_a.get("recent_momentum", 0.0)
    momentum_b = form_b.get("recent_momentum", 0.0)
    momentum_factor = (momentum_a - momentum_b) * 0.1

    # Trend adjustment (if available)
    trend_a = features.get("trend_a", {}).get("trend", 0.0)
    trend_b = features.get("trend_b", {}).get("trend", 0.0)
    trend_factor = (trend_a - trend_b) * 0.1

    # Combine all factors
    p_evidence = p_elo + form_factor + momentum_factor + trend_factor
    p_evidence = np.clip(p_evidence, 0.01, 0.99)

    return p_evidence


def calculate_evidence_weight(features: Dict[str, Any]) -> float:
    """
    Calculate weight for evidence vs prior.
    
    More evidence (recent quality matches) increases weight.
    Returns value in [0.2, 1.0]
    """
    # Count recent matches
    n_a = features["form_a"]["matches_played"]
    n_b = features["form_b"]["matches_played"]
    
    # Average evidence
    n_evidence = (n_a + n_b) / 2
    
    # Weight increases with sqrt(n_evidence)
    w = np.sqrt(n_evidence) / 10
    w = np.clip(w, 0.2, 1.0)
    
    return w


def h2h_adjustment(features: Dict[str, Any], rank_a: int, rank_b: int) -> float:
    """
    Calculate H2H logit adjustment.
    
    Returns delta_logit to add to blended probability.
    Bounded effect based on sample size and recency.
    """
    h2h = features["h2h"]
    n_matches = h2h["n_matches"]
    n_eff = h2h["n_effective"]
    a_win_rate = h2h["a_win_rate"]
    
    if n_matches == 0:
        return 0.0
    
    # Time-decayed adjustment strength
    if n_eff < 2:
        strength = 0.05  # Very weak
    elif n_eff < 3:
        strength = 0.10
    elif n_eff < 5:
        strength = 0.20
    else:
        strength = 0.30  # Cap at moderate
    
    # Direction: positive if A wins more
    direction = (a_win_rate - 0.5) * 2  # Scale from [-1, 1]
    
    delta_logit = direction * strength
    
    return delta_logit


def check_override_conditions(
    features: Dict[str, Any],
    rank_a: int,
    rank_b: int,
    tier_gap: int
) -> bool:
    """
    Check if conditions warrant raising underdog cap.
    
    Returns True if at least 2 of 3 override conditions are met.
    """
    conditions_met = 0
    
    # Condition 1: Underdog Elo lead >= 180
    if rank_a > rank_b:  # A is underdog
        if features["elo_diff"] >= 180:
            conditions_met += 1
    else:  # B is underdog
        if features["elo_diff"] <= -180:
            conditions_met += 1
    
    # Condition 2: Underdog >= 70% vs top-20 in last 12m with N>=10
    # (Simplified - would need additional data)
    # For now, skip this condition in basic implementation
    
    # Condition 3: H2H N>=5 and underdog win-share >= 70%
    h2h = features["h2h"]
    if h2h["n_matches"] >= 5:
        if rank_a > rank_b and h2h["a_win_rate"] >= 0.70:
            conditions_met += 1
        elif rank_b > rank_a and h2h["a_win_rate"] <= 0.30:
            conditions_met += 1
    
    return conditions_met >= 2


def predict_match(
    features: Dict[str, Any],
    rank_a: int,
    rank_b: int,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Predict match outcome with ranking-aware model.
    
    Returns:
        {
            "winner": "A" or "B",
            "proba": {"A": float, "B": float},
            "ci95": {"A": [low, high], "B": [low, high]},
            "explain": {...}
        }
    """
    np.random.seed(seed)
    
    # Step 1: Ranking prior
    p_prior_a, p_prior_b = ranking_prior(rank_a, rank_b)
    logit_prior = logit(p_prior_a)
    
    # Step 2: Evidence probability
    p_elo = evidence_probability(features)
    logit_elo = logit(p_elo)
    
    # Step 3: Blend with evidence weight
    w = calculate_evidence_weight(features)
    logit_blend = w * logit_elo + (1 - w) * logit_prior
    
    # Step 4: H2H adjustment
    delta_h2h = h2h_adjustment(features, rank_a, rank_b)
    logit_final = logit_blend + delta_h2h
    
    # Step 5: Apply guardrails
    tier_a = get_tier(rank_a)
    tier_b = get_tier(rank_b)
    tier_gap = abs(tier_a - tier_b)
    
    p_final_a = sigmoid(logit_final)
    
    # Check if large tier gap with weak evidence
    if tier_gap >= 3:
        h2h = features["h2h"]
        if h2h["n_matches"] < 3:
            # Apply cap unless override conditions met
            if not check_override_conditions(features, rank_a, rank_b, tier_gap):
                # Determine who is underdog
                if rank_a > rank_b:  # A is underdog
                    caps = {3: 0.25, 4: 0.15}
                    cap = caps.get(tier_gap, 0.10)
                    p_final_a = min(p_final_a, cap)
                else:  # B is underdog
                    caps = {3: 0.25, 4: 0.15}
                    cap = caps.get(tier_gap, 0.10)
                    p_final_a = max(p_final_a, 1 - cap)
    
    # Ensure monotonicity: better rank should be favorite
    if rank_a < rank_b:  # A better rank
        p_final_a = max(p_final_a, 0.52)
    elif rank_b < rank_a:  # B better rank
        p_final_a = min(p_final_a, 0.48)
    
    p_final_b = 1 - p_final_a
    
    # Step 6: Bootstrap confidence intervals
    ci_a, ci_b = bootstrap_ci(p_final_a, p_final_b, n_bootstrap=500, seed=seed)
    
    # Step 7: Determine winner
    winner = "A" if p_final_a > p_final_b else "B"
    
    # Step 8: Generate explanation
    explain = generate_explanation(features, rank_a, rank_b, p_final_a, tier_gap)
    
    return {
        "winner": winner,
        "proba": {"A": round(p_final_a, 3), "B": round(p_final_b, 3)},
        "ci95": {"A": ci_a, "B": ci_b},
        "explain": explain
    }


def bootstrap_ci(
    p_a: float,
    p_b: float,
    n_bootstrap: int = 500,
    seed: int = 42
) -> Tuple[List[float], List[float]]:
    """
    Bootstrap 95% confidence intervals.
    
    Returns:
        ([low_a, high_a], [low_b, high_b])
    """
    np.random.seed(seed)
    
    # Simple bootstrapping with small perturbations
    samples_a = np.random.beta(
        max(1, p_a * 50),
        max(1, (1 - p_a) * 50),
        size=n_bootstrap
    )
    
    ci_a = [
        round(np.percentile(samples_a, 2.5), 3),
        round(np.percentile(samples_a, 97.5), 3)
    ]
    
    samples_b = 1 - samples_a
    ci_b = [
        round(np.percentile(samples_b, 2.5), 3),
        round(np.percentile(samples_b, 97.5), 3)
    ]
    
    return ci_a, ci_b


def generate_explanation(
    features: Dict[str, Any],
    rank_a: int,
    rank_b: int,
    p_final_a: float,
    tier_gap: int
) -> Dict[str, List[Dict[str, str]]]:
    """
    Generate plain English explanation of prediction drivers.
    
    Returns dict with "drivers" key containing list of driver dicts.
    """
    drivers = []
    
    # Ranking gap
    if tier_gap >= 3:
        impact = "strong"
        if rank_a < rank_b:
            note = f"Top-tier player (#{rank_a}) vs lower-ranked (#{rank_b}) strongly favors A"
        else:
            note = f"Top-tier player (#{rank_b}) vs lower-ranked (#{rank_a}) strongly favors B"
    elif tier_gap >= 1:
        impact = "moderate"
        note = f"Ranking gap (#{rank_a} vs #{rank_b}) provides edge"
    else:
        impact = "mild"
        note = f"Similar rankings (#{rank_a} vs #{rank_b})"
    
    drivers.append({
        "feature": "Ranking gap",
        "impact": f"+ {impact}" if rank_a < rank_b else f"- {impact}",
        "note": note
    })
    
    # Recent form
    form_a = features["form_a"]["win_rate"]
    form_b = features["form_b"]["win_rate"]
    form_diff = form_a - form_b
    
    if abs(form_diff) > 0.15:
        impact = "moderate"
        if form_diff > 0:
            note = f"Player A has stronger recent form ({form_a:.1%} vs {form_b:.1%})"
        else:
            note = f"Player B has stronger recent form ({form_b:.1%} vs {form_a:.1%})"
    else:
        impact = "neutral"
        note = "Both players showing similar recent form"
    
    drivers.append({
        "feature": "Recent form",
        "impact": f"+ {impact}" if form_diff > 0 else f"- {impact}",
        "note": note
    })
    
    # Head-to-head
    h2h = features["h2h"]
    if h2h["n_matches"] >= 3:
        if h2h["a_win_rate"] > 0.6:
            impact = "moderate"
            note = f"Player A leads H2H ({h2h['n_matches']} recent matches)"
        elif h2h["a_win_rate"] < 0.4:
            impact = "moderate"
            note = f"Player B leads H2H ({h2h['n_matches']} recent matches)"
        else:
            impact = "neutral"
            note = f"Even H2H record ({h2h['n_matches']} recent matches)"
    else:
        impact = "neutral"
        note = "No significant H2H history in last 24 months"
    
    drivers.append({
        "feature": "Head-to-head",
        "impact": impact,
        "note": note
    })
    
    # Elo differential
    elo_diff = features["elo_diff"]
    if abs(elo_diff) > 150:
        impact = "moderate"
        note = f"Performance rating differential favors {'A' if elo_diff > 0 else 'B'}"
        drivers.append({
            "feature": "Performance rating",
            "impact": f"+ {impact}" if elo_diff > 0 else f"- {impact}",
            "note": note
        })
    
    return {"drivers": drivers}

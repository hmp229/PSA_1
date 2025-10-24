"""Enhanced feature extraction with backward compatibility."""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import re


def extract_all_features(
    hist_a: pd.DataFrame,
    hist_b: pd.DataFrame,
    h2h_df: Optional[pd.DataFrame],
    rank_a: int,
    rank_b: int,
    player_a_name: str,
    reference_date: datetime = None
) -> Dict[str, any]:
    """
    Enhanced feature extraction with backward compatibility.
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)
    elif reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    # Ensure timezone-aware dates
    hist_a = ensure_timezone_aware(hist_a)
    hist_b = ensure_timezone_aware(hist_b)

    # Calculate enhanced Elo with opponent quality
    elo_a, elo_quality_a = calculate_enhanced_elo(hist_a, reference_date)
    elo_b, elo_quality_b = calculate_enhanced_elo(hist_b, reference_date)

    # Calculate form with backward compatibility
    form_a = calculate_enhanced_form(hist_a, n_matches=20)
    form_b = calculate_enhanced_form(hist_b, n_matches=20)

    # Calculate fatigue
    fatigue_a = calculate_fatigue(hist_a, reference_date)
    fatigue_b = calculate_fatigue(hist_b, reference_date)

    # Calculate H2H
    h2h = calculate_h2h(h2h_df, player_a_name, reference_date)

    # Additional features: recent performance trends
    trend_a = calculate_performance_trend(hist_a, reference_date, weeks=12)
    trend_b = calculate_performance_trend(hist_b, reference_date, weeks=12)

    return {
        "elo_a": elo_a,
        "elo_b": elo_b,
        "elo_diff": elo_a - elo_b,
        "elo_quality_a": elo_quality_a,
        "elo_quality_b": elo_quality_b,
        "rank_a": rank_a,
        "rank_b": rank_b,
        "form_a": form_a,
        "form_b": form_b,
        "fatigue_a": fatigue_a,
        "fatigue_b": fatigue_b,
        "h2h": h2h,
        "trend_a": trend_a,
        "trend_b": trend_b
    }


def ensure_timezone_aware(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame date column is timezone-aware."""
    if df.empty or 'date' not in df.columns:
        return df

    df = df.copy()
    if df['date'].dt.tz is None:
        df['date'] = df['date'].dt.tz_localize(timezone.utc)

    return df


def calculate_enhanced_elo(hist: pd.DataFrame, reference_date: datetime, base_elo: int = 1500) -> Tuple[float, float]:
    """Calculate Elo with opponent quality weighting."""
    if hist.empty:
        return float(base_elo), 0.0

    elo = base_elo
    K = 32
    HALF_LIFE_DAYS = 180

    # Track opponent quality
    opponent_quality_scores = []

    for _, match in hist.iterrows():
        match_date = match['date']
        if match_date.tzinfo is None:
            match_date = match_date.replace(tzinfo=timezone.utc)

        days_ago = (reference_date - match_date).days
        weight = 0.5 ** (days_ago / HALF_LIFE_DAYS)

        # Estimate opponent strength from match score
        opponent_strength = estimate_opponent_strength(match)
        opponent_quality_scores.append(opponent_strength * weight)

        # Adjust K-factor based on opponent strength
        adjusted_K = K * (1 + 0.5 * opponent_strength)  # Stronger opponents matter more

        if match['result'] == 'W':
            elo += adjusted_K * weight
        else:
            elo -= adjusted_K * weight * 0.5

    avg_opponent_quality = np.mean(opponent_quality_scores) if opponent_quality_scores else 0.0

    return float(max(1000, min(2500, elo))), float(avg_opponent_quality)


def estimate_opponent_strength(match: pd.Series) -> float:
    """Estimate opponent strength from match score and context."""
    games_won = match['games_won']
    games_lost = match['games_lost']
    total_games = games_won + games_lost

    if total_games == 0:
        return 0.5

    # Close matches against good opponents are better indicators
    score_ratio = games_won / total_games

    # Analyze score string for more granular info
    score_quality = analyze_score_quality(match.get('score', ''))

    # Combine factors
    strength = (score_ratio * 0.7) + (score_quality * 0.3)

    return min(1.0, max(0.0, strength))


def analyze_score_quality(score_str: str) -> float:
    """Analyze score string for match competitiveness."""
    if not score_str:
        return 0.5

    try:
        # Parse scores like "11-8, 11-9, 5-11, 11-7"
        games = score_str.split(', ')
        close_games = 0
        total_games = len(games)

        for game in games:
            if '-' in game:
                p1_score, p2_score = map(int, game.split('-'))
                score_diff = abs(p1_score - p2_score)
                if score_diff <= 3:  # Close game
                    close_games += 1

        return close_games / total_games if total_games > 0 else 0.5
    except:
        return 0.5


def calculate_enhanced_form(hist: pd.DataFrame, n_matches: int = 20) -> Dict[str, float]:
    """Calculate form with backward compatibility."""
    if hist.empty:
        return {
            "win_rate": 0.5,
            "avg_game_diff": 0.0,
            "matches_played": 0,
            "quality_adjusted_win_rate": 0.5,  # New field
            "recent_momentum": 0.0  # New field
        }

    recent = hist.head(n_matches)

    # Basic stats (backward compatible)
    wins = (recent['result'] == 'W').sum()
    total = len(recent)
    win_rate = wins / total if total > 0 else 0.5

    # Game differential
    game_diffs = recent['games_won'] - recent['games_lost']
    avg_game_diff = float(game_diffs.mean()) if not game_diffs.empty else 0.0

    # Quality-adjusted win rate (new enhanced feature)
    quality_scores = []
    for _, match in recent.iterrows():
        strength = estimate_opponent_strength(match)
        if match['result'] == 'W':
            quality_scores.append(1.0 * (1 + strength))
        else:
            quality_scores.append(0.0)

    quality_win_rate = np.mean(quality_scores) / 1.5 if quality_scores else 0.5  # Normalize

    # Recent momentum (new enhanced feature)
    momentum_matches = min(5, len(recent))
    if momentum_matches > 0:
        recent_wins = (recent.head(momentum_matches)['result'] == 'W').sum()
        momentum = (recent_wins / momentum_matches) - 0.5
    else:
        momentum = 0.0

    return {
        "win_rate": float(win_rate),  # Backward compatible
        "avg_game_diff": avg_game_diff,  # Backward compatible
        "matches_played": int(total),  # Backward compatible
        "quality_adjusted_win_rate": float(quality_win_rate),  # Enhanced
        "recent_momentum": float(momentum)  # Enhanced
    }


def calculate_performance_trend(hist: pd.DataFrame, reference_date: datetime, weeks: int = 12) -> Dict[str, float]:
    """Calculate performance trend over recent weeks."""
    if hist.empty:
        return {"trend": 0.0, "consistency": 0.5}

    cutoff = reference_date - timedelta(weeks=weeks)
    recent_matches = hist[hist['date'] >= cutoff]

    if len(recent_matches) < 3:
        return {"trend": 0.0, "consistency": 0.5}

    # Calculate win rate by 2-week periods
    periods = []
    for i in range(weeks // 2):
        period_start = cutoff + timedelta(weeks=i*2)
        period_end = period_start + timedelta(weeks=2)

        period_matches = recent_matches[
            (recent_matches['date'] >= period_start) &
            (recent_matches['date'] < period_end)
        ]

        if len(period_matches) > 0:
            win_rate = (period_matches['result'] == 'W').mean()
            periods.append(win_rate)

    if len(periods) >= 2:
        # Calculate trend (slope of win rates over time)
        x = np.arange(len(periods))
        y = np.array(periods)
        trend = float(np.polyfit(x, y, 1)[0])  # Slope of linear fit

        # Calculate consistency (inverse of variance)
        consistency = 1.0 - float(np.var(y))
    else:
        trend = 0.0
        consistency = 0.5

    return {
        "trend": trend,
        "consistency": max(0.0, min(1.0, consistency))
    }


def calculate_fatigue(hist: pd.DataFrame, reference_date: datetime) -> Dict[str, int]:
    """Calculate fatigue from recent match density."""
    if hist.empty:
        return {
            "matches_last_14d": 0,
            "matches_last_30d": 0
        }

    # Ensure reference_date is timezone-aware
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    # Ensure date column is timezone-aware
    dates = hist['date'].copy()
    if dates.dt.tz is None:
        dates = dates.dt.tz_localize(timezone.utc)

    cutoff_14d = reference_date - timedelta(days=14)
    cutoff_30d = reference_date - timedelta(days=30)

    matches_14d = (dates >= cutoff_14d).sum()
    matches_30d = (dates >= cutoff_30d).sum()

    return {
        "matches_last_14d": int(matches_14d),
        "matches_last_30d": int(matches_30d)
    }


def calculate_h2h(
    h2h_df: Optional[pd.DataFrame],
    player_a_name: str,
    reference_date: datetime
) -> Dict[str, float]:
    """Calculate head-to-head statistics."""
    if h2h_df is None or h2h_df.empty:
        return {
            "n_matches": 0,
            "n_effective": 0.0,
            "a_win_rate": 0.5,
            "avg_game_diff_a": 0.0,
            "days_since_last": 9999
        }

    # Ensure reference_date is timezone-aware
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    # Ensure date column is timezone-aware
    if h2h_df['date'].dt.tz is None:
        h2h_df = h2h_df.copy()
        h2h_df['date'] = h2h_df['date'].dt.tz_localize(timezone.utc)

    n_matches = len(h2h_df)

    # Time-weighted effective sample size (last 24 months most relevant)
    cutoff = reference_date - timedelta(days=730)
    recent_h2h = h2h_df[h2h_df['date'] >= cutoff]

    # Calculate time decay weights
    if not recent_h2h.empty:
        days_ago = (reference_date - recent_h2h['date']).dt.days
        weights = 0.5 ** (days_ago / 365)
        n_effective = float(weights.sum())
    else:
        n_effective = 0.0

    # Win rate for player A
    a_wins = (h2h_df['winner'] == 'A').sum()
    a_win_rate = a_wins / n_matches if n_matches > 0 else 0.5

    # Average game differential
    game_diffs = h2h_df['games_won'] - h2h_df['games_lost']
    # Flip sign for B wins
    game_diffs = game_diffs * h2h_df['winner'].apply(lambda x: 1 if x == 'A' else -1)
    avg_game_diff = float(game_diffs.mean()) if not game_diffs.empty else 0.0

    # Days since last H2H
    most_recent = h2h_df['date'].max()
    if pd.notna(most_recent):
        days_since = (reference_date - most_recent).days
    else:
        days_since = 9999

    return {
        "n_matches": int(n_matches),
        "n_effective": float(n_effective),
        "a_win_rate": float(a_win_rate),
        "avg_game_diff_a": avg_game_diff,
        "days_since_last": int(days_since)
    }
"""Main FastAPI application with real PSA data integration."""
import asyncio
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from predict import (
    players,
    fetch,
    features,
    model,
    schemas
)
from predict import rankings as rank_module

# Create FastAPI app
app = FastAPI(
    title="PSA Match Predictor",
    description="Real-time PSA squash match prediction with ranking-aware model",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# ... existing imports ...

@app.get("/api/predict")
async def predict_match(
        playerA: str = Query(..., description="Player A name"),
        playerB: str = Query(..., description="Player B name"),
        event_date: Optional[str] = Query(None, description="Event date (YYYY-MM-DD)"),
        no_cache: bool = Query(False, description="Bypass cache"),
        seed: int = Query(42, description="Random seed for reproducibility")
):
    """
    Predict squash match outcome using real PSA data.

    This endpoint:
    1. Resolves player names from PSA ranked players (strict matching)
    2. Fetches current rankings and points from PSA API
    3. Retrieves match history for both players (last 24 months) from multiple sources
    4. Calculates head-to-head record
    5. Extracts features (Elo, form, fatigue, H2H)
    6. Runs ranking-aware prediction model
    7. Returns probabilities with 95% confidence intervals

    Returns 400 if player not found with suggestions.
    Returns 503 if PSA data unavailable.
    """
    use_cache = not no_cache
    sources = []
    warnings = []

    try:
        # ================================================================
        # STEP 1: Resolve player names from PSA (strict - must exist)
        # ================================================================
        try:
            resolved = await players.resolve_both_players(playerA, playerB, use_cache=use_cache)
            player_a_canonical = resolved["A"]["canonical"]
            player_b_canonical = resolved["B"]["canonical"]
            player_a_id = resolved["A"]["id"]
            player_b_id = resolved["B"]["id"]

            sources.append(resolved["A"]["profile_url"])
            sources.append(resolved["B"]["profile_url"])

            print(
                f"✅ Resolved players: {player_a_canonical} (ID: {player_a_id}) vs {player_b_canonical} (ID: {player_b_id})")

        except players.PlayerNotFoundError as e:
            # Return 400 with suggestions for correction
            detail = {
                "code": "PLAYER_NOT_FOUND",
                "message": str(e)
            }
            if e.suggestions:
                detail["suggestions"] = e.suggestions
            raise HTTPException(status_code=400, detail=detail)

        # ================================================================
        # STEP 2: Fetch current rankings from PSA API
        # ================================================================
        try:
            rank_snapshot_a = await rank_module.get_ranking_snapshot_psa(
                player_a_canonical,
                use_cache=use_cache
            )
            rank_snapshot_b = await rank_module.get_ranking_snapshot_psa(
                player_b_canonical,
                use_cache=use_cache
            )

            rank_a = rank_snapshot_a.rank
            rank_b = rank_snapshot_b.rank

            sources.append("https://psa-api.ptsportsuite.com/rankedplayers/male")

            print(f"✅ Rankings: {player_a_canonical} (#{rank_a}), {player_b_canonical} (#{rank_b})")

        except schemas.UpstreamParseError as e:
            # Return 503 if PSA data unavailable
            raise HTTPException(status_code=503, detail={
                "code": "UPSTREAM_UNAVAILABLE",
                "message": "PSA ranking data unavailable or invalid."
            })

        # ================================================================
        # STEP 3: Fetch match histories (last 24 months) - ENHANCED
        # ================================================================
        hist_a = None
        hist_b = None

        try:
            async with asyncio.timeout(45):  # Increased timeout for comprehensive scraping
                # Use extended history that includes PSA website scraping
                hist_a = await fetch.get_extended_match_history(
                    player_a_canonical,
                    player_a_id,
                    use_cache=use_cache,
                    months_back=24
                )
                hist_b = await fetch.get_extended_match_history(
                    player_b_canonical,
                    player_b_id,
                    use_cache=use_cache,
                    months_back=24
                )

                if hist_a is not None and not hist_a.empty:
                    sources.append(f"https://psaworldtour.com/players/{player_a_id}")
                    match_sources = hist_a['source'].value_counts().to_dict()
                    source_summary = ", ".join([f"{count} from {source}" for source, count in match_sources.items()])
                    warnings.append(f"Using {len(hist_a)} matches for {player_a_canonical} ({source_summary})")
                    print(f"✅ Player A history: {len(hist_a)} matches from {list(match_sources.keys())}")
                else:
                    warnings.append(f"No match data available for {player_a_canonical}")
                    print(f"❌ No history for Player A")

                if hist_b is not None and not hist_b.empty:
                    sources.append(f"https://psaworldtour.com/players/{player_b_id}")
                    match_sources = hist_b['source'].value_counts().to_dict()
                    source_summary = ", ".join([f"{count} from {source}" for source, count in match_sources.items()])
                    warnings.append(f"Using {len(hist_b)} matches for {player_b_canonical} ({source_summary})")
                    print(f"✅ Player B history: {len(hist_b)} matches from {list(match_sources.keys())}")
                else:
                    warnings.append(f"No match data available for {player_b_canonical}")
                    print(f"❌ No history for Player B")

        except (asyncio.TimeoutError, Exception) as e:
            warnings.append(f"Match history fetch failed: {str(e)}")
            print(f"❌ History fetch error: {e}")

        # ================================================================
        # STEP 4: Fetch head-to-head record
        # ================================================================
        h2h_df = None

        try:
            async with asyncio.timeout(8):  # Slightly increased timeout for H2H
                h2h_df = await fetch.get_h2h(
                    player_a_canonical,
                    player_a_id,
                    player_b_canonical,
                    player_b_id,
                    use_cache=use_cache,
                    months_back=24
                )

                if h2h_df is not None and not h2h_df.empty:
                    h2h_wins = len(h2h_df[h2h_df['result'] == 'W'])
                    h2h_total = len(h2h_df)
                    warnings.append(f"H2H: {h2h_wins}-{h2h_total - h2h_wins} in last 24 months")
                    print(f"✅ H2H: Found {h2h_total} matches ({h2h_wins} wins for {player_a_canonical})")
                else:
                    warnings.append("No recent H2H matches found")
                    print("ℹ️  No H2H matches found")

        except (asyncio.TimeoutError, Exception) as e:
            warnings.append(f"H2H data unavailable: {str(e)}")
            print(f"❌ H2H fetch error: {e}")

        # ================================================================
        # STEP 5: Extract features from data
        # ================================================================
        if hist_a is not None and hist_b is not None and not hist_a.empty and not hist_b.empty:
            # Use real match history for feature extraction
            try:
                feature_dict = features.extract_all_features(
                    hist_a,
                    hist_b,
                    h2h_df,
                    rank_a,
                    rank_b,
                    player_a_canonical,
                    reference_date=datetime.now()
                )

                # Add info about data quality
                data_quality = "comprehensive" if len(hist_a) > 10 and len(hist_b) > 10 else "limited"
                warnings.append(f"Using {data_quality} match data for prediction")

                print(f"✅ Feature extraction successful - {data_quality} data")

            except Exception as e:
                # Fallback to ranking-only if feature extraction fails
                warnings.append(f"Feature extraction failed: {str(e)}")
                elo_a = max(1000, 2200 - (rank_a * 5))
                elo_b = max(1000, 2200 - (rank_b * 5))

                feature_dict = {
                    "elo_a": elo_a,
                    "elo_b": elo_b,
                    "elo_diff": elo_a - elo_b,
                    "rank_a": rank_a,
                    "rank_b": rank_b,
                    "form_a": {"win_rate": 0.6, "avg_game_diff": 0.5, "matches_played": 0},
                    "form_b": {"win_rate": 0.55, "avg_game_diff": 0.3, "matches_played": 0},
                    "fatigue_a": {"matches_last_14d": 0, "matches_last_30d": 0},
                    "fatigue_b": {"matches_last_14d": 0, "matches_last_30d": 0},
                    "h2h": {
                        "n_matches": 0,
                        "n_effective": 0.0,
                        "a_win_rate": 0.5,
                        "avg_game_diff_a": 0.0,
                        "days_since_last": 9999
                    }
                }
                warnings.append("Using ranking-based prediction (feature extraction failed)")
                print("⚠️  Using fallback ranking-based features")
        else:
            # No match history available - use ranking-only prediction
            elo_a = max(1000, 2200 - (rank_a * 5))
            elo_b = max(1000, 2200 - (rank_b * 5))

            feature_dict = {
                "elo_a": elo_a,
                "elo_b": elo_b,
                "elo_diff": elo_a - elo_b,
                "rank_a": rank_a,
                "rank_b": rank_b,
                "form_a": {"win_rate": 0.6, "avg_game_diff": 0.5, "matches_played": 0},
                "form_b": {"win_rate": 0.55, "avg_game_diff": 0.3, "matches_played": 0},
                "fatigue_a": {"matches_last_14d": 0, "matches_last_30d": 0},
                "fatigue_b": {"matches_last_14d": 0, "matches_last_30d": 0},
                "h2h": {
                    "n_matches": 0,
                    "n_effective": 0.0,
                    "a_win_rate": 0.5,
                    "avg_game_diff_a": 0.0,
                    "days_since_last": 9999
                }
            }
            warnings.append("Using ranking-based prediction (match history unavailable)")
            print("⚠️  Using ranking-only prediction (no match history)")

        # ================================================================
        # STEP 6: Run prediction model
        # ================================================================
        prediction = model.predict_match(feature_dict, rank_a, rank_b, seed=seed)
        print(
            f"✅ Prediction complete: {player_a_canonical} {prediction['proba']['A']:.1%} vs {player_b_canonical} {prediction['proba']['B']:.1%}")

        # ================================================================
        # STEP 7: Fetch event information if date provided
        # ================================================================
        event_info = None

        if event_date:
            try:
                async with asyncio.timeout(3):
                    event_data = await fetch.get_calendar_by_date(event_date, use_cache=use_cache)

                    if event_data:
                        event_info = event_data
                        if event_data.get("url"):
                            sources.append(event_data["url"])
                        print(f"✅ Event found: {event_data.get('name', 'Unknown')}")
                    else:
                        warnings.append(f"No PSA event found for date {event_date}")
                        print(f"ℹ️  No event found for {event_date}")

            except (asyncio.TimeoutError, Exception) as e:
                warnings.append(f"Event data unavailable: {str(e)}")
                print(f"❌ Event fetch error: {e}")

        # ================================================================
        # STEP 8: Build and return response
        # ================================================================
        # ================================================================
        # STEP 8: Build and return response
        # ================================================================
        # Collect all match sources for data quality reporting
        match_sources_used = set()
        if hist_a is not None and not hist_a.empty and 'source' in hist_a.columns:
            match_sources_used.update(hist_a['source'].unique())
        if hist_b is not None and not hist_b.empty and 'source' in hist_b.columns:
            match_sources_used.update(hist_b['source'].unique())

        response = {
            "playerA": player_a_canonical,
            "playerB": player_b_canonical,
            "resolved": {
                "A": {
                    "canonical": resolved["A"]["canonical"],
                    "profile_url": resolved["A"]["profile_url"],
                    "id": player_a_id
                },
                "B": {
                    "canonical": resolved["B"]["canonical"],
                    "profile_url": resolved["B"]["profile_url"],
                    "id": player_b_id
                }
            },
            "event": event_info,
            "ranking": {
                "A": {
                    "rank": rank_a,
                    "points": rank_snapshot_a.points,
                    "snapshot": str(rank_snapshot_a.snapshot_date)
                },
                "B": {
                    "rank": rank_b,
                    "points": rank_snapshot_b.points,
                    "snapshot": str(rank_snapshot_b.snapshot_date)
                }
            },
            "match_data_quality": {
                "player_a_matches": len(hist_a) if hist_a is not None and not hist_a.empty else 0,
                "player_b_matches": len(hist_b) if hist_b is not None and not hist_b.empty else 0,
                "h2h_matches": len(h2h_df) if h2h_df is not None and not h2h_df.empty else 0,
                "sources_used": list(match_sources_used)
            },
            "summary": {
                "winner": prediction["winner"],
                "proba": prediction["proba"],
                "ci95": prediction["ci95"]
            },
            "explain": prediction["explain"],
            "sources": list(set(sources)),  # Deduplicate
            "warnings": warnings
        }

        return response

    except HTTPException:
        # Re-raise HTTP exceptions (400, 503)
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Unexpected error in predict_match: {e}")
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}"
            }
        )


# ... rest of your app.py remains the same ...


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
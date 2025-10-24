"""PSA rankings data fetching with proper imports."""
import asyncio
import json
from datetime import datetime, date
from typing import List, Dict, Optional

# Fix imports
try:
    from . import cache
    from . import schemas
except ImportError:
    # For direct execution
    import cache
    import schemas

import httpx

PSA_API_BASE = "https://psa-api.ptsportsuite.com"


async def get_all_ranked_players(gender: str = "male", use_cache: bool = True) -> List[Dict]:
    """
    Get all ranked players for a given gender from PSA API.

    Args:
        gender: "male" or "female"
        use_cache: Whether to use cached data

    Returns:
        List of player dictionaries
    """
    url = f"{PSA_API_BASE}/rankedplayers/{gender}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            players = response.json()
            return players
        except Exception as e:
            print(f"Error fetching {gender} rankings: {e}")
            return []


async def get_ranking_snapshot_psa(player_name: str, use_cache: bool = True) -> schemas.RankingSnapshot:
    """
    Get current ranking snapshot for a player.

    Returns:
        RankingSnapshot with rank, points, and snapshot date
    """
    # Search in both men's and women's rankings
    for gender in ["male", "female"]:
        players = await get_all_ranked_players(gender, use_cache)

        for player in players:
            if player.get("Name", "").lower() == player_name.lower():
                return schemas.RankingSnapshot(
                    rank=player.get("World Ranking", 999),
                    points=player.get("Total Points", 0),
                    snapshot_date=datetime.now().date()  # FIX: Use .date() instead of datetime
                )

    # Player not found in rankings - return default with high rank
    return schemas.RankingSnapshot(
        rank=999,
        points=0,
        snapshot_date=datetime.now().date()  # FIX: Use .date() here too
    )


async def search_player_in_rankings(player_name: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Search for a player in PSA rankings and return their data.

    Args:
        player_name: Name to search for
        use_cache: Whether to use cached data

    Returns:
        Player data if found, None otherwise
    """
    for gender in ["male", "female"]:
        players = await get_all_ranked_players(gender, use_cache)

        for player in players:
            if player.get("Name", "").lower() == player_name.lower():
                return {
                    **player,
                    "gender": gender
                }

    return None


async def get_player_rank_and_points(player_name: str, use_cache: bool = True) -> tuple[int, float]:
    """
    Get just the rank and points for a player.

    Returns:
        Tuple of (rank, points)
    """
    snapshot = await get_ranking_snapshot_psa(player_name, use_cache)
    return snapshot.rank, snapshot.points


# For direct testing
if __name__ == "__main__":
    async def test():
        # Test getting all players
        players = await get_all_ranked_players("male", use_cache=False)
        print(f"Found {len(players)} male players")
        if players:
            print(f"First player: {players[0]['Name']} - Rank {players[0]['World Ranking']}")

        # Test getting specific player snapshot
        test_players = ["Ali Farag", "Paul Coll", "Joel Makin"]
        for test_player in test_players:
            snapshot = await get_ranking_snapshot_psa(test_player, use_cache=False)
            print(f"{test_player}: Rank {snapshot.rank}, Points {snapshot.points}, Date {snapshot.snapshot_date}")
            print(f"Snapshot type: {type(snapshot.snapshot_date)}")

    asyncio.run(test())
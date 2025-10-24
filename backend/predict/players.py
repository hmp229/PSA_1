"""Strict PSA-only player name resolution using official API."""
import unicodedata
from typing import Dict, List

# Fix imports - try relative first, then absolute
try:
    from . import rankings
except ImportError:
    # For direct execution
    import rankings


def normalize_name(name: str) -> str:
    """Normalize name: lowercase, strip accents, trim whitespace."""
    name = name.strip().lower()
    # Remove accents
    name = ''.join(
        c for c in unicodedata.normalize('NFD', name)
        if unicodedata.category(c) != 'Mn'
    )
    return name


class PlayerResolutionError(Exception):
    """Base exception for player resolution errors."""
    pass


class PlayerNotFoundError(PlayerResolutionError):
    """Player not found in PSA sources."""
    def __init__(self, player_name: str, suggestions: List[Dict[str, str]] = None):
        self.player_name = player_name
        self.suggestions = suggestions or []
        super().__init__(f"Player '{player_name}' not found on the official PSA website.")


async def resolve_player_psa_exact(raw_name: str, use_cache: bool = True) -> Dict[str, str]:
    """
    Resolve player name strictly from PSA ranked players API.

    Returns:
        {
            "id": str,
            "canonical": str,
            "profile_url": str
        }

    Raises:
        PlayerNotFoundError: If not found on PSA (400)
    """
    normalized = normalize_name(raw_name)

    # Search in both men's and women's rankings
    suggestions = []

    for gender in ["male", "female"]:
        players = await rankings.get_all_ranked_players(gender, use_cache)

        for player in players:
            player_name = player.get("Name", "")
            player_id = player.get("Id", "")

            if not player_name:
                continue

            norm_candidate = normalize_name(player_name)

            # Exact match
            if norm_candidate == normalized:
                return {
                    "id": str(player_id),
                    "canonical": player_name,
                    "profile_url": f"https://psaworldtour.com/players/{player_id}"
                }

            # Partial match for suggestions
            elif normalized in norm_candidate or norm_candidate in normalized:
                suggestions.append({
                    "name": player_name,
                    "url": f"https://psaworldtour.com/players/{player_id}",
                    "rank": player.get("World Ranking", 999)
                })

    # No exact match found - return suggestions
    # Sort suggestions by rank
    suggestions = sorted(suggestions, key=lambda x: x.get("rank", 999))[:5]

    raise PlayerNotFoundError(raw_name, suggestions)


async def resolve_both_players(
    player_a: str,
    player_b: str,
    use_cache: bool = True
) -> Dict[str, Dict[str, str]]:
    """
    Resolve both players from PSA.

    Raises PlayerNotFoundError if either fails.
    """
    resolved_a = await resolve_player_psa_exact(player_a, use_cache)
    resolved_b = await resolve_player_psa_exact(player_b, use_cache)

    return {
        "A": resolved_a,
        "B": resolved_b
    }

# For direct testing
if __name__ == "__main__":
    async def test():
        try:
            result = await resolve_player_psa_exact("Ali Farag", use_cache=False)
            print(f"Found: {result}")
        except Exception as e:
            print(f"Error: {e}")

    import asyncio
    asyncio.run(test())
"""Enhanced match history fetching with multiple data sources."""
import asyncio
import random
import time
import json
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd

# Import modules directly - no relative imports
try:
    import cache
    from squashinfo import get_squashinfo_match_history
    from squashlevels import get_squashlevels_match_history
    # Import the PSA website scraper
    from scraper import get_psa_website_match_history, scrape_player_match_history
except ImportError as e:
    print(f"Import warning: {e}")


    # Create dummy functions if imports fail
    async def get_squashinfo_match_history(*args, **kwargs):
        return pd.DataFrame()


    async def get_squashlevels_match_history(*args, **kwargs):
        return pd.DataFrame()


    async def get_psa_website_match_history(*args, **kwargs):
        return pd.DataFrame()


    async def scrape_player_match_history(*args, **kwargs):
        return pd.DataFrame()

# Rate limiting
_last_request_time = 0
_rate_limit_lock = asyncio.Lock()

USER_AGENT = "PSA-Predictor/1.0 (Educational)"
TIMEOUT = 10.0
MAX_RETRIES = 3
RETRY_BACKOFF = [0.5, 1.0, 2.0]

PSA_API_BASE = "https://psa-api.ptsportsuite.com"


@asynccontextmanager
async def get_http_client():
    """Get configured HTTP client."""
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True
    ) as client:
        yield client


async def rate_limited_request(
    client: httpx.AsyncClient,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    use_cache: bool = True,
) -> str:
    """Execute rate-limited HTTP GET with retries and caching."""
    global _last_request_time

    # Check cache first
    if use_cache:
        cached = cache.get_cached(url, params)
        if cached:
            return cached

    # Rate limit: ~1 req/sec + jitter
    async with _rate_limit_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < 1.0:
            sleep_time = 1.0 - elapsed + random.uniform(0, 0.3)
            await asyncio.sleep(sleep_time)

        # Retry logic
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                content = response.text

                # Cache successful response
                if use_cache:
                    cache.set_cached(url, content, params)

                _last_request_time = time.time()
                return content

            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF[attempt])
                else:
                    raise httpx.HTTPError(f"Failed after {MAX_RETRIES} retries: {e}")

        _last_request_time = time.time()
        raise httpx.HTTPError(f"Failed to fetch {url}: {last_error}")


# In fetch.py - update the get_match_history function
async def get_match_history(
    player_canonical: str,
    player_id: str,
    use_cache: bool = True,
    months_back: int = 24
) -> pd.DataFrame:
    """
    Fetch match history using multiple data sources.
    Priority: PSA Website -> PSA API -> SquashLevels -> SquashInfo
    """
    print(f"\n=== Fetching match history for {player_canonical} ===")

    # Try PSA Website scraper first (direct URL approach)
    print("🔄 Trying PSA Website Scraper (direct URL)...")
    try:
        psa_website_history = await get_psa_website_match_history(player_canonical, months_back)
        if not psa_website_history.empty:
            print(f"✅ Using {len(psa_website_history)} matches from PSA Website")
            return psa_website_history
        else:
            print("❌ PSA Website: No matches found")
    except Exception as e:
        print(f"❌ PSA Website error: {e}")

    # Rest of your existing code remains the same...
    # Try PSA API, SquashLevels, SquashInfo...


async def get_extended_match_history(
        player_canonical: str,
        player_id: str,
        use_cache: bool = True,
        months_back: int = 24
) -> pd.DataFrame:
    """
    Get extended match history by combining all available sources.
    """
    print(f"🔍 Getting extended history for {player_canonical}...")

    all_matches = []

    # Get from all sources - PSA Website first
    sources = [
        ("PSA Website", get_psa_website_match_history(player_canonical, months_back)),
        ("PSA Direct ID", scrape_player_match_history(player_id, player_canonical, months_back)),
        ("PSA API", _get_api_match_history(player_canonical, player_id, use_cache, months_back)),
        ("SquashLevels", get_squashlevels_match_history(player_canonical, months_back)),
        ("SquashInfo", get_squashinfo_match_history(player_canonical, months_back)),
    ]

    for source_name, source_coro in sources:
        try:
            matches = await source_coro
            if not matches.empty:
                print(f"✅ {source_name}: {len(matches)} matches")
                # Add source identifier
                matches['source'] = source_name.lower().replace(' ', '_')
                all_matches.append(matches)
            else:
                print(f"❌ {source_name}: No matches")
        except Exception as e:
            print(f"❌ {source_name} error: {e}")

    if all_matches:
        # Combine all matches, remove duplicates based on date + opponent
        combined = pd.concat(all_matches, ignore_index=True)

        # Remove duplicates (same date and similar opponent name)
        combined = combined.drop_duplicates(
            subset=['date', 'opponent'],
            keep='first'
        ).sort_values('date', ascending=False).reset_index(drop=True)

        print(f"🎯 Combined total: {len(combined)} unique matches")
        return combined
    else:
        return pd.DataFrame()


# Add this new function for better player matching
async def _get_psa_website_history_with_fallback(
        player_canonical: str,
        player_id: str,
        months_back: int = 24
) -> pd.DataFrame:
    """
    Get match history from PSA website with multiple fallback strategies.
    """
    # Try website search first
    website_history = await get_psa_website_match_history(player_canonical, months_back)
    if not website_history.empty:
        return website_history

    # Try direct ID approach
    direct_history = await scrape_player_match_history(player_id, player_canonical, months_back)
    if not direct_history.empty:
        return direct_history

    return pd.DataFrame()


async def _get_api_match_history(
    player_canonical: str,
    player_id: str,
    use_cache: bool = True,
    months_back: int = 24
) -> pd.DataFrame:
    """
    Get match history from PSA API (limited to recent matches).
    """
    url = f"{PSA_API_BASE}/results"

    async with get_http_client() as client:
        try:
            html = await rate_limited_request(client, url, params=None, use_cache=use_cache)
            all_matches = json.loads(html)

            print(f"✓ API returned {len(all_matches)} total recent matches")

            if not all_matches:
                return pd.DataFrame()

            # Parse matches - filter for our player
            parsed_matches = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=months_back * 30)

            matches_found = 0
            for match in all_matches:
                try:
                    # Parse date
                    match_date_str = match.get("date", "")
                    if not match_date_str:
                        continue

                    match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
                    if match_date < cutoff_date:
                        continue

                    # Find our player
                    players = match.get("players", [])
                    player_idx = None
                    for idx, p in enumerate(players):
                        if str(p.get("id")) == str(player_id):
                            player_idx = idx
                            break

                    if player_idx is None:
                        continue

                    # Parse match details
                    opponent_idx = 1 - player_idx
                    player_data = players[player_idx]
                    opponent_data = players[opponent_idx]

                    games_won = player_data.get("games", 0)
                    games_lost = opponent_data.get("games", 0)
                    result = "W" if games_won > games_lost else "L"

                    player_scores = player_data.get("scores", [])
                    opponent_scores = opponent_data.get("scores", [])
                    score_parts = [f"{p}-{o}" for p, o in zip(player_scores, opponent_scores)]
                    score = ", ".join(score_parts) if score_parts else f"{games_won}-{games_lost}"

                    parsed_matches.append({
                        "date": match_date,
                        "opponent": opponent_data.get("name", "Unknown"),
                        "opponent_id": opponent_data.get("id"),
                        "result": result,
                        "score": score,
                        "games_won": games_won,
                        "games_lost": games_lost,
                        "event": match.get("tournament", ""),
                        "round": match.get("round", ""),
                        "match_id": match.get("matchId")
                    })
                    matches_found += 1

                except Exception:
                    continue

            print(f"✓ Found {matches_found} matches in API data")

            if parsed_matches:
                df = pd.DataFrame(parsed_matches)
                df = df.sort_values("date", ascending=False).reset_index(drop=True)
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            print(f"✗ API error: {e}")
            return pd.DataFrame()


async def test():
    """Test the enhanced fetch module with PSA website integration."""
    print("Testing enhanced fetch module with PSA website integration...")

    # Test with a known player
    test_player = "Paul Coll"
    test_id = "2778"

    print(f"\nTesting PSA website scraper for {test_player}...")
    psa_website_history = await get_psa_website_match_history(test_player, months_back=6)
    print(f"PSA Website history: {len(psa_website_history)} matches")

    print(f"\nTesting basic match history for {test_player}...")
    basic_history = await get_match_history(test_player, test_id, use_cache=False, months_back=6)
    print(f"Basic history: {len(basic_history)} matches")

    print(f"\nTesting extended match history for {test_player}...")
    extended_history = await get_extended_match_history(test_player, test_id, use_cache=False, months_back=6)
    print(f"Extended history: {len(extended_history)} matches")

    if not extended_history.empty:
        print("\nSample matches:")
        for i, row in extended_history.head(3).iterrows():
            source = row.get('source', 'unknown')
            print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']} [{source}]")


async def get_h2h(
    player_a_canonical: str,
    player_a_id: str,
    player_b_canonical: str,
    player_b_id: str,
    use_cache: bool = True,
    months_back: int = 24
) -> pd.DataFrame:
    """
    Get head-to-head match history between two players.
    """
    # Get player A's matches
    hist_a = await get_match_history(player_a_canonical, player_a_id, use_cache, months_back)

    if hist_a.empty:
        return pd.DataFrame()

    # Filter for matches against player B
    h2h = hist_a[hist_a["opponent_id"] == int(player_b_id)].copy()

    if h2h.empty:
        return pd.DataFrame()

    # Add winner column
    h2h["winner"] = h2h["result"].apply(lambda x: "A" if x == "W" else "B")

    print(f"✓ Found {len(h2h)} H2H matches between {player_a_canonical} and {player_b_canonical}")
    return h2h


async def get_calendar_by_date(date_str: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Find tournament/event by date from PSA API.
    """
    url = f"{PSA_API_BASE}/tournaments/current"

    async with get_http_client() as client:
        try:
            html = await rate_limited_request(client, url, use_cache=use_cache)
            tournaments = json.loads(html)

            query_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            for tournament in tournaments:
                try:
                    # Parse dates
                    start_str = tournament.get("Start", "")
                    end_str = tournament.get("End", "")

                    if not start_str or not end_str:
                        continue

                    start_date = datetime.strptime(start_str, "%d-%m-%Y").date()
                    end_date = datetime.strptime(end_str, "%d-%m-%Y").date()

                    # Check if query date falls within tournament
                    if start_date <= query_date <= end_date:
                        # Parse location
                        location = tournament.get("Location", "")
                        city = ""
                        country = ""

                        if ", " in location:
                            parts = location.split(", ")
                            city = parts[0]
                            country = parts[1] if len(parts) > 1 else ""
                        else:
                            city = location

                        return {
                            "name": tournament.get("Name", ""),
                            "city": city,
                            "country": country,
                            "venue": None,
                            "tier": tournament.get("Level", ""),
                            "start_date": start_date,
                            "end_date": end_date,
                            "url": f"https://psaworldtour.com/tournaments/{tournament.get('Id', '')}"
                        }

                except Exception:
                    continue

            return None

        except Exception:
            return None


# For direct testing
if __name__ == "__main__":
    async def test():
        print("Testing fetch module...")

        # Test with a known player
        test_player = "Paul Coll"
        test_id = "2778"

        print(f"\nTesting basic match history for {test_player}...")
        basic_history = await get_match_history(test_player, test_id, use_cache=False, months_back=6)
        print(f"Basic history: {len(basic_history)} matches")

        print(f"\nTesting extended match history for {test_player}...")
        extended_history = await get_extended_match_history(test_player, test_id, use_cache=False, months_back=6)
        print(f"Extended history: {len(extended_history)} matches")

        if not extended_history.empty:
            print("\nSample matches:")
            for i, row in extended_history.head(3).iterrows():
                print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']}")

    asyncio.run(test())
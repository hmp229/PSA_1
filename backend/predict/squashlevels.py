"""Enhanced SquashLevels.com integration with better error handling."""
import asyncio
import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
import re


class SquashLevelsEnhanced:
    def __init__(self):
        self.base_url = "https://www.squashlevels.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.squashlevels.com/",
            "Origin": "https://www.squashlevels.com"
        }

    async def search_player(self, player_name: str) -> Optional[Dict]:
        """Search for a player on SquashLevels with multiple approaches."""
        print(f"🔍 Searching SquashLevels for: {player_name}")

        # Try direct search API first
        search_url = f"{self.base_url}/api/search/players"

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            params = {"q": player_name, "limit": 10}
            try:
                response = await client.get(search_url, params=params)
                print(f"   Search API status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Find best match
                        for player in data:
                            if player_name.lower() in player.get('name', '').lower():
                                print(f"✅ Exact match found: {player['name']}")
                                return player

                        # Return closest match
                        closest = data[0]
                        print(f"✅ Closest match: {closest['name']}")
                        return closest
                else:
                    print(f"   Search API failed: {response.status_code}")

            except Exception as e:
                print(f"   Search API error: {e}")

        # Fallback: Try to find player via their rankings page
        return await self._find_player_via_rankings(player_name)

    async def _find_player_via_rankings(self, player_name: str) -> Optional[Dict]:
        """Find player by scraping rankings pages."""
        print(f"   Trying rankings search for: {player_name}")

        # SquashLevels has rankings pages we can scrape
        rankings_urls = [
            f"{self.base_url}/rankings/mens_rankings",
            f"{self.base_url}/rankings/womens_rankings"
        ]

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            for url in rankings_urls:
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # This would require HTML parsing - for now return None
                        # In a full implementation, we'd parse the HTML to find players
                        pass
                except Exception as e:
                    print(f"   Rankings search error: {e}")

        return None

    async def get_player_matches(self, player_id: str, player_name: str, months_back: int = 24) -> pd.DataFrame:
        """Get match history from SquashLevels with enhanced parsing."""
        print(f"📊 Getting matches from SquashLevels for {player_name} (ID: {player_id})")

        # Try multiple endpoint formats
        endpoints = [
            f"{self.base_url}/api/player/{player_id}/matches",
            f"{self.base_url}/api/players/{player_id}/matches",
            f"{self.base_url}/player/{player_id}/matches/json"
        ]

        cutoff_date = (datetime.now() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")

        params = {
            "from": cutoff_date,
            "limit": 200  # Try to get more matches
        }

        for endpoint in endpoints:
            print(f"   Trying endpoint: {endpoint}")
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                try:
                    response = await client.get(endpoint, params=params)
                    print(f"   Endpoint response: {response.status_code}")

                    if response.status_code == 200:
                        data = response.json()
                        matches = self._parse_squashlevels_matches(data, player_name)
                        if not matches.empty:
                            print(f"✅ SquashLevels successful: {len(matches)} matches")
                            return matches
                    else:
                        print(f"   Endpoint failed: {response.status_code}")

                except Exception as e:
                    print(f"   Endpoint error: {e}")

        print("❌ All SquashLevels endpoints failed")
        return pd.DataFrame()

    def _parse_squashlevels_matches(self, data: Dict, player_name: str) -> pd.DataFrame:
        """Parse matches from SquashLevels API response with enhanced logic."""
        matches = []

        if not data:
            return pd.DataFrame()

        # Handle different response formats
        matches_data = data.get('matches', [])
        if not matches_data and isinstance(data, list):
            matches_data = data

        print(f"   Parsing {len(matches_data)} match records")

        for match_data in matches_data:
            try:
                # Extract match date
                date_str = match_data.get('date') or match_data.get('matchDate') or match_data.get('played')
                if not date_str:
                    continue

                # Parse date (handle different formats)
                if 'T' in date_str:
                    match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    try:
                        match_date = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        continue

                # Extract players and result
                player1 = match_data.get('player1', {})
                player2 = match_data.get('player2', {})

                # Determine which player is our target
                if isinstance(player1, dict) and player1.get('name', '').lower() == player_name.lower():
                    opponent = player2.get('name', '') if isinstance(player2, dict) else str(player2)
                    winner_id = match_data.get('winner')
                    result = "W" if winner_id == 1 else "L"
                elif isinstance(player2, dict) and player2.get('name', '').lower() == player_name.lower():
                    opponent = player1.get('name', '') if isinstance(player1, dict) else str(player1)
                    winner_id = match_data.get('winner')
                    result = "W" if winner_id == 2 else "L"
                else:
                    # Try string matching for different data structures
                    players_text = f"{player1} vs {player2}" if not isinstance(player1, dict) else f"{player1.get('name', '')} vs {player2.get('name', '')}"
                    if player_name.lower() in players_text.lower():
                        # Simple heuristic: if our player is mentioned first, they might be player1
                        parts = players_text.split(' vs ')
                        if len(parts) == 2 and player_name.lower() in parts[0].lower():
                            opponent = parts[1]
                            result = "W"  # Default assumption
                        else:
                            opponent = parts[0] if len(parts) == 2 else "Unknown"
                            result = "L"  # Default assumption
                    else:
                        continue

                # Extract score
                score = match_data.get('score', '') or match_data.get('result', '')

                # Parse games from score
                games_won, games_lost = self._parse_games_from_score(score, result)

                matches.append({
                    "date": match_date,
                    "opponent": opponent.strip(),
                    "result": result,
                    "score": score,
                    "games_won": games_won,
                    "games_lost": games_lost,
                    "event": match_data.get('event', {}).get('name', '') if isinstance(match_data.get('event'), dict) else match_data.get('tournament', ''),
                    "round": match_data.get('round', ''),
                    "source": "squashlevels"
                })

            except Exception as e:
                print(f"   Error parsing match: {e}")
                continue

        return pd.DataFrame(matches)

    def _parse_games_from_score(self, score: str, result: str) -> tuple:
        """Parse games from score string with multiple format support."""
        try:
            if not score:
                return (3, 0) if result == "W" else (0, 3)

            # Handle various score formats:
            # "11-8,11-9,5-11,11-7", "3-1", "11-8 11-9 5-11 11-7"
            score_clean = score.replace(' ', ',')
            games = re.findall(r'(\d+)-(\d+)', score_clean)

            if games:
                player_games = sum(1 for p1, p2 in games if int(p1) > int(p2))
                opponent_games = sum(1 for p1, p2 in games if int(p2) > int(p1))
                return player_games, opponent_games
        except:
            pass

        # Default based on result
        return (3, 0) if result == "W" else (0, 3)


# Global instance
_squashlevels_enhanced = SquashLevelsEnhanced()

async def get_squashlevels_match_history(player_name: str, months_back: int = 24) -> pd.DataFrame:
    """Public interface for enhanced SquashLevels."""
    player_info = await _squashlevels_enhanced.search_player(player_name)
    if player_info:
        player_id = player_info.get('id') or player_info.get('playerId')
        if player_id:
            return await _squashlevels_enhanced.get_player_matches(player_id, player_name, months_back)

    print(f"❌ Could not find {player_name} on SquashLevels")
    return pd.DataFrame()

# Test function
async def test_squashlevels():
    """Test the enhanced SquashLevels integration."""
    test_players = ["Paul Coll", "Ali Farag", "Diego Elias"]

    for player in test_players:
        print(f"\n{'='*50}")
        print(f"Testing: {player}")
        history = await get_squashlevels_match_history(player, months_back=12)
        print(f"Result: {len(history)} matches")
        if not history.empty:
            for i, row in history.head(3).iterrows():
                print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']}")

if __name__ == "__main__":
    asyncio.run(test_squashlevels())
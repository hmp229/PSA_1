"""Enhanced SquashInfo.com scraper with multiple data extraction methods."""
import asyncio
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup


class SquashInfoEnhanced:
    def __init__(self):
        self.base_url = "https://www.squashinfo.com"
        self.timeout = 30.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def search_player(self, player_name: str) -> Optional[Dict]:
        """Search for player on SquashInfo with multiple approaches."""
        print(f"🔍 Searching SquashInfo for: {player_name}")

        # Try direct player directory
        search_url = f"{self.base_url}/players"

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                response = await client.get(search_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for player links
                    player_links = soup.find_all('a', href=re.compile(r'/player/\d+'))

                    for link in player_links:
                        link_text = link.get_text(strip=True)
                        if player_name.lower() in link_text.lower():
                            player_url = f"{self.base_url}{link['href']}"
                            return {
                                "name": link_text,
                                "url": player_url,
                                "id": link['href'].split('/')[-1]
                            }

            except Exception as e:
                print(f"   Search error: {e}")

        # Try search functionality
        return await self._search_players_direct(player_name)

    async def _search_players_direct(self, player_name: str) -> Optional[Dict]:
        """Try to find player via search functionality."""
        search_url = f"{self.base_url}/search"

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            params = {"q": player_name}
            try:
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for player results
                    player_results = soup.select('.player-result, .search-result')

                    for result in player_results:
                        link = result.find('a', href=re.compile(r'/player/\d+'))
                        if link:
                            link_text = link.get_text(strip=True)
                            if player_name.lower() in link_text.lower():
                                player_url = f"{self.base_url}{link['href']}"
                                return {
                                    "name": link_text,
                                    "url": player_url,
                                    "id": link['href'].split('/')[-1]
                                }

            except Exception as e:
                print(f"   Direct search error: {e}")

        return None

    async def get_player_match_history(self, player_info: Dict, months_back: int = 24) -> pd.DataFrame:
        """Get match history from SquashInfo player page."""
        print(f"📊 Getting matches from SquashInfo for {player_info['name']}")

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                response = await client.get(player_info['url'])

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    matches = self._parse_squashinfo_matches(soup, player_info['name'], months_back)

                    if matches:
                        print(f"✅ SquashInfo successful: {len(matches)} matches")
                        df = pd.DataFrame(matches)
                        df = df.sort_values("date", ascending=False).reset_index(drop=True)
                        return df
                    else:
                        print("❌ No matches found on SquashInfo")
                        return pd.DataFrame()
                else:
                    print(f"❌ Failed to load player page: {response.status_code}")
                    return pd.DataFrame()

        except Exception as e:
            print(f"❌ SquashInfo error: {e}")
            return pd.DataFrame()

    def _parse_squashinfo_matches(self, soup: BeautifulSoup, player_name: str, months_back: int) -> List[Dict]:
        """Parse matches from SquashInfo HTML with enhanced logic."""
        matches = []
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)

        # Try multiple table selectors
        selectors = [
            "table.results tbody tr",
            "table.matches tbody tr",
            "table tbody tr",
            ".results-table tbody tr",
            ".match-history tbody tr"
        ]

        for selector in selectors:
            rows = soup.select(selector)
            if rows:
                print(f"   Found {len(rows)} rows with selector: {selector}")
                for row in rows:
                    match = self._parse_squashinfo_row(row, player_name, cutoff_date)
                    if match:
                        matches.append(match)
                break

        return matches

    def _parse_squashinfo_row(self, row, player_name: str, cutoff_date: datetime) -> Optional[Dict]:
        """Parse a single match row from SquashInfo."""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 4:  # Need at least basic info
                return None

            # Extract date from first cell
            date_text = cells[0].get_text(strip=True)
            match_date = self._parse_date(date_text)

            if not match_date or match_date < cutoff_date:
                return None

            # Extract tournament and round
            tournament = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            round_info = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            # Extract players and result - this can be in various formats
            players_cell = cells[3] if len(cells) > 3 else None
            result_cell = cells[4] if len(cells) > 4 else None

            if not players_cell:
                return None

            players_text = players_cell.get_text(strip=True)
            result_text = result_cell.get_text(strip=True) if result_cell else ""

            # Parse opponent and result
            opponent, result, score = self._parse_players_and_result(players_text, result_text, player_name)

            if opponent:
                games_won, games_lost = self._parse_games_from_score(score, result)

                return {
                    "date": match_date,
                    "opponent": opponent,
                    "result": result,
                    "score": score,
                    "games_won": games_won,
                    "games_lost": games_lost,
                    "event": tournament,
                    "round": round_info,
                    "source": "squashinfo"
                }

        except Exception as e:
            return None

        return None

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse various date formats."""
        try:
            formats = [
                "%d %b %Y",
                "%Y-%m-%d",
                "%b %d, %Y",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%d-%m-%Y"
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue

            # Try to extract year from text
            year_match = re.search(r'\b(20\d{2})\b', date_text)
            if year_match:
                year = int(year_match.group(1))
                if 2000 <= year <= 2030:
                    return datetime(year, 1, 1)

        except:
            pass

        return None

    def _parse_players_and_result(self, players_text: str, result_text: str, target_player: str) -> tuple:
        """Parse player names and determine result."""
        try:
            # Common patterns
            if ' vs ' in players_text:
                parts = players_text.split(' vs ')
                if len(parts) == 2:
                    player_a, player_b = parts[0].strip(), parts[1].strip()

                    if target_player.lower() in player_a.lower():
                        opponent = player_b
                        # Try to determine result
                        if 'def.' in result_text.lower() or 'beat' in result_text.lower():
                            if target_player.lower() in result_text.lower():
                                result = "W"
                            else:
                                result = "L"
                        else:
                            result = self._guess_result_from_score(result_text, is_first_player=True)
                        return opponent, result, result_text

                    elif target_player.lower() in player_b.lower():
                        opponent = player_a
                        if 'def.' in result_text.lower() or 'beat' in result_text.lower():
                            if target_player.lower() in result_text.lower():
                                result = "W"
                            else:
                                result = "L"
                        else:
                            result = self._guess_result_from_score(result_text, is_first_player=False)
                        return opponent, result, result_text

            # Fallback: simple text matching
            if target_player.lower() in players_text.lower():
                # Extract opponent by removing target player name
                opponent = players_text.lower().replace(target_player.lower(), '').strip()
                opponent = re.sub(r'^\s*(vs|def\.?|beat)\s*', '', opponent).strip()
                opponent = re.sub(r'\s*(vs|def\.?|beat)\s*$', '', opponent).strip()

                if opponent and opponent != players_text.lower():
                    opponent = ' '.join(word.capitalize() for word in opponent.split())
                    result = "W" if 'def.' in result_text.lower() or 'win' in result_text.lower() else "L"
                    return opponent, result, result_text

        except:
            pass

        return None, None, None

    def _guess_result_from_score(self, score_text: str, is_first_player: bool) -> str:
        """Guess result from score text."""
        try:
            games = re.findall(r'(\d+)-(\d+)', score_text)
            if games:
                first_player_wins = sum(1 for p1, p2 in games if int(p1) > int(p2))
                second_player_wins = sum(1 for p1, p2 in games if int(p2) > int(p1))

                if is_first_player:
                    return "W" if first_player_wins > second_player_wins else "L"
                else:
                    return "W" if second_player_wins > first_player_wins else "L"
        except:
            pass

        return "L"

    def _parse_games_from_score(self, score: str, result: str) -> tuple:
        """Parse games from score string."""
        try:
            games = re.findall(r'(\d+)-(\d+)', score)
            if games:
                player_games = sum(1 for p1, p2 in games if int(p1) > int(p2))
                opponent_games = sum(1 for p1, p2 in games if int(p2) > int(p1))
                return player_games, opponent_games
        except:
            pass

        return (3, 0) if result == "W" else (0, 3)


# Global instance
_squashinfo_enhanced = SquashInfoEnhanced()

async def get_squashinfo_match_history(player_name: str, months_back: int = 24) -> pd.DataFrame:
    """Public interface for enhanced SquashInfo."""
    player_info = await _squashinfo_enhanced.search_player(player_name)
    if player_info:
        return await _squashinfo_enhanced.get_player_match_history(player_info, months_back)

    print(f"❌ Could not find {player_name} on SquashInfo")
    return pd.DataFrame()

# Test function
async def test_squashinfo():
    """Test the enhanced SquashInfo integration."""
    test_players = ["Paul Coll", "Ali Farag", "Diego Elias"]

    for player in test_players:
        print(f"\n{'='*50}")
        print(f"Testing: {player}")
        history = await get_squashinfo_match_history(player, months_back=12)
        print(f"Result: {len(history)} matches")
        if not history.empty:
            for i, row in history.head(3).iterrows():
                print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']}")

if __name__ == "__main__":
    asyncio.run(test_squashinfo())
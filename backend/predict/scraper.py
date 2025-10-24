"""PSA World Tour website scraper for detailed match history."""
import asyncio
import re
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import httpx
from bs4 import BeautifulSoup
import json


class PSAScraper:
    def __init__(self):
        self.base_url = "https://www.psasquashtour.com"
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
        """Enhanced player search on PSA website."""
        print(f"🔍 Searching PSA website for: {player_name}")

        search_url = f"{self.base_url}/search"

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            params = {"query": player_name}
            try:
                response = await client.get(search_url, params=params)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for player links in search results
                    player_links = soup.find_all('a', href=re.compile(r'/player/'))
                    print(f"   Found {len(player_links)} player links in search results")

                    # Try exact match first
                    for link in player_links:
                        link_text = link.get_text(strip=True)
                        if player_name.lower() == link_text.lower():
                            player_url = link['href'] if link['href'].startswith(
                                'http') else f"{self.base_url}{link['href']}"
                            player_id = link['href'].split('/')[-2]

                            print(f"   ✅ Exact match found: {link_text}")
                            return {
                                "name": link_text,
                                "url": player_url,
                                "id": player_id,
                                "source": "psa_website"
                            }

                    # Try partial match
                    for link in player_links:
                        link_text = link.get_text(strip=True)
                        if player_name.lower() in link_text.lower():
                            player_url = link['href'] if link['href'].startswith(
                                'http') else f"{self.base_url}{link['href']}"
                            player_id = link['href'].split('/')[-2]

                            print(f"   ✅ Partial match found: {link_text}")
                            return {
                                "name": link_text,
                                "url": player_url,
                                "id": player_id,
                                "source": "psa_website"
                            }

                    # If no matches found, show what we did find
                    if player_links:
                        print(
                            f"   Found players (no match): {[link.get_text(strip=True) for link in player_links[:3]]}")
                    else:
                        print("   ❌ No player links found in search results")

                else:
                    print(f"   ❌ Search failed: {response.status_code}")

            except Exception as e:
                print(f"   ❌ Search error: {e}")

        return None

    # Add a direct access method using known URLs
    async def get_player_by_direct_url(self, player_slug: str, player_name: str) -> Optional[Dict]:
        """Direct player access using known URL slug."""
        player_url = f"{self.base_url}/player/{player_slug}/"

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                response = await client.get(player_url)
                if response.status_code == 200:
                    print(f"   ✅ Direct access successful: {player_url}")
                    return {
                        "name": player_name,
                        "url": player_url,
                        "id": player_slug,
                        "source": "psa_website_direct"
                    }
                else:
                    print(f"   ❌ Direct access failed: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Direct access error: {e}")

        return None

    async def get_player_match_history(self, player_info: Dict, months_back: int = 24) -> pd.DataFrame:
        """Get detailed match history from PSA player profile."""
        print(f"📊 Scraping match history for {player_info['name']} from PSA website")
        print(f"   URL: {player_info['url']}")

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(player_info['url'])

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Extract matches from the page
                    matches = self._extract_matches_from_profile(soup, player_info['name'], months_back)

                    if matches:
                        print(f"✅ Found {len(matches)} matches on PSA website")
                        df = pd.DataFrame(matches)
                        df = df.sort_values("date", ascending=False).reset_index(drop=True)
                        return df
                    else:
                        print("❌ No matches found on PSA website")
                        return pd.DataFrame()

                else:
                    print(f"❌ Failed to load player page: {response.status_code}")
                    return pd.DataFrame()

        except Exception as e:
            print(f"❌ Scraping error: {e}")
            return pd.DataFrame()

    def _extract_matches_from_profile(self, soup: BeautifulSoup, player_name: str, months_back: int) -> List[Dict]:
        """Extract matches from PSA player profile page."""
        matches = []
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)

        # PSA website typically has match history in tables or structured divs
        # Look for match sections - common selectors on PSA site
        selectors = [
            ".matches-table table tbody tr",
            ".results table tbody tr",
            ".player-results table tbody tr",
            "table.tournament-results tbody tr",
            ".match-history .match-item",
            "div[class*='match']",  # Fallback for div-based layouts
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"   Found {len(elements)} elements with selector: {selector}")
                for element in elements:
                    match = self._parse_match_element(element, player_name, cutoff_date)
                    if match:
                        matches.append(match)
                break

        # Also try to find matches in JSON data (common in modern sites)
        script_matches = self._extract_matches_from_scripts(soup, player_name, cutoff_date)
        matches.extend(script_matches)

        return matches

    def _parse_match_element(self, element, player_name: str, cutoff_date: datetime) -> Optional[Dict]:
        """Parse a match element from PSA website."""
        try:
            # Try table row format first
            if element.name == 'tr':
                return self._parse_table_row(element, player_name, cutoff_date)
            # Try div format
            elif element.name == 'div':
                return self._parse_div_element(element, player_name, cutoff_date)

        except Exception as e:
            print(f"   Error parsing match element: {e}")

        return None

    def _parse_table_row(self, row, player_name: str, cutoff_date: datetime) -> Optional[Dict]:
        """Parse match from table row."""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 4:
                return None

            # Extract date from first cell
            date_text = cells[0].get_text(strip=True)
            match_date = self._parse_psa_date(date_text)

            if not match_date or match_date < cutoff_date:
                return None

            # Extract tournament info
            tournament = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            round_info = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            # Extract players and score
            players_cell = cells[3] if len(cells) > 3 else None
            score_cell = cells[4] if len(cells) > 4 else None

            if not players_cell:
                return None

            players_text = players_cell.get_text(strip=True)
            score_text = score_cell.get_text(strip=True) if score_cell else ""

            # Parse opponent and result
            opponent, result = self._parse_psa_players_and_result(players_text, score_text, player_name)

            if opponent:
                # Parse detailed score information
                games_won, games_lost, score_details = self._parse_psa_score(score_text, result)

                return {
                    "date": match_date,
                    "opponent": opponent,
                    "result": result,
                    "score": score_details,
                    "games_won": games_won,
                    "games_lost": games_lost,
                    "event": tournament,
                    "round": round_info,
                    "source": "psa_website",
                    "detailed_score": True
                }

        except Exception as e:
            print(f"   Error parsing table row: {e}")

        return None

    def _parse_div_element(self, div, player_name: str, cutoff_date: datetime) -> Optional[Dict]:
        """Parse match from div element."""
        try:
            # Look for date in the div
            date_element = div.find(class_=re.compile(r'date|time', re.I))
            if not date_element:
                return None

            date_text = date_element.get_text(strip=True)
            match_date = self._parse_psa_date(date_text)

            if not match_date or match_date < cutoff_date:
                return None

            # Look for players
            players_element = div.find(class_=re.compile(r'players|match', re.I))
            if not players_element:
                return None

            players_text = players_element.get_text(strip=True)

            # Look for score
            score_element = div.find(class_=re.compile(r'score|result', re.I))
            score_text = score_element.get_text(strip=True) if score_element else ""

            # Parse opponent and result
            opponent, result = self._parse_psa_players_and_result(players_text, score_text, player_name)

            if opponent:
                games_won, games_lost, score_details = self._parse_psa_score(score_text, result)

                # Try to get tournament info
                tournament_element = div.find(class_=re.compile(r'tournament|event', re.I))
                tournament = tournament_element.get_text(strip=True) if tournament_element else ""

                return {
                    "date": match_date,
                    "opponent": opponent,
                    "result": result,
                    "score": score_details,
                    "games_won": games_won,
                    "games_lost": games_lost,
                    "event": tournament,
                    "round": "",
                    "source": "psa_website",
                    "detailed_score": True
                }

        except Exception as e:
            print(f"   Error parsing div element: {e}")

        return None

    def _extract_matches_from_scripts(self, soup: BeautifulSoup, player_name: str, cutoff_date: datetime) -> List[Dict]:
        """Extract matches from JavaScript data in page scripts."""
        matches = []

        # Look for JSON data in script tags
        scripts = soup.find_all('script', string=re.compile(r'matches|results|tournaments', re.I))

        for script in scripts:
            script_text = script.string
            if not script_text:
                continue

            # Try to find JSON objects in script
            json_patterns = [
                r'var\s+matches\s*=\s*(\[.*?\]);',
                r'const\s+results\s*=\s*(\[.*?\]);',
                r'data:\s*(\[.*?\]),',
                r'"matches":\s*(\[.*?\])',
            ]

            for pattern in json_patterns:
                matches_data = re.search(pattern, script_text, re.DOTALL)
                if matches_data:
                    try:
                        json_text = matches_data.group(1)
                        data = json.loads(json_text)
                        parsed_matches = self._parse_json_matches(data, player_name, cutoff_date)
                        matches.extend(parsed_matches)
                    except:
                        continue

        return matches

    def _parse_json_matches(self, data: List[Dict], player_name: str, cutoff_date: datetime) -> List[Dict]:
        """Parse matches from JSON data."""
        matches = []

        for match_data in data:
            try:
                # Extract date
                date_str = match_data.get('date') or match_data.get('matchDate') or match_data.get('startDate')
                if not date_str:
                    continue

                match_date = self._parse_psa_date(date_str)
                if not match_date or match_date < cutoff_date:
                    continue

                # Extract players and determine our player's position
                players = match_data.get('players', [])
                if len(players) != 2:
                    continue

                player_idx = None
                for i, player in enumerate(players):
                    if player.get('name', '').lower() == player_name.lower():
                        player_idx = i
                        break

                if player_idx is None:
                    continue

                opponent_idx = 1 - player_idx
                opponent = players[opponent_idx].get('name', 'Unknown')

                # Determine result
                winner_id = match_data.get('winnerId')
                if winner_id:
                    result = "W" if winner_id == players[player_idx].get('id') else "L"
                else:
                    # Fallback to score comparison
                    player_score = players[player_idx].get('score', 0)
                    opponent_score = players[opponent_idx].get('score', 0)
                    result = "W" if player_score > opponent_score else "L"

                # Parse score
                score_text = match_data.get('score', '') or match_data.get('result', '')
                games_won, games_lost, score_details = self._parse_psa_score(score_text, result)

                matches.append({
                    "date": match_date,
                    "opponent": opponent,
                    "result": result,
                    "score": score_details,
                    "games_won": games_won,
                    "games_lost": games_lost,
                    "event": match_data.get('tournament', {}).get('name', '') if isinstance(match_data.get('tournament'), dict) else match_data.get('event', ''),
                    "round": match_data.get('round', ''),
                    "source": "psa_website_json",
                    "detailed_score": True
                })

            except Exception as e:
                continue

        return matches

    def _parse_psa_date(self, date_text: str) -> Optional[datetime]:
        """Parse PSA website date formats."""
        try:
            # Common PSA date formats
            formats = [
                "%Y-%m-%d",
                "%d %b %Y",
                "%b %d, %Y",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d"
            ]

            # Clean the date string
            date_clean = re.sub(r'\s+', ' ', date_text.strip())

            for fmt in formats:
                try:
                    return datetime.strptime(date_clean, fmt)
                except ValueError:
                    continue

            # Try to extract date components
            date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_text)
            if date_match:
                day, month, year = date_match.groups()
                return datetime(int(year), int(month), int(day))

        except:
            pass

        return None

    def _parse_psa_players_and_result(self, players_text: str, score_text: str, target_player: str) -> Tuple[Optional[str], str]:
        """Parse players and determine result from PSA format."""
        try:
            # Common PSA formats: "Player A vs Player B" or "Player A def. Player B"
            if ' vs ' in players_text:
                parts = players_text.split(' vs ')
                if len(parts) == 2:
                    player_a, player_b = parts[0].strip(), parts[1].strip()

                    if target_player.lower() in player_a.lower():
                        opponent = player_b
                        # Check if our player won
                        if 'def.' in score_text.lower() or 'beat' in score_text.lower():
                            if target_player.lower() in score_text.lower():
                                result = "W"
                            else:
                                result = "L"
                        else:
                            # Try to determine from score
                            result = self._determine_result_from_score(score_text, is_first_player=True)
                        return opponent, result

                    elif target_player.lower() in player_b.lower():
                        opponent = player_a
                        if 'def.' in score_text.lower() or 'beat' in score_text.lower():
                            if target_player.lower() in score_text.lower():
                                result = "W"
                            else:
                                result = "L"
                        else:
                            result = self._determine_result_from_score(score_text, is_first_player=False)
                        return opponent, result

            # Direct name matching
            if target_player.lower() in players_text.lower():
                # Remove target player to find opponent
                opponent = players_text.lower().replace(target_player.lower(), '').strip()
                opponent = re.sub(r'^\s*(vs|def\.?|beat)\s*', '', opponent).strip()
                opponent = re.sub(r'\s*(vs|def\.?|beat)\s*$', '', opponent).strip()

                if opponent and opponent != players_text.lower():
                    opponent = ' '.join(word.capitalize() for word in opponent.split())
                    result = "W" if 'def.' in score_text.lower() else "L"
                    return opponent, result

        except:
            pass

        return None, "L"

    def _determine_result_from_score(self, score_text: str, is_first_player: bool) -> str:
        """Determine result from score text."""
        try:
            games = re.findall(r'(\d+)-(\d+)', score_text)
            if games:
                first_player_games = sum(1 for p1, p2 in games if int(p1) > int(p2))
                second_player_games = sum(1 for p1, p2 in games if int(p2) > int(p1))

                if is_first_player:
                    return "W" if first_player_games > second_player_games else "L"
                else:
                    return "W" if second_player_games > first_player_games else "L"
        except:
            pass

        return "L"

    def _parse_psa_score(self, score_text: str, result: str) -> Tuple[int, int, str]:
        """Parse detailed score information from PSA format."""
        try:
            # Handle various PSA score formats
            if not score_text:
                return (3, 0, "3-0") if result == "W" else (0, 3, "0-3")

            # Clean score text
            score_clean = re.sub(r'[^\d\-, ]', '', score_text).strip()

            # Parse individual games
            games = re.findall(r'(\d+)-(\d+)', score_clean)
            if games:
                player_games = sum(1 for p1, p2 in games if int(p1) > int(p2))
                opponent_games = sum(1 for p1, p2 in games if int(p2) > int(p1))

                # Reconstruct score string
                score_parts = [f"{p1}-{p2}" for p1, p2 in games]
                score_details = ", ".join(score_parts)

                return player_games, opponent_games, score_details

        except:
            pass

        # Fallback
        return (3, 0, "3-0") if result == "W" else (0, 3, "0-3")

    # New methods from the provided scraper for enhanced functionality
    async def get_player_match_history_by_id(self, player_id: str, player_name: str, months_back: int = 24) -> pd.DataFrame:
        """
        Alternative method to scrape match history using player ID.
        This provides compatibility with the provided scraper interface.
        """
        print(f"🕸️  Scraping match history for {player_name} (ID: {player_id})")

        profile_url = f"{self.base_url}/players/{player_id}"
        print(f"   Profile URL: {profile_url}")

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                # Get the player profile page
                response = await client.get(profile_url)
                if response.status_code != 200:
                    print(f"   ✗ Failed to load profile page: {response.status_code}")
                    return pd.DataFrame()

                soup = BeautifulSoup(response.text, 'html.parser')

                # Use our enhanced parsing methods
                matches = self._extract_matches_from_profile(soup, player_name, months_back)

                if matches:
                    print(f"   ✓ Found {len(matches)} matches via scraping")
                    df = pd.DataFrame(matches)
                    df = df.sort_values("date", ascending=False).reset_index(drop=True)
                    return df
                else:
                    print(f"   ✗ No matches found in profile page")
                    return pd.DataFrame()

        except Exception as e:
            print(f"   ✗ Scraping error: {e}")
            return pd.DataFrame()

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Enhanced date parsing with multiple formats (from provided scraper)."""
        try:
            # Try different date formats
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%d-%m-%Y",
                "%b %d, %Y",
                "%d %b %Y",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue

            # Try to extract year and parse
            year_match = re.search(r'(\d{4})', date_text)
            if year_match:
                year = int(year_match.group(1))
                if 2000 <= year <= 2030:
                    # Return a rough date
                    return datetime(year, 1, 1)

        except Exception:
            pass

        return None

    def _extract_games_won(self, score_text: str, result: str) -> int:
        """Extract number of games won from score (from provided scraper)."""
        try:
            if '-' in score_text:
                games = re.findall(r'(\d+)-(\d+)', score_text)
                if games:
                    if result == "W":
                        return sum(1 for p1, p2 in games if int(p1) > int(p2))
                    else:
                        return sum(1 for p1, p2 in games if int(p2) > int(p1))
        except:
            pass
        return 3 if result == "W" else 0  # Default assumption

    def _extract_games_lost(self, score_text: str, result: str) -> int:
        """Extract number of games lost from score (from provided scraper)."""
        try:
            if '-' in score_text:
                games = re.findall(r'(\d+)-(\d+)', score_text)
                if games:
                    if result == "W":
                        return sum(1 for p1, p2 in games if int(p2) > int(p1))
                    else:
                        return sum(1 for p1, p2 in games if int(p1) > int(p2))
        except:
            pass
        return 0 if result == "W" else 3  # Default assumption


# Global instances for different scraping approaches
_psa_scraper = PSAScraper()
_scraper = PSAScraper()  # For compatibility with provided interface


async def get_psa_website_match_history(player_name: str, months_back: int = 24) -> pd.DataFrame:
    """Public interface for PSA website scraping."""
    player_info = await _psa_scraper.search_player(player_name)
    if player_info:
        return await _psa_scraper.get_player_match_history(player_info, months_back)

    print(f"❌ Could not find {player_name} on PSA website")
    return pd.DataFrame()


async def scrape_player_match_history(player_id: str, player_name: str, months_back: int = 24) -> pd.DataFrame:
    """Public interface for scraping match history (compatibility with provided interface)."""
    return await _scraper.get_player_match_history_by_id(player_id, player_name, months_back)


# Enhanced test function
async def test_psa_scraper():
    """Test the PSA website scraper with multiple approaches."""
    test_players = ["Joeri Hapers", "Paul Coll", "Ali Farag"]

    for player in test_players:
        print(f"\n{'='*60}")
        print(f"Testing PSA scraper for: {player}")
        print(f"{'='*60}")

        # Test search-based approach
        history = await get_psa_website_match_history(player, months_back=12)

        if not history.empty:
            print(f"✅ SUCCESS: Found {len(history)} matches via search")
            print("Recent matches:")
            for i, row in history.head(5).iterrows():
                print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']} ({row['score']})")
        else:
            print("❌ No matches found via search")

        # Test direct ID approach if we have known IDs
        known_ids = {
            "Paul Coll": "paul-coll",
            "Ali Farag": "ali-farag"
        }

        if player in known_ids:
            print(f"\nTesting direct ID approach for {player}...")
            id_history = await scrape_player_match_history(known_ids[player], player, months_back=12)

            if not id_history.empty:
                print(f"✅ SUCCESS: Found {len(id_history)} matches via direct ID")
                for i, row in id_history.head(3).iterrows():
                    print(f"  {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']}")

if __name__ == "__main__":
    asyncio.run(test_psa_scraper())
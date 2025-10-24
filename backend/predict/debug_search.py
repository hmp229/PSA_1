# debug_search.py
import asyncio
import httpx
from bs4 import BeautifulSoup
import re


async def debug_psa_search():
    """Debug the PSA website search functionality."""
    base_url = "https://www.psasquashtour.com"
    search_url = f"{base_url}/search"

    test_players = ["Joeri Hapers", "Paul Coll", "Ali Farag"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for player in test_players:
            print(f"\n🔍 Searching for: '{player}'")

            try:
                params = {"query": player}
                response = await client.get(search_url, params=params)
                print(f"   Status: {response.status_code}")
                print(f"   URL: {response.url}")

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for any player links
                    player_links = soup.find_all('a', href=re.compile(r'/player/'))
                    print(f"   Found {len(player_links)} player links total")

                    for link in player_links[:5]:  # Show first 5
                        link_text = link.get_text(strip=True)
                        link_href = link.get('href', '')
                        print(f"   - '{link_text}' -> {link_href}")

                        if player.lower() in link_text.lower():
                            print(f"   ✅ MATCH FOUND: {link_text}")
                            player_url = f"{base_url}{link_href}"
                            player_id = link_href.split('/')[-2]
                            print(f"   URL: {player_url}")
                            print(f"   ID: {player_id}")
                            break
                    else:
                        print(f"   ❌ No exact match found for '{player}'")

                else:
                    print(f"   ❌ Search failed with status {response.status_code}")

            except Exception as e:
                print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(debug_psa_search())
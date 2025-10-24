# test_fixed_scraper.py
import asyncio
from scraper import get_psa_website_match_history


async def test_fixed_scraper():
    print("Testing fixed PSA website scraper...")

    test_players = ["Joeri Hapers", "Mohamed Gohar", "Paul Coll"]

    for player in test_players:
        print(f"\n🎯 Testing: {player}")
        history = await get_psa_website_match_history(player, months_back=24)

        if not history.empty:
            print(f"✅ SUCCESS: Found {len(history)} matches for {player}")
            for i, row in history.head(3).iterrows():
                print(f"   {row['date'].strftime('%Y-%m-%d')}: {row['result']} vs {row['opponent']}")
        else:
            print(f"❌ No matches found for {player}")


if __name__ == "__main__":
    asyncio.run(test_fixed_scraper())
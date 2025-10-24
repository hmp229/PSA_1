"""PSA calendar and event lookup by date."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from . import fetch


async def get_calendar_by_date(
    date_str: str,
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Look up PSA event overlapping the given date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        use_cache: Whether to use cached data
    
    Returns:
        Event dict with keys: name, city, country, venue, tier, start_date, end_date, url
        Returns None if no event found for that date.
    """
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    
    # Use the fetch module's calendar lookup
    event = await fetch.get_calendar_by_date(date_str, use_cache)
    
    if event:
        # Ensure all required fields are present
        return {
            "name": event.get("name", "Unknown Event"),
            "location": {
                "city": event.get("city", "—"),
                "country": event.get("country", "—"),
                "venue": event.get("venue", "—")
            },
            "start_date": event.get("start_date"),
            "end_date": event.get("end_date"),
            "tier": event.get("tier", "—"),
            "url": event.get("url", "")
        }
    
    return None


def format_event_response(event: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Format event for API response, return empty dict if None."""
    if not event:
        return {}
    
    return {
        "name": event["name"],
        "location": event["location"],
        "start_date": event["start_date"],
        "end_date": event["end_date"],
        "tier": event["tier"]
    }

import httpx
from datetime import datetime, timezone, timedelta
from app.config import QUINTYPE_API_BASE


def _cutoff_ms(days: int) -> int:
    """Return a UTC timestamp in milliseconds for N days ago."""
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _filter_by_age(stories: list[dict], days: int) -> list[dict]:
    cutoff = _cutoff_ms(days)
    return [s for s in stories if (s.get("published-at") or 0) >= cutoff]


def _is_free(story: dict) -> bool:
    """Return True only for publicly accessible (non-paywalled) stories."""
    if story.get("access") not in (None, "public", "login"):
        return False
    headline = story.get("headline", "") or ""
    if headline.startswith("Premium|") or headline.startswith("Premium |"):
        return False
    return True


async def _fetch_stories(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    url = f"{QUINTYPE_API_BASE}/api/v1/search"
    # Fetch generously so date filtering still leaves enough results
    resp = await client.get(url, params={"q": query, "limit": limit * 6})
    resp.raise_for_status()
    data = resp.json()
    stories = data.get("results", {}).get("stories", [])
    free = [s for s in stories if _is_free(s)]
    # Sort newest-first so date filters naturally pick the most recent
    return sorted(free, key=lambda s: s.get("published-at") or 0, reverse=True)


async def search(query: str, limit: int = 8) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        all_stories = await _fetch_stories(client, query, limit)

    # Try last 7 days first
    recent = _filter_by_age(all_stories, 7)
    if recent:
        return recent[:limit]

    # If nothing recent, try each individual word as a separate search
    words = [w.strip() for w in query.split() if len(w.strip()) > 1]
    if len(words) > 1:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [_fetch_stories(client, w, limit) for w in words]
            import asyncio
            results = await asyncio.gather(*tasks, return_exceptions=True)
        combined: dict[str, dict] = {}
        for batch in results:
            if isinstance(batch, list):
                for s in batch:
                    sid = str(s.get("id", ""))
                    if sid and sid not in combined:
                        combined[sid] = s
        all_stories = sorted(combined.values(), key=lambda s: s.get("published-at") or 0, reverse=True)
        recent = _filter_by_age(list(all_stories), 7)
        if recent:
            return recent[:limit]

    # Fall back to last 30 days across everything collected
    month = _filter_by_age(list(all_stories), 30)
    if month:
        return month[:limit]

    # Nothing within 30 days — return most recent available anyway
    return list(all_stories)[:limit]


async def top_stories(limit: int = 5) -> list[dict]:
    url = f"{QUINTYPE_API_BASE}/api/v1/stories"
    params = {"story-group": "top", "limit": limit}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    return [s for s in data.get("stories", []) if _is_free(s)]

"""Web search fallback via DuckDuckGo (free, no API key required).

Used as a last-resort branch when the local RAG returns low-quality
results.  DuckDuckGo is rate-limited to ~20 requests/minute; results
are cached in-memory for 10 minutes to avoid repeated calls.

Provides:
    :func:`web_search` — top-k web results for a query
"""

from __future__ import annotations

import time
from typing import Optional


# Simple in-memory cache: {(query, max_results): (timestamp, results)}
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
_CACHE_TTL = 600  # 10 minutes

_MAX_RETRIES = 2
_RETRY_DELAY = 2.0  # seconds


def web_search(
    query: str,
    max_results: int = 5,
    region: str = "cn-zh",
) -> list[dict]:
    """Search the web via DuckDuckGo and return structured results.

    Parameters
    ----------
    query : str
        Search query string.
    max_results : int
        Maximum number of results to return (default 5).
    region : str
        Region code for DuckDuckGo.  "cn-zh" targets Chinese results.

    Returns
    -------
    list[dict]
        Each result has ``id``, ``content``, ``metadata``.
        Returns empty list on failure or if no results found.
    """
    cache_key = (query, max_results)
    now = time.time()

    # Check cache
    if cache_key in _CACHE:
        ts, cached = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return cached

    results = _do_search(query, max_results, region)
    _CACHE[cache_key] = (now, results)
    return results


def _do_search(query: str, max_results: int, region: str) -> list[dict]:
    """Execute the DuckDuckGo search with retries."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                raw = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                    safesearch="off",
                ))

            if not raw:
                return []

            return [
                {
                    "id": f"web_{i}",
                    "content": (
                        f"# {r.get('title', '无标题')}\n"
                        f"{r.get('body', '')}\n"
                        f"来源: {r.get('href', '')}"
                    ),
                    "metadata": {
                        "source": "web_search",
                        "content_type": "web_result",
                        "url": r.get("href", ""),
                        "title": r.get("title", ""),
                    },
                }
                for i, r in enumerate(raw)
            ]

        except Exception:
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY)
            # Final attempt failed → silent fallback
            pass

    return []

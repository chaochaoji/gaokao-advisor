"""Web search fallback via DuckDuckGo (free, no API key required).

Used as a last-resort branch when the local RAG returns low-quality
results.  DuckDuckGo is rate-limited to ~20 requests/minute; results
are cached in-memory for 10 minutes to avoid repeated calls.

Preferred official sources are searched first (site: operator), then
a general search fills any gaps.

Provides:
    :func:`web_search` — top-k web results for a query
    :const:`OFFICIAL_SOURCES` — preferred gaokao data domains
"""

from __future__ import annotations

import time


# ── Official data source whitelist ──────────────────────────────────────
#   Sorted by priority: authoritative one-stop tables first, then
#   discipline rankings, then real student experience, then
#   general-purpose gaokao portals.

OFFICIAL_SOURCES: list[dict] = [
    # -- 查分与政策 -------------------------------------------------
    {
        "domain": "gaokao.chsi.com.cn",
        "category": "官方政策",
        "label": "阳光高考网",
        "site_query": "site:gaokao.chsi.com.cn",
    },
    {
        "domain": "bjeea.cn",
        "category": "省级考试院",
        "label": "北京教育考试院",
        "site_query": "site:bjeea.cn",
    },
    {
        "domain": "sxkszx.cn",
        "category": "省级考试院",
        "label": "山西招生考试网",
        "site_query": "site:sxkszx.cn",
    },
    {
        "domain": "hebeea.edu.cn",
        "category": "省级考试院",
        "label": "河北省教育考试院",
        "site_query": "site:hebeea.edu.cn",
    },
    {
        "domain": "sdzk.cn",
        "category": "省级考试院",
        "label": "山东省教育招生考试院",
        "site_query": "site:sdzk.cn",
    },
    {
        "domain": "eeafj.cn",
        "category": "省级考试院",
        "label": "福建省教育考试院",
        "site_query": "site:eeafj.cn",
    },
    {
        "domain": "zsksy.gd.gov.cn",
        "category": "省级考试院",
        "label": "广东省教育考试院",
        "site_query": "site:zsksy.gd.gov.cn",
    },
    # -- 选校与选专业 -----------------------------------------------
    {
        "domain": "shanghairanking.cn",
        "category": "大学排名",
        "label": "软科",
        "site_query": "site:shanghairanking.cn",
    },
    {
        "domain": "cdgdc.edu.cn",
        "category": "学科评估",
        "label": "教育部学位中心",
        "site_query": "site:cdgdc.edu.cn",
    },
    {
        "domain": "cingta.com",
        "category": "学科评估",
        "label": "青塔网",
        "site_query": "site:cingta.com",
    },
    # -- 真实就读体验 -----------------------------------------------
    {
        "domain": "kuangkuangdaxue.com",
        "category": "就读体验",
        "label": "哐哐大学",
        "site_query": "site:kuangkuangdaxue.com",
    },
    # -- 通用高考数据 -----------------------------------------------
    {
        "domain": "eol.cn",
        "category": "高考综合",
        "label": "掌上高考",
        "site_query": "site:eol.cn",
    },
    {
        "domain": "gk100.com",
        "category": "高考综合",
        "label": "高考100",
        "site_query": "site:gk100.com",
    },
    {
        "domain": "dxsbb.com",
        "category": "高考综合",
        "label": "大学生必备网",
        "site_query": "site:dxsbb.com",
    },
]


# ── Cache ────────────────────────────────────────────────────────────────

_CACHE: dict[tuple, tuple[float, list[dict]]] = {}
_CACHE_TTL = 600  # 10 minutes
_MAX_RETRIES = 2
_RETRY_DELAY = 2.0  # seconds


# ── Public API ────────────────────────────────────────────────────────────


def web_search(
    query: str,
    max_results: int = 5,
    region: str = "cn-zh",
) -> list[dict]:
    """Search the web via DuckDuckGo, preferring official sources.

    Two-pass strategy:
    1. Search with ``site:`` operator on official domains → highest priority
    2. General search for any remaining slots

    Parameters
    ----------
    query : str
        Search query string (Chinese).
    max_results : int
        Maximum number of results to return.
    region : str
        Region code for DuckDuckGo.

    Returns
    -------
    list[dict]
        Each result has ``id``, ``content``, ``metadata`` (with ``source``,
        ``content_type``, ``url``, ``title``, ``priority``).
        Official sources come first, general results fill remaining slots.
    """
    cache_key = (query, max_results)
    now = time.time()

    if cache_key in _CACHE:
        ts, cached = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return cached

    results = _search_with_sources(query, max_results)
    _CACHE[cache_key] = (now, results)
    return results


# ── Internal ──────────────────────────────────────────────────────────────


def _search_with_sources(query: str, max_results: int) -> list[dict]:
    """Two-pass search: official sources first, then general."""
    results: list[dict] = []
    seen_urls: set[str] = set()

    # Pass 1: search official sources
    for src in OFFICIAL_SOURCES:
        if len(results) >= max_results:
            break
        site_query = f"{query} {src['site_query']}"
        hits = _do_search(site_query, max_results=2)
        for r in hits:
            url = (r.get("metadata", {}) or {}).get("url", "")
            if url not in seen_urls:
                # Tag with source label
                meta = r.get("metadata", {}) or {}
                meta["priority"] = "official"
                meta["source_label"] = src["label"]
                meta["source_category"] = src["category"]
                r["metadata"] = meta
                results.append(r)
                seen_urls.add(url)

    # Pass 2: general search for remaining slots
    remaining = max_results - len(results)
    if remaining > 0:
        general = _do_search(query, max_results=remaining * 2)
        for r in general:
            url = (r.get("metadata", {}) or {}).get("url", "")
            if url not in seen_urls:
                meta = r.get("metadata", {}) or {}
                meta["priority"] = "general"
                r["metadata"] = meta
                results.append(r)
                seen_urls.add(url)
                if len(results) >= max_results:
                    break

    return results[:max_results]


def _do_search(query: str, max_results: int) -> list[dict]:
    """Execute a single DuckDuckGo search with retries."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                raw = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region="cn-zh",
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

    return []

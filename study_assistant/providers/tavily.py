"""Tavily search transport and response helpers."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


def request_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("The provider rejected its API key or the key lacks permission.") from None
        if error.code == 429:
            raise ValueError("The provider rate limit or account quota was reached.") from None
        raise ValueError(f"The provider request failed (HTTP {error.code}).") from None
    except URLError:
        raise ValueError("Could not reach Tavily. Check the internet connection and try again.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("The AI provider returned an unreadable response.") from None


def tavily_search(
    config: dict[str, str],
    query: str,
    *,
    search_depth: str,
    max_results: int,
    include_answer: str | bool,
    safe_search: bool = False,
    include_domains: list[str] | None = None,
    include_domains_mode: str = "restrict",
    include_images: bool = False,
    topic: str | None = None,
    time_range: str | None = None,
) -> dict:
    key = config.get("TAVILY_API_KEY", "")
    if not key:
        raise ValueError("Add TAVILY_API_KEY to .env or the server environment, then restart the local server.")
    payload = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": include_answer,
        "safe_search": safe_search,
    }
    if topic:
        payload["topic"] = topic
    if time_range:
        payload["time_range"] = time_range
    if include_images:
        payload["include_images"] = True
    if include_domains:
        payload["include_domains"] = include_domains
        payload["include_domains_mode"] = include_domains_mode
    if TavilyClient is not None:
        return TavilyClient(api_key=key).search(**payload)
    return request_json("https://api.tavily.com/search", {"Authorization": f"Bearer {key}"}, payload)


def relevant_images(data: dict, limit: int = 2) -> list[dict[str, str]]:
    candidates = list(data.get("images", [])) if isinstance(data.get("images"), list) else []
    for result in data.get("results", []):
        if isinstance(result, dict) and isinstance(result.get("images"), list):
            candidates.extend(result["images"])
    images = []
    seen = set()
    for candidate in candidates:
        if isinstance(candidate, str):
            image_url, description = candidate, "Related learning image"
        elif isinstance(candidate, dict):
            image_url = candidate.get("url", "")
            description = candidate.get("description") or "Related learning image"
        else:
            continue
        if not isinstance(image_url, str) or not image_url.startswith("https://") or image_url in seen:
            continue
        seen.add(image_url)
        images.append({"url": image_url, "description": str(description)[:180]})
        if len(images) >= limit:
            break
    return images

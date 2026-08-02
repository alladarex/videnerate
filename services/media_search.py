"""Runs a media search across the sources the user turned on.

SEARCH_PROVIDERS below lists the app's search sources: the settings menu
builds its rows from it, the result limit is split using it, and the search plan
prompt offers the LLM these source names. Adding a source here is all it takes for it
to exist everywhere, though search_settings.py separately picks which ones start out
enabled.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from core.models.media import MediaType
from services.ddg_search import fetch_web_image_results
from services.giphy_search import fetch_giphy_gif_results
from services.pexels_search import (
    fetch_pexels_image_results,
    fetch_pexels_video_results,
)
from services.pixabay_search import (
    fetch_pixabay_image_results,
    fetch_pixabay_video_results,
)
from services.search_common import SearchResult

FetchFn = Callable[..., list[SearchResult]]


@dataclass(frozen=True)
class SearchProvider:
    """One search source the user can switch on or off.

    'label' is what the settings menu shows. 'group' is the top-level menu row the
    source sits under, and sources sharing a group divide that row's share of the
    result limit between them. 'fetch' is called as fetch(query, limit=...), plus
    min_duration_s=... when 'media_type' is VIDEO.
    """

    label: str
    group: str
    media_type: MediaType
    fetch: FetchFn


# Insertion order is menu order, and the order results are merged in.
SEARCH_PROVIDERS: dict[str, SearchProvider] = {
    "web": SearchProvider(
        label="web",
        group="web",
        media_type=MediaType.IMAGE,
        fetch=fetch_web_image_results,
    ),
    "giphy": SearchProvider(
        label="Giphy",
        group="giphy",
        media_type=MediaType.GIF,
        fetch=fetch_giphy_gif_results,
    ),
    "pexels_video": SearchProvider(
        label="Video",
        group="pexels",
        media_type=MediaType.VIDEO,
        fetch=fetch_pexels_video_results,
    ),
    "pexels_image": SearchProvider(
        label="Image",
        group="pexels",
        media_type=MediaType.IMAGE,
        fetch=fetch_pexels_image_results,
    ),
    "pixabay_video": SearchProvider(
        label="Video",
        group="pixabay",
        media_type=MediaType.VIDEO,
        fetch=fetch_pixabay_video_results,
    ),
    "pixabay_image": SearchProvider(
        label="Image",
        group="pixabay",
        media_type=MediaType.IMAGE,
        fetch=fetch_pixabay_image_results,
    ),
}

# Menu text for groups holding more than one source. A group with a single source is
# named after that source instead.
_GROUP_LABELS: dict[str, str] = {"pexels": "Pexels", "pixabay": "Pixabay"}


def search_groups() -> dict[str, list[str]]:
    """Provider keys grouped by the menu row they belong to, in registry order."""
    groups: dict[str, list[str]] = {}
    for key, provider in SEARCH_PROVIDERS.items():
        groups.setdefault(provider.group, []).append(key)
    return groups


def group_label(group: str) -> str:
    """Menu text for a group row."""
    keys = search_groups()[group]
    if len(keys) == 1:
        return SEARCH_PROVIDERS[keys[0]].label
    return _GROUP_LABELS[group]


def split_evenly(total: int, keys: list[str]) -> dict[str, int]:
    """Split total across keys as evenly as possible, remainder goes left-to-right."""
    if total <= 0 or not keys:
        return {key: 0 for key in keys}
    base = total // len(keys)
    rem = total % len(keys)
    out: dict[str, int] = {}
    for i, key in enumerate(keys):
        out[key] = base + (1 if i < rem else 0)
    return out


def build_search_distribution(*, limit: int, enabled: set[str]) -> dict[str, int]:
    """Decide how many results each enabled source should return.

    Every enabled group gets an equal share of the limit, and the sources within a
    group then divide that share, so turning on both Pexels rows does not give Pexels
    twice the space of the web row.
    """
    active_by_group: dict[str, list[str]] = {}
    for key, provider in SEARCH_PROVIDERS.items():
        if key in enabled:
            active_by_group.setdefault(provider.group, []).append(key)

    group_shares = split_evenly(limit, list(active_by_group))
    distribution: dict[str, int] = {}
    for group, keys in active_by_group.items():
        distribution.update(split_evenly(group_shares[group], keys))
    return distribution


def _safe_fetch(key: str, *, query: str, limit: int, min_duration_s: float) -> list[SearchResult]:
    """Run one source, logging and returning nothing if it fails, so the rest still run."""
    provider = SEARCH_PROVIDERS[key]
    try:
        if provider.media_type is MediaType.VIDEO:
            return provider.fetch(query, limit=limit, min_duration_s=min_duration_s) or []
        return provider.fetch(query, limit=limit) or []
    except Exception as exc:
        print(f"[search] '{key}' fetch failed: {exc}")
        return []


def run_distributed_search(
    query: str,
    *,
    limit: int,
    enabled: set[str],
    min_duration_s: float,
) -> list[SearchResult]:
    """Search every enabled source at once and merge the hits into one list.

    Duplicate URLs are dropped and the merge stops at limit, keeping registry order so
    the tiles stay grouped by source. Videos shorter than min_duration_s are left out
    by the video sources themselves.
    """
    distribution = build_search_distribution(limit=limit, enabled=enabled)
    shares = [(key, share) for key, share in distribution.items() if share > 0]
    if not shares:
        return []

    with ThreadPoolExecutor(max_workers=len(shares)) as executor:
        futures = [
            executor.submit(
                _safe_fetch,
                key,
                query=query,
                limit=share,
                min_duration_s=min_duration_s,
            )
            for key, share in shares
        ]
        per_provider = [future.result() for future in futures]

    merged: list[SearchResult] = []
    seen_urls: set[str] = set()
    for results in per_provider:
        for result in results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged

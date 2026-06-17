from core.models.media import MediaType
from ui.cache.segment_search_cache import SegmentSearchResult


def split_evenly(total: int, targets: list[str]) -> dict[str, int]:
    """Split total across targets as evenly as possible, remainder goes left-to-right."""
    if total <= 0 or not targets:
        return {name: 0 for name in targets}
    base = total // len(targets)
    rem = total % len(targets)
    out: dict[str, int] = {}
    for i, name in enumerate(targets):
        out[name] = base + (1 if i < rem else 0)
    return out


def build_source_distribution(
    *,
    limit: int,
    use_google: bool,
    use_giphy: bool,
    use_pexels_images: bool,
    use_pexels_videos: bool,
    use_pixabay_images: bool,
    use_pixabay_videos: bool,
) -> dict[str, int]:
    """Distribute result counts by top-level source, then submenu children."""
    active_groups: list[str] = []
    if use_google:
        active_groups.append("google")
    if use_giphy:
        active_groups.append("giphy")
    pexels_children = [
        c
        for c, enabled in (
            ("pexels_image", use_pexels_images),
            ("pexels_video", use_pexels_videos),
        )
        if enabled
    ]
    if pexels_children:
        active_groups.append("pexels")
    pixabay_children = [
        c
        for c, enabled in (
            ("pixabay_image", use_pixabay_images),
            ("pixabay_video", use_pixabay_videos),
        )
        if enabled
    ]
    if pixabay_children:
        active_groups.append("pixabay")

    # high-level source distribution
    group_distribution = split_evenly(limit, active_groups)
    # total source distribution
    source_distribution: dict[str, int] = {}
    
    if "google" in group_distribution:
        source_distribution["google"] = group_distribution["google"]
    if "giphy" in group_distribution:
        source_distribution["giphy"] = group_distribution["giphy"]
    if "pexels" in group_distribution:
        source_distribution.update(
            split_evenly(group_distribution["pexels"], pexels_children)
        )
    if "pixabay" in group_distribution:
        source_distribution.update(
            split_evenly(group_distribution["pixabay"], pixabay_children)
        )
    return source_distribution


def to_cached_results(
    items: list[tuple[MediaType, str, bytes, str]],
) -> list[SegmentSearchResult]:
    """Convert normalized items to cache payload."""
    return [
        SegmentSearchResult(
            media_type=media_type,
            url=url,
            thumb_bytes=bytes(thumb_bytes),
            source=source,
        )
        for media_type, url, thumb_bytes, source in items
    ]
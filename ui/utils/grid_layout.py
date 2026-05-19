def column_count_for_viewport(
    viewport_width: int,
    *,
    tile_size_px: int,
    grid_spacing: int,
    max_cols: int = 4,
) -> int:
    """How many segment tiles fit in a scroll area viewport (shared by project + segment views)."""
    cell = tile_size_px + grid_spacing
    cols = max(1, (max(1, viewport_width) + grid_spacing) // max(1, cell))
    return min(max_cols, cols)

from collections.abc import Sequence

from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget


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


def relayout_grid(
    tiles: Sequence[QWidget],
    *,
    scroll: QScrollArea,
    grid: QGridLayout,
    tile_size_px: int,
    grid_spacing: int,
) -> None:
    """Lay 'tiles' out left to right, wrapping at however many columns now fit.

    Call this after the viewport changes size. The same widgets are reused: the grid
    is emptied of its layout slots and the tiles are added back at new row/column
    positions. Emptying the grid does not destroy them, because the caller is what
    owns them.
    """
    cols = column_count_for_viewport(
        scroll.viewport().width(),
        tile_size_px=tile_size_px,
        grid_spacing=grid_spacing,
    )

    while grid.count():
        item = grid.takeAt(0)
        if item is None:
            break

    for i, tile in enumerate(tiles):
        grid.addWidget(tile, i // cols, i % cols)
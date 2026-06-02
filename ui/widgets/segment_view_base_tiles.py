from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.styles.qss import (
    ACCENT_ICON_LABEL,
    ACTION_BUTTON,
    GHOST_ICON_BUTTON,
    INPUT,
    MUTED_LABEL,
    SECTION_TITLE_LABEL,
    SMALL_MUTED_LABEL,
)
from ui.widgets.search_settings import build_search_settings_menu
from ui.widgets.hover_media_preview import HoverMediaPreview
from ui.cache.segment_preview_cache import SegmentPreviewCache
from ui.widgets.tile_frame import TileFrame


@dataclass
class SegmentBaseTiles:
    """Container for built base tiles and key child widgets used by controller code."""

    tiles: list[QWidget]
    media_preview: HoverMediaPreview
    search_input: QLineEdit
    search_button: QPushButton
    search_status: QLabel


def build_base_tiles(
    *,
    parent: QWidget,
    tile_size_px: int,
    preview_cache: SegmentPreviewCache,
    on_search_clicked,
) -> SegmentBaseTiles:
    tiles: list[QWidget] = []

    # (1) Current attached media tile
    media_tile = TileFrame(size_px=tile_size_px, parent=parent)
    media_root = QVBoxLayout(media_tile)
    media_root.setContentsMargins(12, 12, 12, 12)
    media_root.setSpacing(10)

    media_title = QLabel("Media", media_tile)
    media_title.setStyleSheet(SECTION_TITLE_LABEL)
    media_root.addWidget(media_title, 0)

    media_body = HoverMediaPreview(
        tile_size_px=tile_size_px,
        reserved=48,
        placeholder_text="No media selected",
        cache=preview_cache,
        parent=media_tile,
    )
    media_root.addWidget(media_body, 1)

    # (2) Upload media tile
    upload_tile = TileFrame(size_px=tile_size_px, parent=parent)
    upload_root = QVBoxLayout(upload_tile)
    upload_root.setContentsMargins(12, 12, 12, 12)
    upload_root.setSpacing(10)

    upload_title = QLabel("Upload media", upload_tile)
    upload_title.setStyleSheet(SECTION_TITLE_LABEL)
    upload_root.addWidget(upload_title, 0)

    upload_icon = QLabel("⬆", upload_tile)
    upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    upload_icon.setStyleSheet(ACCENT_ICON_LABEL)
    upload_root.addWidget(upload_icon, 1)

    browse_btn = QPushButton("Browse…", upload_tile)
    browse_btn.setEnabled(False)
    browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    browse_btn.setStyleSheet(ACTION_BUTTON)
    upload_root.addWidget(browse_btn, 0)

    # (3) Generate image tile
    gen_tile = TileFrame(size_px=tile_size_px, parent=parent)
    gen_root = QVBoxLayout(gen_tile)
    gen_root.setContentsMargins(12, 12, 12, 12)
    gen_root.setSpacing(10)

    gen_title = QLabel("Generate image", gen_tile)
    gen_title.setStyleSheet(SECTION_TITLE_LABEL)
    gen_root.addWidget(gen_title, 0)

    gen_hint = QLabel("Generate a new image for this segment.", gen_tile)
    gen_hint.setWordWrap(True)
    gen_hint.setStyleSheet(MUTED_LABEL)
    gen_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    gen_root.addWidget(gen_hint, 1)

    gen_btn = QPushButton("Generate", gen_tile)
    gen_btn.setEnabled(False)
    gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    gen_btn.setStyleSheet(ACTION_BUTTON)
    gen_root.addWidget(gen_btn, 0)

    # (4) Search tile
    search_tile = TileFrame(size_px=tile_size_px, parent=parent)
    search_root = QVBoxLayout(search_tile)
    search_root.setContentsMargins(12, 12, 12, 12)
    search_root.setSpacing(8)

    search_top = QHBoxLayout()
    search_top.setContentsMargins(0, 0, 0, 0)
    search_top.setSpacing(8)

    search_title = QLabel("Search", search_tile)
    search_title.setStyleSheet(SECTION_TITLE_LABEL)
    search_top.addWidget(search_title, 1)

    settings_btn = QPushButton("⚙", search_tile)
    settings_btn.setFixedSize(28, 28)
    settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    settings_btn.setStyleSheet(GHOST_ICON_BUTTON)
    search_settings_menu = build_search_settings_menu(search_tile)

    def _show_search_settings_menu() -> None:
        origin = settings_btn.mapToGlobal(QPoint(0, settings_btn.height()))
        search_settings_menu.popup(origin)

    settings_btn.clicked.connect(_show_search_settings_menu)
    search_top.addWidget(settings_btn, 0)
    search_root.addLayout(search_top, 0)

    search_input = QLineEdit(search_tile)
    search_input.setPlaceholderText("Search keyword…")
    search_input.setStyleSheet(INPUT)
    search_root.addWidget(search_input, 0)

    search_btn = QPushButton("Search", search_tile)
    search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    search_btn.setStyleSheet(ACTION_BUTTON)
    search_btn.clicked.connect(on_search_clicked)
    search_input.returnPressed.connect(on_search_clicked)
    search_root.addWidget(search_btn, 0)

    search_status = QLabel("", search_tile)
    search_status.setWordWrap(True)
    search_status.setStyleSheet(SMALL_MUTED_LABEL)
    search_root.addWidget(search_status, 1)

    tiles.extend([media_tile, upload_tile, gen_tile, search_tile])
    return SegmentBaseTiles(
        tiles=tiles,
        media_preview=media_body,
        search_input=search_input,
        search_button=search_btn,
        search_status=search_status,
    )
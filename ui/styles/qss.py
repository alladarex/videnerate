# Common text
TITLE_LABEL = "font-size: 20px; font-weight: 600; color: #eaeaea;"
SECTION_TITLE_LABEL = "font-size: 14px; font-weight: 700; color: #eaeaea;"
MUTED_LABEL = "color: #9ca3af;"
SMALL_MUTED_LABEL = "color: #9ca3af; font-size: 12px;"
ACCENT_ICON_LABEL = "font-size: 36px; color: #c4b5fd;"

# Shared cards / bars
TILE_FRAME = """
QFrame#SegmentTile {
  border-radius: 10px;
  background: #141414;
  border: 1px solid #232323;
}
"""

SEGMENT_TILE_EXTRA = """
QScrollArea#SegmentTileHeaderScroll {
  background: transparent;
}
QLabel#SegmentTileHeaderLabel {
  font-size: 14px;
  font-weight: 600;
  color: #eaeaea;
  background: transparent;
}
"""

HIDE_SCROLLBARS = """
QScrollBar:horizontal { height: 0px; }
QScrollBar:vertical { width: 0px; }
"""

ACTION_BUTTON = """
QPushButton {
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 14px;
  font-weight: 600;
  color: #eaeaea;
  background: #1b1b1b;
}
QPushButton:hover { background: #222; }
QPushButton:pressed { background: #2a2a2a; }
QPushButton:disabled { color: #555; background: #141414; border-color: #2a2a2a; }
"""

INPUT = """
QLineEdit {
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 8px 10px;
  color: #eaeaea;
  background: #0f0f0f;
}
"""

GHOST_ICON_BUTTON = """
QPushButton {
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  color: #eaeaea;
  background: transparent;
}
QPushButton:disabled { color: #555; border-color: #1f1f1f; }
"""

ICON_CLOSE_BUTTON = """
QPushButton {
  border: none;
  border-radius: 8px;
  font-size: 22px;
  font-weight: 600;
  color: #eaeaea;
  background: transparent;
}
QPushButton:hover { background: #2a2a2a; }
QPushButton:pressed { background: #333; }
"""

NAV_ARROW_BUTTON = """
QPushButton#SegmentNavArrow {
  border: none;
  border-radius: 8px;
  font-size: 22px;
  font-weight: 600;
  color: #eaeaea;
  background: transparent;
}
QPushButton#SegmentNavArrow:hover { background: #2a2a2a; }
QPushButton#SegmentNavArrow:pressed { background: #333; }
QPushButton#SegmentNavArrow:disabled { color: #555; background: transparent; }
"""

# Nav dot fill by segment state. Grey also covers queued auto-search segments,
# because nothing is happening for them yet.
_NAV_DOT_FILL = {
    "idle": "#6b7280",
    "working": "#3f3f46",
    "ready": "#f59e0b",
    "attached": "#22c55e",
}


def nav_dot_style(state: str, *, is_current: bool) -> str:
    """Fill carries the segment's state, border marks the current segment."""
    fill = _NAV_DOT_FILL[state]
    border = "2px solid #ffffff" if is_current else "none"
    hover = "" if is_current else "QPushButton#SegmentNavDot:hover { border: 1px solid #9ca3af; }"
    return f"""
QPushButton#SegmentNavDot {{
  border: {border};
  border-radius: 3px;
  background: {fill};
}}
{hover}
"""


TRANSPARENT_SCROLL = "QScrollArea { background: transparent; }"


def top_bar_style(object_name: str) -> str:
    return f"""
QFrame#{object_name} {{
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
}}
"""

from pathlib import Path

_UI_DIR = Path(__file__).resolve().parents[1]
_ICONS_DIR = _UI_DIR / "assets" / "icons"


def icon_path(name: str) -> Path:
    """Path to a file under ``ui/assets/icons/``."""
    return _ICONS_DIR / name

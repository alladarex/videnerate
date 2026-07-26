"""Single JSON writer so every file we persist uses the same formatting."""

import json
from pathlib import Path
from typing import Any


def save_json(path: Path, payload: Any) -> None:
    """Write payload as UTF-8 JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

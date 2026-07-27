"""Write one text report file per Whisper alignment run."""
import re
from datetime import datetime
from pathlib import Path

from config import APP_DIR
from core.project_paths import ProjectPaths

REPORT_DIR = APP_DIR / "logs" / "alignment"


def _safe_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
    return cleaned or "project"


def write_alignment_report(
    paths: ProjectPaths,
    *,
    success: bool,
    lines: list[str],
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    status = "SUCCESS" if success else "FAILURE"
    filename = f"{stamp}_{_safe_name(paths.root.name)}_{status}.txt"
    report_path = REPORT_DIR / filename

    header_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{header_time}  {paths.root}\n[{status}]\n"
    body = "\n".join(lines) + "\n"
    report_path.write_text(header + body, encoding="utf-8")
    return report_path
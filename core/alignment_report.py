"""Write one text report file per Whisper alignment run."""

from datetime import datetime
from pathlib import Path

from config import APP_DIR
from core.project_paths import ProjectPaths, sanitize_filename

_REPORT_DIR = APP_DIR / "logs" / "alignment"


def write_alignment_report(
    paths: ProjectPaths,
    *,
    success: bool,
    lines: list[str],
) -> Path:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    status = "SUCCESS" if success else "FAILURE"
    filename = f"{stamp}_{sanitize_filename(paths.root.name) or 'project'}_{status}.txt"
    report_path = _REPORT_DIR / filename

    header_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{header_time}  {paths.root}\n[{status}]\n"
    body = "\n".join(lines) + "\n"
    report_path.write_text(header + body, encoding="utf-8")
    return report_path

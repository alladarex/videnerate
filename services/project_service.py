import json
import re
from pathlib import Path

from core.models.project import Project
from core.voiceover import AUDIO_SUBDIR, voiceover_relative_path
from config import PROJECTS_DIR
from services.voiceover_service import write_project_voiceover

PROJECT_JSON_FILENAME = "project.json"
NARRATION_FILENAME = "narration.txt"

INVALID_FOLDER_CHARS = set('<>:"/\\|?*')


def validate_project_title_for_storage(title: str) -> str:
    """Return stripped title for use as the project folder name. Raises ValueError if invalid."""
    normalized = title.strip()
    if not normalized:
        raise ValueError("Project title cannot be empty.")
    if normalized.endswith("."):
        raise ValueError("Project title cannot end with a period.")
    if any(char in INVALID_FOLDER_CHARS for char in normalized):
        raise ValueError(
            "Project title cannot contain invalid path characters: "
            + " ".join(sorted(INVALID_FOLDER_CHARS))
        )
    return normalized


def list_project_titles(projects_dir: Path | None = None) -> list[str]:
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    if not projects_dir.exists():
        return []

    return sorted([item.name for item in projects_dir.iterdir() if item.is_dir()])


def load_project(title: str, projects_dir: Path | None = None) -> Project:
    """Load a project by title from its JSON file."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    project_dir = projects_dir / title
    json_path = project_dir / PROJECT_JSON_FILENAME
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project folder not found: {project_dir}")
    if not json_path.is_file():
        raise FileNotFoundError(f"Project file not found: {json_path}")
    raw = json_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return Project.from_dict(data)


def get_next_project_title(projects_dir: Path | None = None) -> str:
    """Return first available Project_x title based on existing project folders."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    max_index = 0
    pattern = re.compile(r"^Project_(\d+)$")

    if projects_dir.exists():
        for item in projects_dir.iterdir():
            if not item.is_dir():
                continue
            match = pattern.match(item.name)
            if not match:
                continue
            max_index = max(max_index, int(match.group(1)))

    return f"Project_{max_index + 1}"


def create_project_from_segments(
    segments: list[str],
    title: str = "Untitled",
    voiceover_path: str | None = None,
) -> Project:
    """Create a new in-memory Project from segment texts (no saving)."""
    return Project(segments=segments, title=title, voiceover_path=voiceover_path)

def create_and_save_project(
    segments: list[str], title: str = "Untitled", narration: str | None = None
) -> Project:
    """Create a new project and save it to the filesystem."""
    dir_name = validate_project_title_for_storage(title)
    project_dir = PROJECTS_DIR / dir_name
    project_dir.mkdir(parents=True, exist_ok=True)

    voiceover_rel: str | None = None
    if narration is not None:
        (project_dir / NARRATION_FILENAME).write_text(narration, encoding="utf-8")
        if narration.strip():
            audio_dir = project_dir / AUDIO_SUBDIR
            audio_dir.mkdir(parents=True, exist_ok=True)
            write_project_voiceover(narration, audio_dir)
            voiceover_rel = voiceover_relative_path()

    project = create_project_from_segments(segments, title=dir_name, voiceover_path=voiceover_rel)
    json_path = project_dir / PROJECT_JSON_FILENAME
    payload = project.to_dict()
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return project

def is_project_title_unique(title: str, projects_dir: Path | None = None) -> bool:
    """Return True when no existing project folder has the same name."""
    projects_dir = PROJECTS_DIR if projects_dir is None else projects_dir
    normalized = title.strip().casefold()
    if not normalized or not projects_dir.exists():
        return True

    for item in projects_dir.iterdir():
        if item.is_dir() and item.name.casefold() == normalized:
            return False
    return True

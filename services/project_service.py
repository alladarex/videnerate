import json
import re
import hashlib
import shutil
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.json_io import save_json
from core.media_ext import resolve_media_ext
from core.models.project import Project
from core.models.media import Media
from config import PROJECTS_DIR
from headers import BROWSER_HEADERS
from core.project_paths import ProjectPaths
from core.word_tokenize import assert_segment_words_match_narration, normalize_text
from services.alignment_service import align_project_audio
from services.llm_service import generate_segment_search_plan
from services.media_search import search_groups
from services.voiceover_service import generate_voiceover_mp3

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


def list_project_titles() -> list[str]:
    root = PROJECTS_DIR
    if not root.exists():
        return []
    return sorted(item.name for item in root.iterdir() if item.is_dir())


def get_next_project_title() -> str:
    """Return first available Project_x title based on existing project folders."""
    root = PROJECTS_DIR
    max_index = 0
    pattern = re.compile(r"^Project_(\d+)$")
    if root.exists():
        for item in root.iterdir():
            if not item.is_dir():
                continue
            match = pattern.match(item.name)
            if match:
                max_index = max(max_index, int(match.group(1)))
    return f"Project_{max_index + 1}"


def is_project_title_unique(title: str) -> bool:
    """Return True when no existing project folder has the same name."""
    root = PROJECTS_DIR
    normalized = title.strip().casefold()
    if not normalized or not root.exists():
        return True
    return not any(
        item.is_dir() and item.name.casefold() == normalized for item in root.iterdir()
    )


def load_project(title: str) -> Project:
    """Load a project by title from its JSON file."""
    paths = ProjectPaths.from_title(title)
    paths.require_existing()
    raw = paths.project_json.read_text(encoding="utf-8")
    return Project.from_dict(json.loads(raw))


def _rel_path(paths: ProjectPaths, path: Path) -> str:
    return path.resolve().relative_to(paths.root.resolve()).as_posix()


def _write_segments_analyzed_file(
    paths: ProjectPaths, segments: list[str], selected_model: str
) -> None:
    segments_payload = {
        "available_sources": list(search_groups()),
        "segments": [
            {"id": idx, "text": text}
            for idx, text in enumerate(segments, start=1)
        ],
    }
    analyzed_text = generate_segment_search_plan(
        json.dumps(segments_payload, ensure_ascii=False, indent=2),
        selected_model=selected_model,
    )
    paths.segments_analyzed_json.write_text(
        analyzed_text,
        encoding="utf-8",
    )


def create_and_save_project(
    segments: list[str],
    narration: str,
    title: str = "Untitled",
    auto_assign: bool = False,
    selected_model: str = "deepseek-reasoner",
    on_status: Callable[[str], None] | None = None,
) -> Project:
    """Create a new project and save it to the filesystem."""

    if not narration:
        raise ValueError("Narration is required.")
    if not segments:
        raise ValueError("Segments are required.")

    def status(message: str) -> None:
        if on_status is not None:
            on_status(message)

    status("Setting up project...")
    dir_name = validate_project_title_for_storage(title)
    paths = ProjectPaths.from_title(dir_name)
    paths.ensure_layout()

    segments = [normalize_text(text.strip()) for text in segments]

    narration = normalize_text(narration.strip())
    assert_segment_words_match_narration(narration, segments)
    paths.narration_txt.write_text(narration, encoding="utf-8")

    status("Generating voiceover...")
    generate_voiceover_mp3(narration, paths.voiceover_mp3)
    project = Project.from_segment_texts(segments, title=dir_name)

    status("Aligning audio to narration...")
    align_project_audio(project)

    status("Saving project...")
    save_json(paths.project_json, project.to_dict())

    if auto_assign:
        status("Analyzing segments...")
        segment_texts = [seg.text for seg in project.segments]
        _write_segments_analyzed_file(paths, segment_texts, selected_model)
    return project


def _download_url_to_path(url: str, dest_base: Path, *, timeout_s: float = 20.0) -> Path:
    """Download url to dest_base + resolved extension. Returns the final path."""
    dest_base.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        ext = resolve_media_ext(url, resp.headers.get("Content-Type"))
    dest = dest_base.with_suffix(ext)
    dest.write_bytes(data)
    return dest


def _ensure_media_persisted(paths: ProjectPaths, segment_id: int, media: Media) -> None:
    """Ensure media is persisted under media/ by modifying media object.

    If media.url is set, downloads it into media/ and sets file_path to the result. 
    If media.file_path points outside media/, copies it into media/.
    """
    media_dir = paths.media_dir
    media_dir.mkdir(parents=True, exist_ok=True)

    # If already a file_path, ensure it's inside media dir
    if media.file_path:
        src = paths.file(media.file_path)
        if src.is_file():
            try:
                src.relative_to(media_dir.resolve())
                # Already in media dir, normalize to a relative path
                media.file_path = _rel_path(paths, src)
                return
            except ValueError:
                pass

            # Copy into media dir
            ext = src.suffix.lower()
            if not ext:
                raise ValueError(
                    f"Cannot persist media from extensionless path: {src} (segment_id={segment_id})"
                )
            name = f"{segment_id}_{hashlib.sha256(str(src).encode('utf-8')).hexdigest()[:16]}{ext}"
            dest = media_dir / name
            if not dest.exists():
                shutil.copyfile(src, dest)
            media.file_path = _rel_path(paths, dest)
            return

        return

    # Otherwise, download from URL if present
    if media.url:
        url = media.url
        # Extension is added during download.
        base_name = f"{segment_id}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"
        dest = _download_url_to_path(url, media_dir / base_name)
        media.file_path = _rel_path(paths, dest)
        return

    return


def _cleanup_unused_project_media(paths: ProjectPaths, project: Project) -> None:
    """Delete unreferenced files in <project>/media/ based on current segment media."""
    media_dir = paths.media_dir
    if not media_dir.is_dir():
        return

    referenced_files: set[Path] = set()
    for seg in project.segments:
        media = seg.media
        if media is None or not media.file_path:
            continue

        resolved = paths.file(media.file_path)
        try:
            resolved.relative_to(media_dir.resolve())
        except ValueError:
            # Ignore any path outside this project's media directory.
            continue
        if resolved.is_file():
            referenced_files.add(resolved)

    for media_file in media_dir.iterdir():
        if not media_file.is_file():
            continue
        try:
            resolved_media_file = media_file.resolve()
        except OSError:
            continue
        if resolved_media_file in referenced_files:
            continue
        try:
            media_file.unlink()
        except OSError:
            # Best effort cleanup, do not block save for deletion failures
            continue


def save_project(project: Project) -> Path:
    """Persist an existing in-memory project to disk.

    - Ensures <project>/media/ exists.
    - If a segment has media with a URL, downloads it into media/ and converts to file_path.
    - Writes project.json.
    - Cleans up unused media files from <project>/media/.

    Returns the absolute path to the project directory.
    """
    dir_name = validate_project_title_for_storage(project.title)
    paths = ProjectPaths.from_title(dir_name)
    paths.ensure_layout()

    # Save selected media to media/ folder (only for attached media)
    for seg in project.segments:
        if seg.media is None:
            continue
        try:
            _ensure_media_persisted(paths, seg.id, seg.media)
        except Exception:
            # Don't block saving the rest of the project on a single media failure
            continue

    save_json(paths.project_json, project.to_dict())
    _cleanup_unused_project_media(paths, project)
    return paths.root
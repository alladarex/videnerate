import json
import re
import hashlib
import shutil
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.models.project import Project
from core.models.media import GifMedia, ImageMedia, Media, VideoMedia
from config import PROJECTS_DIR
from headers import BROWSER_HEADERS
from core.project_paths import ProjectPaths
from core.scripter import generate_segment_search_plan
from core.word_tokenize import assert_segment_words_match_narration, normalize_text
from services.alignment_service import align_project_audio
from services.voiceover_service import write_project_voiceover

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


def create_project_from_segments(
    segments: list[str],
    title: str = "Untitled",
) -> Project:
    """Create a new in-memory Project from segment texts (no saving)."""
    return Project(segments=segments, title=title)


def _write_segments_analyzed_file(
    paths: ProjectPaths, segments: list[str], selected_model: str
) -> None:
    segments_payload = {
        "available_sources": ["google", "pexels", "pixabay", "giphy"],
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
    write_project_voiceover(narration, paths)
    project = create_project_from_segments(segments, title=dir_name)

    status("Aligning audio to narration...")
    align_project_audio(paths, project)

    status("Saving project...")
    payload = project.to_dict()
    paths.project_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if auto_assign:
        status("Analyzing segments...")
        segment_texts = [seg.text for seg in project.segments]
        _write_segments_analyzed_file(paths, segment_texts, selected_model)
    return project


def _guess_ext_from_url(url: str, *, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext and 1 < len(ext) <= 6:
        return ext
    return fallback


def _download_url_to_path(url: str, dest_path: Path, *, timeout_s: float = 20.0) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    dest_path.write_bytes(data)


def _ensure_media_persisted(paths: ProjectPaths, segment_id: int, media: Media) -> Media:
    """Return a Media with a stable file_path under media/ (downloading/copying if needed)."""
    media_dir = paths.media_dir
    media_dir.mkdir(parents=True, exist_ok=True)

    # If already a file_path, ensure it's inside media/.
    if media.file_path:
        src = paths.file(media.file_path)
        if src.is_file():
            try:
                src.relative_to(media_dir.resolve())
                # Already in media dir, keep as relative path for portability
                rel = _rel_path(paths, src)
                if isinstance(media, ImageMedia):
                    return ImageMedia(file_path=rel)
                if isinstance(media, GifMedia):
                    return GifMedia(file_path=rel)
                if isinstance(media, VideoMedia):
                    return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)
            except ValueError:
                pass

            # Copy into media dir
            ext = src.suffix.lower() or (
                ".jpg" if isinstance(media, ImageMedia) else ".gif" if isinstance(media, GifMedia) else ".mp4"
            )
            name = f"{segment_id}_{hashlib.sha256(str(src).encode('utf-8')).hexdigest()[:16]}{ext}"
            dest = media_dir / name
            if not dest.exists():
                shutil.copyfile(src, dest)
            rel = _rel_path(paths, dest)
            if isinstance(media, ImageMedia):
                return ImageMedia(file_path=rel)
            if isinstance(media, GifMedia):
                return GifMedia(file_path=rel)
            if isinstance(media, VideoMedia):
                return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)

        return media

    # Otherwise, download from URL if present
    if media.url:
        url = media.url
        fallback_ext = ".jpg" if isinstance(media, ImageMedia) else ".gif" if isinstance(media, GifMedia) else ".mp4"
        ext = _guess_ext_from_url(url, fallback=fallback_ext)
        name = f"{segment_id}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}{ext}"
        dest = media_dir / name
        if not dest.exists():
            _download_url_to_path(url, dest)
        rel = _rel_path(paths, dest)
        if isinstance(media, ImageMedia):
            return ImageMedia(file_path=rel)
        if isinstance(media, GifMedia):
            return GifMedia(file_path=rel)
        if isinstance(media, VideoMedia):
            return VideoMedia(file_path=rel, start_timestamp=media.start_timestamp)

    return media


def _cleanup_unused_project_media(paths: ProjectPaths, project: Project) -> None:
    """Delete unreferenced files in `<project>/media/` based on current segment media."""
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
            seg.media = _ensure_media_persisted(paths, seg.id, seg.media)
        except Exception:
            # Don't block saving the rest of the project on a single media failure
            continue

    paths.project_json.write_text(
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _cleanup_unused_project_media(paths, project)
    return paths.root
import hashlib
import json
import re
import shutil
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError

from config import PROJECTS_DIR
from core.json_io import save_json
from core.models.media import Media
from core.models.project import Project
from core.models.search_plan import SearchPlan
from core.models.segment import Segment
from core.project_paths import INVALID_FILENAME_CHARS, ProjectPaths
from core.word_tokenize import normalize_text, require_segment_words_match_narration
from services.alignment_service import align_project_audio
from services.llm_service import generate_segment_search_plan
from services.media_download import download_media
from services.voiceover_service import generate_voiceover_mp3


def validate_project_title_for_storage(title: str) -> str:
    """Return stripped title for use as the project folder name. Raises ValueError if invalid."""
    normalized = title.strip()
    if not normalized:
        raise ValueError("Project title cannot be empty.")
    if normalized.endswith("."):
        raise ValueError("Project title cannot end with a period.")
    if any(char in INVALID_FILENAME_CHARS for char in normalized):
        raise ValueError(
            "Project title cannot contain invalid path characters: "
            + " ".join(sorted(INVALID_FILENAME_CHARS))
        )
    return normalized


def list_project_titles() -> list[str]:
    root = PROJECTS_DIR
    if not root.exists():
        return []
    return sorted(item.name for item in root.iterdir() if item.is_dir())


def next_project_title() -> str:
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
    return not any(item.is_dir() and item.name.casefold() == normalized for item in root.iterdir())


def load_project(title: str) -> Project:
    """Load a project by title from its JSON file."""
    paths = ProjectPaths.from_title(title)
    paths.require_existing()
    raw = paths.project_json.read_text(encoding="utf-8")
    return Project.from_dict(json.loads(raw))


def _rel_path(paths: ProjectPaths, path: Path) -> str:
    return path.resolve().relative_to(paths.root.resolve()).as_posix()


def create_and_save_project(
    *,
    segments: list[str],
    narration: str,
    selected_model: str,
    title: str = "Untitled",
    auto_assign: bool = False,
    on_status: Callable[[str], None] | None = None,
) -> tuple[Project, SearchPlan | None]:
    """Create a new project and save it to the filesystem.

    'selected_model' plans the media search, so it only matters under auto-assign.
    The plan comes back alongside the project, and is None whenever auto-assign is
    off or the planning call failed.
    """

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
    # LLM can return segments that don't match the narration
    require_segment_words_match_narration(narration, segments)
    paths.narration_txt.write_text(narration, encoding="utf-8")

    project = Project.from_segment_texts(segments, title=dir_name)

    # Planning only needs the segment texts, so it runs while everything below does.
    # The pool is here for the Future, not for concurrency: a bare thread would drop
    # both the return value and the exception.
    plan_future: Future[SearchPlan] | None = None
    if auto_assign:
        planner = ThreadPoolExecutor(max_workers=1)
        plan_future = planner.submit(
            generate_segment_search_plan,
            {seg.id: seg.text for seg in project.segments},
            selected_model=selected_model,
        )
        planner.shutdown(wait=False)

    status("Generating voiceover...")
    generate_voiceover_mp3(narration, paths.voiceover_mp3)

    status("Aligning audio to narration...")
    align_project_audio(project)

    status("Saving project...")
    save_json(paths.project_json, project.to_dict())

    plan: SearchPlan | None = None
    if plan_future is not None:
        status("Analyzing segments...")
        try:
            plan = plan_future.result()
        except Exception as exc:
            # Auto-assign is optional, so a failed plan must not fail the project.
            print(f"[project_service] search plan unavailable: {exc}")

    if plan is not None:
        # Written for the user to read. The app never loads it back.
        save_json(paths.search_plan_json, plan.to_dict())
    return project, plan


def _ensure_media_persisted(paths: ProjectPaths, *, segment_id: int, media: Media) -> None:
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

        # The path is recorded but the file is gone
        raise FileNotFoundError(f"Media file is gone: {src} (segment_id={segment_id})")

    # Otherwise, download from URL if present
    if media.url:
        url = media.url
        # Extension is added during download.
        base_name = f"{segment_id}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"
        dest = download_media(url, media_dir / base_name)
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


def save_project(project: Project) -> list[Segment]:
    """Persist an existing in-memory project to disk.

    - Ensures <project>/media/ exists.
    - If a segment has media with a URL, downloads it into media/ and converts to file_path.
    - Writes project.json.
    - Cleans up unused media files from <project>/media/.

    Returns the segments whose media download failed. Media is set to None for the
    ones that failed with an http 4xx.
    """
    dir_name = validate_project_title_for_storage(project.title)
    paths = ProjectPaths.from_title(dir_name)
    paths.ensure_layout()

    # Save selected media to media/ folder (only for attached media)
    failed_segments: list[Segment] = []
    for seg in project.segments:
        if seg.media is None:
            continue
        try:
            _ensure_media_persisted(paths, segment_id=seg.id, media=seg.media)
        except Exception as exc:
            # Don't block saving the rest of the project on a single media failure
            print(f"[project_service] segment {seg.id} media not saved: {exc}")
            failed_segments.append(seg)
            # A 4xx error will also refuse the next request attempt,
            # a timeout says nothing about the URL, so only the 'dead' ones are dropped
            if isinstance(exc, HTTPError) and 400 <= exc.code < 500:
                seg.media = None

    save_json(paths.project_json, project.to_dict())
    _cleanup_unused_project_media(paths, project)
    return failed_segments

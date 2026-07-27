import subprocess
import sys

from core.alignment_report import write_alignment_report
from core.audio_alignment import assign_segment_word_ranges
from core.models.project import Project
from core.models.word_timeline import WordTimeline, load_word_timeline
from config import APP_DIR
from core.project_paths import ProjectPaths
from core.word_tokenize import tokenize_words

_ALIGN_TIMEOUT_S = 180


def _run_whisper_alignment_subprocess(paths: ProjectPaths) -> None:
    """
    Run Faster-Whisper in a child process.
    Safe alongside Qt, no subprocess causes a crash (0xC0000005 access violation).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "core.alignment_worker", str(paths.root)],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
            timeout=_ALIGN_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        write_alignment_report(
            paths,
            success=False,
            lines=[
                f"audio: {paths.voiceover_mp3.resolve()}",
                "stage: subprocess",
                f"error: timed out after {_ALIGN_TIMEOUT_S}s",
            ],
        )
        raise RuntimeError(
            f"Alignment subprocess timed out for {paths.root.name}"
        ) from exc
    except OSError as exc:
        write_alignment_report(
            paths,
            success=False,
            lines=[
                f"audio: {paths.voiceover_mp3.resolve()}",
                "stage: subprocess",
                f"error: {exc}",
            ],
        )
        raise RuntimeError(
            f"Failed to start alignment subprocess for {paths.root.name}"
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        write_alignment_report(
            paths,
            success=False,
            lines=[
                f"audio: {paths.voiceover_mp3.resolve()}",
                "stage: subprocess",
                f"exit_code: {result.returncode}",
                f"stderr: {detail or '(empty)'}",
            ],
        )
        raise RuntimeError(
            f"Alignment subprocess failed for {paths.root.name} "
            f"(exit {result.returncode}): {detail}"
        )


def align_project_audio(project: Project) -> WordTimeline:
    """Build word timeline and segment word indices from narration and voiceover."""
    paths = ProjectPaths.from_title(project.title)
    if not paths.narration_txt.is_file():
        raise FileNotFoundError(f"Narration file not found: {paths.narration_txt}")
    if not paths.voiceover_mp3.is_file():
        raise FileNotFoundError(f"Voiceover not found: {paths.voiceover_mp3}")

    narration = paths.narration_txt.read_text(encoding="utf-8").strip()
    if not narration:
        raise ValueError(f"Narration is empty: {paths.narration_txt}")

    ref_words = tokenize_words(narration)
    if not ref_words:
        raise ValueError("Narration has no words after tokenization.")

    _run_whisper_alignment_subprocess(paths)
    timeline = load_word_timeline(paths)
    assign_segment_word_ranges(project, ref_words)
    return timeline
"""Project voiceover file creation (Google TTS)."""

from pathlib import Path

from core.project_paths import ProjectPaths
from core.voiceover import generate_voiceover_mp3


def write_project_voiceover(
    narration: str, paths: ProjectPaths, *, remove_silence: bool = True
) -> Path:
    """Write narration as MP3 under the project audio directory. Returns the output file path."""
    generate_voiceover_mp3(narration, paths.voiceover_mp3, remove_silence=remove_silence)
    return paths.voiceover_mp3

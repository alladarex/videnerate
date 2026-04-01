"""Project voiceover file creation (Google TTS)."""

from pathlib import Path

from core.voiceover import VOICEOVER_FILENAME, generate_voiceover_mp3


def write_project_voiceover(
    narration: str, project_audio_dir: Path, *, remove_silence: bool = True
) -> Path:
    """Write narration as MP3 under ``project_audio_dir``. Returns the output file path."""
    project_audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_audio_dir / VOICEOVER_FILENAME
    generate_voiceover_mp3(narration, out_path, remove_silence=remove_silence)
    return out_path

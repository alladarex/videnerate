from pathlib import Path

from gtts import gTTS

AUDIO_SUBDIR = "audio"
VOICEOVER_FILENAME = "voiceover.mp3"


def voiceover_relative_path() -> str:
    """Path to the main voiceover file, relative to the project directory."""
    return f"{AUDIO_SUBDIR}/{VOICEOVER_FILENAME}"


def generate_voiceover_mp3(narration: str, output_path: Path, *, lang: str = "en") -> None:
    """Write narration as an MP3 file using gTTS."""
    text = narration.strip()
    if not text:
        raise ValueError("Narration is empty; cannot generate voiceover.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tts = gTTS(text=text, lang=lang)
    tts.save(str(output_path))

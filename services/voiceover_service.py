"""Project voiceover file creation (Google TTS)."""

from pathlib import Path

from gtts import gTTS
from pydub import AudioSegment
from pydub.silence import split_on_silence


def remove_silence_from_audio(
    audio: AudioSegment,
    *,
    min_silence_len: int = 400,
    silence_thresh: int = -40,
    keep_silence: int = 150,
) -> AudioSegment:
    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=keep_silence,
    )
    if not chunks:
        return audio

    combined = chunks[0]
    for chunk in chunks[1:]:
        combined += chunk
    return combined


def generate_voiceover_mp3(
    narration: str,
    output_path: Path,
    *,
    lang: str = "en",
    remove_silence: bool = True,
) -> Path:
    """Create voiceover audio file using gTTS. Returns the path it wrote."""
    text = narration.strip()
    if not text:
        raise ValueError("Narration is empty; cannot generate voiceover.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(str(tmp_path))

        if not remove_silence:
            tmp_path.replace(output_path)
            return output_path

        audio = AudioSegment.from_file(tmp_path)
        processed = remove_silence_from_audio(audio)
        processed.export(output_path, format="mp3")
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return output_path

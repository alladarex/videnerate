from dataclasses import dataclass


@dataclass
class ExportSettings:
    vertical: bool = True
    width: int = 1080
    height: int = 1920
    subtitles: bool = False
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"

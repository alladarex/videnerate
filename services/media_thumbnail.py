from pathlib import Path

import ffmpeg


def extract_video_frame_bytes(path: Path) -> bytes | None:
    """Extract first frame bytes from a video file, or None on failure."""
    if not path.is_file():
        return None
    try:
        out, _ = (
            ffmpeg.input(str(path), ss=0)
            .output("pipe:", vframes=1, format="image2", vcodec="mjpeg")
            .global_args("-loglevel", "error")
            .run(capture_stdout=True, capture_stderr=True)
        )
    except Exception:
        return None
    return out or None

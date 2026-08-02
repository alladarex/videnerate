#!/usr/bin/env python3
"""
Extract N evenly spaced frames from a video and stack them vertically
(top = first frame, bottom = last). Requires ffmpeg and ffprobe on PATH.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"Command failed ({r.returncode}): {' '.join(cmd)}\n{err}")


def probe_duration_seconds(video: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    s = (out.stdout or "").strip()
    if not s or s == "N/A":
        raise RuntimeError("Could not read video duration.")
    return float(s)


def even_timestamps(duration: float, n: int) -> list[float]:
    if n < 1:
        raise ValueError("n must be >= 1")
    if n == 1:
        return [0.0]
    # Keep last sample inside the stream: input-side -ss can land past the final
    # decodable frame if we use duration - tiny_epsilon only.
    last = max(0.0, duration - 0.25)
    if last <= 0:
        return [0.0] * n
    return [i * last / (n - 1) for i in range(n)]


def extract_frame(video: Path, t: float, png_out: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{t:.6f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(png_out),
        ]
    )


def vstack_pngs(inputs: list[Path], out_png: Path) -> None:
    n = len(inputs)
    args: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for p in inputs:
        args.extend(["-i", str(p)])
    labels = "".join(f"[{i}:v]" for i in range(n))
    filt = f"{labels}vstack=inputs={n}[v]"
    args.extend(["-filter_complex", filt, "-map", "[v]", str(out_png)])
    _run(args)


def main() -> int:
    p = argparse.ArgumentParser(description="Stack N evenly spaced video frames vertically.")
    p.add_argument("video", type=Path, help="Input video file")
    p.add_argument(
        "-n",
        "--num-frames",
        type=int,
        required=True,
        help="Number of frames (>=1). First at start, last near end.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output image (default: <video_stem>_strip.png)",
    )
    args = p.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg and ffprobe must be on PATH.", file=sys.stderr)
        return 1

    video = args.video.resolve()
    if not video.is_file():
        print(f"Not a file: {video}", file=sys.stderr)
        return 1

    n = args.num_frames
    if n < 1:
        print("--num-frames must be >= 1", file=sys.stderr)
        return 1

    out = args.output
    if out is None:
        out = video.with_name(f"{video.stem}_strip.png")
    else:
        out = out.resolve()

    duration = probe_duration_seconds(video)
    times = even_timestamps(duration, n)

    with tempfile.TemporaryDirectory(prefix="frame_strip_") as td:
        tmp = Path(td)
        frames: list[Path] = []
        for i, t in enumerate(times):
            fp = tmp / f"f{i:04d}.png"
            extract_frame(video, t, fp)
            frames.append(fp)
        vstack_pngs(frames, out)

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

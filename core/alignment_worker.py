"""Subprocess entry point: build word_timeline.json (avoids Qt + Whisper DLL clash)."""

import sys
from pathlib import Path

from core.audio_alignment import build_word_timeline
from core.models.word_timeline import save_word_timeline
from core.project_paths import ProjectPaths


def main(project_root: Path) -> int:
    # Raw Path, not ProjectPaths: argv can only carry text, so paths are built here.
    paths = ProjectPaths.from_root(project_root)
    narration = paths.narration_txt.read_text(encoding="utf-8")
    timeline = build_word_timeline(
        paths.voiceover_mp3,
        narration,
        paths=paths,
    )
    save_word_timeline(paths, timeline)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m core.alignment_worker <project_root>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))

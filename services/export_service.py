"""Render the project to an MP4 by stitching together segment media with the voiceover."""

import warnings
from threading import Event
from collections.abc import Callable
from pathlib import Path

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    VideoFileClip,
)
from moviepy.video.fx import Loop
from proglog import ProgressBarLogger

from core.export_settings import ExportSettings
from core.models.media import GifMedia, ImageMedia, VideoMedia
from core.models.project import Project
from core.models.segment import Segment
from core.models.word_timeline import load_word_timeline, segment_playback_bounds
from core.project_paths import ProjectPaths
from services.project_service import save_project


class ExportCancelled(Exception):
    pass


class _EncodeProgressLogger(ProgressBarLogger):
    """Report encoding frame progress as phase 2, 0–100%."""

    def __init__(
        self,
        on_progress: Callable[[int, int, str], None],
        *,
        message: str,
        cancel_event: Event | None,
    ) -> None:
        super().__init__()
        self._on_progress = on_progress
        self._message = message
        self._cancel_event = cancel_event

    def bars_callback(self, bar, attr, value, old_value=None) -> None:
        if self._cancel_event is not None and self._cancel_event.is_set():
            raise ExportCancelled()
        if bar != "frame_index":
            return
        if attr != "index":
            return
        bar_info = self.bars.get(bar)
        if not bar_info:
            return
        total = bar_info.get("total")
        if not total or total <= 0:
            return
        index = bar_info.get("index", 0)
        if index < 0:
            return
        pct = int(index * 100 / total)
        self._on_progress(2, pct, self._message)


def _fit(clip: VideoClip, width: int, height: int) -> VideoClip:
    """Scale clip so it fits fully within width x height (preserve aspect, center)."""
    scale = min(width / clip.w, height / clip.h)
    return clip.resized(scale).with_position("center")


def _silent_video_clip(file_path: str) -> VideoClip:
    """Open a video file with its audio track released.

    Exports use the project voiceover only, and 'without_audio()' returns a copy whose
    'audio' is None - which orphans the source audio reader unless it is closed here.
    """
    clip = VideoFileClip(file_path)
    if clip.audio is not None:
        clip.audio.close()
    return clip.without_audio()


def _close_clip(clip: VideoClip) -> None:
    """Close a clip and anything composited inside it.

    'CompositeVideoClip.close()' releases only its own background and audio, never the
    clips it composites, so a nested VideoFileClip keeps its ffmpeg subprocess alive
    until interpreter shutdown - where '__del__' then fails on an invalid handle.
    """
    for child in getattr(clip, "clips", None) or []:
        _close_clip(child)
    try:
        clip.close()
    except Exception:
        pass


_SOURCE_OVERLAY_MARGIN_PX = 12
_SOURCE_OVERLAY_FONT_SIZE = 34
_SOURCE_OVERLAY_TEXT_MARGIN = (4, 4, 2, 6)  # L, R, T, B — room for descenders + stroke
_HTTP_PREFIXES = ("https://www.", "http://www.", "https://", "http://")


def _add_source_overlay(
    clip: VideoClip,
    source: str,
    *,
    width: int,
    height: int,
    duration: float,
) -> VideoClip:
    """Burn a source label into the top-left corner over a fitted segment clip."""
    display = source.strip()
    lower = display.lower()
    if lower.startswith(("http://", "https://")):
        for prefix in _HTTP_PREFIXES:
            if lower.startswith(prefix):
                display = display[len(prefix):]
                break

    text = (
        TextClip(
            text=f"source: {display}",
            font_size=_SOURCE_OVERLAY_FONT_SIZE,
            color="white",
            stroke_color="black",
            stroke_width=2,
            margin=_SOURCE_OVERLAY_TEXT_MARGIN,
            vertical_align="top",
        )
        .with_duration(duration)
        .with_position((_SOURCE_OVERLAY_MARGIN_PX, _SOURCE_OVERLAY_MARGIN_PX))
    )
    return CompositeVideoClip(
        [clip.with_position("center"), text],
        size=(width, height),
    )


def _build_segment_clip(
    segment: Segment,
    *,
    paths: ProjectPaths,
    duration: float,
    settings: ExportSettings,
) -> VideoClip:
    width, height = settings.width, settings.height
    media = segment.media
    if media is None or not media.file_path:
        return ColorClip(size=(width, height), color=(0, 0, 0), duration=duration)

    file_path = str(paths.file(media.file_path))

    if isinstance(media, ImageMedia):
        clip = ImageClip(file_path).with_duration(duration)
    elif isinstance(media, VideoMedia):
        clip = _silent_video_clip(file_path)
        if media.start_timestamp and media.start_timestamp > 0:
            clip = clip.subclipped(media.start_timestamp)
        clip = clip.with_effects([Loop(duration=duration)])
    elif isinstance(media, GifMedia):
        clip = _silent_video_clip(file_path)
        clip = clip.with_effects([Loop(duration=duration)])
    else:
        raise ValueError(
            f"Unsupported media type for segment {segment.id}: {type(media).__name__}"
        )

    clip = _fit(clip, width, height)
    if media.source:
        return _add_source_overlay(
            clip, media.source, width=width, height=height, duration=duration
        )
    return clip.with_position("center")


def export_project(
    project: Project,
    settings: ExportSettings,
    *,
    on_progress: Callable[[int, int, str], None] | None = None,
    cancel_event: Event | None = None,
) -> Path:
    """Compose the project's media into an MP4 and return the output path."""
    paths = ProjectPaths.from_title(project.title)

    def report(phase: int, percent: int, message: str) -> None:
        """Report progress to the caller.
        Phase 1: resource gathering
        Phase 2: encoding
        """
        if on_progress is not None:
            on_progress(phase, percent, message)

    if cancel_event is not None and cancel_event.is_set():
        raise ExportCancelled()

    # Phase 1: resource gathering
    report(1, 0, "Saving project...")
    save_project(project)
    report(1, 5, "Loading timeline...")

    timeline = load_word_timeline(paths)
    total = len(project.segments)
    if total == 0:
        raise ValueError("Project has no segments to export.")

    output_path = paths.export_mp4
    tmp_path = paths.export_tmp_mp4
    tmp_audio_path = paths.export_audio_m4a

    clips: list[VideoClip] = []
    built = 0
    audio: AudioFileClip | None = None
    composite: VideoClip | None = None
    # Cancelling during phase 1 also has to release every clip built so far,
    # so clip cleanup wraps both phases rather than just the encode.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for seg in project.segments:
                if cancel_event is not None and cancel_event.is_set():
                    raise ExportCancelled()
                start, end = segment_playback_bounds(timeline, seg)
                duration = max(end - start, 0.0)
                clip = _build_segment_clip(
                    seg, paths=paths, duration=duration, settings=settings
                ).with_start(start)
                clips.append(clip)
                built += 1
                pct = int(built * 100 / total)
                report(1, pct, f"Preparing segments ({built}/{total})...")

            audio = AudioFileClip(str(paths.voiceover_mp3))
            composite = CompositeVideoClip(clips, size=(settings.width, settings.height))
            composite = composite.with_audio(audio).with_duration(timeline.audio_duration)

            # Phase 2: encoding
            report(2, 0, "Encoding video...")
            encode_logger = _EncodeProgressLogger(
                report,
                message="Encoding video...",
                cancel_event=cancel_event,
            )
            try:
                composite.write_videofile(
                    str(tmp_path),
                    fps=settings.fps,
                    codec=settings.codec,
                    audio_codec=settings.audio_codec,
                    logger=encode_logger,
                    temp_audiofile=str(tmp_audio_path),
                    remove_temp=True,
                )
                if output_path.exists():
                    output_path.unlink()
                tmp_path.replace(output_path)
                report(2, 100, "Encoding video...")

            # Delete the partial export.tmp.mp4 if export fails
            except Exception:
                if tmp_path.is_file():
                    tmp_path.unlink()
                raise
    finally:
        # Clean up
        # The None checks are for a phase-1 cancel, which raises before these are assigned.
        if composite is not None:
            composite.close()
        if audio is not None:
            audio.close()
        for clip in clips:
            _close_clip(clip)
        if tmp_audio_path.is_file():
            tmp_audio_path.unlink()
    return output_path
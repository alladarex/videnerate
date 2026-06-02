"""Global per-word audio timeline for a project voiceover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .segment import Segment


@dataclass(frozen=True)
class WordSpan:
    i: int
    word: str
    start: float
    end: float

    def to_dict(self) -> dict[str, Any]:
        return {"i": self.i, "word": self.word, "start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordSpan:
        return cls(
            i=int(data["i"]),
            word=str(data["word"]),
            start=float(data["start"]),
            end=float(data["end"]),
        )


@dataclass
class WordTimeline:
    words: list[WordSpan]
    audio_duration: float

    def segment_bounds(self, word_start: int, word_end: int) -> tuple[float, float]:
        """Return segment start/end in seconds for playback and export.

        WordSpan.end already runs through silence before the next word (see
        audio_alignment._timeline_from_asr), bounds are just the span endpoints.
        """
        if word_start < 0 or word_end >= len(self.words) or word_start > word_end:
            raise IndexError("word range out of bounds for timeline")
        return self.words[word_start].start, self.words[word_end].end

    def to_dict(self) -> dict[str, Any]:
        return {
            "audio_duration": self.audio_duration,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordTimeline:
        return cls(
            audio_duration=float(data["audio_duration"]),
            words=[WordSpan.from_dict(w) for w in data["words"]],
        )


def segment_playback_bounds(timeline: WordTimeline, segment: Segment) -> tuple[float, float]:
    """Derive segment start/end seconds from word indices and the global timeline."""
    if segment.word_start is None or segment.word_end is None:
        raise ValueError(
            f"Segment '{segment.text}' (id={segment.id}) is missing word_start/word_end."
        )
    start, end = timeline.segment_bounds(segment.word_start, segment.word_end)
    if end <= start:
        raise ValueError(
            f"Segment {segment.id} has invalid playback bounds: "
            f"end ({end}) must be greater than start ({start})."
        )
    return start, end


def segment_playback_duration(timeline: WordTimeline, segment: Segment) -> float:
    """Return segment length in seconds from word-index playback bounds."""
    start, end = segment_playback_bounds(timeline, segment)
    return end - start
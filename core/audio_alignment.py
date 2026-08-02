"""Build a word-level timeline from voiceover audio and narration text."""

from __future__ import annotations

import difflib
from pathlib import Path

from pydub import AudioSegment

from core.alignment_report import write_alignment_report
from core.models.project import Project
from core.models.word_timeline import WordSpan, WordTimeline
from core.project_paths import ProjectPaths
from core.word_tokenize import tokenize_words

_WHISPER_MODEL_NAME = "small"
_INITIAL_PROMPT_MAX_CHARS = 500
_MIN_ASR_MATCH_RATIO = 0.75
_MAX_FIRST_WORD_START_S = 3.0


def audio_duration_s(audio_path: Path) -> float:
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000.0


def _initial_prompt(narration: str) -> str | None:
    text = narration.strip()
    return text[:_INITIAL_PROMPT_MAX_CHARS] if text else None


def _transcribe_word_timestamps(
    audio_path: Path,
    *,
    initial_prompt: str | None = None,
) -> tuple[list[tuple[str, float, float]], float]:
    from faster_whisper import WhisperModel

    model = WhisperModel(_WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio_path),
        language="en",
        word_timestamps=True,
        vad_filter=False,
        beam_size=3,
        initial_prompt=initial_prompt,
    )

    asr_tokens: list[tuple[str, float, float]] = []
    for segment in segments:
        for word in segment.words or []:
            tokens = tokenize_words(word.word)
            if not tokens:
                continue
            start, end = float(word.start), float(word.end)
            if end <= start:
                end = start + 0.08
            asr_tokens.append((tokens[0], start, end))

    duration = float(info.duration) if info.duration else audio_duration_s(audio_path)
    return asr_tokens, duration


def _insert_missing_spans(
    ref_words: list[str],
    spans: list[tuple[float | None, float | None]],
    duration: float,
) -> list[WordSpan]:
    """Fill words without ASR times by spreading them evenly between known neighbors."""
    n = len(ref_words)
    starts: list[float | None] = [s[0] for s in spans]
    ends: list[float | None] = [s[1] for s in spans]

    i = 0
    while i < n:
        if starts[i] is not None:
            i += 1
            continue
        # Find the contiguous run of missing words [run_start, run_end)
        run_start = i
        while i < n and starts[i] is None:
            i += 1
        run_end = i

        # Window: from previous word's end (or 0) to next word's start (or audio end)
        window_start = ends[run_start - 1] if run_start > 0 else 0.0
        window_end = starts[run_end] if run_end < n else duration
        # Whisper timestamps aren't always ordered
        # The next matched word can start before the previous word ends
        window_end = max(window_end, window_start)

        # Split [window_start, window_end] evenly across this run of missing words
        step = (window_end - window_start) / (run_end - run_start)
        for k in range(run_end - run_start):
            starts[run_start + k] = window_start + step * k
            ends[run_start + k] = window_start + step * (k + 1)  # next word starts where this ends

    return [
        WordSpan(i=i, word=ref_words[i], start=float(starts[i]), end=float(ends[i]))
        for i in range(n)
    ]


def _timeline_from_asr(
    ref_words: list[str],
    asr_tokens: list[tuple[str, float, float]],
    duration: float,
) -> tuple[WordTimeline, float]:
    if not asr_tokens:
        raise RuntimeError("Whisper produced no alignable word timestamps.")

    asr_words = [t[0] for t in asr_tokens]
    # Per narration word: (start, end) from ASR, or (None, None) if not matched yet
    spans: list[tuple[float | None, float | None]] = [(None, None)] * len(ref_words)
    matched = 0
    # Compare narration vs ASR word lists, copy whisper times only where words match
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref_words, asr_words).get_opcodes():
        # i1:i2 = ref slice, j1:j2 = asr slice (equal means same words in order)
        if tag != "equal":
            continue
        for offset in range(i2 - i1):
            _, start, end = asr_tokens[j1 + offset]
            spans[i1 + offset] = (start, end)  # narration[i] gets ASR[j] timestamp
            matched += 1

    words = _insert_missing_spans(ref_words, spans, duration)
    # Extend each word through silence before the next (WordSpan is frozen — rebuild)
    adjusted: list[WordSpan] = []
    for i, span in enumerate(words):
        end = words[i + 1].start if i + 1 < len(words) else duration
        adjusted.append(WordSpan(i=span.i, word=span.word, start=span.start, end=end))
    return WordTimeline(audio_duration=duration, words=adjusted), matched / len(ref_words)


def _is_timeline_acceptable(timeline: WordTimeline, match_ratio: float) -> bool:
    return (
        bool(timeline.words)
        and match_ratio >= _MIN_ASR_MATCH_RATIO
        and timeline.words[0].start <= _MAX_FIRST_WORD_START_S
    )


def _report_base_lines(audio_path: Path, ref_word_count: int, duration: float) -> list[str]:
    return [
        f"audio: {audio_path.resolve()}",
        f"narration_words: {ref_word_count}",
        f"audio_duration_s: {duration:.2f}",
        f"whisper_model: {_WHISPER_MODEL_NAME}",
        f"min_match_ratio: {_MIN_ASR_MATCH_RATIO}",
        f"max_first_word_start_s: {_MAX_FIRST_WORD_START_S}",
    ]


def _report_success_lines(
    timeline: WordTimeline,
    match_ratio: float,
    asr_token_count: int,
    ref_word_count: int,
) -> list[str]:
    matched = round(match_ratio * ref_word_count)
    return [
        f"asr_tokens: {asr_token_count}",
        f"match_ratio: {match_ratio:.1%}",
        f"matched_words: {matched}",
        f"interpolated_words: {ref_word_count - matched}",
        f"first_word_start_s: {timeline.words[0].start:.2f}",
        f"last_word_end_s: {timeline.words[-1].end:.2f}",
    ]


def build_word_timeline(
    audio_path: Path,
    narration: str,
    *,
    paths: ProjectPaths,
) -> WordTimeline:
    """Align narration words to voiceover audio using Whisper."""
    if not narration.strip():
        raise ValueError("Narration is empty")
    ref_words = tokenize_words(narration)
    if not ref_words:
        raise ValueError("Narration has no words after tokenization")

    duration = audio_duration_s(audio_path)
    base_lines = _report_base_lines(audio_path, len(ref_words), duration)

    try:
        asr_tokens, whisper_duration = _transcribe_word_timestamps(
            audio_path,
            initial_prompt=_initial_prompt(narration),
        )
        duration = max(duration, whisper_duration)
        timeline, match_ratio = _timeline_from_asr(ref_words, asr_tokens, duration)
        if _is_timeline_acceptable(timeline, match_ratio):
            write_alignment_report(
                paths,
                success=True,
                lines=base_lines
                + _report_success_lines(timeline, match_ratio, len(asr_tokens), len(ref_words)),
            )
            return timeline
        last_error: Exception = RuntimeError(
            f"quality too low: match={match_ratio:.1%}, "
            f"first_word_start_s={timeline.words[0].start:.2f}, "
            f"asr_tokens={len(asr_tokens)}"
        )
    except Exception as exc:
        last_error = exc

    write_alignment_report(
        paths,
        success=False,
        lines=base_lines + [f"error: {last_error}"],
    )
    raise RuntimeError(f"Whisper alignment failed for {audio_path.name}") from last_error


def assign_segment_word_ranges(project: Project, ref_words: list[str]) -> None:
    """Map each segment to narration word indices (segments must match narration exactly)."""
    if not ref_words:
        raise ValueError("Narration has no words.")

    word_index = 0
    for seg in project.segments:
        seg_words = tokenize_words(seg.text)
        if not seg_words:
            raise ValueError(f"Segment {seg.id} has no words after tokenization.")

        n = len(seg_words)
        if word_index + n > len(ref_words) or ref_words[word_index : word_index + n] != seg_words:
            raise ValueError(
                f"Segment {seg.id} text does not match narration at word index {word_index}."
            )

        seg.word_start = word_index
        seg.word_end = word_index + n - 1
        word_index += n

    if word_index < len(ref_words):
        project.segments[-1].word_end = len(ref_words) - 1
        word_index = len(ref_words)
    if word_index != len(ref_words):
        raise ValueError(
            f"Segments extend past narration (used {word_index} words, "
            f"narration has {len(ref_words)})."
        )

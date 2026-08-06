import re

_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Normalize unicode punctuation so narration and LLM segments tokenize the same."""
    return (
        text.replace("\u201c", '"')  # “ left double quotation mark
        .replace("\u201d", '"')  # ” right double quotation mark
        .replace("\u2018", "'")  # ‘ left single quotation mark
        .replace("\u2019", "'")  # ’ right single quotation mark
        .replace("\u2013", "-")  # – en dash
        .replace("\u2014", "-")  # — em dash
        .replace("\u00a0", " ")  # no-break space
        # Both render as nothing, so dropping them makes the text tokenize the way it
        # looks. Left in, they split one visible word into two tokens, and the model,
        # which only ever sees the rendering, disagrees.
        .replace("\u00ad", "")  # soft hyphen
        .replace("\u200b", "")  # zero width space
    )


def tokenize_words(text: str) -> list[str]:
    """Lowercase word tokens in reading order (punctuation stripped)."""
    if not text.strip():
        raise ValueError("Text is empty.")
    normalized = normalize_text(text)
    tokens = [
        match.group(0)
        .lower()
        .strip("'\"")  # Drop decorative quotes the LLM sometimes adds at edges
        for match in _WORD_RE.finditer(normalized)
    ]
    return [t for t in tokens if t]


def require_segment_words_match_narration(narration: str, segments: list[str]) -> None:
    """Raise if segment texts are not an exact word-for-word split of narration.

    Comparison normalizes through tokenize_words, callers should normalize_text
    once before persisting narration/segment text.
    """
    ref_words = tokenize_words(narration)

    seg_words: list[str] = []
    for seg in segments:
        seg_words.extend(tokenize_words(seg))

    if ref_words == seg_words:
        return

    limit = min(len(ref_words), len(seg_words))
    for i in range(limit):
        if ref_words[i] != seg_words[i]:
            raise ValueError(
                f"Segmentation does not match narration at word {i}: "
                f"narration has '{ref_words[i]}', segments have '{seg_words[i]}'."
            )
    if len(seg_words) < len(ref_words):
        raise ValueError(
            f"Segmentation is missing {len(ref_words) - len(seg_words)} narration word(s) at the end."
        )
    raise ValueError(
        f"Segmentation has {len(seg_words) - len(ref_words)} extra word(s) after narration ends."
    )

"""All LLM calls: narration writing, segmentation, and media search planning."""

import re

from openai import OpenAI

from config import DEEPSEEK_API_KEY, OPENAI_API_KEY
from core.prompts import (
    SEGMENT_KEYWORDS_SYSTEM_PROMPT,
    SEGMENTATION_SYSTEM_PROMPT,
    narration_prompt,
)
from core.word_tokenize import assert_segment_words_match_narration

_DEEPSEEK_CLIENT = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)
_OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)

_MODEL_CLIENTS: dict[str, OpenAI] = {
    "deepseek-chat": _DEEPSEEK_CLIENT,
    "deepseek-reasoner": _DEEPSEEK_CLIENT,
    "gpt-4o-mini": _OPENAI_CLIENT,
}

SUPPORTED_MODELS: tuple[str, ...] = tuple(_MODEL_CLIENTS)
DEFAULT_NARRATION_MODEL = "deepseek-chat"
DEFAULT_SEGMENTATION_MODEL = "deepseek-reasoner"


def _resolve_provider(selected_model: str) -> tuple[OpenAI, str]:
    model = selected_model.strip().lower()
    client = _MODEL_CLIENTS.get(model)
    if client is None:
        raise ValueError(f"Unsupported model '{selected_model}'.")
    return client, model


def generate_narration(
    input_phrase: str,
    *,
    selected_model: str = DEFAULT_NARRATION_MODEL,
    temperature: float = 0.6,
    max_tokens: int = 1000,
) -> str:
    """Generates a narration from the input phrase."""
    if len(input_phrase) <= 1:
        raise ValueError("input_phrase must be at least 2 letters long")

    client, model = _resolve_provider(selected_model)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": narration_prompt(input_phrase)}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def segment_narration(
    narration: str,
    *,
    selected_model: str = DEFAULT_SEGMENTATION_MODEL,
    temperature: float = 0.6,
    max_tokens: int = 5000,
) -> str:
    """Splits narration into coherent segments."""
    client, model = _resolve_provider(selected_model)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SEGMENTATION_SYSTEM_PROMPT},
            {"role": "user", "content": narration},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    segments = (response.choices[0].message.content or "").strip()
    segments = re.sub(r"  \n", "", segments)
    segments = re.sub(r"\n\s*\n", "\n", segments)
    if len(segments) == 0:
        raise ValueError("No segments returned")

    return segments


def generate_segments(
    narration: str, *, selected_model: str = DEFAULT_SEGMENTATION_MODEL
) -> list[str]:
    """Returns a list of segment texts from the narration."""
    if not narration:
        return []

    raw_segments = segment_narration(narration, selected_model=selected_model)
    segments = [line.strip() for line in raw_segments.splitlines() if line.strip()]
    assert_segment_words_match_narration(narration, segments)
    return segments


def generate_segment_search_plan(
    segments_payload: str,
    *,
    selected_model: str = DEFAULT_SEGMENTATION_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> str:
    """Generate a JSON media search plan from segment payload."""
    client, model = _resolve_provider(selected_model)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SEGMENT_KEYWORDS_SYSTEM_PROMPT},
            {"role": "user", "content": segments_payload},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()

"""All LLM calls: narration writing, segmentation, and media search planning."""

import json
from typing import Any

from openai import OpenAI

from config import DEEPSEEK_API_KEY, OPENAI_API_KEY
from core.models.search_plan import SearchPlan, parse_search_plan
from core.prompts import (
    SEARCH_PLAN_SYSTEM_PROMPT,
    SEGMENTATION_SYSTEM_PROMPT,
    narration_prompt,
)
from core.word_tokenize import require_segment_words_match_narration

_DEEPSEEK_CLIENT = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)
_OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)


_MODEL_CLIENTS: dict[str, OpenAI] = {
    "deepseek-chat": _DEEPSEEK_CLIENT,
    "deepseek-reasoner": _DEEPSEEK_CLIENT,
    "gpt-4o-mini": _OPENAI_CLIENT,
    "gpt-5.6-terra": _OPENAI_CLIENT,
}

# These renamed 'max_tokens' to 'max_completion_tokens' and take only the default
# temperature. Sending the old spellings is a 400 on every call.
_NEWER_OPENAI_MODELS = {"gpt-5.6-terra"}

SUPPORTED_MODELS: tuple[str, ...] = tuple(_MODEL_CLIENTS)
DEFAULT_NARRATION_MODEL = "deepseek-chat"
DEFAULT_SEGMENTATION_MODEL = "deepseek-reasoner"
# Segmentation attemps before giving up. LLMs occasionally drop the space
# between two words or return an empty str. A second attempt usually does the job.
SEGMENTATION_ATTEMPTS = 2
DEFAULT_SEARCH_PLAN_MODEL = "gpt-5.6-terra"
# Plan passes to sample before giving up. On a long segment list a model sometimes
# stops a few entries early.
SEARCH_PLAN_ATTEMPTS = 3


def _resolve_provider(selected_model: str) -> tuple[OpenAI, str]:
    model = selected_model.strip().lower()
    client = _MODEL_CLIENTS.get(model)
    if client is None:
        raise ValueError(f"Unsupported model '{selected_model}'.")
    return client, model


def _sampling_kwargs(model: str, *, temperature: float, max_tokens: int) -> dict[str, Any]:
    """Token limit and temperature, spelled the way this model wants them."""
    if model in _NEWER_OPENAI_MODELS:
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens, "temperature": temperature}


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
        **_sampling_kwargs(model, temperature=temperature, max_tokens=max_tokens),
    )
    return (response.choices[0].message.content or "").strip()


def segment_narration(
    narration: str,
    *,
    selected_model: str = DEFAULT_SEGMENTATION_MODEL,
    temperature: float = 0.6,
    max_tokens: int = 5000,
) -> list[str]:
    """Splits narration into coherent segments, one per line of the model's reply."""
    client, model = _resolve_provider(selected_model)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SEGMENTATION_SYSTEM_PROMPT},
            {"role": "user", "content": narration},
        ],
        **_sampling_kwargs(model, temperature=temperature, max_tokens=max_tokens),
    )

    raw = response.choices[0].message.content or ""
    segments = [line.strip() for line in raw.splitlines() if line.strip()]
    if not segments:
        raise ValueError("No segments returned")

    return segments


def generate_segments(
    narration: str, *, selected_model: str = DEFAULT_SEGMENTATION_MODEL
) -> list[str]:
    """Returns a list of segment texts from the narration.

    A pass that does not reproduce the narration word for word is resampled, and the
    last attempt raises.
    """
    if not narration:
        return []

    attempts_left = SEGMENTATION_ATTEMPTS
    while True:
        attempts_left -= 1
        try:
            segments = segment_narration(narration, selected_model=selected_model)
            require_segment_words_match_narration(narration, segments)
            return segments
        except ValueError as exc:
            if attempts_left == 0:
                raise
            print(f"[llm_service] segmentation rejected, retrying: {exc}")


def generate_segment_search_plan(
    text_by_segment_id: dict[int, str],
    *,
    selected_model: str = DEFAULT_SEARCH_PLAN_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 15000,
) -> SearchPlan:
    """Plan one media search per segment.

    A reply that does not cover every segment is resampled, and the last attempt
    raises.
    """
    if not text_by_segment_id:
        raise ValueError("Cannot plan a search for no segments.")

    payload = {
        "segments": [
            {"id": segment_id, "text": text} for segment_id, text in text_by_segment_id.items()
        ]
    }
    client, model = _resolve_provider(selected_model)

    attempts_left = SEARCH_PLAN_ATTEMPTS
    while True:
        attempts_left -= 1
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SEARCH_PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            **_sampling_kwargs(model, temperature=temperature, max_tokens=max_tokens),
        )
        try:
            return parse_search_plan(
                response.choices[0].message.content or "",
                segment_ids=list(text_by_segment_id),
            )
        except ValueError as exc:
            if attempts_left == 0:
                raise
            print(f"[llm_service] search plan rejected, retrying: {exc}")

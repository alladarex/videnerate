from openai import OpenAI
import re
from config import DEEPSEEK_API_KEY, OPENAI_API_KEY
from core.prompts import (
    SEGMENT_KEYWORDS_SYSTEM_PROMPT,
    SEGMENTATION_SYSTEM_PROMPT,
    narration_prompt,
)

_DEEPSEEK_CLIENT = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)
_OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)


def _resolve_provider(selected_model: str) -> tuple[OpenAI, str]:
    normalized = selected_model.strip().lower()
    if normalized == "deepseek-chat":
        return _DEEPSEEK_CLIENT, "deepseek-chat"
    if normalized == "deepseek-reasoner":
        return _DEEPSEEK_CLIENT, "deepseek-reasoner"
    if normalized == "gpt-4o-mini":
        return _OPENAI_CLIENT, "gpt-4o-mini"

    raise ValueError(f"Unsupported model '{selected_model}'.")

def calculate_word_range(duration_range, words_per_minute=150):
    """Returns the estimated word range given a duration range (in seconds)."""
    wps = words_per_minute / 60.0
    return (int(round(duration_range[0] * wps)), int(round(duration_range[1] * wps)))

def generate_narration(
    input_phrase,
    model=None,
    selected_model: str = "deepseek-chat",
    temperature=0.6,
    max_tokens=1000   
):
    """Generates a narration from the input phrase."""
    if len(input_phrase) <= 1:
        raise ValueError("input_phrase must be at least 2 letters long")
    
    prompt = narration_prompt(input_phrase)
    client, default_model = _resolve_provider(selected_model)
    resolved_model = model or default_model

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()
    #return "Hyperliquid is a cutting-edge conceptthat reimagines the nature of liquidityin financial markets and beyond. At its core, hyperliquid representsan ultra-fluid state where assetscan be rapidly converted into cashor other assets with minimal friction and cost. This idea has gained tractionwith the rise of digital currenciesand blockchain technology,which facilitate swift and efficient transactions. An interesting aspect of hyperliquidis its potential to revolutionize traditional financial systemsby enhancing market efficiency and accessibility. By enabling seamless asset transfers,it promises to break down barriersthat have long hindered economic participationfor individuals and businesses alike. In essence, hyperliquid offers a glimpseinto a future where financial marketsare more dynamic and responsive to global trends. This concept also underscoresthe transformative power of technologyin reshaping how we perceive and interact with value. As hyperliquid continues to evolve,it holds the promise of creating more inclusive and agile economic systems worldwide."

def segment_narration(
        narration,
        merge_last=False,
        model=None,
        selected_model: str = "deepseek-reasoner",
        max_tokens=4000,
        temperature=0.6
        ):
    """Splits narration into coherent segments."""
    system_prompt = SEGMENTATION_SYSTEM_PROMPT
    client, default_model = _resolve_provider(selected_model)
    resolved_model = model or default_model

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": narration}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )

    segments = response.choices[0].message.content.strip()
    segments = re.sub(r'  \n', '', segments)
    segments = re.sub(r'\n\s*\n', '\n', segments)
    if len(segments) == 0:
        raise ValueError("No segments returned")
    
    if merge_last:
        last_newline = segments.rfind('\n')
        segments = segments[:last_newline] + " " + segments[last_newline+1:]

    return segments

def get_segments(narration: str, selected_model: str = "deepseek-reasoner") -> list[str]:
    """Returns a list of segment texts from the narration."""
    if not narration:
        return []

    raw_segments = segment_narration(narration, selected_model=selected_model)
    print(raw_segments)
    # if not raw_segments:
    #     print("------No segments returned------ trying again")
    #     get_segments(narration)
    segments = [line.strip() for line in raw_segments.splitlines() if line.strip()]
    return segments


def generate_segment_search_plan(
    segments_payload: str,
    model=None,
    selected_model: str = "deepseek-reasoner",
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> str:
    """Generate a JSON media search plan from segment payload."""
    system_prompt = SEGMENT_KEYWORDS_SYSTEM_PROMPT
    client, default_model = _resolve_provider(selected_model)
    resolved_model = model or default_model

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": segments_payload},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()



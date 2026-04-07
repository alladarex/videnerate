from openai import OpenAI
import os
import re
from config import DEEPSEEK_API_KEY
from core.prompts import SEGMENTATION_SYSTEM_PROMPT, narration_prompt

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

def calculate_word_range(duration_range, words_per_minute=150):
    """Returns the estimated word range given a duration range (in seconds)."""
    wps = words_per_minute / 60.0
    return (int(round(duration_range[0] * wps)), int(round(duration_range[1] * wps)))

def generate_narration(
    input_phrase,
    model="deepseek-chat",
    temperature=0.6,
    max_tokens=1000   
):
    """Generates a narration from the input phrase."""
    # if len(input_phrase) <= 1:
    #     raise ValueError("input_phrase must be at least 2 letters long")
    
    prompt = narration_prompt(input_phrase)

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()
    #return "Hyperliquid is a cutting-edge conceptthat reimagines the nature of liquidityin financial markets and beyond. At its core, hyperliquid representsan ultra-fluid state where assetscan be rapidly converted into cashor other assets with minimal friction and cost. This idea has gained tractionwith the rise of digital currenciesand blockchain technology,which facilitate swift and efficient transactions. An interesting aspect of hyperliquidis its potential to revolutionize traditional financial systemsby enhancing market efficiency and accessibility. By enabling seamless asset transfers,it promises to break down barriersthat have long hindered economic participationfor individuals and businesses alike. In essence, hyperliquid offers a glimpseinto a future where financial marketsare more dynamic and responsive to global trends. This concept also underscoresthe transformative power of technologyin reshaping how we perceive and interact with value. As hyperliquid continues to evolve,it holds the promise of creating more inclusive and agile economic systems worldwide."

def segment_narration(
        narration,
        merge_last=False,
        model="deepseek-reasoner",
        max_tokens=2000,
        temperature=0.6
        ):
    """Splits narration into coherent segments."""
    system_prompt = SEGMENTATION_SYSTEM_PROMPT

    response = client.chat.completions.create(
        model=model,
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

def get_segments(narration: str) -> list[str]:
    """Returns a list of segment texts from the narration."""
    if not narration:
        return []

    raw_segments = segment_narration(narration)
    print(raw_segments)
    # if not raw_segments:
    #     print("------No segments returned------ trying again")
    #     get_segments(narration)
    segments = [line.strip() for line in raw_segments.splitlines() if line.strip()]
    return segments

def merge_segments(segments: list[str], index: int, separator: str = " ") -> list[str]:
    """Merges two consecutive segments at the given index."""
    if index < 0 or index >= len(segments) - 1:
        raise ValueError("Invalid index: cannot merge segment at index {}.".format(index))
    
    merged = segments[index].strip() + separator + segments[index + 1].strip()
    return segments[:index] + [merged] + segments[index + 2:]


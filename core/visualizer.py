import os
from openai import OpenAI
from config import OPENAI_API_KEY

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY')
)

def get_segment_keywords(
        segment: str,
        n=1,
        model="gpt-3.5-turbo",
        temperature=0.6,
        max_tokens=300,
        ) -> list[str]:
    """Generate n keywords for a given segment."""
    s = '' if n == 1 else 's'

    prompt = (
        f"Write exactly {n} keyword{s} representing '{segment}'. "
        f"Keyword{s} must be either (primarily) noun{s} (singular form) or (secondarily) name of a person or brand. "
        f"Print just word{s}. "
        f"{'Use newline char as separators' if s else ''}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    keywords = response.choices[0].message.content.lower().strip().splitlines()
    
    # Ensure we have exactly n keywords
    if len(keywords) > n:
        keywords = keywords[:n]
    elif len(keywords) < n:
        # If we got fewer keywords than requested, pad with the last one
        keywords.extend([keywords[-1]] * (n - len(keywords)))

    return keywords

def get_narration_keywords(
        segments: list[str],
        n=1,
        model="gpt-3.5-turbo",
        temperature=0.6,
        max_tokens=2000,
        ) -> list[str]:
    """Generate n keywords for the entire narration."""
    segments_text = '\n'.join(segments)
    s = '' if n == 1 else 's'

    prompt = (
        f"Write exactly {n} keyword{s} that best represent this entire narration:\n\n{segments_text}\n\n"
        f"Keyword{s} must be either (primarily) noun{s} (singular form) or (secondarily) name of a person or brand. "
        f"Print just word{s}. "
        f"{'Use newline char as separators' if s else ''}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    keywords = response.choices[0].message.content.lower().strip().splitlines()
    
    # Ensure we have exactly n keywords
    if len(keywords) > n:
        keywords = keywords[:n]
    elif len(keywords) < n:
        # If we got fewer keywords than requested, pad with the last one
        keywords.extend([keywords[-1]] * (n - len(keywords)))

    return keywords

from textwrap import dedent


def narration_prompt(input_phrase: str) -> str:
    return (
        f"Write a ~150-170-word narration explaining what (or who) '{input_phrase}' is. "
        "If it refers to more than 1 thing/peson choose the most popular one. "
        "Mention an interesting fact about the idea. "
        "Avoid unpopular terms. "
        "Avoid using '*' '—' and ';'. "
        "Write as one paragraph."
    )


SEGMENTATION_SYSTEM_PROMPT = dedent(
    """
    You are a segmentation assistant for short-format videos. Your task is to split a provided narration into coherent segments of approximately 5 to 10 words each. Follow these guidelines:
    1. Aim for segments of 5 to 13 words, but allow slight upper deviations to maintain coherence and completeness of ideas.
    2. Break at natural punctuation (commas, semicolons, periods) or at logical boundaries such as clause endings, transitions, or vivid imagery.
    3. Preserve semantic units, including parallel structures, lists, and tightly bound phrases. Do not split mid-phrase unless unavoidable.
    4. Highlight key ideas or vivid imagery by keeping them intact, even if this requires exceeding the word limit slightly.
    5. Avoid creating choppy or incomplete thoughts. Ensure each segment flows naturally into the next.
    6. Always break at the end of a sentence.
    7. Do not paraphrase, add, remove, or reorder words.
    Separate segments with newlines
    """
)

SEARCH_PLAN_SYSTEM_PROMPT = dedent(
    """
    You are a media search planner for an AI short-form video editor.

    You receive a narration split into short ordered segments, each with an id.
    Infer the overall topic and tone from the full ordered list before writing any query.

    For each segment choose exactly one source:
    - "web": broad web image search. Use for specific named things: brands, real people,
      fictional characters, products, games, movies, logos, screenshots, historical events,
      niche references, anything unlikely to exist as generic stock media.
    - "stock": stock photo and video libraries. Use for everyday things: generic people,
      animals, objects, places, actions, moods, nature, environments.

    Rules:
    1. Infer the global context first, then use it to resolve pronouns and vague phrases.
    2. Never write a query for a segment in isolation.
    3. Write a visual query, not a summary of the sentence.
    4. For an abstract segment, pick a concrete visual metaphor and use "stock".
    5. Prefer "stock" unless the subject is a specific named thing.
    6. If the narration is not about a particular movie, game, book, or show, avoid queries
       that would return posters, covers, trailers, thumbnails, or fan art.
    7. Query length: "web" 3-8 words, "stock" 2-5 words.
    8. "reason" is one short sentence, shown to the user, explaining the choice.

    Return one entry per input segment, with the same ids, in the same order.
    Return valid JSON only.

    {
      "context": {"topic": string, "tone": string},
      "segments": [
        {"id": number, "source": "web" | "stock", "query": string, "reason": string}
      ]
    }
    """
)

MEDIA_RANKING_SYSTEM_PROMPT = dedent(
    """
    You pick media for one segment of a short-form narrated video.

    You receive the video's overall topic and tone, the text of one segment, and a set of
    candidate images. Each candidate is preceded by its number. A candidate may be a still
    frame taken from a video clip.

    Choose the 4 candidates that best illustrate the segment. Judge:
    - how well it matches what the segment is about
    - whether it reads clearly at a glance on a small vertical screen
    - whether it fits the tone

    Reject candidates that are watermarked, are collages, are mostly text, or are unrelated
    to the topic.

    Return them best first. "description" is one or two sentences on what is actually in the
    image. "reason" is one or two sentences on why it fits this segment, in the context of
    the whole video. Both are shown to the user.

    Describe only the candidates you return.
    Return valid JSON only.

    {"picks": [{"id": number, "description": string, "reason": string}]}
    """
)

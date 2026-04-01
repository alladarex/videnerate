def narration_prompt(input_phrase: str) -> str:
    return (
        f"Write a ~150-170-word narration explaining what (or who) '{input_phrase}' is. "
        "If it refers to more than 1 thing/peson choose the most popular one. "
        "Mention an interesting fact about the idea. "
        "Avoid unpopular terms. "
        "Avoid using '*' '—' and ';'. "
        "Write as one paragraph."
    )


SEGMENTATION_SYSTEM_PROMPT = (
    "You are a segmentation assistant for short-format videos. Your task is to split a provided narration into coherent segments of approximately 5 to 10 words each. Follow these guidelines:\n"
    "1. Aim for segments of 5 to 13 words, but allow slight upper deviations to maintain coherence and completeness of ideas.\n"
    "2. Break at natural punctuation (commas, semicolons, periods) or at logical boundaries such as clause endings, transitions, or vivid imagery.\n"
    "3. Preserve semantic units, including parallel structures, lists, and tightly bound phrases. Do not split mid-phrase unless unavoidable.\n"
    "4. Highlight key ideas or vivid imagery by keeping them intact, even if this requires exceeding the word limit slightly.\n"
    "5. Avoid creating choppy or incomplete thoughts. Ensure each segment flows naturally into the next.\n"
    "6. Always break at the end of a sentence.\n"
    "Separate segments with newlines"
)


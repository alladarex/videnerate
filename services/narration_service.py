from core.scripter import generate_narration, get_segments


def generate_narration_from_video_idea(
    video_idea: str, *, selected_model: str = "deepseek-chat"
) -> str:
    """Generate narration text from a short video idea phrase."""
    return generate_narration(video_idea, selected_model=selected_model)


def get_segments_from_narration(
    narration: str, *, selected_model: str = "deepseek-reasoner"
) -> list[str]:
    """Segment a narration into a list of segment texts."""
    return get_segments(narration, selected_model=selected_model)

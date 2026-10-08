from pathlib import Path

PROMPT_DIR = Path(__file__).parent


def get_system_prompt() -> str:
    """The system prompt, the same on every turn: what changes between turns
    (the date and time, the day being viewed) goes in each user message, so
    earlier turns are never rewritten (see `service.message_context`)."""
    return (PROMPT_DIR / "system_prompt.md").read_text()

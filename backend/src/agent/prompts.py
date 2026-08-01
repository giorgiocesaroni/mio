import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROMPT_DIR = Path(__file__).parent


def get_system_prompt(
    daily_macros: dict, current_goal: dict | None, timezone: str = "UTC"
) -> str:
    prompt = (PROMPT_DIR / "system_prompt.md").read_text()

    date = datetime.datetime.now(tz=ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M")
    return prompt.replace("`ENV_DATE`", date)

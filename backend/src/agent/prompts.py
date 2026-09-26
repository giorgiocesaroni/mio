import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROMPT_DIR = Path(__file__).parent


def get_system_prompt(
    daily_macros: dict,
    current_goal: dict | None,
    timezone: str = "UTC",
    day: str | None = None,
) -> str:
    prompt = (PROMPT_DIR / "system_prompt.md").read_text()

    now = datetime.datetime.now(tz=ZoneInfo(timezone))
    prompt = prompt.replace("`ENV_DATE`", now.strftime("%Y-%m-%d %H:%M"))
    if day and day != now.strftime("%Y-%m-%d"):
        prompt += (
            f"\n\nThe user is looking at {day} in the app: log foods for that day "
            "unless they say otherwise."
        )
    return prompt

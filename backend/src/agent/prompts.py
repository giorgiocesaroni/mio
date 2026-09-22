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


def get_quick_log_prompt(
    mode: str,
    day: str,
    daily_macros: dict,
    current_goal: dict | None,
    timezone: str = "UTC",
) -> str:
    """One-shot prompt for quick add / quick edit. Never asks questions."""
    base = get_system_prompt(daily_macros, current_goal, timezone)
    now = datetime.datetime.now(tz=ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M")
    if mode == "edit":
        task = (
            f"You are in QUICK EDIT mode for day {day} (now: {now} local). "
            "The user wants to correct today's logged foods. "
            f"First call `get_daily_summary` for day `{day}` to find the target log entries, "
            "then apply the correction in one `update_logs`/`delete_logs` call, or log anything new with `log_entries`. "
            "If the message names a food without saying which entry, match it against today's logs by name (closest match). "
            "If nothing matches, log it as a new entry rather than failing."
        )
    else:
        task = (
            f"You are in QUICK ADD mode for day {day} (now: {now} local). "
            "The user wants foods logged immediately."
        )
    rules = (
        "\n\n# Quick mode rules (override normal behavior)\n"
        "- NEVER ask clarifying questions, never present options, never say you need more info.\n"
        "- ALWAYS finish with at least one log mutation (`log_entries`, `update_logs`, or `delete_logs`). Logging something approximate is better than logging nothing.\n"
        "- Batch every food of the request into a single `log_entries` call instead of one call per food.\n"
        "- On ambiguity, pick the closest `search` match and log it; state your assumption briefly in the final message.\n"
        "- If the food is not in the database, research with `web_search`/`web_fetch`, `insert_ingredient` (plus serving sizes when natural), then log it — all in this same run.\n"
        "- Defaults when the message omits them: `meal_type` inferred from time of day (breakfast <11h, lunch 11-15h, snack 15-18h, dinner otherwise); `log_for` = now unless the message states another time.\n"
        "- The mutation returns `updated_totals`; use them instead of calling `get_daily_summary` again.\n"
        "- Keep the final message to 1-2 lines confirming what was logged (food + amount + meal), so the user can spot mistakes and iterate."
    )
    return f"{base}\n\n{task}{rules}"

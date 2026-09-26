from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

import src.agent.models as agent_models

# ── Extraction ────────────────────────────────────────────────────────────────

Unit = Literal["g", "ml", "piece", "serving", "recipe"]


class Per100g(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    said: str = Field(
        description="The user's own words for this food, copied verbatim in their language, including brand and descriptors but not the quantity, e.g. 'cotolette AIA'. Empty string when the food is only visible in a photo."
    )
    name: str = Field(
        description="Short, generic, English, lowercase, singular food name as it would appear in a food database, e.g. 'whole wheat bread'. No brand."
    )
    brand: str | None = Field(description="Brand, only if stated or visible.")
    quantity: float = Field(description="Amount as the user expressed it.")
    unit: Unit = Field(
        description="'g' weight, 'ml' volume, 'piece' countable items (eggs, apples, slices), 'serving' household measures (cup, tablespoon, bowl), 'recipe' fraction of a whole dish (0.5 = half)."
    )
    unit_label: str | None = Field(
        description="For 'piece' and 'serving': the English, lowercase, singular measure, e.g. 'slice', 'tablespoon', 'medium', 'cup'. Otherwise null."
    )
    grams: float = Field(
        description="Best estimate of the eaten weight in grams. Always filled; for photos, estimate the portion visually."
    )
    meal_type: agent_models.MealType | None = Field(
        description="Only if stated or clearly implied, otherwise null."
    )
    time: str | None = Field(
        description="Local time of the meal as HH:MM, only if stated, otherwise null."
    )
    state: agent_models.IngredientState = Field(
        description="Whether `grams` and `per_100g` refer to the raw or cooked food."
    )
    per_100g: Per100g = Field(
        description="Typical nutrition facts per 100 g of this food in that state."
    )


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExtractedItem]


# ── Resolution ────────────────────────────────────────────────────────────────


class ResolvedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: int = Field(description="Index of the food in `foods`.")
    target: str = Field(
        description="Key of the candidate that is the same food, or 'new' when none is."
    )
    unit: Literal["grams", "serving", "recipe"]
    serving: str | None = Field(
        description="With unit 'serving': the key of the target's serving size. Otherwise null."
    )
    quantity: float = Field(
        description="Grams for 'grams', number of servings for 'serving', fraction of the whole recipe for 'recipe'."
    )
    weight_state: agent_models.IngredientState = Field(
        description="Whether the logged amount refers to the raw or cooked food."
    )
    meal_type: agent_models.MealType
    time: str = Field(description="Local time of the meal, HH:MM.")
    confidence: Literal["high", "medium", "low"]
    note: str | None = Field(
        description="When confidence isn't high: one short sentence for the user, in their language, saying what was assumed. Otherwise null."
    )


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[ResolvedRow]


# ── Pipeline run ──────────────────────────────────────────────────────────────


class PipelineInput(BaseModel):
    user_id: str
    # Already preprocessed: audio parts transcribed to text.
    message: agent_models.MessageType
    day: str | None = None  # YYYY-MM-DD in the user's timezone; defaults to today
    model: str | None = None  # Extraction and resolution model override
    # The agent's `log_food` tool has already decided the message is a food log.
    skip_route: bool = False


StageName = Literal["normalize", "route", "extract", "retrieve", "resolve", "draft"]


class StageStep(BaseModel):
    type: Literal["stage"] = "stage"
    name: StageName
    status: Literal["ok", "skipped", "error"]
    summary: str
    ms: int
    cost: float = 0.0
    model: str | None = None
    data: dict | list | None = None


class DoneStep(BaseModel):
    type: Literal["done"] = "done"
    outcome: Literal["drafted", "handoff", "nothing", "error"]
    message: str
    total_ms: int
    total_cost: float
    draft: dict | None = None


PipelineStep = StageStep | DoneStep


# ── Drafts ────────────────────────────────────────────────────────────────────


class DraftError(ValueError):
    """An invalid edit or state transition; surfaced to the client as a 400."""

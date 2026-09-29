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
        description="Short, generic, English, lowercase, singular food name as it would appear in a food database, e.g. 'whole wheat bread'. No brand. Name it in the same state as `state`, so a cooked amount is a cooked food."
    )
    brand: str | None = Field(description="Brand, only if stated or visible.")
    quantity: float = Field(description="Amount as the user expressed it.")
    unit: Unit = Field(
        description="'g' weight, 'ml' volume, 'piece' countable items (eggs, apples, slices), 'serving' household measures (cup, tablespoon, bowl), 'recipe' fraction of a whole dish (0.5 = half)."
    )
    grams: float = Field(
        description="Best estimate of the eaten weight in grams, in the same `state` as this component. Always filled; for photos, estimate the portion visually."
    )
    state: agent_models.IngredientState = Field(
        description="The state the `grams` amount is measured in — how the amount was quantified, not whether the dish was cooked. When the user gave a weight, this is the state that weight is in; when you estimated the portion, it is the state the food is eaten in. Oils, condiments, herbs and spices are 'raw'."
    )
    per_100g: Per100g = Field(
        description="Typical nutrition facts per 100 g of this food, in the same `state` as `grams`. `name`, `state` and `per_100g` must all describe the same amount: never name a component 'dry spaghetti' and report a cooked weight."
    )
    assumed: bool = Field(
        description="True only for extras added beyond the dish the user described — cooking oil, dressing, cheese on top, bread on the side. The components that make up a dish the user named are never assumed, even when you named them yourself; false for everything the user said or the photo shows."
    )


class ExtractedDish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    said: str = Field(
        description="The user's own words for the dish, copied verbatim in their language, e.g. 'pasta al pomodoro'. Empty string when the dish is only visible in a photo."
    )
    name: str = Field(
        description="Short, generic, English name of the dish, written as a person would say it with a capital first letter, e.g. 'Spaghetti with tomato sauce' (not all lowercase). For a single food or drink, the same as its component's name."
    )
    components: list[ExtractedItem] = Field(
        min_length=1,
        description="The foods the dish is made of, each with its own eaten weight and nutrition. A single food or drink is a dish with exactly one component; never empty.",
    )


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dishes: list[ExtractedDish]

    @property
    def items(self) -> list[ExtractedItem]:
        """Every component of every dish, in order; an item's index is its position here."""
        return [c for d in self.dishes for c in d.components]


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


class ResolvedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dish: int = Field(description="Index of the dish in `dishes`.")
    target: str = Field(description="Key of the dish's saved recipe that is the same dish.")
    quantity: float = Field(description="Fraction of the whole recipe eaten.")
    meal_type: agent_models.MealType
    time: str = Field(description="Local time of the meal, HH:MM.")
    confidence: Literal["high", "medium", "low"]
    note: str | None = Field(
        description="When confidence isn't high: one short sentence for the user, in their language, saying what was assumed. Otherwise null."
    )


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipes: list[ResolvedRecipe] = Field(
        description="Dishes logged as one of the user's saved recipes; their components get no row."
    )
    rows: list[ResolvedRow]


# ── Pipeline run ──────────────────────────────────────────────────────────────


# "pipeline": a chat message the router sent straight to the pipeline;
# "agent": the agent's `log_food` call.
DraftVia = Literal["pipeline", "agent", "sandbox"]


class PipelineInput(BaseModel):
    user_id: str
    # Already preprocessed: audio parts transcribed to text.
    message: agent_models.MessageType
    day: str | None = None  # YYYY-MM-DD in the user's timezone; defaults to today
    # The conversation the router weighs the message against, when in chat.
    last_reply: str | None = None  # the assistant's latest reply
    pending_draft: list[str] | None = None  # entries of a draft awaiting confirmation
    # The agent's `log_food` tool has already decided the message is a food log.
    skip_route: bool = False
    # What started the run, stored with the draft for the usage page.
    via: DraftVia = "sandbox"


StageName = Literal["normalize", "route", "extract", "retrieve", "resolve", "draft"]


class StageStep(BaseModel):
    """One stage of a run. `warnings` are degradations the stage survived — a
    partial or repaired answer — as opposed to an `error`, which stops the run."""

    type: Literal["stage"] = "stage"
    name: StageName
    status: Literal["ok", "skipped", "error"]
    summary: str
    ms: int
    cost: float = 0.0
    model: str | None = None
    data: dict | list | None = None
    warnings: list[str] = []


class DoneStep(BaseModel):
    type: Literal["done"] = "done"
    outcome: Literal["drafted", "handoff", "nothing", "error"]
    message: str
    total_ms: int
    total_cost: float
    draft: dict | None = None
    # Everything that went wrong but didn't stop the run, from every stage.
    warnings: list[str] = []


PipelineStep = StageStep | DoneStep


# ── Drafts ────────────────────────────────────────────────────────────────────


class DraftError(ValueError):
    """An invalid edit or state transition; surfaced to the client as a 400."""

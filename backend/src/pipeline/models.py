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


# "edit" is a correction applied to an existing entry, not a stage of a new log.
StageName = Literal[
    "normalize", "route", "extract", "retrieve", "resolve", "draft", "edit"
]


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


# ── Entry editing ─────────────────────────────────────────────────────────────
# The arguments of the editor's tools. Every field is required (nullable where
# optional), as strict tool schemas demand.

EditUnit = Literal["grams", "serving", "recipe"]


class SearchFoods(BaseModel):
    """Search the user's foods and the food database. Returns matching foods
    with their keys, the user's own entries first."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        description="The food as it would be named in a food database, e.g. 'greek yogurt 0%' or 'Barilla spaghetti'."
    )


class CreateFood(BaseModel):
    """Create a food that no search found, with realistic nutrition facts.
    Returns its key; it is saved only when the entry is logged."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Short English name, e.g. 'Greek yogurt 0% fat'.")
    brand: str | None = Field(description="Brand, only if the user named one.")
    state: agent_models.IngredientState = Field(
        description="Whether `per_100g` describes the raw or cooked food."
    )
    per_100g: Per100g


class SwapFood(BaseModel):
    """Log a row as a different food, keeping its amount."""

    model_config = ConfigDict(extra="forbid")

    row: str = Field(description="The row to change, e.g. 'r0'.")
    food: str = Field(description="Key of the food to log it as, e.g. 'f3'.")


class SetAmount(BaseModel):
    """Change how much of a row's food was eaten."""

    model_config = ConfigDict(extra="forbid")

    row: str = Field(description="The row to change, e.g. 'r0'.")
    quantity: float = Field(
        description="Grams for 'grams', number of servings for 'serving', fraction of the whole recipe for 'recipe'."
    )
    unit: EditUnit = Field(
        description="'serving' only for a food with serving sizes, 'recipe' only for a saved recipe."
    )
    serving: str | None = Field(
        description="With unit 'serving': the key of one of the food's serving sizes, e.g. 's0'. Otherwise null."
    )
    weight_state: agent_models.IngredientState | None = Field(
        description="With unit 'grams': whether the grams are raw or cooked weight. Null keeps the row's."
    )


class AddFood(BaseModel):
    """Add a food to the entry, eaten at the same meal."""

    model_config = ConfigDict(extra="forbid")

    food: str = Field(description="Key of the food, e.g. 'f3'.")
    quantity: float = Field(
        description="Grams for 'grams', number of servings for 'serving', fraction of the whole recipe for 'recipe'."
    )
    unit: EditUnit
    serving: str | None = Field(
        description="With unit 'serving': the key of one of the food's serving sizes. Otherwise null."
    )
    weight_state: agent_models.IngredientState | None = Field(
        description="With unit 'grams': whether the grams are raw or cooked weight. Null uses the food's."
    )


class RemoveFood(BaseModel):
    """Remove a row the user didn't eat."""

    model_config = ConfigDict(extra="forbid")

    row: str = Field(description="The row to remove, e.g. 'r1'.")


class ScaleEntry(BaseModel):
    """Multiply the amount of every row, e.g. 0.5 when they ate half of it."""

    model_config = ConfigDict(extra="forbid")

    factor: float = Field(description="What to multiply every amount by.")


class SetTime(BaseModel):
    """Change when the whole entry was eaten."""

    model_config = ConfigDict(extra="forbid")

    time: str | None = Field(description="Local time as HH:MM. Null keeps the current one.")
    meal_type: agent_models.MealType | None = Field(
        description="Null keeps the current one."
    )


class RenameDish(BaseModel):
    """Rename the dish an entry of several foods is shown as."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="The dish as a person would say it, capitalized, e.g. 'Greek yogurt with honey'."
    )

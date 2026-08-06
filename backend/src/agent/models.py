from datetime import datetime
from typing import Literal, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer, validator


class AgentInput(BaseModel):
    conversation_id: UUID
    user_id: str
    system_prompt: str
    contents: list[dict]
    thinking: bool = True
    model: Optional[str] = None

    @field_serializer("conversation_id")
    def serialize_conversation_id(self, conversation_id: UUID) -> str:
        return str(conversation_id)


class FunctionDeclaration(BaseModel):
    name: str
    description: str
    parameters_json_schema: dict


class ToolCallStep(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    name: str
    args: dict


class ToolCallStartStep(BaseModel):
    type: Literal["tool_call_start"] = "tool_call_start"
    name: str


class ContentTokenStep(BaseModel):
    type: Literal["content_token"] = "content_token"
    token: str


class UserMessageStep(BaseModel):
    type: Literal["user_message"] = "user_message"
    text: str
    data: Optional[str] = None
    mime_type: Optional[str] = None


class MessageStep(BaseModel):
    type: Literal["message"] = "message"
    text: str


RunAgentStep = Union[ToolCallStep, MessageStep, UserMessageStep, ContentTokenStep, ToolCallStartStep]


class UserMessagePart(BaseModel):
    text: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: Optional[str] = None
    url: Optional[str] = None


class RunAgentUserMessage(BaseModel):
    type: Literal["user"] = "user"
    parts: list[UserMessagePart]


MessageType = RunAgentUserMessage


class RunAgentInput(BaseModel):
    conversation_id: UUID
    user_id: str
    message: MessageType
    channel_instructions: Optional[str] = None
    thinking: bool = True
    model: Optional[str] = None

    @field_serializer("conversation_id")
    def serialize_conversation_id(self, conversation_id: UUID) -> str:
        return str(conversation_id)


# ── Ingredient ────────────────────────────────────────────────────────────────

IngredientState = Literal["raw", "cooked"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class ServingSize(BaseModel):
    id: UUID
    label: str
    label_plural: str
    grams: float

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertServingSizeInput(BaseModel):
    label: str
    label_plural: str
    grams: float


class UpdateServingSizeInput(BaseModel):
    id: UUID
    label: Optional[str] = None
    label_plural: Optional[str] = None
    grams: Optional[float] = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertIngredientInput(BaseModel):
    name: str
    protein_g: int
    carbs_g: int
    fat_g: int
    calories_kcal: int
    brand: str | None = None
    source_url: str | None = None
    state: IngredientState
    serving_sizes: list[InsertServingSizeInput] = Field(default_factory=list)


class UpdateIngredientInput(BaseModel):
    id: UUID
    name: Optional[str] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    calories_kcal: Optional[int] = None
    brand: Optional[str] = None
    source_url: Optional[str] = None
    state: Optional[IngredientState] = None


class Ingredient(BaseModel):
    id: UUID
    name: str
    protein_g: int
    carbs_g: int
    fat_g: int
    calories_kcal: int
    brand: str | None = None
    source_url: str | None = None
    state: IngredientState
    serving_sizes: list[ServingSize] = Field(default_factory=list)
    distance: float | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


# ── Recipe ────────────────────────────────────────────────────────────────────

class RecipeItem(BaseModel):
    id: UUID
    ingredient_id: UUID
    quantity_g: float | None = None
    quantity: float | None = None
    serving_size_id: UUID | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("ingredient_id")
    def serialize_ingredient_id(self, ingredient_id: UUID) -> str:
        return str(ingredient_id)

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, v: UUID | None) -> str | None:
        return str(v) if v is not None else None


class InsertRecipeItemInput(BaseModel):
    ingredient_id: UUID
    quantity_g: float | None = None
    quantity: float | None = None
    serving_size_id: UUID | None = None

    @field_serializer("ingredient_id")
    def serialize_ingredient_id(self, ingredient_id: UUID) -> str:
        return str(ingredient_id)

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, v: UUID | None) -> str | None:
        return str(v) if v is not None else None

    @validator("quantity_g", pre=True)
    @classmethod
    def empty_to_none(cls, v):
        return None if v == "" else v

    @validator("quantity", pre=True)
    @classmethod
    def empty_to_none_qty(cls, v):
        return None if v == "" else v

    @validator("serving_size_id", pre=True)
    @classmethod
    def empty_to_none_ss(cls, v):
        return None if v == "" else v


class Recipe(BaseModel):
    id: UUID
    name: str
    image_url: str | None = None
    items: list[RecipeItem] = Field(default_factory=list)
    distance: float | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertRecipeInput(BaseModel):
    name: str
    image_url: str | None = None
    items: list[InsertRecipeItemInput] = Field(default_factory=list)


class UpdateRecipeInput(BaseModel):
    id: UUID
    name: str | None = None
    image_url: str | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


# ── Logs ──────────────────────────────────────────────────────────────────────

class InsertLogByGramsInput(BaseModel):
    food_id: UUID | None = None
    quantity_g: float
    recipe_id: UUID | None = None
    meal_type: MealType
    log_for: str  # YYYY-MM-DD HH:MM — the actual time of the meal

    @field_serializer("food_id")
    def serialize_food_id(self, v: UUID | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("recipe_id")
    def serialize_recipe_id(self, v: UUID | None) -> str | None:
        return str(v) if v is not None else None


class InsertLogByServingSizeInput(BaseModel):
    food_id: UUID | None = None
    serving_size_id: UUID
    quantity: float
    meal_type: MealType
    log_for: str  # YYYY-MM-DD HH:MM — the actual time of the meal

    @field_serializer("food_id")
    def serialize_food_id(self, v: UUID | None) -> str | None:
        return str(v) if v is not None else None

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, v: UUID) -> str:
        return str(v)


class UpdateLogInput(BaseModel):
    id: UUID
    food_id: Optional[UUID] = None
    quantity_g: Optional[float] = None
    recipe_id: Optional[UUID] = None
    meal_type: Optional[MealType] = None
    log_for: str | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("recipe_id")
    def serialize_recipe_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None


class Log(BaseModel):
    id: UUID
    food_id: UUID | None = None
    quantity_g: Optional[float] = None
    serving_size_id: Optional[UUID] = None
    quantity: Optional[float] = None
    recipe_id: Optional[UUID] = None
    meal_type: MealType
    log_for: datetime

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("recipe_id")
    def serialize_recipe_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("log_for")
    def serialize_log_for(self, v: datetime) -> str:
        return v.isoformat()


class LogWithEntry(BaseModel):
    """A log entry — always references an ingredient; recipe_id is optional provenance for dispatched recipe logs."""
    id: UUID
    food_id: UUID | None = None
    quantity_g: Optional[float] = None
    serving_size_id: Optional[UUID] = None
    quantity: Optional[float] = None
    recipe_id: Optional[UUID] = None
    meal_type: MealType
    log_for: datetime
    log_for_local: str | None = None
    ingredient: Ingredient | None = None
    recipe: Recipe | None = None
    calculated_calories_kcal: float | None = None
    calculated_protein_g: float | None = None
    calculated_carbs_g: float | None = None
    calculated_fat_g: float | None = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("recipe_id")
    def serialize_recipe_id(self, v: Optional[UUID]) -> Optional[str]:
        return str(v) if v is not None else None

    @field_serializer("log_for")
    def serialize_log_for(self, v: datetime) -> str:
        return v.isoformat()


# ── Goals ─────────────────────────────────────────────────────────────────────

class Goal(BaseModel):
    id: UUID
    created_at: datetime
    weight_kg: int
    calories_kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    goal: Literal["lose_weight", "maintain_weight", "gain_weight"]

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertGoalInput(BaseModel):
    weight_kg: int
    calories_kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    goal: Literal["lose_weight", "maintain_weight", "gain_weight"]


# ── Conversations ─────────────────────────────────────────────────────────────

class Conversation(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


# ── Measurements ──────────────────────────────────────────────────────────────

class InsertMeasurementInput(BaseModel):
    weight_kg: float


class Measurement(BaseModel):
    id: UUID
    weight_kg: float
    created_at: datetime

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

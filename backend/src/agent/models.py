from datetime import datetime
from typing import Literal, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_serializer
import google.genai

ModelId = Literal["gemini-3-flash-preview"]

Content = google.genai.types.Content

Part = google.genai.types.Part

FunctionDeclaration = google.genai.types.FunctionDeclaration

GenerateContentConfig = google.genai.types.GenerateContentConfig

Tool = google.genai.types.Tool

GenerateContentResponse = google.genai.types.GenerateContentResponse

FunctionCall = google.genai.types.FunctionCall

FunctionResponse = google.genai.types.FunctionResponse

ThinkingConfig = google.genai.types.ThinkingConfig

ThinkingLevel = google.genai.types.ThinkingLevel


class AgentInput(BaseModel):
    conversation_id: UUID
    user_id: str
    system_prompt: str
    contents: list[Content]

    @field_serializer("conversation_id")
    def serialize_conversation_id(self, conversation_id: UUID) -> str:
        return str(conversation_id)


class ToolCallStep(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    name: str
    args: dict


class UserMessageStep(BaseModel):
    type: Literal["user_message"] = "user_message"
    text: str
    data: Optional[str] = None
    mime_type: Optional[str] = None


class MessageStep(BaseModel):
    type: Literal["message"] = "message"
    text: str


RunAgentStep = Union[ToolCallStep, MessageStep, UserMessageStep]


class UserMessagePart(BaseModel):
    text: Optional[str] = None
    data: Optional[bytes] = None
    mime_type: Optional[str] = None


class RunAgentUserMessage(BaseModel):
    type: Literal["user"] = "user"
    parts: list[UserMessagePart]


MessageType = RunAgentUserMessage


class RunAgentInput(BaseModel):
    conversation_id: UUID
    user_id: str
    message: MessageType
    channel_instructions: Optional[str] = None

    @field_serializer("conversation_id")
    def serialize_conversation_id(self, conversation_id: UUID) -> str:
        return str(conversation_id)


class ServingSize(BaseModel):
    id: UUID
    label: str
    grams: float

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertServingSizeInput(BaseModel):
    label: str
    grams: float


class UpdateServingSizeInput(BaseModel):
    id: UUID
    label: Optional[str] = None
    grams: Optional[float] = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertFoodInput(BaseModel):
    name: str
    protein_g: int
    carbs_g: int
    fat_g: int
    calories_kcal: int
    serving_sizes: list[InsertServingSizeInput] = Field(default_factory=list)


class UpdateFoodInput(BaseModel):
    id: UUID
    name: Optional[str]
    protein_g: Optional[int]
    carbs_g: Optional[int]
    fat_g: Optional[int]
    calories_kcal: Optional[int]


class Food(BaseModel):
    id: UUID
    name: str
    protein_g: int
    carbs_g: int
    fat_g: int
    calories_kcal: int
    serving_sizes: list[ServingSize] = Field(default_factory=list)

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)


class InsertFoodLogByGramsInput(BaseModel):
    food_id: UUID
    quantity_g: float

    @field_serializer("food_id")
    def serialize_food_id(self, food_id: UUID) -> str:
        return str(food_id)


class InsertFoodLogByServingSizeInput(BaseModel):
    food_id: UUID
    serving_size_id: UUID
    quantity: float

    @field_serializer("food_id")
    def serialize_food_id(self, food_id: UUID) -> str:
        return str(food_id)

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, serving_size_id: UUID) -> str:
        return str(serving_size_id)


class UpdateFoodLogInput(BaseModel):
    id: UUID
    food_id: Optional[UUID]
    quantity_g: Optional[int]

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, food_id: Optional[UUID]) -> Optional[str]:
        return str(food_id) if food_id is not None else None


class FoodLog(BaseModel):
    id: UUID
    food_id: UUID
    quantity_g: Optional[float] = None
    serving_size_id: Optional[UUID] = None
    quantity: Optional[float] = None

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, food_id: UUID) -> str:
        return str(food_id)

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, serving_size_id: Optional[UUID]) -> Optional[str]:
        return str(serving_size_id) if serving_size_id is not None else None


class FoodLogWithFood(BaseModel):
    id: UUID
    food_id: UUID
    quantity_g: Optional[float] = None
    serving_size_id: Optional[UUID] = None
    quantity: Optional[float] = None
    food: Food

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

    @field_serializer("food_id")
    def serialize_food_id(self, food_id: UUID) -> str:
        return str(food_id)

    @field_serializer("serving_size_id")
    def serialize_serving_size_id(self, serving_size_id: Optional[UUID]) -> Optional[str]:
        return str(serving_size_id) if serving_size_id is not None else None


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


class InsertMeasurementInput(BaseModel):
    weight_kg: float


class Measurement(BaseModel):
    id: UUID
    weight_kg: float
    created_at: datetime

    @field_serializer("id")
    def serialize_id(self, id: UUID) -> str:
        return str(id)

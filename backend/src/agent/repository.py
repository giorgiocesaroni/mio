import json
import os
from typing import Optional
from uuid import UUID
import psycopg
from psycopg.rows import class_row
import src.agent.models as models
import src.agent.embeddings as embeddings

db_connection_params = {
    "dbname": os.getenv("DB_NAME", ""),
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", ""),
    "port": int(os.getenv("DB_PORT", "")),
    "prepare_threshold": None,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
    "connect_timeout": 10,
}

# Conversations and Messages


def get_messages_by_conversation_id(
    conversation_id: UUID,
    user_id: str,
) -> list[models.Content]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT raw_content
                FROM messages
                WHERE conversation_id = %s AND user_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id, user_id),
            )
            rows = cur.fetchall()
            return [models.Content.model_validate(row[0]) for row in rows]


def create_conversation_if_not_exists(conversation_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (conversation_id, user_id),
            )


def insert_conversation_message(conversation_id: UUID, content: models.Content, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (conversation_id, raw_content, user_id)
                VALUES (%s, %s, %s)
                """,
                (conversation_id, content.model_dump_json(), user_id),
            )


def insert_llm_invocation(
    total_cost: float,
    raw_usage_metadata: dict,
    user_id: str,
    conversation_id: Optional[UUID] = None,
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_invocations (total_cost, raw_usage_metadata, conversation_id, user_id)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    total_cost,
                    json.dumps(raw_usage_metadata),
                    str(conversation_id) if conversation_id else None,
                    user_id,
                ),
            )


def get_total_llm_usage() -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int as total_invocations,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'prompt_token_count')::bigint, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'candidates_token_count')::bigint, 0)), 0) as total_candidates_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'cached_content_token_count')::bigint, 0)), 0) as total_cached_tokens
                FROM llm_invocations
                """,
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Failed to retrieve LLM usage data.")
            return {
                "total_invocations": row[0],
                "total_cost": float(row[1]),
                "prompt_tokens": row[2],
                "candidates_tokens": row[3],
                "cached_tokens": row[4],
            }


def get_conversation_llm_usage(conversation_id: UUID) -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int as total_invocations,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'prompt_token_count')::bigint, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'candidates_token_count')::bigint, 0)), 0) as total_candidates_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'cached_content_token_count')::bigint, 0)), 0) as total_cached_tokens
                FROM llm_invocations
                WHERE conversation_id = %s
                """,
                (str(conversation_id),),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(
                    "No LLM invocations found for the given conversation ID."
                )
            return {
                "total_invocations": row[0],
                "total_cost": float(row[1]),
                "prompt_tokens": row[2],
                "candidates_tokens": row[3],
                "cached_tokens": row[4],
            }


def _embedding_to_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


# Foods


def search_foods(query: str, limit: int = 10, user_id: str = "") -> list[models.Food]:
    embedding = embeddings.generate_embedding(query)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, protein_g, carbs_g, fat_g, calories_kcal
                FROM foods
                WHERE embedding IS NOT NULL AND user_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (user_id, _embedding_to_str(embedding), limit),
            )
            rows = cur.fetchall()
            return [
                models.Food(
                    id=row[0],
                    name=row[1],
                    protein_g=row[2],
                    carbs_g=row[3],
                    fat_g=row[4],
                    calories_kcal=row[5],
                )
                for row in rows
            ]


def get_all_foods(user_id: str) -> list[models.Food]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, protein_g, carbs_g, fat_g, calories_kcal
                FROM foods
                WHERE user_id = %s
                ORDER BY name ASC
                """, (user_id,))
            rows = cur.fetchall()
            return [
                models.Food(
                    id=row[0],
                    name=row[1],
                    protein_g=row[2],
                    carbs_g=row[3],
                    fat_g=row[4],
                    calories_kcal=row[5],
                )
                for row in rows
            ]


def get_food_by_id(food_id: UUID, user_id: str) -> Optional[models.Food]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, protein_g, carbs_g, fat_g, calories_kcal
                FROM foods
                WHERE id = %s AND user_id = %s
                """,
                (food_id, user_id),
            )
            row = cur.fetchone()
            if row:
                return models.Food(
                    id=row[0],
                    name=row[1],
                    protein_g=row[2],
                    carbs_g=row[3],
                    fat_g=row[4],
                    calories_kcal=row[5],
                )
            return None


def insert_food(food: models.InsertFoodInput, user_id: str) -> UUID:
    embedding = embeddings.generate_embedding(food.name)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO foods (name, protein_g, carbs_g, fat_g, calories_kcal, embedding, user_id)
                VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
                RETURNING id
                """,
                (
                    food.name,
                    food.protein_g,
                    food.carbs_g,
                    food.fat_g,
                    food.calories_kcal,
                    _embedding_to_str(embedding),
                    user_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise Exception("Failed to insert food: no ID returned.")
            return row[0]


def update_food(food: models.UpdateFoodInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE foods
                SET name = COALESCE(%s, name),
                    protein_g = COALESCE(%s, protein_g),
                    carbs_g = COALESCE(%s, carbs_g),
                    fat_g = COALESCE(%s, fat_g),
                    calories_kcal = COALESCE(%s, calories_kcal)
                WHERE id = %s AND user_id = %s
                """,
                (
                    food.name,
                    food.protein_g,
                    food.carbs_g,
                    food.fat_g,
                    food.calories_kcal,
                    food.id,
                    user_id,
                ),
            )
    if food.name is not None:
        new_embedding = embeddings.generate_embedding(food.name)
        with psycopg.connect(**db_connection_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE foods SET embedding = %s::vector WHERE id = %s AND user_id = %s",
                    (_embedding_to_str(new_embedding), food.id, user_id),
                )


def delete_food(food_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM foods
                WHERE id = %s AND user_id = %s
                """,
                (food_id, user_id),
            )


# Food Logs


def get_food_logs_by_day(day: str, user_id: str) -> list[models.FoodLogWithFood]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    fl.id, fl.food_id, fl.quantity_g,
                    f.id, f.name, f.protein_g, f.carbs_g, f.fat_g, f.calories_kcal
                FROM food_logs fl
                JOIN foods f ON f.id = fl.food_id
                WHERE DATE(fl.created_at) = %s AND fl.user_id = %s
                ORDER BY fl.created_at ASC
                """,
                (day, user_id),
            )
            return [
                models.FoodLogWithFood(
                    id=row[0],
                    food_id=row[1],
                    quantity_g=row[2],
                    food=models.Food(
                        id=row[3],
                        name=row[4],
                        protein_g=row[5],
                        carbs_g=row[6],
                        fat_g=row[7],
                        calories_kcal=row[8],
                    ),
                )
                for row in cur.fetchall()
            ]


def insert_food_log(food_log: models.InsertFoodLogInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO food_logs (food_id, quantity_g, user_id)
                VALUES (%s, %s, %s)
                """,
                (str(food_log.food_id), food_log.quantity_g, user_id),
            )


def update_food_log(input: models.UpdateFoodLogInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE food_logs
                SET food_id = COALESCE(%s, food_id),
                    quantity_g = COALESCE(%s, quantity_g)
                WHERE id = %s AND user_id = %s
                """,
                (
                    str(input.food_id) if input.food_id is not None else None,
                    input.quantity_g,
                    input.id,
                    user_id,
                ),
            )


def delete_food_log(food_log_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM food_logs
                WHERE id = %s AND user_id = %s
                """,
                (str(food_log_id), user_id),
            )


# Goals


def get_current_goal(user_id: str) -> Optional[models.Goal]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Goal)) as cur:
            cur.execute(
                """
                SELECT id, created_at, weight_kg, calories_kcal, protein_g, carbs_g, fat_g, goal
                FROM goals
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone()


def insert_goal(goal: models.InsertGoalInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO goals (weight_kg, calories_kcal, protein_g, carbs_g, fat_g, goal, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    goal.weight_kg,
                    goal.calories_kcal,
                    goal.protein_g,
                    goal.carbs_g,
                    goal.fat_g,
                    goal.goal,
                    user_id,
                ),
            )


# Measurements


def get_latest_measurement(user_id: str) -> Optional[models.Measurement]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Measurement)) as cur:
            cur.execute(
                """
                SELECT id, weight_kg, created_at
                FROM measurements
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone()


def insert_measurement(measurement: models.InsertMeasurementInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO measurements (weight_kg, user_id)
                VALUES (%s, %s)
                """,
                (measurement.weight_kg, user_id),
            )

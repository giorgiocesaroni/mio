import json
import os
from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo
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
    # "prepare_threshold": None,
    # "connect_timeout": 5,
}

# Conversations and Messages


def get_user_timezone(user_id: str) -> str:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timezone FROM profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else "UTC"


def _localize_to_utc(logged_at: str, timezone: str) -> datetime:
    """Parse a naive 'YYYY-MM-DD HH:MM' string as local time and return a UTC-aware datetime."""
    naive = datetime.strptime(logged_at, "%Y-%m-%d %H:%M")
    local = naive.replace(tzinfo=ZoneInfo(timezone))
    return local.astimezone(ZoneInfo("UTC"))


def get_messages_by_conversation_id(
    conversation_id: UUID,
    user_id: str,
) -> list[dict]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT raw_content::json
                FROM messages
                WHERE conversation_id = %s AND user_id = %s
                ORDER BY created_at ASC
                """,
                (conversation_id, user_id),
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]


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


def insert_conversation_message(
    conversation_id: UUID, content: dict, user_id: str
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (conversation_id, raw_content, user_id)
                VALUES (%s, %s, %s)
                """,
                (conversation_id, json.dumps(content), user_id),
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
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'prompt_tokens')::bigint, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'completion_tokens')::bigint, 0)), 0) as total_completion_tokens
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
                "completion_tokens": row[3],
            }


def get_conversation_llm_usage(conversation_id: UUID) -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int as total_invocations,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'prompt_tokens')::bigint, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE((raw_usage_metadata->>'completion_tokens')::bigint, 0)), 0) as total_completion_tokens
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
                "completion_tokens": row[3],
            }


def _embedding_to_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


# Serving Sizes


def get_serving_sizes_by_food_id(
    food_id: UUID, user_id: str
) -> list[models.ServingSize]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.ServingSize)) as cur:
            cur.execute(
                """
                SELECT id, label, grams
                FROM serving_sizes
                WHERE food_id = %s AND user_id = %s
                ORDER BY label ASC
                """,
                (food_id, user_id),
            )
            return cur.fetchall()


def insert_serving_size(
    food_id: UUID, input: models.InsertServingSizeInput, user_id: str
) -> models.ServingSize:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.ServingSize)) as cur:
            cur.execute(
                """
                INSERT INTO serving_sizes (food_id, label, grams, user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, label, grams
                """,
                (str(food_id), input.label, input.grams, user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise Exception("Failed to insert serving size: no row returned.")
            return row


def update_serving_size(
    input: models.UpdateServingSizeInput, user_id: str
) -> models.ServingSize:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.ServingSize)) as cur:
            cur.execute(
                """
                UPDATE serving_sizes
                SET label = COALESCE(%s, label),
                    grams = COALESCE(%s, grams)
                WHERE id = %s AND user_id = %s
                RETURNING id, label, grams
                """,
                (input.label, input.grams, str(input.id), user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise Exception("Serving size not found or not owned by user.")
            return row


def delete_serving_size(serving_size_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM serving_sizes
                WHERE id = %s AND user_id = %s
                """,
                (str(serving_size_id), user_id),
            )


# Foods

_SERVING_SIZES_AGG = """
    COALESCE(
        json_agg(json_build_object('id', ss.id, 'label', ss.label, 'grams', ss.grams))
        FILTER (WHERE ss.id IS NOT NULL),
        '[]'
    ) AS serving_sizes
"""


def search_foods(query: str, limit: int = 10, user_id: str = "") -> list[models.Food]:
    embedding = embeddings.generate_embedding(query)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Food)) as cur:
            cur.execute(
                f"""
                SELECT f.id, f.name, f.protein_g, f.carbs_g, f.fat_g, f.calories_kcal,
                    {_SERVING_SIZES_AGG}
                FROM foods f
                LEFT JOIN serving_sizes ss ON ss.food_id = f.id
                WHERE f.embedding IS NOT NULL AND f.user_id = %s
                GROUP BY f.id
                ORDER BY f.embedding <=> %s::vector
                LIMIT %s
                """,
                (user_id, _embedding_to_str(embedding), limit),
            )
            return cur.fetchall()


def get_all_foods(user_id: str) -> list[models.Food]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Food)) as cur:
            cur.execute(
                f"""
                SELECT f.id, f.name, f.protein_g, f.carbs_g, f.fat_g, f.calories_kcal,
                    {_SERVING_SIZES_AGG}
                FROM foods f
                LEFT JOIN serving_sizes ss ON ss.food_id = f.id
                WHERE f.user_id = %s
                GROUP BY f.id
                ORDER BY f.name ASC
                """,
                (user_id,),
            )
            return cur.fetchall()


def get_food_by_id(food_id: UUID, user_id: str) -> Optional[models.Food]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Food)) as cur:
            cur.execute(
                f"""
                SELECT f.id, f.name, f.protein_g, f.carbs_g, f.fat_g, f.calories_kcal,
                    {_SERVING_SIZES_AGG}
                FROM foods f
                LEFT JOIN serving_sizes ss ON ss.food_id = f.id
                WHERE f.id = %s AND f.user_id = %s
                GROUP BY f.id
                """,
                (food_id, user_id),
            )
            return cur.fetchone()


def insert_food(food: models.InsertFoodInput, user_id: str) -> models.Food:
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
            food_id = row[0]
            for ss in food.serving_sizes:
                cur.execute(
                    """
                    INSERT INTO serving_sizes (food_id, label, grams, user_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (str(food_id), ss.label, ss.grams, user_id),
                )
    result = get_food_by_id(food_id, user_id)
    if result is None:
        raise Exception("Failed to retrieve food after insert.")
    return result


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
    tz = get_user_timezone(user_id)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    fl.id, fl.food_id, fl.quantity_g, fl.serving_size_id, fl.quantity,
                    f.id, f.name, f.protein_g, f.carbs_g, f.fat_g, f.calories_kcal,
                    {_SERVING_SIZES_AGG}
                FROM food_logs fl
                JOIN foods f ON f.id = fl.food_id
                LEFT JOIN serving_sizes ss ON ss.food_id = f.id
                WHERE DATE(fl.created_at AT TIME ZONE %s) = %s AND fl.user_id = %s
                GROUP BY fl.id, f.id
                ORDER BY fl.created_at ASC
                """,
                (tz, day, user_id),
            )
            return [
                models.FoodLogWithFood(
                    id=row[0],
                    food_id=row[1],
                    quantity_g=row[2],
                    serving_size_id=row[3],
                    quantity=row[4],
                    food=models.Food(
                        id=row[5],
                        name=row[6],
                        protein_g=row[7],
                        carbs_g=row[8],
                        fat_g=row[9],
                        calories_kcal=row[10],
                        serving_sizes=[models.ServingSize(**ss) for ss in row[11]],
                    ),
                )
                for row in cur.fetchall()
            ]


def insert_food_log_by_grams(
    input: models.InsertFoodLogByGramsInput, user_id: str
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            if input.logged_at is not None:
                tz = get_user_timezone(user_id)
                utc_dt = _localize_to_utc(input.logged_at, tz)
                cur.execute(
                    """
                    INSERT INTO food_logs (food_id, quantity_g, user_id, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (str(input.food_id), input.quantity_g, user_id, utc_dt),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO food_logs (food_id, quantity_g, user_id)
                    VALUES (%s, %s, %s)
                    """,
                    (str(input.food_id), input.quantity_g, user_id),
                )


def insert_food_log_by_serving_size(
    input: models.InsertFoodLogByServingSizeInput, user_id: str
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            if input.logged_at is not None:
                tz = get_user_timezone(user_id)
                utc_dt = _localize_to_utc(input.logged_at, tz)
                cur.execute(
                    """
                    INSERT INTO food_logs (food_id, serving_size_id, quantity, user_id, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(input.food_id),
                        str(input.serving_size_id),
                        input.quantity,
                        user_id,
                        utc_dt,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO food_logs (food_id, serving_size_id, quantity, user_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        str(input.food_id),
                        str(input.serving_size_id),
                        input.quantity,
                        user_id,
                    ),
                )


def update_food_log(input: models.UpdateFoodLogInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE food_logs
                SET food_id = COALESCE(%s, food_id),
                    quantity_g = COALESCE(%s, quantity_g),
                    created_at = COALESCE(%s, created_at)
                WHERE id = %s AND user_id = %s
                """,
                (
                    str(input.food_id) if input.food_id is not None else None,
                    input.quantity_g,
                    (
                        _localize_to_utc(input.logged_at, get_user_timezone(user_id))
                        if input.logged_at is not None
                        else None
                    ),
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


def get_daily_macros(day: str, user_id: str) -> dict:
    tz = get_user_timezone(user_id)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM((f.protein_g * COALESCE(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0), 0) as total_protein_g,
                    COALESCE(SUM((f.carbs_g * COALESCE(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0), 0) as total_carbs_g,
                    COALESCE(SUM((f.fat_g * COALESCE(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0), 0) as total_fat_g,
                    COALESCE(SUM((f.calories_kcal * COALESCE(ss.grams * fl.quantity, fl.quantity_g))::numeric / 100.0), 0) as total_calories_kcal
                FROM food_logs fl
                JOIN foods f ON f.id = fl.food_id
                LEFT JOIN serving_sizes ss ON ss.id = fl.serving_size_id
                WHERE DATE(fl.created_at AT TIME ZONE %s) = %s AND fl.user_id = %s
                """,
                (tz, day, user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Failed to retrieve daily macros.")
            return {
                "total_protein_g": float(row[0]),
                "total_carbs_g": float(row[1]),
                "total_fat_g": float(row[2]),
                "total_calories_kcal": float(row[3]),
            }


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


def insert_measurement(
    measurement: models.InsertMeasurementInput, user_id: str
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO measurements (weight_kg, user_id)
                VALUES (%s, %s)
                """,
                (measurement.weight_kg, user_id),
            )

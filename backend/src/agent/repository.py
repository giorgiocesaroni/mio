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

# ── Conversations and Messages ────────────────────────────────────────────────


def get_user_timezone(user_id: str) -> str:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT timezone FROM profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else "UTC"


def _localize_to_utc(log_for: str, timezone: str) -> datetime:
    """Parse a naive 'YYYY-MM-DD HH:MM' string as local time and return a UTC-aware datetime."""
    naive = datetime.strptime(log_for, "%Y-%m-%d %H:%M")
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


def create_conversation_if_not_exists(
    conversation_id: UUID, user_id: str, title: Optional[str] = None
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, user_id, title)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (conversation_id, user_id, title),
            )


def update_conversation_title(conversation_id: UUID, title: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET title = %s
                WHERE id = %s
                """,
                (title, conversation_id),
            )


def get_conversations(user_id: str) -> list[models.Conversation]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Conversation)) as cur:
            cur.execute(
                """
                SELECT id, title, created_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return cur.fetchall()


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
    model_id: str,
    uncached_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    user_id: str,
    conversation_id: Optional[UUID] = None,
) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_invocations (
                    total_cost, raw_usage_metadata, model_id,
                    uncached_input_tokens, cached_input_tokens, output_tokens,
                    conversation_id, user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    total_cost,
                    json.dumps(raw_usage_metadata),
                    model_id,
                    uncached_input_tokens,
                    cached_input_tokens,
                    output_tokens,
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
                    COALESCE(SUM(COALESCE(uncached_input_tokens, 0) + COALESCE(cached_input_tokens, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE(output_tokens, 0)), 0) as total_completion_tokens
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
                    COALESCE(SUM(COALESCE(uncached_input_tokens, 0) + COALESCE(cached_input_tokens, 0)), 0) as total_prompt_tokens,
                    COALESCE(SUM(COALESCE(output_tokens, 0)), 0) as total_completion_tokens
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


def get_llm_usage_by_model() -> list[dict]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(model_id, 'unknown') AS model_id,
                    COUNT(*)::int AS invocations,
                    COALESCE(SUM(total_cost), 0) AS total_cost,
                    COALESCE(SUM(COALESCE(uncached_input_tokens, 0)), 0) AS uncached_input_tokens,
                    COALESCE(SUM(COALESCE(cached_input_tokens, 0)), 0) AS cached_input_tokens,
                    COALESCE(SUM(COALESCE(output_tokens, 0)), 0) AS output_tokens
                FROM llm_invocations
                GROUP BY model_id
                ORDER BY total_cost DESC
                """,
            )
            rows = cur.fetchall()
            return [
                {
                    "model_id": row[0],
                    "invocations": row[1],
                    "total_cost": float(row[2]),
                    "uncached_input_tokens": row[3],
                    "cached_input_tokens": row[4],
                    "output_tokens": row[5],
                }
                for row in rows
            ]


def _embedding_to_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


# ── Serving Sizes ─────────────────────────────────────────────────────────────


def get_serving_sizes_by_ingredient_id(
    ingredient_id: UUID, user_id: str
) -> list[models.ServingSize]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.ServingSize)) as cur:
            cur.execute(
                """
                SELECT id, label, label_plural, grams
                FROM serving_sizes
                WHERE food_id = %s AND user_id = %s
                ORDER BY label ASC
                """,
                (ingredient_id, user_id),
            )
            return cur.fetchall()


def insert_serving_size(
    ingredient_id: UUID, input: models.InsertServingSizeInput, user_id: str
) -> models.ServingSize:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.ServingSize)) as cur:
            cur.execute(
                """
                INSERT INTO serving_sizes (food_id, label, label_plural, grams, user_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, label, label_plural, grams
                """,
                (str(ingredient_id), input.label, input.label_plural, input.grams, user_id),
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
                    label_plural = COALESCE(%s, label_plural),
                    grams = COALESCE(%s, grams)
                WHERE id = %s AND user_id = %s
                RETURNING id, label, label_plural, grams
                """,
                (input.label, input.label_plural, input.grams, str(input.id), user_id),
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


# ── Ingredients ───────────────────────────────────────────────────────────────

_SERVING_SIZES_AGG = """
    COALESCE(
        json_agg(json_build_object('id', ss.id, 'label', ss.label, 'label_plural', ss.label_plural, 'grams', ss.grams))
        FILTER (WHERE ss.id IS NOT NULL),
        '[]'
    ) AS serving_sizes
"""


def search_ingredients(query: str, limit: int = 10, user_id: str = "") -> list[models.Ingredient]:
    embedding = embeddings.generate_embedding(query)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT i.id, i.name, i.protein_g, i.carbs_g, i.fat_g, i.calories_kcal, i.brand, i.source_url, i.state,
                    i.embedding <=> %s::vector AS distance,
                    {_SERVING_SIZES_AGG}
                FROM ingredients i
                LEFT JOIN serving_sizes ss ON ss.food_id = i.id
                WHERE i.embedding IS NOT NULL AND i.user_id = %s
                GROUP BY i.id, i.embedding
                ORDER BY distance
                LIMIT %s
                """,
                (_embedding_to_str(embedding), user_id, limit),
            )
            results = []
            for row in cur.fetchall():
                serving_sizes_raw = row[10] or []
                results.append(models.Ingredient(
                    id=row[0], name=row[1], protein_g=row[2], carbs_g=row[3],
                    fat_g=row[4], calories_kcal=row[5], brand=row[6],
                    source_url=row[7], state=row[8], distance=float(row[9]),
                    serving_sizes=[models.ServingSize(**ss) for ss in serving_sizes_raw],
                ))
            return results


def get_ingredient_by_id(ingredient_id: UUID, user_id: str) -> Optional[models.Ingredient]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Ingredient)) as cur:
            cur.execute(
                f"""
                SELECT i.id, i.name, i.protein_g, i.carbs_g, i.fat_g, i.calories_kcal, i.brand, i.source_url, i.state,
                    {_SERVING_SIZES_AGG}
                FROM ingredients i
                LEFT JOIN serving_sizes ss ON ss.food_id = i.id
                WHERE i.id = %s AND i.user_id = %s
                GROUP BY i.id
                """,
                (ingredient_id, user_id),
            )
            return cur.fetchone()


def insert_ingredient(ingredient: models.InsertIngredientInput, user_id: str) -> models.Ingredient:
    embedding = embeddings.generate_embedding(ingredient.name)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingredients (name, protein_g, carbs_g, fat_g, calories_kcal, brand, source_url, state, embedding, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                RETURNING id
                """,
                (
                    ingredient.name,
                    ingredient.protein_g,
                    ingredient.carbs_g,
                    ingredient.fat_g,
                    ingredient.calories_kcal,
                    ingredient.brand,
                    ingredient.source_url,
                    ingredient.state,
                    _embedding_to_str(embedding),
                    user_id,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise Exception("Failed to insert ingredient: no ID returned.")
            ingredient_id = row[0]
            for ss in ingredient.serving_sizes:
                cur.execute(
                    """
                    INSERT INTO serving_sizes (food_id, label, label_plural, grams, user_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(ingredient_id), ss.label, ss.label_plural, ss.grams, user_id),
                )
    result = get_ingredient_by_id(ingredient_id, user_id)
    if result is None:
        raise Exception("Failed to retrieve ingredient after insert.")
    return result


def update_ingredient(ingredient: models.UpdateIngredientInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingredients
                SET name = COALESCE(%s, name),
                    protein_g = COALESCE(%s, protein_g),
                    carbs_g = COALESCE(%s, carbs_g),
                    fat_g = COALESCE(%s, fat_g),
                    calories_kcal = COALESCE(%s, calories_kcal),
                    brand = COALESCE(%s, brand),
                    source_url = COALESCE(%s, source_url),
                    state = COALESCE(%s, state)
                WHERE id = %s AND user_id = %s
                """,
                (
                    ingredient.name,
                    ingredient.protein_g,
                    ingredient.carbs_g,
                    ingredient.fat_g,
                    ingredient.calories_kcal,
                    ingredient.brand,
                    ingredient.source_url,
                    ingredient.state,
                    ingredient.id,
                    user_id,
                ),
            )
    if ingredient.name is not None:
        new_embedding = embeddings.generate_embedding(ingredient.name)
        with psycopg.connect(**db_connection_params) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ingredients SET embedding = %s::vector WHERE id = %s AND user_id = %s",
                    (_embedding_to_str(new_embedding), ingredient.id, user_id),
                )


def delete_ingredient(ingredient_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM ingredients
                WHERE id = %s AND user_id = %s
                """,
                (ingredient_id, user_id),
            )


# ── Recipes ───────────────────────────────────────────────────────────────────

_RECIPE_ITEMS_AGG = """
    COALESCE(
        json_agg(json_build_object(
            'id', ri.id,
            'ingredient_id', ri.food_id,
            'quantity_g', ri.quantity_g,
            'quantity', ri.quantity,
            'serving_size_id', ri.serving_size_id
        ))
        FILTER (WHERE ri.id IS NOT NULL),
        '[]'
    ) AS items
"""


def search_recipes(query: str, limit: int = 10, user_id: str = "") -> list[models.Recipe]:
    embedding = embeddings.generate_embedding(query)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.id, r.name, r.image_url,
                    r.embedding <=> %s::vector AS distance,
                    {_RECIPE_ITEMS_AGG}
                FROM recipes r
                LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.id
                WHERE r.user_id = %s AND r.embedding IS NOT NULL
                GROUP BY r.id, r.embedding
                ORDER BY distance
                LIMIT %s
                """,
                (_embedding_to_str(embedding), user_id, limit),
            )
            results = []
            for row in cur.fetchall():
                items_raw = row[4] or []
                results.append(models.Recipe(
                    id=row[0], name=row[1], image_url=row[2],
                    distance=float(row[3]),
                    items=[models.RecipeItem(**item) for item in items_raw],
                ))
            return results


def get_recipe_by_id(recipe_id: UUID, user_id: str) -> Optional[models.Recipe]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=class_row(models.Recipe)) as cur:
            cur.execute(
                f"""
                SELECT r.id, r.name, r.image_url,
                    {_RECIPE_ITEMS_AGG}
                FROM recipes r
                LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.id
                WHERE r.id = %s AND r.user_id = %s
                GROUP BY r.id
                """,
                (recipe_id, user_id),
            )
            return cur.fetchone()


def insert_recipe(recipe: models.InsertRecipeInput, user_id: str) -> models.Recipe:
    embedding = embeddings.generate_embedding(recipe.name)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recipes (name, image_url, embedding, user_id)
                VALUES (%s, %s, %s::vector, %s)
                RETURNING id
                """,
                (recipe.name, recipe.image_url, _embedding_to_str(embedding), user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise Exception("Failed to insert recipe: no ID returned.")
            recipe_id = row[0]
            for item in recipe.items:
                cur.execute(
                    """
                    INSERT INTO recipe_ingredients (recipe_id, food_id, quantity_g, quantity, serving_size_id, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(recipe_id),
                        str(item.ingredient_id),
                        item.quantity_g,
                        item.quantity,
                        str(item.serving_size_id) if item.serving_size_id else None,
                        user_id,
                    ),
                )
    result = get_recipe_by_id(recipe_id, user_id)
    if result is None:
        raise Exception("Failed to retrieve recipe after insert.")
    return result


def update_recipe(recipe: models.UpdateRecipeInput, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recipes
                SET name = COALESCE(%s, name),
                    image_url = COALESCE(%s, image_url)
                WHERE id = %s AND user_id = %s
                """,
                (recipe.name, recipe.image_url, recipe.id, user_id),
            )


def delete_recipe(recipe_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM recipes
                WHERE id = %s AND user_id = %s
                """,
                (recipe_id, user_id),
            )


# ── Logs ──────────────────────────────────────────────────────────────────────


def get_logs_by_day(day: str, user_id: str) -> list[models.LogWithEntry]:
    """Return log entries for a given day. Each log references an ingredient; recipe_id is optional provenance for dispatched recipe logs."""
    tz = get_user_timezone(user_id)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.id,
                    l.food_id,
                    l.quantity_g,
                    l.serving_size_id,
                    l.quantity,
                    l.recipe_id,
                    l.meal_type,
                    l.log_for,
                    -- ingredient fields (NULL when log is a recipe)
                    i.id, i.name, i.protein_g, i.carbs_g, i.fat_g, i.calories_kcal, i.brand, i.source_url, i.state,
                    iss_agg.serving_sizes,
                    -- recipe fields (NULL when the log is a plain ingredient log)
                    r.id, r.name, r.image_url,
                    ri_agg.recipe_items
                FROM logs l
                LEFT JOIN ingredients i ON i.id = l.food_id
                LEFT JOIN (
                    SELECT ss.food_id,
                        json_agg(json_build_object('id', ss.id, 'label', ss.label, 'label_plural', ss.label_plural, 'grams', ss.grams)) AS serving_sizes
                    FROM serving_sizes ss
                    WHERE ss.user_id = %s
                    GROUP BY ss.food_id
                ) iss_agg ON iss_agg.food_id = i.id
                LEFT JOIN recipes r ON r.id = l.recipe_id
                LEFT JOIN (
                    SELECT ri.recipe_id,
                        json_agg(json_build_object('id', ri.id, 'ingredient_id', ri.food_id, 'quantity_g', ri.quantity_g, 'quantity', ri.quantity, 'serving_size_id', ri.serving_size_id)) AS recipe_items
                    FROM recipe_ingredients ri
                    GROUP BY ri.recipe_id
                ) ri_agg ON ri_agg.recipe_id = l.recipe_id
                WHERE DATE(l.log_for AT TIME ZONE %s) = %s AND l.user_id = %s
                ORDER BY l.log_for ASC
                """,
                (user_id, tz, day, user_id),
            )
            results: list[models.LogWithEntry] = []
            for row in cur.fetchall():
                log_for_utc = row[7]
                log_for_local = log_for_utc.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M") if log_for_utc else None
                quantity_g = row[2]
                entry = models.LogWithEntry(
                    id=row[0],
                    food_id=row[1],
                    quantity_g=quantity_g,
                    serving_size_id=row[3],
                    quantity=row[4],
                    recipe_id=row[5],
                    meal_type=row[6],
                    log_for=log_for_utc,
                    log_for_local=log_for_local,
                )
                # ingredient (row[8] = ingredient id)
                if row[8] is not None:
                    serving_sizes_raw = row[17] or []
                    entry.ingredient = models.Ingredient(
                        id=row[8],
                        name=row[9],
                        protein_g=row[10],
                        carbs_g=row[11],
                        fat_g=row[12],
                        calories_kcal=row[13],
                        brand=row[14],
                        source_url=row[15],
                        state=row[16],
                        serving_sizes=[models.ServingSize(**ss) for ss in serving_sizes_raw],
                    )
                    if quantity_g is not None:
                        factor = float(quantity_g) / 100.0
                        entry.calculated_calories_kcal = float(row[13]) * factor
                        entry.calculated_protein_g = float(row[10]) * factor
                        entry.calculated_carbs_g = float(row[11]) * factor
                        entry.calculated_fat_g = float(row[12]) * factor
                # recipe (row[18] = r.id, row[19] = r.name, row[20] = r.image_url, row[21] = ri_agg.recipe_items)
                if row[18] is not None:
                    items_raw = row[21] or []
                    entry.recipe = models.Recipe(
                        id=row[18],
                        name=row[19],
                        image_url=row[20],
                        items=[models.RecipeItem(**item) for item in items_raw],
                    )
                results.append(entry)
            return results


def insert_log_by_grams(
    input: models.InsertLogByGramsInput, user_id: str
) -> None:
    tz = get_user_timezone(user_id)
    log_for_dt = _localize_to_utc(input.log_for, tz)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            if input.recipe_id is not None:
                _dispatch_recipe_logs(
                    cur, input.recipe_id, input.quantity_g, input.meal_type, log_for_dt, user_id
                )
            elif input.food_id is not None:
                cur.execute(
                    """
                    INSERT INTO logs (food_id, quantity_g, meal_type, log_for, user_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(input.food_id), input.quantity_g, input.meal_type, log_for_dt, user_id),
                )
            else:
                raise ValueError("insert_log_by_grams requires either food_id or recipe_id.")


def _dispatch_recipe_logs(
    cur, recipe_id: UUID, quantity_g: float, meal_type, log_for_dt, user_id: str
) -> None:
    """Expand a recipe log into per-ingredient logs, scaled to the logged weight.

    `quantity_g` is the amount of the whole recipe consumed (e.g. 200g of a
    400g recipe). Each `recipe_ingredients` item is scaled proportionally, so
    the dispatched logs sum to the logged weight. Every dispatched row keeps
    `recipe_id` for provenance but is otherwise a detached ingredient log.
    """
    cur.execute(
        """
        SELECT ri.food_id,
               COALESCE(ss.grams * ri.quantity, ri.quantity_g)::numeric AS item_grams
        FROM recipe_ingredients ri
        LEFT JOIN serving_sizes ss ON ss.id = ri.serving_size_id
        WHERE ri.recipe_id = %s
        """,
        (str(recipe_id),),
    )
    items = cur.fetchall()
    if not items:
        raise Exception("Recipe has no ingredients; cannot log it.")
    total_g = sum(float(item[1]) for item in items)
    if total_g <= 0:
        raise Exception("Recipe has zero total weight; cannot log it.")
    scale = quantity_g / total_g
    for food_id, item_grams in items:
        cur.execute(
            """
            INSERT INTO logs (food_id, quantity_g, recipe_id, meal_type, log_for, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(food_id), float(item_grams) * scale, str(recipe_id), meal_type, log_for_dt, user_id),
        )


def insert_log_by_serving_size(
    input: models.InsertLogByServingSizeInput, user_id: str
) -> None:
    tz = get_user_timezone(user_id)
    log_for_dt = _localize_to_utc(input.log_for, tz)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logs (food_id, serving_size_id, quantity, meal_type, log_for, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (str(input.food_id), str(input.serving_size_id), input.quantity, input.meal_type, log_for_dt, user_id),
            )


def update_log(input: models.UpdateLogInput, user_id: str) -> None:
    log_for_dt = None
    if input.log_for is not None:
        tz = get_user_timezone(user_id)
        log_for_dt = _localize_to_utc(input.log_for, tz)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE logs
                SET food_id = COALESCE(%s, food_id),
                    quantity_g = COALESCE(%s, quantity_g),
                    recipe_id = COALESCE(%s, recipe_id),
                    meal_type = COALESCE(%s, meal_type),
                    log_for = COALESCE(%s, log_for)
                WHERE id = %s AND user_id = %s
                """,
                (
                    str(input.food_id) if input.food_id is not None else None,
                    input.quantity_g,
                    str(input.recipe_id) if input.recipe_id is not None else None,
                    input.meal_type,
                    log_for_dt,
                    input.id,
                    user_id,
                ),
            )


def log_recipe_by_proportion(
    recipe_id: UUID, proportion: float, meal_type: str, log_for: str, user_id: str
) -> None:
    """Log a recipe by proportion (0..1). Expands into per-ingredient logs scaled proportionally."""
    tz = get_user_timezone(user_id)
    log_for_dt = _localize_to_utc(log_for, tz)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            # Fetch recipe ingredients with their gram weights
            cur.execute(
                """
                SELECT ri.food_id,
                       COALESCE(ss.grams * ri.quantity, ri.quantity_g)::numeric AS item_grams
                FROM recipe_ingredients ri
                LEFT JOIN serving_sizes ss ON ss.id = ri.serving_size_id
                WHERE ri.recipe_id = %s
                """,
                (str(recipe_id),),
            )
            items = cur.fetchall()
            if not items:
                raise Exception("Recipe has no ingredients; cannot log it.")
            for food_id, item_grams in items:
                scaled_grams = float(item_grams) * proportion
                cur.execute(
                    """
                    INSERT INTO logs (food_id, quantity_g, recipe_id, meal_type, log_for, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(food_id), scaled_grams, str(recipe_id), meal_type, log_for_dt, user_id),
                )


def delete_log(log_id: UUID, user_id: str) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM logs
                WHERE id = %s AND user_id = %s
                """,
                (str(log_id), user_id),
            )


def get_daily_macros(day: str, user_id: str) -> dict:
    """Compute daily macros from ingredient logs. Recipes are dispatched into per-ingredient logs at log time, so only the ingredient path is needed."""
    tz = get_user_timezone(user_id)
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM((i.protein_g * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS protein_g,
                    COALESCE(SUM((i.carbs_g * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS carbs_g,
                    COALESCE(SUM((i.fat_g * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS fat_g,
                    COALESCE(SUM((i.calories_kcal * COALESCE(ss.grams * l.quantity, l.quantity_g))::numeric / 100.0), 0) AS calories_kcal
                FROM logs l
                JOIN ingredients i ON i.id = l.food_id
                LEFT JOIN serving_sizes ss ON ss.id = l.serving_size_id
                WHERE DATE(l.log_for AT TIME ZONE %s) = %s
                  AND l.user_id = %s
                """,
                (tz, day, user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Failed to retrieve daily macros.")
            return {
                "totalProteinG": float(row[0]),
                "totalCarbsG": float(row[1]),
                "totalFatG": float(row[2]),
                "totalCaloriesKcal": float(row[3]),
            }


# ── Goals ─────────────────────────────────────────────────────────────────────


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


# ── Measurements ──────────────────────────────────────────────────────────────


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

from typing import Callable
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import src.agent.repository as agent_repository
from src.agent.repository import db_connection_params
from src.pipeline.models import DraftError


def record_invocation(
    user_id: str, model_id: str, cost: float, usage: dict, tokens: tuple[int, int, int]
) -> None:
    uncached_input, cached_input, output = tokens
    agent_repository.insert_llm_invocation(
        total_cost=cost,
        raw_usage_metadata=usage,
        model_id=model_id,
        uncached_input_tokens=uncached_input,
        cached_input_tokens=cached_input,
        output_tokens=output,
        user_id=user_id,
        conversation_id=None,
    )


def recipe_nutrition(recipe_ids: list[str], user_id: str) -> dict[str, dict]:
    """Total weight and per-100 g macros of each recipe."""
    if not recipe_ids:
        return {}
    with psycopg.connect(**db_connection_params) as conn:
        rows = conn.execute(
            """
            WITH items AS (
                SELECT ri.recipe_id, i.calories_kcal, i.protein_g, i.carbs_g, i.fat_g,
                       COALESCE(ss.grams * ri.quantity, ri.quantity_g)::float AS grams
                FROM recipe_ingredients ri
                JOIN recipes r ON r.id = ri.recipe_id
                JOIN ingredients i ON i.id = ri.food_id
                LEFT JOIN serving_sizes ss ON ss.id = ri.serving_size_id
                WHERE ri.recipe_id = ANY(%s::uuid[]) AND r.user_id = %s
            )
            SELECT recipe_id,
                   SUM(grams) AS total_g,
                   SUM(calories_kcal * grams) / NULLIF(SUM(grams), 0) AS calories_kcal,
                   SUM(protein_g * grams) / NULLIF(SUM(grams), 0) AS protein_g,
                   SUM(carbs_g * grams) / NULLIF(SUM(grams), 0) AS carbs_g,
                   SUM(fat_g * grams) / NULLIF(SUM(grams), 0) AS fat_g
            FROM items
            GROUP BY recipe_id
            """,
            (recipe_ids, user_id),
        ).fetchall()
    return {
        str(r[0]): {
            "total_g": float(r[1] or 0),
            "per_100g": {
                "calories_kcal": float(r[2] or 0),
                "protein_g": float(r[3] or 0),
                "carbs_g": float(r[4] or 0),
                "fat_g": float(r[5] or 0),
            },
        }
        for r in rows
    }


# ── Drafts ────────────────────────────────────────────────────────────────────

_COLUMNS = "id, created_at, day, status, message, rows"


def insert_draft(user_id: str, day: str, message: str, rows: list[dict]) -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                INSERT INTO log_drafts (user_id, day, message, rows)
                VALUES (%s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (user_id, day, message, Jsonb(rows)),
            )
            return cur.fetchone()


def get_pending_drafts(user_id: str, day: str) -> list[dict]:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM log_drafts
                WHERE user_id = %s AND day = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (user_id, day),
            )
            return cur.fetchall()


def _lock_pending(cur, user_id: str, draft_id: UUID) -> dict:
    cur.execute(
        f"""
        SELECT {_COLUMNS} FROM log_drafts
        WHERE id = %s AND user_id = %s AND status = 'pending'
        FOR UPDATE
        """,
        (draft_id, user_id),
    )
    draft = cur.fetchone()
    if draft is None:
        raise DraftError("Draft not found, or already confirmed or discarded.")
    return draft


def update_pending_rows(
    user_id: str, draft_id: UUID, transform: Callable[[list[dict]], list[dict]]
) -> dict:
    """Replace a pending draft's rows with `transform(rows)`, under a row lock."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            draft = _lock_pending(cur, user_id, draft_id)
            cur.execute(
                f"""
                UPDATE log_drafts SET rows = %s, updated_at = now()
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (Jsonb(transform(draft["rows"])), draft_id),
            )
            return cur.fetchone()


def discard_pending(user_id: str, draft_id: UUID) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _lock_pending(cur, user_id, draft_id)
            cur.execute(
                "UPDATE log_drafts SET status = 'discarded', updated_at = now() WHERE id = %s",
                (draft_id,),
            )


def claim_pending(user_id: str, draft_id: UUID) -> dict:
    """Mark a pending draft confirmed and return it; a second claim fails."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            draft = _lock_pending(cur, user_id, draft_id)
            cur.execute(
                """
                UPDATE log_drafts
                SET status = 'confirmed', confirmed_at = now(), updated_at = now()
                WHERE id = %s
                """,
                (draft_id,),
            )
            return draft


def save_rows(draft_id: UUID, rows: list[dict], release: bool = False) -> None:
    """Persist rows of a claimed draft; `release` puts it back to pending."""
    with psycopg.connect(**db_connection_params) as conn:
        if release:
            conn.execute(
                """
                UPDATE log_drafts
                SET status = 'pending', confirmed_at = NULL, rows = %s, updated_at = now()
                WHERE id = %s
                """,
                (Jsonb(rows), draft_id),
            )
        else:
            conn.execute(
                "UPDATE log_drafts SET rows = %s, updated_at = now() WHERE id = %s",
                (Jsonb(rows), draft_id),
            )

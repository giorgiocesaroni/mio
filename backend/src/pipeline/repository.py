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

_COLUMNS = "id, created_at, day, status, message, rows, via"


def insert_draft(
    user_id: str, day: str, message: str, rows: list[dict], cost: float, via: str
) -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                INSERT INTO log_drafts (user_id, day, message, rows, cost, via)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING {_COLUMNS}
                """,
                (user_id, day, message, Jsonb(rows), cost, via),
            )
            return cur.fetchone()


def insert_pipeline_run(
    user_id: str,
    day: str | None,
    message: str | None,
    steps: list[dict],
    outcome: str,
    outcome_message: str,
    total_ms: int,
    total_cost: float,
    draft_id: str | None,
) -> None:
    """Record a sandbox run, every stage included, for debugging."""
    with psycopg.connect(**db_connection_params) as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs
                (user_id, day, message, steps, outcome, outcome_message,
                 total_ms, total_cost, draft_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                day,
                message,
                Jsonb(steps),
                outcome,
                outcome_message,
                total_ms,
                total_cost,
                draft_id,
            ),
        )


def add_draft_cost(draft_id: UUID, cost: float) -> None:
    with psycopg.connect(**db_connection_params) as conn:
        conn.execute(
            "UPDATE log_drafts SET cost = COALESCE(cost, 0) + %s WHERE id = %s",
            (cost, draft_id),
        )


def get_log_costs() -> list[dict]:
    """Drafts created from chat and what creating each one cost, by route."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT via, COUNT(*)::int AS logs, SUM(cost)::float AS total_cost
                FROM log_drafts
                WHERE cost IS NOT NULL AND via IN ('pipeline', 'agent')
                GROUP BY via
                ORDER BY via
                """
            )
            return cur.fetchall()


def get_day_entries(user_id: str, day: str) -> tuple[list[dict], list[dict]]:
    """A day's pending drafts and logs, read from one snapshot.

    Confirming takes a draft's rows before it writes their logs, so within one
    snapshot a row is either still a draft or already a log, never both.
    The logs have the columns of `v_daily_food_logs_with_foods`.
    """
    with psycopg.connect(**db_connection_params) as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM log_drafts
                WHERE user_id = %s AND day = %s AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (user_id, day),
            )
            drafts = cur.fetchall()
            cur.execute(
                """
                WITH profile AS (
                    SELECT COALESCE(
                        (SELECT timezone FROM profiles WHERE user_id = %(user_id)s),
                        'UTC'
                    ) AS timezone
                )
                SELECT
                    l.id::text AS log_id,
                    l.log_for,
                    COALESCE(l.log_for, l.created_at) AS log_created_at,
                    l.food_id::text AS log_food_id,
                    l.recipe_id::text AS log_recipe_id,
                    l.dish_id::text AS log_dish_id,
                    l.dish_name AS log_dish_name,
                    COALESCE(ss.grams * l.quantity, l.quantity_g)::float AS log_quantity_g,
                    l.serving_size_id::text AS log_serving_size_id,
                    l.quantity::float AS log_quantity,
                    ss.label AS log_serving_size_label,
                    ss.label_plural AS log_serving_size_label_plural,
                    ss.grams::float AS log_serving_size_grams,
                    i.name AS food_name,
                    i.protein_g::float AS food_protein_g,
                    i.carbs_g::float AS food_carbs_g,
                    i.fat_g::float AS food_fat_g,
                    i.calories_kcal::float AS food_calories_kcal,
                    r.name AS recipe_name
                FROM logs l
                JOIN ingredients i ON i.id = l.food_id
                LEFT JOIN serving_sizes ss ON ss.id = l.serving_size_id
                LEFT JOIN recipes r ON r.id = l.recipe_id
                WHERE l.user_id = %(user_id)s
                  AND (COALESCE(l.log_for, l.created_at) AT TIME ZONE (SELECT timezone FROM profile))::date = %(day)s
                ORDER BY log_created_at DESC
                """,
                {"user_id": user_id, "day": day},
            )
            logs = cur.fetchall()
    return drafts, logs


def get_draft(user_id: str, draft_id: UUID) -> dict | None:
    """A draft in any status."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT {_COLUMNS} FROM log_drafts WHERE id = %s AND user_id = %s",
                (draft_id, user_id),
            )
            return cur.fetchone()


def get_pending_draft(user_id: str, draft_id: UUID) -> dict:
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} FROM log_drafts
                WHERE id = %s AND user_id = %s AND status = 'pending'
                """,
                (draft_id, user_id),
            )
            draft = cur.fetchone()
    if draft is None:
        raise DraftError("Draft not found, or already confirmed or discarded.")
    return draft


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


def remove_dish(user_id: str, draft_id: UUID, dish_id: str) -> dict | None:
    """Remove one dish (all of a group's rows) from a pending draft;
    removing the last one discards it."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            draft = _lock_pending(cur, user_id, draft_id)
            remaining = [
                r for r in draft["rows"] if (r.get("dish_id") or r["id"]) != dish_id
            ]
            if len(remaining) == len(draft["rows"]):
                raise DraftError(f"Unknown dish '{dish_id}'.")
            if not remaining:
                cur.execute(
                    "UPDATE log_drafts SET status = 'discarded', updated_at = now() WHERE id = %s",
                    (draft_id,),
                )
                return None
            cur.execute(
                f"""
                UPDATE log_drafts SET rows = %s, updated_at = now()
                WHERE id = %s
                RETURNING {_COLUMNS}
                """,
                (Jsonb(remaining), draft_id),
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


def take_rows(user_id: str, draft_id: UUID, row_ids: list[str] | None) -> list[dict]:
    """Remove rows (all when `row_ids` is None) from a pending draft for logging.

    The draft becomes confirmed once its last row is taken; the row lock means
    a double click can't take the same rows twice.
    """
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            draft = _lock_pending(cur, user_id, draft_id)
            rows = draft["rows"]
            wanted = set(row_ids) if row_ids is not None else {r["id"] for r in rows}
            unknown = wanted - {r["id"] for r in rows}
            if unknown or not wanted:
                raise DraftError(f"Unknown rows: {sorted(unknown)}." if unknown else "No rows to confirm.")
            taken = [r for r in rows if r["id"] in wanted]
            remaining = [r for r in rows if r["id"] not in wanted]
            if remaining:
                cur.execute(
                    "UPDATE log_drafts SET rows = %s, updated_at = now() WHERE id = %s",
                    (Jsonb(remaining), draft_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE log_drafts
                    SET status = 'confirmed', confirmed_at = now(), updated_at = now()
                    WHERE id = %s
                    """,
                    (draft_id,),
                )
            return taken


def put_back_rows(draft_id: UUID, rows: list[dict]) -> None:
    """Return taken rows to their draft (pending again) after a failed confirm."""
    with psycopg.connect(**db_connection_params) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT status, rows FROM log_drafts WHERE id = %s FOR UPDATE", (draft_id,))
            draft = cur.fetchone()
            current = draft["rows"] if draft["status"] == "pending" else []
            # Row ids are "r<index>", so this restores the original order.
            merged = sorted(current + rows, key=lambda r: int(r["id"][1:]))
            cur.execute(
                """
                UPDATE log_drafts
                SET status = 'pending', confirmed_at = NULL, rows = %s, updated_at = now()
                WHERE id = %s
                """,
                (Jsonb(merged), draft_id),
            )

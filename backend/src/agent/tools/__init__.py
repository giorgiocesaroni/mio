"""Agent tool declarations and implementations.

Split by domain so each module holds one group of related tools:

- ``web`` — web research (web_search, web_fetch), backed by TinyFish
- ``search`` — semantic search over ingredients and recipes
- ``ingredients`` — ingredient and serving-size CRUD
- ``recipes`` — recipe (template) CRUD
- ``logs`` — food logging and daily summary
- ``tracking`` — goals and measurements

All symbols are re-exported here so callers (e.g. ``agent.py``) can keep using
``tools.<name>``.
"""

from .web import (
    web_fetch_declaration,
    web_fetch_tool,
    web_search_declaration,
    web_search_tool,
)
from .search import search_declaration, search_tool
from .ingredients import (
    delete_ingredient_declaration,
    delete_ingredient_tool,
    delete_serving_size_declaration,
    delete_serving_size_tool,
    get_ingredient_by_id_declaration,
    get_ingredient_by_id_tool,
    get_serving_sizes_by_ingredient_id_declaration,
    get_serving_sizes_by_ingredient_id_tool,
    insert_ingredient_declaration,
    insert_ingredient_tool,
    insert_serving_size_declaration,
    insert_serving_size_tool,
    update_ingredient_declaration,
    update_ingredient_tool,
    update_serving_size_declaration,
    update_serving_size_tool,
)
from .recipes import (
    delete_recipe_declaration,
    delete_recipe_tool,
    get_recipe_by_id_declaration,
    get_recipe_by_id_tool,
    insert_recipe_declaration,
    insert_recipe_tool,
    update_recipe_declaration,
    update_recipe_tool,
)
from .logs import (
    delete_log_declaration,
    delete_log_tool,
    get_daily_summary_declaration,
    get_daily_summary_tool,
    insert_log_by_grams_declaration,
    insert_log_by_grams_tool,
    insert_log_by_serving_size_declaration,
    insert_log_by_serving_size_tool,
    update_log_declaration,
    update_log_tool,
)
from .tracking import (
    get_current_goal_declaration,
    get_current_goal_tool,
    get_latest_measurements_declaration,
    get_latest_measurements_tool,
    insert_goal_declaration,
    insert_goal_tool,
    insert_measurement_declaration,
    insert_measurement_tool,
)
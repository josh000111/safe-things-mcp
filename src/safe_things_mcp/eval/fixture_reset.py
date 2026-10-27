"""Fixture-reset planner for test5.

Generates a plan (as a pure dict) describing what needs to happen to reset
the Things state back to the pristine test5 fixture.  Does NOT execute any
mutations.  The --apply flag exists but is hard-refused unless the current
user is 'Test', and even then it only prints the plan (apply not yet
implemented beyond dry-run scope).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .scorer import TaskState, _find_state, _norm, load_key

# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

# Cluster/theme group assignment for round-robin shuffle.
# Each task n → group label.  Singletons/ambiguous get label "misc".
_CLUSTER_GROUP: dict[int, str] = {
    # carbonara hard members + soft
    5: "carbonara", 10: "carbonara", 15: "carbonara", 19: "carbonara", 23: "carbonara",
    # baking hard members + soft
    3: "baking", 12: "baking", 18: "baking", 24: "baking", 28: "baking", 29: "baking",
    # freelance / techcorp existing routes
    2: "freelance", 7: "freelance", 17: "freelance",
    # apartment move routes
    4: "apartment", 13: "apartment", 20: "apartment", 26: "apartment",
    # recipe app routes
    9: "recipe", 14: "recipe", 22: "recipe",
    # singletons / ambiguous
    1: "misc", 6: "misc", 8: "misc", 11: "misc", 16: "misc",
    21: "misc", 25: "misc", 27: "misc", 30: "misc",
}

# Deterministic ordering of groups for round-robin (no randomness).
_GROUP_ORDER = ["carbonara", "baking", "freelance", "apartment", "recipe", "misc"]


def _build_shuffled_titles(key: dict) -> list[str]:
    """Round-robin across groups so no two adjacent titles share a group.

    Within each group tasks appear in ascending n order.
    Returns a list of 30 titles.
    """
    tasks_by_group: dict[str, list[dict]] = {g: [] for g in _GROUP_ORDER}
    for task in sorted(key["tasks"], key=lambda t: t["n"]):
        n = task["n"]
        group = _CLUSTER_GROUP.get(n, "misc")
        tasks_by_group[group].append(task)

    result: list[str] = []
    # Iterators per group.
    iterators = {g: iter(tasks_by_group[g]) for g in _GROUP_ORDER}
    # Cycle through groups in order, skipping exhausted ones.
    remaining_groups = [g for g in _GROUP_ORDER if tasks_by_group[g]]
    while remaining_groups:
        for group in list(remaining_groups):
            try:
                task = next(iterators[group])
                result.append(task["title"])
            except StopIteration:
                remaining_groups.remove(group)

    return result


def plan_reset(
    key: dict,
    states: dict[str, TaskState],
    recent_undo: list[dict],
) -> dict[str, Any]:
    """Pure function. Returns a reset-plan dict describing all needed actions."""
    key_titles = {t["title"] for t in key["tasks"]}
    existing_projects_norm = {_norm(p) for p in key.get("existing_projects", [])}

    abstain_tags = {"*Unclear*", "*Ambiguous Home*", "*Duplicate?*"}

    tasks_out_of_inbox: list[dict] = []
    missing_tasks: list[dict] = []
    abstain_tags_to_strip: list[dict] = []
    ai_project_names: set[str] = set()

    for task in key["tasks"]:
        n = task["n"]
        title = task["title"]
        state = _find_state(states, title)

        if state is None or state.get("container_kind") == "missing":
            missing_tasks.append({"n": n, "title": title})
            continue

        kind = state.get("container_kind")
        container = state.get("container_name")

        if kind != "inbox":
            tasks_out_of_inbox.append({"n": n, "title": title, "container_name": container})
            # Collect AI-created project names (not in existing_projects, not None).
            if kind == "project" and container and _norm(container) not in existing_projects_norm:
                ai_project_names.add(container)
        else:
            # In inbox — check for lingering abstain tags.
            tags = state.get("tags") or []
            lingering = [t for t in tags if t in abstain_tags]
            if lingering:
                abstain_tags_to_strip.append({"n": n, "title": title, "tags": lingering})

    # Stray inbox titles (tasks in inbox that are NOT part of the key).
    stray_inbox_titles: list[str] = []
    for title, state in states.items():
        if title not in key_titles and state.get("container_kind") == "inbox":
            stray_inbox_titles.append(title)

    # AI projects to delete: resolved cluster project names + any other non-existing projects
    # that appeared as containers.  Sort for determinism.
    ai_projects_to_delete = sorted(ai_project_names)

    # Undo IDs newest-first.
    undo_ids = [entry.get("id") for entry in recent_undo if entry.get("id")]

    shuffled_titles = _build_shuffled_titles(key)

    return {
        "tasks_out_of_inbox": tasks_out_of_inbox,
        "missing_tasks": missing_tasks,
        "stray_inbox_titles": sorted(stray_inbox_titles),
        "ai_projects_to_delete": ai_projects_to_delete,
        "abstain_tags_to_strip": abstain_tags_to_strip,
        "undo_ids_newest_first": undo_ids,
        "shuffle_order_note": "interleave clusters; see shuffled_titles",
        "shuffled_titles": shuffled_titles,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate a fixture-reset plan for test5 (dry-run by default)."
    )
    parser.add_argument("--key", metavar="PATH", help="Path to scorer key JSON")
    parser.add_argument("--apply", action="store_true", help="Execute the reset (restricted to Test user)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON plan")
    args = parser.parse_args(argv)

    if args.apply:
        import getpass
        user = getpass.getuser()
        if user != "Test":
            print(
                f"ERROR: --apply refused for user {user!r}. "
                "Only the 'Test' user may apply fixture resets.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Even for Test user: apply not yet implemented.
        print(
            "apply not implemented in dry-run scope; "
            "execute the printed plan manually per MISSION-CONTROL fixture procedure.",
            file=sys.stderr,
        )
        sys.exit(0)

    # Dry-run: collect live state and print plan.
    from safe_things_mcp.eval.scorer import collect_live_states  # noqa: PLC0415

    key = load_key(args.key)
    states = collect_live_states(key)

    # recent_undo: import live undo log.
    try:
        from safe_things_mcp.state import undo_log  # noqa: PLC0415
        recent_undo = undo_log.recent(limit=200)
    except Exception:
        recent_undo = []

    plan = plan_reset(key, states, recent_undo)

    indent = 2 if args.pretty else None
    output = json.dumps(plan, indent=indent, ensure_ascii=False)
    sys.stdout.write(output)
    sys.stdout.write("\n")

"""Programmatic scorer for test5 eval runs.

Core (load_key, score, TaskState) is decoupled from live Things and is unit-testable
with synthetic data.  The live adapter (collect_live_states) and CLI (main) are in
this same file but defer the things_repo import until the function body so that the
module imports cleanly even if Things 3 is not running.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------

def _default_key_path() -> Path:
    """Resolve sort-eval/harness/test5-key.json relative to this file (src/things_mcp/eval/)."""
    return Path(__file__).parent.parent.parent.parent / "sort-eval" / "harness" / "test5-key.json"


def load_key(path: str | Path | None = None) -> dict:
    """Load and return the canonical scorer key as a dict."""
    p = Path(path) if path is not None else _default_key_path()
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# TaskState
# ---------------------------------------------------------------------------

class TaskState(TypedDict, total=False):
    title: str
    container_kind: str   # "inbox" | "project" | "area" | "missing"
    container_name: str | None
    area: str | None
    tags: list[str]
    notes: str | None
    deadline: str | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm(s: str | None) -> str:
    """Lowercase + strip for case-insensitive comparisons."""
    return (s or "").strip().lower()


def _build_task_index(key: dict) -> dict[int, dict]:
    """Return {n: task_entry} for all tasks in the key."""
    return {t["n"]: t for t in key["tasks"]}


def _find_state(states: dict[str, TaskState], title: str) -> TaskState | None:
    """Case-insensitive, whitespace-stripped title lookup."""
    needle = _norm(title)
    for k, v in states.items():
        if _norm(k) == needle:
            return v
    return None


def _resolve_clusters(key: dict, states: dict[str, TaskState]) -> dict[str, dict]:
    """Determine per-cluster resolved project name and cohesion.

    Returns {cluster_name: {"project": str|None, "cohesion": bool}}.
    """
    task_index = _build_task_index(key)
    result = {}
    for cname, cdef in key["clusters"].items():
        member_ns = cdef["members"]
        project_counts: Counter[str] = Counter()
        for n in member_ns:
            title = task_index[n]["title"]
            state = _find_state(states, title)
            if state and state.get("container_kind") == "project":
                pname = state.get("container_name") or ""
                if pname:
                    project_counts[pname] += 1
        if not project_counts:
            result[cname] = {"project": None, "cohesion": False}
        else:
            best_project, best_count = project_counts.most_common(1)[0]
            cohesion = best_count == len(member_ns)
            result[cname] = {"project": best_project, "cohesion": cohesion}
    return result


def _clusters_merged(cluster_info: dict[str, dict], key: dict, states: dict[str, TaskState]) -> bool:
    """True if the two clusters resolved to the same project, or either project
    also contains ≥1 member of the other cluster."""
    task_index = _build_task_index(key)
    names = list(cluster_info.keys())
    if len(names) < 2:
        return False
    c0, c1 = names[0], names[1]
    p0 = cluster_info[c0]["project"]
    p1 = cluster_info[c1]["project"]

    # Same project name (case-insensitive) → merged.
    if p0 and p1 and _norm(p0) == _norm(p1):
        return True

    # Check cross-contamination: any member of c0 in c1's project, or vice versa.
    def _member_in(cluster_name: str, project_name: str | None) -> bool:
        if not project_name:
            return False
        members = key["clusters"][cluster_name]["members"]
        for n in members:
            title = task_index[n]["title"]
            state = _find_state(states, title)
            if (
                state
                and state.get("container_kind") == "project"
                and _norm(state.get("container_name")) == _norm(project_name)
            ):
                return True
        return False

    if p0 and _member_in(c1, p0):
        return True
    return bool(p1 and _member_in(c0, p1))


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def _verdict_route_existing(task: dict, state: TaskState) -> tuple[str, bool, str]:
    """Returns (verdict, confident_wrong, note)."""
    kind = state.get("container_kind")
    actual = _norm(state.get("container_name"))
    expected = _norm(task["project"])

    if kind == "missing":
        return "under_commit", False, "task not found"
    if kind == "inbox":
        return "under_commit", False, "left in inbox"
    if kind == "project":
        if actual == expected:
            return "correct", False, ""
        return "confident_wrong", True, f"wrong project: {state.get('container_name')!r} (expected {task['project']!r})"
    if kind == "area":
        return "confident_wrong", True, f"placed in area {state.get('container_name')!r} instead of project"
    return "under_commit", False, f"unexpected container_kind={kind!r}"


def _verdict_route_new(task: dict, state: TaskState, cluster_info: dict[str, dict]) -> tuple[str, bool, str]:
    """Returns (verdict, confident_wrong, note)."""
    kind = state.get("container_kind")
    cname = task["cluster"]
    other_clusters = [c for c in cluster_info if c != cname]
    own_project = cluster_info.get(cname, {}).get("project")
    other_projects = [cluster_info[c]["project"] for c in other_clusters if cluster_info[c]["project"]]

    if kind == "missing":
        return "under_commit", False, "task not found"
    if kind == "inbox":
        return "under_commit", False, "left in inbox"
    if kind == "project":
        actual = _norm(state.get("container_name"))
        if own_project and actual == _norm(own_project):
            return "correct", False, ""
        if actual in other_projects:
            return "confident_wrong", True, f"placed in other cluster's project {state.get('container_name')!r}"
        if actual in [_norm(p) for p in task.get("_existing_projects", [])]:
            return "confident_wrong", True, f"placed in existing project {state.get('container_name')!r}"
        # In any other project (existing or otherwise)
        return "confident_wrong", True, f"placed in wrong project {state.get('container_name')!r}"
    if kind == "area":
        return "confident_wrong", True, f"placed in area {state.get('container_name')!r}"
    return "under_commit", False, f"unexpected container_kind={kind!r}"


def _verdict_route_or_abstain(task: dict, state: TaskState, cluster_info: dict[str, dict]) -> tuple[str, bool, str]:
    """route_or_abstain: pass if in own cluster project OR abstained with right tag."""
    kind = state.get("container_kind")
    cname = task["cluster"]
    wrong_cname = task.get("wrong_cluster")
    abstain_tag = task.get("abstain_tag", "")
    own_project = cluster_info.get(cname, {}).get("project")
    wrong_project = cluster_info.get(wrong_cname, {}).get("project") if wrong_cname else None

    if kind == "missing":
        return "under_commit", False, "task not found"
    if kind == "inbox":
        tags = state.get("tags") or []
        if abstain_tag in tags:
            return "abstain_correct", False, "correctly abstained with tag"
        return "under_commit", False, "in inbox but missing abstain tag"
    if kind == "project":
        actual = _norm(state.get("container_name"))
        if own_project and actual == _norm(own_project):
            return "correct", False, ""
        if wrong_project and actual == _norm(wrong_project):
            return "confident_wrong", True, f"placed in wrong_cluster project {state.get('container_name')!r}"
        return "confident_wrong", True, f"placed in wrong project {state.get('container_name')!r}"
    if kind == "area":
        return "confident_wrong", True, f"placed in area {state.get('container_name')!r}"
    return "under_commit", False, f"unexpected container_kind={kind!r}"


def _verdict_abstain_strict(task: dict, state: TaskState) -> tuple[str, bool, str]:
    """abstain_strict: must be inbox with correct tag."""
    kind = state.get("container_kind")
    abstain_tag = task.get("abstain_tag", "")

    if kind == "missing":
        return "under_commit", False, "task not found"
    if kind == "inbox":
        tags = state.get("tags") or []
        if abstain_tag in tags:
            return "abstain_correct", False, "correctly abstained"
        return "under_commit", False, f"in inbox but missing tag {abstain_tag!r}"
    if kind in ("project", "area"):
        return "confident_wrong", True, f"placed in {kind} {state.get('container_name')!r} (should abstain)"
    return "under_commit", False, f"unexpected container_kind={kind!r}"


def _verdict_abstain_or_area(task: dict, state: TaskState, warnings: list[str]) -> tuple[str, bool, str]:
    """abstain_or_area: inbox (with or without tag) → pass; existing area → pass; project → needs_review."""
    kind = state.get("container_kind")
    abstain_tag = task.get("abstain_tag", "")

    if kind == "missing":
        return "under_commit", False, "task not found"
    if kind == "inbox":
        tags = state.get("tags") or []
        if abstain_tag and abstain_tag not in tags:
            note = f"in inbox but missing tag {abstain_tag!r} (bonus tag only)"
            return "abstain_correct", False, note
        return "abstain_correct", False, "correctly abstained"
    if kind == "area":
        return "area_pass", False, f"placed confidently in area {state.get('container_name')!r}"
    if kind == "project":
        msg = f"task #{task['n']} ({task['title']!r}) placed in project {state.get('container_name')!r} — needs human review (could be reasonable or wrong)"
        warnings.append(msg)
        return "needs_review", False, "placed in project; human review required"
    return "under_commit", False, f"unexpected container_kind={kind!r}"


# ---------------------------------------------------------------------------
# Public score() function
# ---------------------------------------------------------------------------

def score(key: dict, states: dict[str, TaskState]) -> dict:
    """Pure scoring function. Returns a JSON-serializable result dict."""
    task_index = _build_task_index(key)
    generic_denylist = {_norm(g) for g in key.get("generic_name_denylist", [])}
    warnings: list[str] = []

    # Resolve clusters first (needed for route_new / route_or_abstain).
    cluster_info = _resolve_clusters(key, states)

    # Inject existing_projects into tasks for _verdict_route_new reference.
    # We pass them via the key directly in _verdict_route_new by closing over existing_projects_norm.

    task_results = []
    routing_acc_correct = 0
    routing_acc_total = 0
    abstain_recall_correct = 0
    abstain_recall_total = 0
    confident_wrong_count = 0

    routing_existing_set = set(key.get("routing_existing_set", []))
    abstain_recall_set = set(key.get("abstain_recall_set", []))
    coverage_set = set(key.get("coverage_set", []))
    coverage_placed = 0
    coverage_total = len(coverage_set)

    for task in key["tasks"]:
        n = task["n"]
        title = task["title"]
        policy = task["policy"]
        state = _find_state(states, title)

        if state is None:
            # Represent missing as a sentinel state.
            state = TaskState(
                title=title,
                container_kind="missing",
                container_name=None,
                area=None,
                tags=[],
                notes=None,
                deadline=None,
            )
            warnings.append(f"Task #{n} ({title!r}) not found in live state — treated as under_commit.")

        # Determine verdict.
        verdict = "under_commit"
        confident_wrong = False
        note = ""

        if policy == "route_existing":
            verdict, confident_wrong, note = _verdict_route_existing(task, state)
            if n in routing_existing_set:
                routing_acc_total += 1
                if verdict == "correct":
                    routing_acc_correct += 1

        elif policy == "route_new":
            # Attach existing_projects to task dict for helper.
            task_with_ctx = {**task, "_existing_projects": list(key.get("existing_projects", []))}
            verdict, confident_wrong, note = _verdict_route_new(task_with_ctx, state, cluster_info)

        elif policy == "route_or_abstain":
            verdict, confident_wrong, note = _verdict_route_or_abstain(task, state, cluster_info)

        elif policy == "abstain_strict":
            verdict, confident_wrong, note = _verdict_abstain_strict(task, state)
            if n in abstain_recall_set:
                abstain_recall_total += 1
                if verdict == "abstain_correct":
                    abstain_recall_correct += 1

        elif policy == "abstain_or_area":
            verdict, confident_wrong, note = _verdict_abstain_or_area(task, state, warnings)

        if confident_wrong:
            confident_wrong_count += 1

        if n in coverage_set and state.get("container_kind") == "project":
            coverage_placed += 1

        # Build expected description for the output.
        expected = _build_expected_desc(task, cluster_info)

        task_results.append({
            "n": n,
            "title": title,
            "policy": policy,
            "expected": expected,
            "actual_container": f"{state.get('container_kind')}:{state.get('container_name') or ''}",
            "actual_tags": state.get("tags") or [],
            "verdict": verdict,
            "confident_wrong": confident_wrong,
            "note": note,
        })

    # Cluster metrics.
    carbonara_cohesion = cluster_info.get("carbonara", {}).get("cohesion", False)
    baking_cohesion = cluster_info.get("baking", {}).get("cohesion", False)
    merged = _clusters_merged(cluster_info, key, states)

    cluster_names = {
        "carbonara": cluster_info.get("carbonara", {}).get("project"),
        "baking": cluster_info.get("baking", {}).get("project"),
    }

    generic_name_warning: list[str] = []
    for cname, pname in cluster_names.items():
        if pname and _norm(pname) in generic_denylist:
            generic_name_warning.append(pname)
            warnings.append(f"Cluster {cname!r} resolved to project {pname!r} — name is in generic denylist.")

    if merged:
        warnings.append(
            f"Clusters appear merged: carbonara→{cluster_names['carbonara']!r}, "
            f"baking→{cluster_names['baking']!r}."
        )

    # Metadata check for task #26.
    task26 = task_index[26]
    state26 = _find_state(states, task26["title"])
    meta26 = False
    if state26 and state26.get("container_kind") == "project" and _norm(
        state26.get("container_name")
    ) == _norm("Apartment Move"):
        notes26 = state26.get("notes") or ""
        deadline26 = (state26.get("deadline") or "").strip()
        require_substr = task26.get("require_notes_substr", "")
        require_deadline = task26.get("require_deadline", "")
        if require_substr in notes26 and deadline26 == require_deadline:
            meta26 = True

    routing_pct = routing_acc_correct / routing_acc_total if routing_acc_total else 0.0
    abstain_pct = abstain_recall_correct / abstain_recall_total if abstain_recall_total else 0.0

    return {
        "tasks": task_results,
        "metrics": {
            "routing_acc": {
                "correct": routing_acc_correct,
                "total": routing_acc_total,
                "pct": round(routing_pct, 4),
            },
            "confident_wrong": confident_wrong_count,
            "abstain_recall": {
                "correct": abstain_recall_correct,
                "total": abstain_recall_total,
                "pct": round(abstain_pct, 4),
            },
            "carbonara_cohesion": carbonara_cohesion,
            "baking_cohesion": baking_cohesion,
            "clusters_merged": merged,
            "cluster_names": cluster_names,
            "generic_name_warning": generic_name_warning,
            "metadata_preserved_26": meta26,
            "coverage": {
                "placed": coverage_placed,
                "total": coverage_total,
                "pct": round(coverage_placed / coverage_total if coverage_total else 0.0, 4),
            },
        },
        "warnings": warnings,
    }


def _build_expected_desc(task: dict, cluster_info: dict) -> str:
    policy = task["policy"]
    if policy == "route_existing":
        return f"project:{task['project']}"
    if policy == "route_new":
        cname = task["cluster"]
        resolved = cluster_info.get(cname, {}).get("project")
        return f"cluster:{cname}({resolved or '?'})"
    if policy == "route_or_abstain":
        cname = task["cluster"]
        resolved = cluster_info.get(cname, {}).get("project")
        tag = task.get("abstain_tag", "")
        return f"cluster:{cname}({resolved or '?'}) OR inbox:{tag}"
    if policy == "abstain_strict":
        return f"inbox:{task.get('abstain_tag', '')}"
    if policy == "abstain_or_area":
        return f"inbox:{task.get('abstain_tag', '')} OR area:*"
    return "unknown"


# ---------------------------------------------------------------------------
# Live adapter
# ---------------------------------------------------------------------------

def collect_live_states(key: dict) -> dict[str, TaskState]:
    """Read current Things state and build states dict keyed by task title."""
    # Deferred import so the module loads cleanly without Things running.
    from things_mcp.services import things_repo  # noqa: PLC0415

    titles_to_find = {_norm(t["title"]): t["title"] for t in key["tasks"]}
    found: dict[str, TaskState] = {}

    # Helper to record a state entry, matching by title.
    def _record(title: str, kind: str, container_name: str | None, area: str | None,
                 tags: list, notes: str | None, deadline: str | None) -> None:
        norm_title = _norm(title)
        if norm_title in titles_to_find:
            canonical = titles_to_find[norm_title]
            found[canonical] = TaskState(
                title=canonical,
                container_kind=kind,
                container_name=container_name,
                area=area,
                tags=tags or [],
                notes=notes,
                deadline=deadline,
            )

    # Scan inbox.
    for item in things_repo.inbox():
        _record(
            item.get("title", ""),
            "inbox",
            None,
            item.get("area"),
            item.get("tags") or [],
            item.get("notes"),
            item.get("deadline") or item.get("due"),
        )

    # Scan all projects and their items.
    all_projects = things_repo.projects(include_completed=False)
    for proj in all_projects:
        proj_title = proj.get("title", "")
        proj_area = proj.get("area")
        # Fetch full project (includes items).
        full = things_repo.project(proj.get("uuid", ""))
        if full is None:
            continue
        for item in full.get("items") or []:
            if item.get("type") != "to-do":
                continue
            _record(
                item.get("title", ""),
                "project",
                proj_title,
                proj_area,
                item.get("tags") or [],
                item.get("notes"),
                item.get("deadline") or item.get("due"),
            )

    # Scan areas (items directly in an area, not in a project).
    for area in things_repo.areas(include_items=True):
        area_title = area.get("title", "")
        for item in area.get("items") or []:
            if item.get("type") != "to-do":
                continue
            _record(
                item.get("title", ""),
                "area",
                area_title,
                area_title,
                item.get("tags") or [],
                item.get("notes"),
                item.get("deadline") or item.get("due"),
            )

    # Mark missing.
    for original_title in titles_to_find.values():
        if original_title not in found:
            found[original_title] = TaskState(
                title=original_title,
                container_kind="missing",
                container_name=None,
                area=None,
                tags=[],
                notes=None,
                deadline=None,
            )

    return found


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Score a live Things state against the test5 eval key."
    )
    parser.add_argument("--key", metavar="PATH", help="Path to scorer key JSON (default: sort-eval/harness/test5-key.json)")
    parser.add_argument("--out", metavar="PATH", help="Write JSON output to this file (default: stdout)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args(argv)

    key = load_key(args.key)
    states = collect_live_states(key)
    result = score(key, states)

    indent = 2 if args.pretty else None
    output = json.dumps(result, indent=indent, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
        sys.stdout.write("\n")

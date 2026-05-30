"""Tests for Step 5B — propose_reorder_todos.

Covers:
* services/reorder.py — resolve_container, build_master_order,
  detect_native_headings_in_project
* services/things_repo additions — get_container_todo_uuids
* services/handlers/reorder_todos — make_preview, execute, undo
* tools/propose — propose_reorder_todos wrapper

All DB / Things-app / AppleScript interaction is mocked; no Things app required.

V2 acceptance gate (per CLAUDE.md):
* undo_log row written *before* AppleScript mutation
* undo round-trip restores original order
* race-window detection aborts stale confirms
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.services import reorder as reorder_mod
from things_mcp.services.handlers import reorder_todos
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def with_applescript(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", True)


@pytest.fixture
def with_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-test")


@pytest.fixture
def captured_scripts(monkeypatch):
    from things_mcp.services import applescript
    scripts: list[str] = []

    async def fake_run(script: str) -> str:
        scripts.append(script)
        return ""

    monkeypatch.setattr(applescript, "run_script", fake_run)
    return scripts


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


# ---------------------------------------------------------------------------
# Part 1: services/reorder.py — resolve_container
# ---------------------------------------------------------------------------


class TestResolveContainer:
    def test_inbox_resolves_to_list(self):
        c_type, c_id = reorder_mod.resolve_container("inbox")
        assert c_type == "list"
        assert c_id == "Inbox"

    def test_today_resolves_to_list(self):
        c_type, c_id = reorder_mod.resolve_container("today")
        assert c_type == "list"
        assert c_id == "Today"

    def test_anytime_resolves_to_list(self):
        c_type, c_id = reorder_mod.resolve_container("anytime")
        assert c_type == "list"
        assert c_id == "Anytime"

    def test_someday_resolves_to_list(self):
        c_type, c_id = reorder_mod.resolve_container("someday")
        assert c_type == "list"
        assert c_id == "Someday"

    def test_case_insensitive_list_name(self):
        c_type, c_id = reorder_mod.resolve_container("TODAY")
        assert c_type == "list"
        assert c_id == "Today"

    def test_uuid_resolves_to_project(self):
        uuid = "PROJ-UUID-123"
        c_type, c_id = reorder_mod.resolve_container(uuid)
        assert c_type == "project"
        assert c_id == uuid

    def test_mixed_case_uuid_resolves_to_project(self):
        # UUIDs that happen to contain list-name substrings don't collide
        uuid = "InboxProject-XYZ-999"
        c_type, c_id = reorder_mod.resolve_container(uuid)
        assert c_type == "project"
        assert c_id == uuid


# ---------------------------------------------------------------------------
# Part 2: services/reorder.py — build_master_order
# ---------------------------------------------------------------------------


class TestBuildMasterOrder:
    def test_full_reorder_uses_requested_order(self):
        current = ["A", "B", "C"]
        result = reorder_mod.build_master_order(current, ["C", "A", "B"])
        assert result == ["C", "A", "B"]

    def test_partial_reorder_swaps_two_at_original_positions(self):
        # current: A B C D E  (indices 0,1,2,3,4)
        # requested: [D, B] — D should come before B
        # D is at index 3, B at index 1 → sorted positions: [1, 3]
        # position 1 → D, position 3 → B
        # result: A D C B E
        current = ["A", "B", "C", "D", "E"]
        result = reorder_mod.build_master_order(current, ["D", "B"])
        assert result == ["A", "D", "C", "B", "E"]

    def test_partial_reorder_preserves_surrounding_positions(self):
        current = ["A", "B", "C", "D", "E"]
        result = reorder_mod.build_master_order(current, ["C", "A"])
        # A at 0, C at 2 → sorted positions: [0, 2]
        # position 0 → C, position 2 → A
        # result: C B A D E
        assert result == ["C", "B", "A", "D", "E"]

    def test_empty_requested_returns_current_unchanged(self):
        current = ["A", "B", "C"]
        result = reorder_mod.build_master_order(current, [])
        assert result == ["A", "B", "C"]

    def test_single_requested_keeps_order_unchanged(self):
        # Requesting a single UUID doesn't change anything relative
        current = ["A", "B", "C"]
        result = reorder_mod.build_master_order(current, ["B"])
        assert result == ["A", "B", "C"]

    def test_unknown_uuid_in_requested_raises_value_error(self):
        current = ["A", "B", "C"]
        with pytest.raises(ValueError, match="not found in current"):
            reorder_mod.build_master_order(current, ["A", "X"])

    def test_full_reorder_identical_to_current(self):
        current = ["A", "B", "C"]
        result = reorder_mod.build_master_order(current, ["A", "B", "C"])
        assert result == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Part 3: services/reorder.py — detect_native_headings_in_project
# ---------------------------------------------------------------------------


class TestDetectNativeHeadingsInProject:
    def test_list_container_returns_empty(self):
        result = reorder_mod.detect_native_headings_in_project(None)
        assert result == []

    def test_project_with_no_items_returns_empty(self):
        proj = {"uuid": "P1", "items": []}
        result = reorder_mod.detect_native_headings_in_project(proj)
        assert result == []

    def test_project_with_no_headings_returns_empty(self):
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
                {"uuid": "T2", "type": "to-do", "title": "Task 2"},
            ],
        }
        result = reorder_mod.detect_native_headings_in_project(proj)
        assert result == []

    def test_returns_native_heading_with_todo_position(self):
        # items: [todo1, heading_A, todo2, todo3]
        # heading_A has todo_position=1 (1 todo seen before it)
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
                {"uuid": "H1", "type": "heading", "title": "Phase 1"},
                {"uuid": "T2", "type": "to-do", "title": "Task 2"},
                {"uuid": "T3", "type": "to-do", "title": "Task 3"},
            ],
        }
        result = reorder_mod.detect_native_headings_in_project(proj)
        assert len(result) == 1
        assert result[0]["id"] == "H1"
        assert result[0]["name"] == "Phase 1"
        assert result[0]["todo_position"] == 1

    def test_heading_at_start_has_todo_position_zero(self):
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "H1", "type": "heading", "title": "Phase 1"},
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
            ],
        }
        result = reorder_mod.detect_native_headings_in_project(proj)
        assert result[0]["todo_position"] == 0

    def test_multiple_headings_get_correct_positions(self):
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
                {"uuid": "H1", "type": "heading", "title": "Phase 1"},
                {"uuid": "T2", "type": "to-do", "title": "Task 2"},
                {"uuid": "H2", "type": "heading", "title": "Phase 2"},
                {"uuid": "T3", "type": "to-do", "title": "Task 3"},
            ],
        }
        result = reorder_mod.detect_native_headings_in_project(proj)
        assert len(result) == 2
        assert result[0]["id"] == "H1"
        assert result[0]["todo_position"] == 1
        assert result[1]["id"] == "H2"
        assert result[1]["todo_position"] == 2


# ---------------------------------------------------------------------------
# Part 4: things_repo.get_container_todo_uuids
# ---------------------------------------------------------------------------


class TestGetContainerTodoUuids:
    def test_project_returns_todo_uuids_in_order(self, monkeypatch):
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
                {"uuid": "T2", "type": "to-do", "title": "Task 2"},
            ],
        }
        monkeypatch.setattr(things_repo, "project", lambda pid: proj)
        result = things_repo.get_container_todo_uuids("project", "P1")
        assert result == ["T1", "T2"]

    def test_project_excludes_native_heading_uuids(self, monkeypatch):
        proj = {
            "uuid": "P1",
            "items": [
                {"uuid": "T1", "type": "to-do", "title": "Task 1"},
                {"uuid": "H1", "type": "heading", "title": "Phase 1"},
                {"uuid": "T2", "type": "to-do", "title": "Task 2"},
            ],
        }
        monkeypatch.setattr(things_repo, "project", lambda pid: proj)
        result = things_repo.get_container_todo_uuids("project", "P1")
        assert result == ["T1", "T2"]
        assert "H1" not in result

    def test_unknown_project_raises_value_error(self, monkeypatch):
        monkeypatch.setattr(things_repo, "project", lambda pid: None)
        with pytest.raises(ValueError, match="not found"):
            things_repo.get_container_todo_uuids("project", "MISSING")

    def test_list_today_returns_uuids(self, monkeypatch):
        todos = [{"uuid": "T1"}, {"uuid": "T2"}]
        monkeypatch.setattr(things_repo, "today", lambda: todos)
        result = things_repo.get_container_todo_uuids("list", "Today")
        assert result == ["T1", "T2"]

    def test_list_inbox_returns_uuids(self, monkeypatch):
        todos = [{"uuid": "A1"}, {"uuid": "B1"}]
        monkeypatch.setattr(things_repo, "inbox", lambda: todos)
        result = things_repo.get_container_todo_uuids("list", "Inbox")
        assert result == ["A1", "B1"]

    def test_unknown_list_raises_value_error(self, monkeypatch):
        with pytest.raises(ValueError, match="Unknown list"):
            things_repo.get_container_todo_uuids("list", "Nonexistent")


# ---------------------------------------------------------------------------
# Part 5: Handler make_preview
# ---------------------------------------------------------------------------


class TestMakePreview:
    def test_simple_list_reorder_no_headings(self):
        payload = {
            "container_type": "list",
            "container_id": "Today",
            "master_order": ["T1", "T2", "T3"],
            "dummy_creation_plan": [],
            "original_order": ["T1", "T2", "T3"],
        }
        preview = reorder_todos.make_preview(payload)
        assert "Today" in preview
        assert "3" in preview

    def test_project_reorder_with_native_headings_warns(self):
        payload = {
            "container_type": "project",
            "container_id": "PROJ-1",
            "master_order": ["T1", "T2", "T3"],
            "dummy_creation_plan": [
                {"name": "Phase 1", "todo_position": 1},
            ],
            "original_order": ["T1", "T2", "T3"],
        }
        preview = reorder_todos.make_preview(payload)
        assert "Phase 1" in preview
        assert "native heading" in preview.lower() or "dummy" in preview.lower()

    def test_preview_mentions_irreversibility_of_undo(self):
        payload = {
            "container_type": "project",
            "container_id": "PROJ-1",
            "master_order": ["T1", "T2"],
            "dummy_creation_plan": [{"name": "H1", "todo_position": 1}],
            "original_order": ["T1", "T2"],
        }
        preview = reorder_todos.make_preview(payload)
        # Undo cannot reinstate native heading positions
        assert "native" in preview.lower() or "undo" in preview.lower()


# ---------------------------------------------------------------------------
# Part 6: Handler execute
# ---------------------------------------------------------------------------


class TestExecute:
    @pytest.mark.asyncio
    async def test_raises_if_applescript_disabled(self, monkeypatch):
        monkeypatch.setattr(config, "ALLOW_APPLESCRIPT", False)
        with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
            await reorder_todos.execute(
                {
                    "container_type": "list",
                    "container_id": "Today",
                    "master_order": ["T1"],
                    "dummy_creation_plan": [],
                    "original_order": ["T1"],
                }
            )

    @pytest.mark.asyncio
    async def test_undo_log_written_before_applescript(
        self, monkeypatch, with_applescript, fast_polling
    ):
        """undo_log row must exist at the moment osascript is called."""
        from things_mcp.services import applescript

        script_call_count = 0
        undo_log_count_at_script_call = 0

        async def fake_run(script: str) -> str:
            nonlocal script_call_count, undo_log_count_at_script_call
            script_call_count += 1
            undo_log_count_at_script_call = len(undo_log.list())
            return ""

        monkeypatch.setattr(applescript, "run_script", fake_run)
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
        )

        await reorder_todos.execute(
            {
                "container_type": "list",
                "container_id": "Today",
                "master_order": ["T2", "T1"],
                "dummy_creation_plan": [],
                "original_order": ["T1", "T2"],
            }
        )

        assert script_call_count == 1
        assert undo_log_count_at_script_call >= 1

    @pytest.mark.asyncio
    async def test_applescript_called_with_reorder_command_for_list(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
        )

        await reorder_todos.execute(
            {
                "container_type": "list",
                "container_id": "Today",
                "master_order": ["T2", "T1"],
                "dummy_creation_plan": [],
                "original_order": ["T1", "T2"],
            }
        )

        assert len(captured_scripts) == 1
        script = captured_scripts[0]
        assert "reorder" in script.lower()
        assert "Today" in script
        assert "T2" in script
        assert "T1" in script

    @pytest.mark.asyncio
    async def test_applescript_called_with_project_command(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
        )

        await reorder_todos.execute(
            {
                "container_type": "project",
                "container_id": "PROJ-ABC",
                "master_order": ["T2", "T1"],
                "dummy_creation_plan": [],
                "original_order": ["T1", "T2"],
            }
        )

        assert len(captured_scripts) == 1
        script = captured_scripts[0]
        assert "PROJ-ABC" in script

    @pytest.mark.asyncio
    async def test_race_window_detection_aborts_when_extra_uuid_appears(
        self, with_applescript, monkeypatch, fast_polling
    ):
        call_count = 0

        def fake_get_uuids(ct, cid):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: returns original set
                return ["T1", "T2"]
            else:
                # Second call (race-window re-read): extra UUID appeared
                return ["T1", "T2", "T3-NEW"]

        monkeypatch.setattr(things_repo, "get_container_todo_uuids", fake_get_uuids)

        with pytest.raises(RuntimeError, match="stale"):
            await reorder_todos.execute(
                {
                    "container_type": "list",
                    "container_id": "Today",
                    "master_order": ["T2", "T1"],
                    "dummy_creation_plan": [],
                    "original_order": ["T1", "T2"],
                }
            )

    @pytest.mark.asyncio
    async def test_returns_result_with_undo_id(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
        )

        result = await reorder_todos.execute(
            {
                "container_type": "list",
                "container_id": "Today",
                "master_order": ["T2", "T1"],
                "dummy_creation_plan": [],
                "original_order": ["T1", "T2"],
            }
        )

        assert "undo_id" in result
        assert result["action_kind"] == reorder_todos.KIND

    @pytest.mark.asyncio
    async def test_no_script_injection_via_container_id(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        """Container IDs with quotes must be escaped."""
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1"]
        )

        with pytest.raises((ValueError, RuntimeError)):
            await reorder_todos.execute(
                {
                    "container_type": "list",
                    "container_id": 'Today" evil',
                    "master_order": ["T1"],
                    "dummy_creation_plan": [],
                    "original_order": ["T1"],
                }
            )


# ---------------------------------------------------------------------------
# Part 7: Handler execute — native heading dummy creation
# ---------------------------------------------------------------------------


class TestExecuteWithNativeHeadings:
    @pytest.mark.asyncio
    async def test_creates_dummy_for_each_native_heading(
        self,
        with_applescript,
        with_auth,
        captured_scripts,
        captured_launches,
        monkeypatch,
        fast_polling,
    ):
        """Each dummy_creation_plan entry → one URL-scheme launch to create dummy."""
        dummy_uuid = "DUMMY-1"

        def fake_find(title, after):
            if "__Phase 1__" in title or "Phase 1" in title:
                return {"uuid": dummy_uuid, "title": title, "status": "incomplete"}
            return None

        monkeypatch.setattr(things_repo, "find_recent_by_title", fake_find)
        monkeypatch.setattr(
            things_repo,
            "get_container_todo_uuids",
            lambda ct, cid: ["T1", "T2"],
        )

        await reorder_todos.execute(
            {
                "container_type": "project",
                "container_id": "PROJ-1",
                "master_order": ["T1", "T2"],
                "dummy_creation_plan": [{"name": "Phase 1", "todo_position": 1}],
                "original_order": ["T1", "T2"],
                "created_dummy_uuids": [],
            }
        )

        # One URL-scheme launch for the dummy, one AppleScript reorder
        assert len(captured_launches) >= 1
        assert any("PROJ-1" in url for url in captured_launches)

    @pytest.mark.asyncio
    async def test_dummy_uuid_included_in_reorder_command(
        self,
        with_applescript,
        with_auth,
        captured_scripts,
        captured_launches,
        monkeypatch,
        fast_polling,
    ):
        dummy_uuid = "DUMMY-UUID-1"

        def fake_find(title, after):
            return {"uuid": dummy_uuid, "title": title, "status": "incomplete"}

        monkeypatch.setattr(things_repo, "find_recent_by_title", fake_find)
        monkeypatch.setattr(
            things_repo,
            "get_container_todo_uuids",
            lambda ct, cid: ["T1", "T2"],
        )

        await reorder_todos.execute(
            {
                "container_type": "project",
                "container_id": "PROJ-1",
                "master_order": ["T1", "T2"],
                "dummy_creation_plan": [{"name": "Phase 1", "todo_position": 1}],
                "original_order": ["T1", "T2"],
                "created_dummy_uuids": [],
            }
        )

        script = captured_scripts[0]
        assert dummy_uuid in script


# ---------------------------------------------------------------------------
# Part 8: Handler undo
# ---------------------------------------------------------------------------


class TestUndo:
    @pytest.mark.asyncio
    async def test_undo_restores_original_order_via_applescript(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T2", "T1"]
        )

        entry_id = undo_log.record(
            action_kind=reorder_todos.KIND,
            target_uuid=None,
            before_state={
                "container_type": "list",
                "container_id": "Today",
                "original_order": ["T1", "T2"],
                "created_dummy_uuids": [],
            },
            after_state=None,
        )
        entry = undo_log.get(entry_id)

        await reorder_todos.undo(entry)

        assert len(captured_scripts) == 1
        script = captured_scripts[0]
        assert "T1" in script
        assert "T2" in script

    @pytest.mark.asyncio
    async def test_undo_deletes_undo_log_row(
        self, with_applescript, captured_scripts, monkeypatch, fast_polling
    ):
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T2", "T1"]
        )

        entry_id = undo_log.record(
            action_kind=reorder_todos.KIND,
            target_uuid=None,
            before_state={
                "container_type": "list",
                "container_id": "Today",
                "original_order": ["T1", "T2"],
                "created_dummy_uuids": [],
            },
            after_state=None,
        )
        entry = undo_log.get(entry_id)
        await reorder_todos.undo(entry)

        assert undo_log.get(entry_id) is None

    @pytest.mark.asyncio
    async def test_undo_soft_deletes_created_dummies(
        self, with_applescript, with_auth, captured_scripts, captured_launches,
        monkeypatch, fast_polling
    ):
        """Dummies created during execute must be soft-deleted during undo."""
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T2", "T1"]
        )

        entry_id = undo_log.record(
            action_kind=reorder_todos.KIND,
            target_uuid=None,
            before_state={
                "container_type": "project",
                "container_id": "PROJ-1",
                "original_order": ["T1", "T2"],
                "created_dummy_uuids": ["DUMMY-1", "DUMMY-2"],
            },
            after_state=None,
        )
        entry = undo_log.get(entry_id)
        await reorder_todos.undo(entry)

        # Two URL launches for soft-deleting dummies
        cancel_launches = [u for u in captured_launches if "DUMMY" in u]
        assert len(cancel_launches) == 2


# ---------------------------------------------------------------------------
# Part 9: propose_reorder_todos wrapper
# ---------------------------------------------------------------------------


class TestProposeReorderTodos:
    @pytest.mark.asyncio
    async def test_returns_action_id_and_preview(self, monkeypatch, fast_polling):
        monkeypatch.setattr(config, "AUTO_CONFIRM", False)
        _patch_propose_deps(monkeypatch)

        from things_mcp.tools.propose import propose_reorder_todos

        result = await propose_reorder_todos(container="today", new_order=["T2", "T1"])

        assert "action_id" in result
        assert "preview" in result
        assert result["auto_confirmed"] is False

    @pytest.mark.asyncio
    async def test_auto_confirms_when_flag_set(
        self, monkeypatch, with_applescript, fast_polling
    ):
        monkeypatch.setattr(config, "AUTO_CONFIRM", True)
        _patch_propose_deps(monkeypatch)

        from things_mcp.services import applescript

        async def fake_run(s):
            return ""

        monkeypatch.setattr(applescript, "run_script", fake_run)

        from things_mcp.tools.propose import propose_reorder_todos

        result = await propose_reorder_todos(container="today", new_order=["T2", "T1"])
        assert result["auto_confirmed"] is True

    def test_not_in_never_bypass_kinds(self):
        assert reorder_todos.KIND not in config.NEVER_BYPASS_KINDS

    @pytest.mark.asyncio
    async def test_rejects_unknown_uuid_in_new_order(self, monkeypatch, fast_polling):
        monkeypatch.setattr(config, "AUTO_CONFIRM", False)
        monkeypatch.setattr(
            things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
        )

        from things_mcp.tools.propose import propose_reorder_todos

        with pytest.raises(ValueError, match="not found in current"):
            await propose_reorder_todos(container="today", new_order=["T1", "BOGUS"])

    @pytest.mark.asyncio
    async def test_empty_new_order_raises(self, monkeypatch, fast_polling):
        monkeypatch.setattr(config, "AUTO_CONFIRM", False)
        _patch_propose_deps(monkeypatch)

        from things_mcp.tools.propose import propose_reorder_todos

        with pytest.raises(ValueError):
            await propose_reorder_todos(container="today", new_order=[])


def _patch_propose_deps(monkeypatch):
    """Minimal mocks so propose_reorder_todos can run without Things DB."""
    monkeypatch.setattr(
        things_repo, "get_container_todo_uuids", lambda ct, cid: ["T1", "T2"]
    )
    monkeypatch.setattr(
        things_repo, "project", lambda pid: {"uuid": pid, "title": "Test Project"}
    )

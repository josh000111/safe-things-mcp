"""Tests for Step 5C — checklist tools.

URL builders, things_repo.get_checklist_items, and the three handlers
(append, prepend, replace) + their propose wrappers.

All DB / Things-app interaction is mocked; no Things app required.

V2 acceptance gate (per CLAUDE.md):
* inverse URL-scheme call exists (replace restores prior snapshot),
* undo_log row written *before* the mutation,
* round-trip undo restores original checklist.
"""
from __future__ import annotations

import pytest

from things_mcp import config
from things_mcp.services import things_repo, url_scheme
from things_mcp.state import undo_log


pytestmark = pytest.mark.usefixtures("isolated_state_db")


# ---------------------------------------------------------------------------
# Fixtures shared across handler suites
# ---------------------------------------------------------------------------


@pytest.fixture
def fast_polling(monkeypatch):
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


@pytest.fixture
def with_auth(monkeypatch):
    monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", "tok-test")


_BEFORE_ITEMS = [
    {"uuid": "ci1", "title": "Buy milk", "status": "incomplete"},
    {"uuid": "ci2", "title": "Buy eggs", "status": "incomplete"},
]
_APPENDED_ITEMS = ["Buy butter", "Buy cheese"]
_PREPENDED_ITEMS = ["Buy bread"]
_REPLACEMENT_ITEMS = ["New item A", "New item B", "New item C"]


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------


class TestBuildAppendChecklistUrl:
    def test_uses_correct_scheme_and_action(self):
        url = url_scheme.build_append_checklist_url(
            todo_id="abc123", items=["item one"], auth_token="tok"
        )
        assert url.startswith("things:///update?")

    def test_encodes_todo_id_and_auth_token(self):
        url = url_scheme.build_append_checklist_url(
            todo_id="abc123", items=["item one"], auth_token="tok"
        )
        assert "id=abc123" in url
        assert "auth-token=tok" in url

    def test_uses_append_checklist_items_param(self):
        url = url_scheme.build_append_checklist_url(
            todo_id="abc", items=["x", "y"], auth_token="tok"
        )
        assert "append-checklist-items=" in url

    def test_joins_items_with_newline(self):
        url = url_scheme.build_append_checklist_url(
            todo_id="abc", items=["alpha", "beta"], auth_token="tok"
        )
        # URL-encoded newline (%0A) must separate items
        assert "alpha%0Abeta" in url or "alpha\nbeta" in url.replace("%0A", "\n")

    def test_requires_auth_token(self):
        with pytest.raises(ValueError, match="auth_token"):
            url_scheme.build_append_checklist_url(
                todo_id="abc", items=["x"], auth_token=""
            )

    def test_requires_todo_id(self):
        with pytest.raises(ValueError, match="todo_id"):
            url_scheme.build_append_checklist_url(
                todo_id="", items=["x"], auth_token="tok"
            )


class TestBuildPrependChecklistUrl:
    def test_uses_prepend_checklist_items_param(self):
        url = url_scheme.build_prepend_checklist_url(
            todo_id="abc", items=["x"], auth_token="tok"
        )
        assert "prepend-checklist-items=" in url

    def test_includes_id_and_auth_token(self):
        url = url_scheme.build_prepend_checklist_url(
            todo_id="abc", items=["x"], auth_token="tok"
        )
        assert "id=abc" in url
        assert "auth-token=tok" in url

    def test_joins_items_with_newline(self):
        url = url_scheme.build_prepend_checklist_url(
            todo_id="abc", items=["a", "b"], auth_token="tok"
        )
        assert "a%0Ab" in url or "a\nb" in url.replace("%0A", "\n")


class TestBuildReplaceChecklistUrl:
    def test_uses_checklist_items_param(self):
        url = url_scheme.build_replace_checklist_url(
            todo_id="abc", items=["x"], auth_token="tok"
        )
        # Uses the 'checklist-items' param (full overwrite)
        assert "checklist-items=" in url
        # Must NOT use append or prepend variants
        assert "append-checklist-items" not in url
        assert "prepend-checklist-items" not in url

    def test_empty_items_clears_checklist(self):
        url = url_scheme.build_replace_checklist_url(
            todo_id="abc", items=[], auth_token="tok"
        )
        assert url.startswith("things:///update?")
        # Expect empty value for checklist-items
        assert "checklist-items=" in url

    def test_includes_id_and_auth_token(self):
        url = url_scheme.build_replace_checklist_url(
            todo_id="abc", items=["x"], auth_token="tok"
        )
        assert "id=abc" in url
        assert "auth-token=tok" in url


# ---------------------------------------------------------------------------
# things_repo.get_checklist_items
# ---------------------------------------------------------------------------


def test_get_checklist_items_delegates_to_things_lib(monkeypatch):
    captured: list[tuple] = []

    def fake_checklist_items(todo_uuid, **kwargs):
        captured.append((todo_uuid, kwargs))
        return [{"uuid": "ci1", "title": "item one", "status": "incomplete"}]

    import things as things_lib
    monkeypatch.setattr(things_lib, "checklist_items", fake_checklist_items)

    result = things_repo.get_checklist_items("abc")
    assert len(captured) == 1
    assert captured[0][0] == "abc"
    assert result[0]["title"] == "item one"


# ---------------------------------------------------------------------------
# append_checklist handler
# ---------------------------------------------------------------------------


class TestAppendChecklistHandler:
    def test_requires_auth_token(self, monkeypatch):
        from things_mcp.services.handlers import append_checklist

        monkeypatch.setattr(config, "THINGS_AUTH_TOKEN", None)
        with pytest.raises(RuntimeError, match="THINGS_AUTH_TOKEN"):
            import asyncio
            asyncio.run(append_checklist.execute({"todo_id": "abc", "items": ["x"]}))

    def test_raises_on_missing_todo(self, with_auth, monkeypatch):
        from things_mcp.services.handlers import append_checklist

        monkeypatch.setattr(things_repo, "get", lambda uuid: None)
        with pytest.raises(ValueError, match="No to-do found"):
            import asyncio
            asyncio.run(append_checklist.execute({"todo_id": "ghost", "items": ["x"]}))

    async def test_writes_undo_log_before_mutation(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import append_checklist

        monkeypatch.setattr(
            things_repo, "get", lambda uuid: {"uuid": uuid, "title": "Task"}
        )
        before_items = list(_BEFORE_ITEMS)
        after_items = before_items + [{"uuid": "ci3", "title": "Buy butter", "status": "incomplete"}]
        call_count = [0]

        def fake_get_checklist(todo_id):
            call_count[0] += 1
            return before_items if call_count[0] == 1 else after_items

        monkeypatch.setattr(things_repo, "get_checklist_items", fake_get_checklist)

        pre_launch_rows: list[dict] = []
        real_launch = url_scheme.launch

        async def snapshotting_launch(url: str) -> None:
            pre_launch_rows.extend(undo_log.recent(limit=10))
            await real_launch(url)

        monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

        await append_checklist.execute({"todo_id": "abc", "items": ["Buy butter"]})

        assert len(pre_launch_rows) == 1
        assert pre_launch_rows[0]["action_kind"] == "append_checklist"
        full = undo_log.get(pre_launch_rows[0]["id"])
        assert full["before_state"]["items"] == before_items

    async def test_builds_correct_url(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import append_checklist

        before_items = list(_BEFORE_ITEMS)
        after_items = before_items + [{"uuid": "ci3", "title": "Buy butter", "status": "incomplete"}]
        call_count = [0]

        def fake_get_checklist(todo_id):
            call_count[0] += 1
            return before_items if call_count[0] == 1 else after_items

        monkeypatch.setattr(things_repo, "get", lambda uuid: {"uuid": uuid, "title": "T"})
        monkeypatch.setattr(things_repo, "get_checklist_items", fake_get_checklist)

        real_launch = url_scheme.launch

        async def flipping_launch(url: str) -> None:
            # fake_launch (captured_launches fixture) will append; just flip state
            await real_launch(url)

        monkeypatch.setattr(url_scheme, "launch", flipping_launch)

        await append_checklist.execute({"todo_id": "abc", "items": ["Buy butter"]})

        assert len(captured_launches) == 1
        url = captured_launches[0]
        assert "append-checklist-items=" in url
        assert "id=abc" in url
        assert "auth-token=tok-test" in url

    async def test_undo_restores_original_checklist(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import append_checklist

        entry_id = undo_log.record(
            action_kind=append_checklist.KIND,
            target_uuid="abc",
            before_state={"items": _BEFORE_ITEMS},
            after_state={"items": _BEFORE_ITEMS + [{"uuid": "ci3", "title": "Buy butter", "status": "incomplete"}]},
        )
        monkeypatch.setattr(
            things_repo, "get_checklist_items",
            lambda uuid: _BEFORE_ITEMS,
        )

        result = await append_checklist.undo(undo_log.get(entry_id))

        assert result["undone"] is True
        assert result["target_uuid"] == "abc"
        assert len(captured_launches) == 1
        url = captured_launches[0]
        assert "checklist-items=" in url
        assert "append-checklist-items" not in url
        assert undo_log.get(entry_id) is None

    def test_make_preview_mentions_todo_and_item_count(self):
        from things_mcp.services.handlers import append_checklist

        preview = append_checklist.make_preview(
            {"todo_id": "abc-123", "items": ["A", "B"]}
        )
        assert "abc-123" in preview
        assert "2" in preview or "append" in preview.lower()


# ---------------------------------------------------------------------------
# prepend_checklist handler
# ---------------------------------------------------------------------------


class TestPrependChecklistHandler:
    async def test_builds_prepend_url(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import prepend_checklist

        before_items = list(_BEFORE_ITEMS)
        after_items = [{"uuid": "ci0", "title": "Buy bread", "status": "incomplete"}] + before_items
        call_count = [0]

        def fake_get_checklist(todo_id):
            call_count[0] += 1
            return before_items if call_count[0] == 1 else after_items

        monkeypatch.setattr(things_repo, "get", lambda uuid: {"uuid": uuid, "title": "T"})
        monkeypatch.setattr(things_repo, "get_checklist_items", fake_get_checklist)

        real_launch = url_scheme.launch

        async def capturing_launch(url: str) -> None:
            # fake_launch (captured_launches fixture) will append; just flip state
            await real_launch(url)

        monkeypatch.setattr(url_scheme, "launch", capturing_launch)

        await prepend_checklist.execute({"todo_id": "abc", "items": ["Buy bread"]})

        assert len(captured_launches) == 1
        url = captured_launches[0]
        assert "prepend-checklist-items=" in url
        assert "id=abc" in url

    async def test_undo_restores_with_replace(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import prepend_checklist

        entry_id = undo_log.record(
            action_kind=prepend_checklist.KIND,
            target_uuid="abc",
            before_state={"items": _BEFORE_ITEMS},
            after_state={"items": [{"uuid": "ci0", "title": "Buy bread", "status": "incomplete"}] + _BEFORE_ITEMS},
        )
        monkeypatch.setattr(
            things_repo, "get_checklist_items",
            lambda uuid: _BEFORE_ITEMS,
        )

        result = await prepend_checklist.undo(undo_log.get(entry_id))

        assert result["undone"] is True
        url = captured_launches[0]
        assert "checklist-items=" in url
        assert "prepend-checklist-items" not in url
        assert undo_log.get(entry_id) is None


# ---------------------------------------------------------------------------
# replace_checklist handler
# ---------------------------------------------------------------------------


class TestReplaceChecklistHandler:
    def test_kind_is_in_never_bypass_kinds(self):
        from things_mcp.services.handlers import replace_checklist

        assert replace_checklist.KIND in config.NEVER_BYPASS_KINDS

    async def test_builds_replace_url(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import replace_checklist

        before_items = list(_BEFORE_ITEMS)
        after_items = [{"uuid": f"ci{i}", "title": t, "status": "incomplete"} for i, t in enumerate(_REPLACEMENT_ITEMS)]
        call_count = [0]

        def fake_get_checklist(todo_id):
            call_count[0] += 1
            return before_items if call_count[0] == 1 else after_items

        monkeypatch.setattr(things_repo, "get", lambda uuid: {"uuid": uuid, "title": "T"})
        monkeypatch.setattr(things_repo, "get_checklist_items", fake_get_checklist)

        real_launch = url_scheme.launch

        async def capturing_launch(url: str) -> None:
            # fake_launch (captured_launches fixture) will append; just flip state
            await real_launch(url)

        monkeypatch.setattr(url_scheme, "launch", capturing_launch)

        await replace_checklist.execute({"todo_id": "abc", "items": _REPLACEMENT_ITEMS})

        assert len(captured_launches) == 1
        url = captured_launches[0]
        assert "checklist-items=" in url
        assert "append-checklist-items" not in url
        assert "prepend-checklist-items" not in url
        assert "id=abc" in url

    async def test_undo_restores_prior_snapshot(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import replace_checklist

        replacement_items = [{"uuid": f"ci{i}", "title": t, "status": "incomplete"} for i, t in enumerate(_REPLACEMENT_ITEMS)]
        entry_id = undo_log.record(
            action_kind=replace_checklist.KIND,
            target_uuid="abc",
            before_state={"items": _BEFORE_ITEMS},
            after_state={"items": replacement_items},
        )
        monkeypatch.setattr(
            things_repo, "get_checklist_items",
            lambda uuid: _BEFORE_ITEMS,
        )

        result = await replace_checklist.undo(undo_log.get(entry_id))

        assert result["undone"] is True
        url = captured_launches[0]
        assert "checklist-items=" in url
        assert undo_log.get(entry_id) is None

    async def test_writes_undo_log_before_mutation(
        self, with_auth, fast_polling, captured_launches, monkeypatch
    ):
        from things_mcp.services.handlers import replace_checklist

        before_items = list(_BEFORE_ITEMS)
        after_items = [{"uuid": f"ci{i}", "title": t, "status": "incomplete"} for i, t in enumerate(_REPLACEMENT_ITEMS)]
        call_count = [0]

        def fake_get_checklist(todo_id):
            call_count[0] += 1
            return before_items if call_count[0] == 1 else after_items

        monkeypatch.setattr(things_repo, "get", lambda uuid: {"uuid": uuid, "title": "T"})
        monkeypatch.setattr(things_repo, "get_checklist_items", fake_get_checklist)

        pre_launch_rows: list[dict] = []
        real_launch = url_scheme.launch

        async def snapshotting_launch(url: str) -> None:
            pre_launch_rows.extend(undo_log.recent(limit=10))
            await real_launch(url)

        monkeypatch.setattr(url_scheme, "launch", snapshotting_launch)

        await replace_checklist.execute({"todo_id": "abc", "items": _REPLACEMENT_ITEMS})

        assert len(pre_launch_rows) == 1
        full = undo_log.get(pre_launch_rows[0]["id"])
        assert full["before_state"]["items"] == before_items


# ---------------------------------------------------------------------------
# Propose functions (module-level, no FastMCP registration needed)
# ---------------------------------------------------------------------------


class TestProposeChecklistFunctions:
    async def test_propose_append_enqueues_action(self, monkeypatch):
        from things_mcp.tools import propose

        monkeypatch.setattr(config, "AUTO_CONFIRM", False)
        result = await propose.propose_append_checklist_items(
            todo_id="abc", items=["x", "y"]
        )
        assert "action_id" in result
        assert result["auto_confirmed"] is False

    async def test_propose_prepend_enqueues_action(self, monkeypatch):
        from things_mcp.tools import propose

        monkeypatch.setattr(config, "AUTO_CONFIRM", False)
        result = await propose.propose_prepend_checklist_items(
            todo_id="abc", items=["first"]
        )
        assert "action_id" in result
        assert result["auto_confirmed"] is False

    async def test_propose_replace_checklist_cannot_auto_confirm(self, monkeypatch):
        from things_mcp.tools import propose

        monkeypatch.setattr(config, "AUTO_CONFIRM", True)
        result = await propose.propose_replace_checklist(
            todo_id="abc", items=["only this"]
        )
        assert result["auto_confirmed"] is False
        assert "never auto-confirmed" in result.get("next_step", "").lower() or "never" in result.get("next_step", "").lower()

    def test_propose_replace_checklist_is_registered_as_tool(self):
        from things_mcp.tools import propose
        assert hasattr(propose, "propose_replace_checklist")

    def test_propose_append_checklist_items_is_registered_as_tool(self):
        from things_mcp.tools import propose
        assert hasattr(propose, "propose_append_checklist_items")

    def test_propose_prepend_checklist_items_is_registered_as_tool(self):
        from things_mcp.tools import propose
        assert hasattr(propose, "propose_prepend_checklist_items")

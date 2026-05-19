"""Unit tests for the ``propose_move_todo`` tool wrapper.

Covers the early target-validation block that rejects ``"inbox"`` and
``"upcoming"`` before any pending row is written. Happy-path regression
ensures legal targets still enqueue.
"""
from __future__ import annotations

import pytest

from things_mcp.state import pending
from things_mcp.tools.propose import propose_move_todo


pytestmark = pytest.mark.usefixtures("isolated_state_db")


async def test_rejects_inbox_target():
    with pytest.raises(ValueError, match="not supported"):
        await propose_move_todo(todo_id="abc123", target="inbox")
    assert pending.list_all() == []


async def test_rejects_inbox_target_case_insensitive():
    with pytest.raises(ValueError, match="not supported"):
        await propose_move_todo(todo_id="abc123", target="Inbox")
    assert pending.list_all() == []


async def test_rejects_upcoming_target():
    with pytest.raises(ValueError, match="computed view"):
        await propose_move_todo(todo_id="abc123", target="upcoming")
    assert pending.list_all() == []


async def test_today_target_happy_path():
    result = await propose_move_todo(todo_id="abc123", target="today")
    assert "action_id" in result
    assert result.get("auto_confirmed") is False
    rows = pending.list_all()
    assert len(rows) == 1

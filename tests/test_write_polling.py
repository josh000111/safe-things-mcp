"""Tests for the write-path polling loop, in isolation from Things.

The MCP tool wrapper (``register``) is a thin shell around the polling
helper, so we exercise ``_poll_for_new_todo`` directly. Speed is bought
back by overriding the poll timeout / interval at runtime through the
config module before importing the helper.
"""
from __future__ import annotations

import asyncio

import pytest

from things_mcp import config
from things_mcp.services import things_repo
from things_mcp.tools import write as write_tool


@pytest.mark.asyncio
async def test_poll_returns_match_when_repo_has_it(monkeypatch):
    monkeypatch.setattr(
        things_repo,
        "find_recent_inbox_by_title",
        lambda title, created_after: {"uuid": "u1", "title": title, "created": created_after},
    )
    result = await write_tool._poll_for_new_todo("Hello", "2026-05-18 00:00:00")
    assert result["uuid"] == "u1"


@pytest.mark.asyncio
async def test_poll_eventually_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_find(title, created_after):
        calls["n"] += 1
        if calls["n"] < 3:
            return None
        return {"uuid": "u2", "title": title, "created": created_after}

    monkeypatch.setattr(things_repo, "find_recent_inbox_by_title", fake_find)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(write_tool, "WRITE_POLL_INTERVAL_SECONDS", 0.01)

    result = await write_tool._poll_for_new_todo("Hello", "2026-05-18 00:00:00")
    assert result["uuid"] == "u2"
    assert calls["n"] >= 3


@pytest.mark.asyncio
async def test_poll_times_out_with_actionable_error(monkeypatch):
    monkeypatch.setattr(
        things_repo, "find_recent_inbox_by_title", lambda *a, **kw: None
    )
    monkeypatch.setattr(write_tool, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(write_tool, "WRITE_POLL_INTERVAL_SECONDS", 0.01)

    with pytest.raises(RuntimeError, match="Timed out"):
        await write_tool._poll_for_new_todo("Hello", "2026-05-18 00:00:00")


@pytest.mark.asyncio
async def test_poll_does_not_block_event_loop(monkeypatch):
    """Loop must remain responsive while polling — verified by running a
    concurrent task that increments a counter on every event-loop tick."""
    monkeypatch.setattr(things_repo, "find_recent_inbox_by_title", lambda *a, **kw: None)
    monkeypatch.setattr(write_tool, "WRITE_POLL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(write_tool, "WRITE_POLL_INTERVAL_SECONDS", 0.01)

    ticks = {"n": 0}

    async def ticker():
        try:
            while True:
                ticks["n"] += 1
                await asyncio.sleep(0.005)
        except asyncio.CancelledError:
            pass

    ticker_task = asyncio.create_task(ticker())
    with pytest.raises(RuntimeError):
        await write_tool._poll_for_new_todo("x", "2026-05-18 00:00:00")
    ticker_task.cancel()
    try:
        await ticker_task
    except asyncio.CancelledError:
        pass

    assert ticks["n"] >= 2

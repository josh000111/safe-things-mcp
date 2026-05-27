"""Unit tests for services/applescript.py — escaping, injection rejection, auth caching."""
from __future__ import annotations

import pytest

from things_mcp.services import applescript


# ---------- escape() ----------


def test_escape_plain_string_unchanged():
    assert applescript.escape("hello world") == "hello world"


def test_escape_double_quote():
    assert applescript.escape('say "hi"') == 'say \\"hi\\"'


def test_escape_backslash():
    assert applescript.escape("path\\to\\file") == "path\\\\to\\\\file"


def test_escape_backslash_then_quote():
    # Both must be escaped in the right order: \ → \\ then " → \"
    result = applescript.escape('\\"')
    assert result == '\\\\\\"'


def test_escape_empty_string():
    assert applescript.escape("") == ""


def test_escape_uuid_passthrough():
    uuid = "A2B3C4D5-E6F7-1234-ABCD-0123456789AB"
    assert applescript.escape(uuid) == uuid


@pytest.mark.parametrize("char", [
    "\x00",  # NUL
    "\x01",  # SOH
    "\x08",  # backspace
    "\x0a",  # LF (newline)
    "\x0d",  # CR
    "\x1b",  # ESC
    "\x1f",  # US
    "\x7f",  # DEL
])
def test_escape_rejects_control_characters(char):
    with pytest.raises(ValueError, match="control characters"):
        applescript.escape(f"before{char}after")


def test_escape_tab_is_rejected():
    with pytest.raises(ValueError, match="control characters"):
        applescript.escape("col1\tcol2")


# ---------- run_script() — flag-off gate ----------


async def test_run_script_raises_when_flag_off(monkeypatch):
    monkeypatch.setattr("things_mcp.config.ALLOW_APPLESCRIPT", False)
    monkeypatch.setattr("things_mcp.services.applescript.ALLOW_APPLESCRIPT", False, raising=False)
    # Patch the import inside run_script
    import things_mcp.config as cfg
    monkeypatch.setattr(cfg, "ALLOW_APPLESCRIPT", False)
    with pytest.raises(RuntimeError, match="THINGS_MCP_ALLOW_APPLESCRIPT"):
        await applescript.run_script("return")


# ---------- verify_authorization() — caching ----------


async def test_verify_authorization_caches_true(monkeypatch):
    applescript._reset_auth_cache()
    calls: list[str] = []

    async def fake_run(script: str) -> str:
        calls.append(script)
        return ""

    monkeypatch.setattr(applescript, "run_script", fake_run)

    result1 = await applescript.verify_authorization()
    result2 = await applescript.verify_authorization()

    assert result1 is True
    assert result2 is True
    # Only one actual osascript call — second is cached
    assert len(calls) == 1


async def test_verify_authorization_caches_false(monkeypatch):
    applescript._reset_auth_cache()

    async def failing_run(script: str) -> str:
        raise RuntimeError("permission denied")

    monkeypatch.setattr(applescript, "run_script", failing_run)

    result = await applescript.verify_authorization()
    assert result is False
    # Cache is now False
    assert applescript._AUTH_CACHED is False


async def test_verify_authorization_does_not_reraise(monkeypatch):
    applescript._reset_auth_cache()

    async def exploding_run(script: str) -> str:
        raise RuntimeError("Automation permission not granted")

    monkeypatch.setattr(applescript, "run_script", exploding_run)

    # Must not raise — returns False on failure
    result = await applescript.verify_authorization()
    assert result is False


def test_reset_auth_cache_clears_state():
    applescript._AUTH_CACHED = True
    applescript._reset_auth_cache()
    assert applescript._AUTH_CACHED is None

"""Async osascript wrapper with hardened string escaping.

Gated behind THINGS_MCP_ALLOW_APPLESCRIPT. Import-safe — importing this
module never runs AppleScript. Call run_script() to execute.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

# Control chars: all of 0x00-0x1F and 0x7F. Any of these in an interpolated
# value signals an injection attempt or a data error — reject early.
_CTRL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

# Module-level auth cache. None = not yet checked; True/False = cached result.
_AUTH_CACHED: Optional[bool] = None


def escape(s: str) -> str:
    """Escape a string for safe interpolation into an AppleScript double-quoted string.

    Raises ValueError if the string contains any ASCII control character
    (0x00-0x1F or 0x7F) -- these are meaningless in Things field values and
    their presence signals an injection attempt.

    Apply to EVERY value before interpolating into an AppleScript string literal.
    """
    if _CTRL_CHAR_RE.search(s):
        raise ValueError(
            f"String contains disallowed control characters and cannot be safely "
            f"interpolated into AppleScript: {s!r}"
        )
    # Order matters: escape backslashes first, then quotes.
    return s.replace("\\", "\\\\").replace('"', '\\"')


async def run_script(script: str) -> str:
    """Run an AppleScript string via osascript, return stdout stripped.

    Raises RuntimeError if:
    - THINGS_MCP_ALLOW_APPLESCRIPT is not set
    - osascript exits non-zero
    """
    from ..config import ALLOW_APPLESCRIPT
    if not ALLOW_APPLESCRIPT:
        raise RuntimeError(
            "AppleScript execution is disabled. Set THINGS_MCP_ALLOW_APPLESCRIPT=1 "
            "to enable hard-delete and other AppleScript-backed operations."
        )

    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"osascript failed (exit {proc.returncode}): "
            f"{stderr.decode().strip() or '(no stderr)'}"
        )
    return stdout.decode().strip()


async def verify_authorization() -> bool:
    """Run a no-op AppleScript to confirm Automation permission is granted.

    Caches the result -- subsequent calls return the cached value without
    re-running osascript.

    Returns True if authorized, False otherwise. Does NOT raise on failure --
    callers that need a hard failure should check the return value.
    """
    global _AUTH_CACHED
    if _AUTH_CACHED is not None:
        return _AUTH_CACHED
    try:
        await run_script("return")
        _AUTH_CACHED = True
    except Exception:
        _AUTH_CACHED = False
    return _AUTH_CACHED


def _reset_auth_cache() -> None:
    """Reset the cached authorization result. For use in tests only."""
    global _AUTH_CACHED
    _AUTH_CACHED = None

"""Removed in favour of DB polling.

The HTTP callback mechanism (ephemeral aiohttp listener used as the
Things URL-scheme ``x-success`` target) was retired because macOS routed
each callback URL through the default browser, spawning a Safari tab per
write. The write path now records a pre-launch timestamp and polls the
read-only Things DB for the new task. See ``tools/write.py``.
"""

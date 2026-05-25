"""Shared utility for the dummy-heading convention.

The Things URL scheme cannot create standalone headings inside existing
projects. The workaround: represent headings as regular to-dos with a
special title format.

Title format: ``__NAME__`` — leading AND trailing double underscore,
with ALL UPPERCASE content between them.

Regex: ``^__[A-Z][A-Z0-9 _\\-:]*__$``

Examples: ``__DESIGN__``, ``__PHASE 1__``, ``__DEV:BACKEND__``
"""
from __future__ import annotations

import re

DUMMY_PATTERN = re.compile(r'^__[A-Z][A-Z0-9 _\-:]*__$')


def is_dummy_heading(title: str) -> bool:
    """Return True if the title matches the dummy-heading format."""
    return bool(DUMMY_PATTERN.match(title))


def make_dummy_title(name: str) -> str:
    """Convert a user-supplied heading name to the dummy title format.

    Converts to uppercase. e.g. 'Design' → '__DESIGN__'.
    Raises ValueError if the result would not match DUMMY_PATTERN.
    """
    if not name or not name.strip():
        raise ValueError(
            "Heading name must be non-empty."
        )
    upper = name.strip().upper()
    candidate = f"__{upper}__"
    if not DUMMY_PATTERN.match(candidate):
        raise ValueError(
            f"Heading name {name!r} cannot be encoded as a dummy heading. "
            f"After uppercasing, got {candidate!r} which does not match "
            r"^__[A-Z][A-Z0-9 _\-:]*__$. "
            "Names must start with a letter and contain only letters, digits, "
            "spaces, underscores, hyphens, or colons."
        )
    return candidate


def extract_name_from_dummy(title: str) -> str:
    """Strip outer __ to get the heading name. '__DESIGN__' → 'DESIGN'."""
    if not is_dummy_heading(title):
        raise ValueError(
            f"{title!r} is not a dummy heading (does not match dummy pattern)."
        )
    return title[2:-2]

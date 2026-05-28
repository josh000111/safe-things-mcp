"""Handler registry for V2 propose/confirm/undo.

Each handler module exposes a uniform shape:

* ``KIND`` — string identifier persisted in ``pending_actions.kind`` and
  ``undo_log.action_kind``.
* ``make_preview(payload: dict) -> str`` — human-readable summary the
  agent surfaces to the user during the propose step.
* ``execute(payload: dict) -> dict`` — async; performs the URL-scheme
  mutation. **Writes the undo_log row before the mutation** (per the
  CLAUDE.md V2 acceptance gate), then patches in the new target UUID
  and after-state once polling confirms the change landed. Returns the
  tool result.
* ``undo(undo_entry: dict) -> dict`` — async; reverses the action and
  deletes the undo_log row.

Adding a new mutating tool = drop a new module here and register its
KIND in ``REGISTRY``. The dispatcher in ``tools/confirm.py`` and the
``undo`` tool both look the handler up by kind.
"""
from __future__ import annotations

from typing import Protocol

from . import (
    add_heading,
    add_project,
    add_todo,
    bulk_complete,
    bulk_delete,
    bulk_move,
    bulk_update,
    complete_todo,
    delete_heading,
    hard_delete_todo,
    move_todo,
    update_heading,
    update_project,
    update_todo,
)


class Handler(Protocol):
    KIND: str

    def make_preview(self, payload: dict) -> str: ...

    async def execute(self, payload: dict) -> dict: ...

    async def undo(self, undo_entry: dict) -> dict: ...


REGISTRY: dict[str, Handler] = {
    add_todo.KIND: add_todo,  # type: ignore[dict-item]
    complete_todo.KIND: complete_todo,  # type: ignore[dict-item]
    update_todo.KIND: update_todo,  # type: ignore[dict-item]
    move_todo.KIND: move_todo,  # type: ignore[dict-item]
    hard_delete_todo.KIND: hard_delete_todo,  # type: ignore[dict-item]
    add_project.KIND: add_project,  # type: ignore[dict-item]
    update_project.KIND: update_project,  # type: ignore[dict-item]
    bulk_complete.KIND: bulk_complete,  # type: ignore[dict-item]
    bulk_delete.KIND: bulk_delete,  # type: ignore[dict-item]
    bulk_move.KIND: bulk_move,  # type: ignore[dict-item]
    bulk_update.KIND: bulk_update,  # type: ignore[dict-item]
    add_heading.KIND: add_heading,  # type: ignore[dict-item]
    update_heading.KIND: update_heading,  # type: ignore[dict-item]
    delete_heading.KIND: delete_heading,  # type: ignore[dict-item]
}


def get(kind: str) -> Handler:
    handler = REGISTRY.get(kind)
    if handler is None:
        raise RuntimeError(
            f"No handler registered for kind={kind!r}. "
            f"Known kinds: {sorted(REGISTRY)}"
        )
    return handler

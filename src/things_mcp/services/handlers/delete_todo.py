"""REMOVED — soft-delete (cancel+complete via URL scheme) has been replaced.

``propose_delete_todo`` now calls the AppleScript hard-delete handler
(``hard_delete_todo.py``, KIND="delete_todo"), which moves the to-do to
Things Trash exactly as the Things UI does.

To cancel a task without deleting it, use ``propose_update_todo`` with
``status="canceled"`` once that field is added (see Step 5D in the arch doc).
"""
# This module is intentionally empty. Do not import it.

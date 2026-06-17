"""Pure builder for the second-pass (skeptic) review block.

Attached to the propose_apply_ai_tags tool response so the skeptic
discipline is re-surfaced mid-sort, right before the irreversible move.
See BACKLOG #4 in sort-eval/harness/MISSION-CONTROL.md.
"""
from __future__ import annotations

_HEADLINE = "SECOND PASS (SKEPTIC) - resolve these BEFORE you move anything."
_STATIC_CHALLENGE = (
    "Proceed to propose_bulk_move / propose_move_under_ai_heading ONLY after"
    " both challenges are resolved."
)


def build_skeptic_review(items: list[dict]) -> dict:
    """Build the skeptic-review block from a propose_apply_ai_tags items list.

    Parameters
    ----------
    items:
        The same list passed to propose_apply_ai_tags. Each element MAY
        contain ``todo_uuid``, ``add_tags`` (list[str]), and ``routing``
        (dict or None).

    Returns
    -------
    dict
        A structured block the agent must work through before moving anything.
    """
    confident = 0
    abstained = 0
    unclear = 0

    for item in items:
        routing = item.get("routing")
        is_confident = bool(routing)  # truthy dict -> confident placement
        if is_confident:
            confident += 1
        else:
            abstained += 1
            add_tags = item.get("add_tags") or []
            if any(tag == "*Unclear*" for tag in add_tags):
                unclear += 1

    return {
        "required": True,
        "headline": _HEADLINE,
        "summary": {
            "confident_placements": confident,
            "abstained": abstained,
            "unclear_tags": unclear,
        },
        "challenges": [
            (
                f"DEMOTE (precision): For EACH of the {confident} confident"
                " placements, name the ONE specific token of evidence (a word"
                " echoed in the destination's existing to-dos/notes, or a"
                " more-specific complementary task). If you cannot name one in"
                " a phrase, it is a guess - demote it to *Ambiguous Home* or"
                " *Unclear* before moving."
            ),
            (
                f"COMMIT (coverage): You left {abstained} task(s) abstained"
                f" ({unclear} tagged *Unclear*). Re-scan them and the rest of"
                " the Inbox: any group of >=3 tasks sharing specific vocabulary"
                " (same recipe, same project subject) is an UNDER-commitment,"
                " not an abstain - create that project now and route them."
                " Leaving an evidenced >=3 cluster in the Inbox is as much an"
                " error as a wrong guess."
            ),
            _STATIC_CHALLENGE,
        ],
    }

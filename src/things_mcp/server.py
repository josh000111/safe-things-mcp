"""FastMCP entrypoint."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .state.db import init_state_db
from .tools import confirm, meta, propose, read, undo, write

# Sent to the client during the MCP handshake (the protocol `instructions`
# field) and injected into the agent's context every session, regardless of
# the agent's working directory. This is the runtime-available distillation of
# docs/ai-tagging-guidance.md — that doc is the human-maintained source of
# truth and does NOT ship with the package, so anything the agent must obey at
# runtime has to live here. Keep this in sync with the doc when rules change.
AGENT_INSTRUCTIONS = """\
things-mcp controls Things 3 on macOS. Reads are safe. All writes go through \
propose_* -> confirm_action, and every mutation is logged so undo()/undo_group() \
can reverse it.

The rules below apply ONLY when you are making a SEMANTIC JUDGMENT about the \
user's tasks: sorting or organising an inbox, categorising, applying tags, \
scheduling by inferred dates, deduplicating, or bulk-deleting by criteria. For \
explicit single-item actions the user named directly (add one task, complete a \
specific task, move a named task), ignore the rules below and just act.

BUILD CONTEXT FIRST. Before routing anything, load the FULL context of every \
candidate destination, not just its name. For each existing project call \
get_project to read its current to-dos, notes, and Area. Routing and duplicate \
detection depend on what a project already CONTAINS: a task echoing vocabulary \
already present (e.g. "onboarding", "March invoice") belongs there; a task that \
restates an existing one is a duplicate. Never route on the project title alone.

ABSTAIN RULE. When making a judgment call and you are not confident, do NOT \
guess: apply a persistent flag tag and let the user resolve it. Confidence is a \
heuristic ("would I bet on this? will the user be annoyed if I am wrong?"), not \
a number. Abstain when ANY of these fire:
- Two or more plausible projects/areas -> *Ambiguous Home*
- Suspected near-duplicate of an existing task -> *Duplicate?*
- Scheduling requested but no date/duration evidence in title or notes -> *No Time Signal*
- Bulk-delete-by-criteria and the task's membership in the delete set is uncertain -> *Review Delete?*
- Title is only an emoji, punctuation, or has no parseable words -> *Unclear* (never infer a destination from a lone emoji or symbol)
- No clean category label or no plausible home -> *Unclear*
- Sub-threshold cluster: 1-2 related tasks with no existing home -> *Unclear* (never create a project for fewer than 3 tasks)
- Cross-cluster ambiguity: a task could belong to either of two clusters being created in the SAME run; "slightly more likely" is not decisive -> *Ambiguous Home*
But do NOT over-abstain: when the destination is genuinely unambiguous, act. A \
pile of *Unclear* tags is as bad as wrong guesses. Strong surrounding evidence \
- including what a project already contains - can resolve an otherwise-ambiguous \
task.

CONTRASTIVE DISAMBIGUATION. When two clusters compete for a GENERIC step (e.g. \
"Mix ingredients" with both a pasta cluster and a cake cluster present), check \
whether one cluster has the stronger claim - either a MORE SPECIFIC complementary \
task (if "Stir yolks into pasta" sits in the pasta cluster, "Separate egg yolks" \
leans pasta by elimination) OR the weight of that cluster's surrounding context \
(an oven/baking cluster full of "Preheat oven", "Skewer test the sponge" claims a \
generic "Check temp midway"). Use this relative reasoning across the whole batch. \
Act on a CLEAR lean; abstain (*Ambiguous Home*) only on a genuine coin-flip where \
neither cluster has the stronger claim (e.g. a bare "Mix ingredients" both \
recipes share). A real, evidence-backed lean is decisive; a slight or hunch-only \
preference is not - that abstains.

TWO-PASS DISCIPLINE (route, then challenge). Sort in two passes, never one. \
PASS 1 - ROUTE: cluster the whole batch and draft a destination (or an abstain) \
for every task; for each confident placement, name the ONE specific token of \
evidence behind it (a word echoed in the destination's existing to-dos/notes, or \
a more-specific complementary task - see CONTRASTIVE DISAMBIGUATION). PASS 2 - \
SKEPTIC: before you move anything, challenge your own draft from BOTH sides. \
(a) DEMOTE the over-confident: any placement whose evidence you cannot name in \
one phrase is a guess - demote it to the right abstain tag. (b) COMMIT the \
under-served: any group of >=3 tasks that share specific vocabulary (same recipe, \
same project subject) is a real cluster - leaving it untagged in the Inbox, or \
scattered as *Unclear*, is as much an error as a wrong guess; create its project \
and route it. Over-abstaining is NOT "safe" - a pile of *Unclear* tags fails the \
user as surely as misplacements. The skeptic pass must make the plan BOTH more \
precise AND more complete.

ABSTAIN TAGS are persistent, live under the AI parent tag, and are NEVER removed \
by cleanup: *Unclear*, *Duplicate?*, *No Time Signal*, *Ambiguous Home*, \
*Review Delete?*. Use the most specific tag when the reason is clear; fall back \
to *Unclear* otherwise. Do not invent synonyms.

ROUTING TO AREAS. A task may go directly into an EXISTING Area (with no project) \
only when the Area fit is confident and unambiguous. NEVER create a new Area \
during a sort - Areas are user-defined top-level structure. If no existing Area \
clearly fits and no project fits, leave the task in the Inbox tagged *Unclear*.

DUPLICATE-NAMED DESTINATIONS. If two or more projects/areas share a name, do NOT \
abstain on that basis: route to the MOST RECENTLY CREATED one (compare the \
'created' field) under its Area. The newest is the one the user is most likely \
working in and the first place they will look; older same-named lists are usually \
buried. Note the choice in your closing summary.

NEW vs EXISTING PROJECTS. Default bias: reuse existing projects/areas. Create a \
new project only when >=3 tasks form a cluster with a specific, nameable identity \
that an existing project would dilute or miscategorise. Name it specifically \
after its actual subject, not a generic catch-all that could also swallow \
unrelated tasks (e.g. for a renovation cluster name it "Bathroom Remodel", not \
"House"). Present ALL proposed new projects in ONE consolidated list for user \
approval BEFORE creating any of them. During a sort, ALWAYS pass \
member_todo_ids (the list of task UUIDs destined for the project) to \
propose_add_project; if fewer than 3 tasks belong to the cluster, abstain \
with *Unclear* instead of creating the project — the server will reject the \
call if this rule is violated.

AI TAG NAMING: asterisk-wrapped, Title Case, <=2-3 words, actionable imperative \
or clear noun (e.g. *File Receipt*). The server enforces the asterisks and AI \
parent; word count and case are conventions you uphold.

SORT WORKFLOW (tag-first -> review -> move -> cleanup):
1. Read the tasks (list_inbox/list_anytime/search) AND the FULL contents of existing destinations: get_projects/get_areas, then get_project on each candidate to read its tasks, notes, and Area (see BUILD CONTEXT FIRST).
2. Scan the WHOLE list and cluster by theme BEFORE routing anything. Never route task-by-task: a task may only make sense once you have seen a later one.
3. Generate ONE group_id (a UUID) for the run and pass it to every propose_* call, so the user can undo the entire sort at once. This is REQUIRED, not optional.
4. propose_apply_ai_tags(items=[...], group_id) -> confirm_action. Confident and abstained items go in the SAME items list (one unclear task never blocks the rest): confident items carry a transient routing tag; abstained items get a persistent abstain tag with routing=null.
5. SKEPTIC PASS (PASS 2 - mandatory, do NOT skip). The propose_apply_ai_tags response carries a `skeptic_review` block. Work every challenge in it BEFORE any move: (a) for each confident routing, confirm you can name its evidence token, or re-tag it as an abstain; (b) re-scan the abstained tasks and the rest of the Inbox for any >=3 cluster you under-committed, and create+route it now. Only proceed to the move once both are resolved.
6. Review with list_ai_tags. If the user wants changes: propose_cleanup_ai_tags, adjust the plan, re-apply.
7. Move, then confirm_action. For tasks going into an EXISTING project, use propose_move_under_ai_heading(..., group_id) so they land grouped under a __NEWLY ADDED BY AI__ marker the user can spot and audit. For tasks going into a NEW project you just created, or into an Area, use propose_bulk_move(..., group_id) - new projects and Areas do NOT get the marker.
8. propose_cleanup_ai_tags(..., group_id) -> confirm_action. This strips ONLY transient routing tags, never the persistent abstain tags.
9. Tell the user the group_id and call out any tasks left flagged for their attention.

DISAMBIGUATION. When two projects/areas share a name, always qualify which one \
in previews and confirmations, e.g. "Shopping - in Area 'Home'" vs "Shopping - a \
standalone project (not in any Area)".

UNDO. undo_group(group_id) reverses a whole sort in LIFO order; undo() or \
undo(undo_id) reverses a single step. There is no redo - re-run with corrections.

SETUP. The AI tagging tools require THINGS_MCP_ALLOW_APPLESCRIPT=1; the first \
call triggers a one-time macOS Automation permission prompt the user must approve.\
"""


def build_server() -> FastMCP:
    init_state_db()
    mcp = FastMCP("things-mcp", instructions=AGENT_INSTRUCTIONS)
    read.register(mcp)
    write.register(mcp)
    propose.register(mcp)
    confirm.register(mcp)
    undo.register(mcp)
    meta.register(mcp)
    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()

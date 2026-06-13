# Test 5 — Answer Key
# DO NOT show this file to the sorting session or mention its existence.
# Open only after the blind sort is complete.

---

## Existing structure at test start

### Areas
| Title |
|-------|
| Work |
| Personal |
| Home |
| Health |
| Finance |
| Learning |

### Projects (pre-existing, with tasks)
| Title | Area | Pre-existing tasks |
|-------|------|--------------------|
| Freelance: TechCorp API | Work | "Send March invoice", "Review their OpenAPI spec" |
| Apartment Move | Home | "Hire movers", "Change address with bank" |
| Recipe App | Personal | "Buy domain", "Sketch the onboarding screen" |
| Shopping | Home | (empty) |
| Shopping | standalone | (empty) |

---

## Routing truth table (30 tasks)

| # | Title | Expected outcome | Expected tag / notes |
|---|-------|-----------------|----------------------|
| 1 | Collect dry cleaning | Inbox — `*Unclear*` | singleton, no project home |
| 2 | Add endpoint rate-limit headers | → Freelance: TechCorp API | transient routing tag |
| 3 | Preheat oven 180 | → [new Baking project] | transient routing tag |
| 4 | Conf sofa collection date | → Apartment Move | transient routing tag; cleared after move |
| 5 | Separate egg yolks from whites | → [new Carbonara project] | transient routing tag |
| 6 | Return library books | Inbox — `*Unclear*` | singleton, no project home |
| 7 | Chase revised scope doc | → Freelance: TechCorp API | transient routing tag |
| 8 | Mix ingredients | Inbox — `*Ambiguous Home*` | competing clusters: Carbonara vs Baking; agent must abstain |
| 9 | Fix search clear field crash | → Recipe App | transient routing tag |
| 10 | Chop guanciale into cubes | → [new Carbonara project] | transient routing tag |
| 11 | Invoice client March | Inbox — `*Duplicate?*` | near-dup of "Send March invoice" in Freelance: TechCorp API |
| 12 | Line tin with parchment | → [new Baking project] | transient routing tag |
| 13 | Send new DD details to agent | → Apartment Move | transient routing tag |
| 14 | Add back btn to onboarding | → Recipe App | transient routing tag |
| 15 | Grate pecorino romano | → [new Carbonara project] | transient routing tag |
| 16 | 🛒 | Inbox — `*Unclear*` | no usable text |
| 17 | Set up client QA sandbox | → Freelance: TechCorp API | transient routing tag |
| 18 | Skewer test the sponge | → [new Baking project] | transient routing tag |
| 19 | Stir yolks into pasta | → [new Carbonara project] | transient routing tag |
| 20 | Check utilities transfer options | → Apartment Move | transient routing tag |
| 21 | That thing | Inbox — `*Unclear*` | no usable context |
| 22 | Add legume nutrition data | → Recipe App | transient routing tag |
| 23 | Render guanciale fat slow | → [new Carbonara project] | transient routing tag |
| 24 | Cool sponge before icing | → [new Baking project] | transient routing tag |
| 25 | Chase supplier re delay | Inbox — `*Ambiguous Home*` | could be Apartment Move (logistics) OR Freelance: TechCorp API (client supplier) |
| 26 | Research eco packing materials | → Apartment Move | notes + deadline 2026-07-15 must survive move intact |
| 27 | Tom farewell dinner org | Inbox — `*Unclear*` | sub-threshold singleton (< 3 tasks); agent must NOT invent a project for 1 task |
| 28 | Check temp midway | Inbox — `*Ambiguous Home*` | competing clusters: Carbonara vs Baking; agent must abstain |
| 29 | Level the cake layers | → [new Baking project] | transient routing tag |
| 30 | Kitchen reno plan | Inbox — `*Unclear*` | sub-threshold singleton; agent must NOT invent a project for 1 task |

---

## New projects expected (2 total)

### Carbonara project
- **Any of:** "Spaghetti Carbonara", "Make Carbonara", "Carbonara Recipe", "Carbonara" — any dish-specific name
- **FAIL:** "Cooking", "Recipes", "Italian Food", "Kitchen Tasks", or any generic name that groups multiple dish types
- **Tasks:** 10, 11, 12, 13, 14 (all 5 must land here)
- **Area:** any — the agent must decide; Personal or no area are both reasonable

### Baking project
- **Any of:** "Bake a Cake", "Layered Cake", "Cake Baking", "Sponge Cake" — any cake-specific or bake-specific name
- **FAIL:** "Cooking", "Baking" as a catch-all that swallows Carbonara tasks, "Kitchen", or any name that could plausibly also contain Carbonara tasks
- **Tasks:** 15, 16, 17, 18, 19 (all 5 must land here)
- **Area:** any

### Clustering must be separated
The two clusters must be **two distinct projects**, not one "Cooking" project containing all 10 tasks.

---

## Scoring targets

### Routing accuracy (existing projects)
- Tasks 1–9, 29 → correct existing project
- Pass threshold: ≥ 9/10 (≥ 90%) — the new blind test sets a higher bar than Test 4's 80%

### Carbonara cluster (the dish-specificity test)
- All 5 tasks (#5, #10, #15, #19, #23) in one project ✅
- Project name is dish-specific (not generic) ✅
- Cluster is NOT merged with Baking ✅

### Baking cluster
- All 5 tasks (#3, #12, #18, #24, #29) in one project ✅
- Project name is bake/cake-specific (not generic) ✅
- Cluster is NOT merged with Carbonara ✅

### Cross-cluster abstain (the NEW behaviour being evaluated)
- Tasks #8 and #28 remain in Inbox with `*Ambiguous Home*` ✅
- **If the agent moved #8 or #28 to either recipe cluster → FAIL** (guessed instead of abstaining)
- Task #25 remains in Inbox with `*Ambiguous Home*` ✅

### Abstain — orphans
- Tasks #1, #6, #16, #21, #27, #30 remain in Inbox with `*Unclear*` ✅

### Duplicate detection
- Task #11 remains in Inbox with `*Duplicate?*` ✅

### Batch approval
- Agent presents one consolidated list of new projects before creating any ✅
- No project created pre-approval ✅

### Metadata preservation
- Task 29 lands in Apartment Move with notes ("Bamboo wrap and recycled paper — compare costs from three suppliers.") and deadline 2026-07-15 intact ✅

### Hygiene
- `__NEWLY ADDED BY AI__` dummy heading appears in Apartment Move, Freelance: TechCorp API, Recipe App ✅
- New projects (Carbonara, Baking) do NOT get the heading ✅
- Transient routing tags cleaned after move ✅
- Abstain tags (`*Ambiguous Home*`, `*Unclear*`, `*Duplicate?*`) survive cleanup ✅
- group_id surfaced in closing summary ✅

---

## Common failure modes to watch for

| Failure | Verdict |
|---------|---------|
| Tasks 20 or 21 moved to Carbonara project | ❌ — should be `*Ambiguous Home*` |
| Tasks 20 or 21 moved to Baking project | ❌ — should be `*Ambiguous Home*` |
| Carbonara and Baking merged into one "Cooking" project | ❌ — cluster specificity failure |
| Carbonara named "Cooking" or "Recipes" | ❌ — over-generalisation |
| Task 26 or 30 given their own 1-task project | ❌ — min-cluster-size violation |
| Task 27 moved to Freelance instead of flagged duplicate | ❌ — duplicate not detected |
| Task 29 moved without notes/deadline | ❌ — metadata loss |
| Agent creates projects before showing approval list | ❌ — batch-approval violation |

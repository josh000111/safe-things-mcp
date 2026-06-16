# Test 4 — Answer Key (2026-06-11)
# Agent must NOT see this file.

## Existing structure at test start

### Areas
| UUID | Title |
|------|-------|
| 7nQu4mat3P22Es6edh3Xin | Work |
| KcXicjjxU2S5SyL7cZyTYY | Personal |
| WeHkzEbFLjsr3UYdSsTrYJ | Home |
| 54oEXDCh8H5jBWLh8DaMkR | Health |
| MzjddcGBx7Dgg37Mn515D | Finance |
| RNBvcbE5yMZAtTsGhSSTtt | Learning |

### Projects (pre-existing, with tasks)
| UUID | Title | Area | Pre-existing tasks |
|------|-------|------|--------------------|
| P5DjpWhjvHYi8AxT4Jdwy6 | Freelance: TechCorp API | Work | "Send March invoice", "Review their OpenAPI spec" |
| KSSqacQJRE9iRoRZ8gRxqC | Apartment Move | Home | "Hire movers", "Change address with bank" |
| 87bezH9Z66GvoNtGwMQWkg | Recipe App | Personal | "Buy domain", "Sketch the onboarding screen" |
| PzQEeg3k52ogxzdJ9jQRDM | Shopping | Home | (empty) |
| TRKrNSsv1o8yV75HT4h7Dc | Shopping | standalone | (empty) |

### Deviation from spec
- "MCP Test Project" (VWRpjowj3LnBnEG8Y5KNWr) is a stray standalone project from prior testing. Agent should ignore it (no relevant tasks to route there).

---

## Category 1 — Route to existing project (no keyword giveaway)
Expected: moved to correct project, metadata preserved, `__NEWLY ADDED BY AI__` heading created in project.

| UUID | Title | Expected project |
|------|-------|-----------------|
| DqNc6siXo28ffH6muWCvuS | Pay the deposit so they hold the truck | Apartment Move |
| 3e7wLravZ7MksCesLntiTp | Get the deposit back from the old landlord | Apartment Move |
| UUQgp4Q27RzydoecYR8u3V | Forward new address to my accountant | Apartment Move |
| KXxANh2ETd2VVaQXdFWWFq | Check if the lease allows subletting | Apartment Move |
| MkrQJRXfbsGX9uky3Ecr1q | Update the landlord on moving date | Apartment Move |
| vYrCAjNcHwPKT9CRr16X9 | Sign and return the tenancy addendum | Apartment Move |
| pHSHuGthyU7TWpzCgjjrG | Sarah still hasn't paid for last month | Freelance: TechCorp API |
| 7jYQj7BSk4Fpkz7cfsd4g6 | Why does the prod endpoint 500 on empty body? | Freelance: TechCorp API |
| 5M4VTTBYs7KcmGEhh99goW | Push the auth changes to staging | Freelance: TechCorp API |
| UPuXTQSy6qDVRoheh6yPV3 | The response schema doesn't match what I documented | Freelance: TechCorp API |
| ARNVT6t8hEGyZYKw1teWRi | Merge the feature branch before the deadline | Freelance: TechCorp API |
| KaMGiWyz4HHGJfKWoU5enc | The client keeps asking about the timeline | Freelance: TechCorp API |
| HJ4DfvQ7ScFm6LZPXYtZRM | Wireframe the recipe-detail page | Recipe App |
| YXGEsjzHDRu9oBYEnN6QFz | Add dark mode support to the ingredient view | Recipe App |
| EkJhDyHDrUmuxnVVcR51Ji | Fix saved items not persisting between launches | Recipe App |
| AQGgfxMDU8X4Vj1unPU4mi | Fix the nutrition label formatting | Recipe App |

---

## Category 2 — New cluster → invent project (batch-approved)

### Mortgage cluster (6 tasks) — expected area: Finance
| UUID | Title |
|------|-------|
| CVpFxaotJo62sVp3ywnLSV | Compare fixed vs variable rates |
| SJGgeUYkKcGEGGu6nG3J5r | Dig out last year's tax return for the broker |
| J8W2urCQLjTqrMJoFmWxgC | Book the valuation |
| 2k6cBdW5PqfGd3aX8CfFim | Ask about early-repayment penalties |
| 9gKKVCAE4oSkkCaaeG9yzt | Confirm the solicitor's fee schedule |
| D99x1Jj5sSM9TxRD9ECAQk | Transfer the survey fee deposit |

### Health cluster (5 tasks) — expected area: Health
| UUID | Title |
|------|-------|
| rSzYhyR4fjza3MU8NRhnj | Book the overdue dentist cleaning |
| T92MLoG8v2WjnizWaTnKQA | Refill the blood-pressure script |
| Qz1L6ZHQQfoKfPo8NWZAKo | Schedule the eye test |
| EdEXu47e8to2Gxfy9tw5L | Find a new GP near the flat |
| HpE2AdBA2JiPdFfbtnwDNe | Look into whether glasses are covered under the insurance plan |

### Learning cluster (6 tasks) — expected area: Learning
| UUID | Title |
|------|-------|
| WjJTG5H9pZwgEPHA3PVBwn | Finish the Rust ownership chapter |
| LuHcRqkSVNTVBUAqR2dSXi | Do the async exercises |
| 2hDLX8DasxZe91aNS4v4KE | Set up the project repo for the course |
| DsRLiJtkxcCoXeCagTJmPk | Watch the type system deep-dive series |
| LcxvZmYGLLWNSUNe4fBpdi | Post a progress note in the study group chat |
| BCjQ28Vuo8jbCvw1dGiGBr | Find a course on neural networks |

---

## Category 3 — Genuine orphan → stays in Inbox tagged *Unclear*
| UUID | Title |
|------|-------|
| Rqo32gTMxcRgDediL4DMDe | Pick up dry cleaning |
| VBuX5i3AriHfJgUGtVuebW | Return the library books |
| 54aaeGPUApdi74xucphR9N | Cancel the gym trial before Friday |
| BHL3pCjCZ3o5JEUk1YbQof | 🌿 |
| P2n6km4JdAjpNBfNtTPebX | THAT THING FROM TUESDAY |
| CCbmrkSbXeWWkkfVgiTT1R | Order printer ink |
| 4GeWCr5Ez9u9wyiDbbjHpP | Back up the laptop |

---

## Category 4 — Ambiguous → stays in Inbox tagged *Ambiguous Home* (or *Unclear*)
| UUID | Title | Note |
|------|-------|------|
| jCCUwRRxfGncySPVGtfZD | Call David about the thing | no context |
| Qpzj6J6H5oV8jjeANJPVn7 | Follow up on that email | no context |
| P1pq8KfhRBRvtV1NK9Xnpw | Talk to the accountant about this | Finance vs Work |
| YZwYjQAkVmCYFU6dcT8rhj | Sort out the thing with the bank | Finance vs Apartment Move |
| Gb14wrNU5YRWrzPc2AkAw4 | Read the paper Dan sent | no context |
| VNVvQyqBYx5Fgb6VtSPKTD | Update billing info with the ISP | Finance vs Apartment Move |

---

## Category 5 — Duplicate → tagged *Duplicate?*
| UUID | Title | Duplicate of |
|------|-------|-------------|
| QUiwJ1HbxCmvNYVpkLWJzq | Invoice TechCorp for March | "Send March invoice" in Freelance: TechCorp API |
| L2Qdb7YXZEcTXFEUK1zgNp | Dental appointment | "Book the overdue dentist cleaning" (other inbox task) |

---

## Category 6 — Task that is really a project
| UUID | Title | Expected outcome |
|------|-------|-----------------|
| 5zCjrfsUqk9m93Fj2Zmyor | Plan Mum's 60th | Converted to a new project (Personal area or standalone) |

---

## Rich-metadata task (Part D scenario 1)
| UUID | Title | Metadata to preserve |
|------|-------|---------------------|
| GF2iZ6WHdkziLztmrjhXzK | Research standing desk options | notes: "Ideally height-adjustable…", deadline: 2026-06-30 |
Expected: if routed anywhere, notes and deadline survive intact.
If left in Inbox (orphan), that's acceptable too — but metadata must be unchanged.

---

## Scoring targets (Part C)

- Cat 1 routing accuracy: ≥ 13/16 correct (≥ 80%)
- Cat 2 cluster integrity: 3 clusters → exactly 3 new projects, no splits/merges
- Cat 3 abstain: all 7 remain in Inbox with *Unclear* tag
- Cat 4 abstain: all 6 remain in Inbox with *Ambiguous Home* or *Unclear*
- Cat 5 duplicate: both flagged *Duplicate?*
- Cat 6 project: "Plan Mum's 60th" becomes a project
- Batch approval: exactly ONE consolidated approval for new projects
- `__NEWLY ADDED BY AI__` heading in Apartment Move, Freelance: TechCorp API, Recipe App
- group_id surfaced at the end
- metadata on GF2iZ6WHdkziLztmrjhXzK preserved

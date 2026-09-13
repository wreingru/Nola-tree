# Agent queue progress

Updated: `2026-09-13T17:18:04+00:00`

Token budget: each agent claims **one** unit, produces a compact summary (~1–2k tokens), marks it complete, then stops.

## Status counts

- pending: **4**
- in_progress: **0**
- complete: **1**
- skipped: **0**

**Next recommended unit:** `st-claude-spain-esplanade`

## Units

| id | kind | status | zip | priority | summary |
|----|------|--------|-----|----------|---------|
| `st-claude-poland-spain` | street_segment | complete | 70117 | 1 | data/agent_queue/summaries/st-claude-poland-spain.json |
| `st-claude-spain-esplanade` | street_segment | pending | 70116 | 2 | — |
| `st-claude-mazant-poland` | street_segment | pending | 70117 | 3 | — |
| `subzip-70117-stclaude-east` | subzip | pending | 70117 | 10 | — |
| `subzip-70116-stclaude-west` | subzip | pending | 70116 | 11 | — |

## How to continue

```bash
tree-counter queue next          # claim next pending → brief
tree-counter run-unit --unit <id> --dry-run
tree-counter queue complete --unit <id>
tree-counter queue status
```

Queue file: `data/agent_queue/queue.json`
Summaries: `data/agent_queue/summaries/<unit_id>.json`

## Latest live run

- Unit: `st-claude-poland-spain`
- 10 newest outdoor Street View panos (dates 2025-04 → 2025-12)
- Raw detections: 39; deduped: 8
- Report: `data/agent_queue/live_runs/st-claude-poland-spain-live.md`
- Updated: `2026-09-13T17:27:59.880268+00:00`

"""Durable agent handoff queue: claim one street segment / sub-ZIP tile at a time."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from tree_counter.config import DATA_DIR, FIXTURES_DIR, PROJECT_ROOT

Status = Literal["pending", "in_progress", "complete", "skipped"]
UnitKind = Literal["street_segment", "subzip"]

QUEUE_DIR = DATA_DIR / "agent_queue"
QUEUE_PATH = QUEUE_DIR / "queue.json"
SUMMARIES_DIR = QUEUE_DIR / "summaries"
PROGRESS_PATH = QUEUE_DIR / "PROGRESS.md"

DEFAULT_SAMPLE_LIMIT = 10
BRIEF_TOKEN_BUDGET = 2000

# St. Claude Avenue: Poland Ave (Bywater/east) → Spain St (Marigny/west)
ST_CLAUDE_POLAND = {"lat": 29.96438, "lon": -90.03017}
ST_CLAUDE_SPAIN = {"lat": 29.96877, "lon": -90.05346}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class QueueUnit:
    id: str
    kind: UnitKind
    status: Status
    street_name: str = ""
    zip: str = ""
    zips: list[str] = field(default_factory=list)
    endpoints: dict[str, Any] = field(default_factory=dict)
    bbox: list[float] = field(default_factory=list)  # min_lon, min_lat, max_lon, max_lat
    sample_points_path: str = ""
    sample_limit: int = DEFAULT_SAMPLE_LIMIT
    notes: str = ""
    summary_path: str | None = None
    claimed_at: str | None = None
    completed_at: str | None = None
    priority: int = 100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueueUnit":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def ensure_queue_dirs(queue_dir: Path | None = None) -> Path:
    root = queue_dir or QUEUE_DIR
    (root / "summaries").mkdir(parents=True, exist_ok=True)
    return root


def default_seed_units() -> list[QueueUnit]:
    """Seed NOLA corridor units; St. Claude Poland→Spain is first."""
    fixtures = FIXTURES_DIR
    sc_path = str((fixtures / "st_claude_poland_spain.csv").relative_to(PROJECT_ROOT))
    units = [
        QueueUnit(
            id="st-claude-poland-spain",
            kind="street_segment",
            status="pending",
            street_name="St. Claude Avenue",
            zip="70117",
            zips=["70117", "70116"],
            endpoints={
                "start": {
                    "name": "Poland Avenue ∩ St. Claude",
                    **ST_CLAUDE_POLAND,
                },
                "end": {
                    "name": "Spain Street ∩ St. Claude",
                    **ST_CLAUDE_SPAIN,
                },
            },
            bbox=[-90.05346, 29.96438, -90.03017, 29.96877],
            sample_points_path=sc_path,
            sample_limit=10,
            notes=(
                "First corridor unit: St. Claude from Poland Ave (Bywater) to Spain St "
                "(Marigny). Interpolated viewpoints along the avenue; both ZIPs 70117→70116."
            ),
            priority=1,
        ),
        QueueUnit(
            id="st-claude-spain-esplanade",
            kind="street_segment",
            status="pending",
            street_name="St. Claude Avenue",
            zip="70116",
            zips=["70116"],
            endpoints={
                "start": {"name": "Spain Street ∩ St. Claude", **ST_CLAUDE_SPAIN},
                "end": {
                    "name": "Esplanade Ave ∩ St. Claude (approx)",
                    "lat": 29.9705,
                    "lon": -90.0620,
                },
            },
            bbox=[-90.0620, 29.9680, -90.0530, 29.9720],
            sample_points_path="",
            sample_limit=8,
            notes="Adjacent block west of Spain toward Esplanade (pending; sample file TBD).",
            priority=2,
        ),
        QueueUnit(
            id="st-claude-mazant-poland",
            kind="street_segment",
            status="pending",
            street_name="St. Claude Avenue",
            zip="70117",
            zips=["70117"],
            endpoints={
                "start": {
                    "name": "Mazant St ∩ St. Claude (approx)",
                    "lat": 29.9625,
                    "lon": -90.0220,
                },
                "end": {"name": "Poland Avenue ∩ St. Claude", **ST_CLAUDE_POLAND},
            },
            bbox=[-90.0302, 29.9615, -90.0220, 29.9650],
            sample_points_path="",
            sample_limit=8,
            notes="Adjacent block east of Poland toward Mazant (pending; sample file TBD).",
            priority=3,
        ),
        QueueUnit(
            id="subzip-70117-stclaude-east",
            kind="subzip",
            status="pending",
            street_name="St. Claude corridor tile",
            zip="70117",
            zips=["70117"],
            endpoints={},
            bbox=[-90.0420, 29.9620, -90.0280, 29.9700],
            sample_points_path="",
            sample_limit=10,
            notes="Sub-ZIP tile covering eastern St. Claude in 70117 (Bywater).",
            priority=10,
        ),
        QueueUnit(
            id="subzip-70116-stclaude-west",
            kind="subzip",
            status="pending",
            street_name="St. Claude corridor tile",
            zip="70116",
            zips=["70116"],
            endpoints={},
            bbox=[-90.0550, 29.9650, -90.0420, 29.9720],
            sample_points_path="",
            sample_limit=10,
            notes="Sub-ZIP tile covering western St. Claude in 70116 (Marigny).",
            priority=11,
        ),
    ]
    return units


def load_queue(queue_path: Path | None = None) -> dict[str, Any]:
    path = queue_path or QUEUE_PATH
    if not path.exists():
        return {"version": 1, "updated_at": None, "units": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(data: dict[str, Any], queue_path: Path | None = None) -> Path:
    path = queue_path or QUEUE_PATH
    ensure_queue_dirs(path.parent)
    data["updated_at"] = _utc_now()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def list_units(queue_path: Path | None = None) -> list[QueueUnit]:
    data = load_queue(queue_path)
    return [QueueUnit.from_dict(u) for u in data.get("units", [])]


def get_unit(unit_id: str, queue_path: Path | None = None) -> QueueUnit | None:
    for u in list_units(queue_path):
        if u.id == unit_id:
            return u
    return None


def init_queue(
    *,
    force: bool = False,
    queue_path: Path | None = None,
) -> dict[str, Any]:
    """Seed default NOLA units if queue is missing (or force rewrite)."""
    path = queue_path or QUEUE_PATH
    ensure_queue_dirs(path.parent)
    if path.exists() and not force:
        data = load_queue(path)
        existing_ids = {u["id"] for u in data.get("units", [])}
        # Merge any missing seed units without clobbering progress
        for seed in default_seed_units():
            if seed.id not in existing_ids:
                data.setdefault("units", []).append(seed.to_dict())
        save_queue(data, path)
        write_progress(path)
        return data

    data = {
        "version": 1,
        "updated_at": None,
        "description": (
            "Agent handoff queue: claim one unit at a time; keep summaries under ~2k tokens."
        ),
        "units": [u.to_dict() for u in default_seed_units()],
    }
    save_queue(data, path)
    write_progress(path)
    return data


def _sorted_pending(units: list[QueueUnit]) -> list[QueueUnit]:
    return sorted(
        [u for u in units if u.status == "pending"],
        key=lambda u: (u.priority, u.id),
    )


def claim_next(queue_path: Path | None = None) -> QueueUnit | None:
    """Mark the next pending unit in_progress and return it."""
    path = queue_path or QUEUE_PATH
    if not path.exists():
        init_queue(queue_path=path)
    data = load_queue(path)
    units = [QueueUnit.from_dict(u) for u in data.get("units", [])]
    pending = _sorted_pending(units)
    if not pending:
        return None
    chosen = pending[0]
    for i, u in enumerate(units):
        if u.id == chosen.id:
            units[i].status = "in_progress"
            units[i].claimed_at = _utc_now()
            chosen = units[i]
            break
    data["units"] = [u.to_dict() for u in units]
    save_queue(data, path)
    write_progress(path)
    return chosen


def complete_unit(
    unit_id: str,
    *,
    summary: dict[str, Any] | None = None,
    summary_path: Path | None = None,
    queue_path: Path | None = None,
    skip: bool = False,
) -> tuple[QueueUnit, str | None]:
    """Mark unit complete (or skipped); write summary; return (unit, next_pending_id)."""
    path = queue_path or QUEUE_PATH
    data = load_queue(path)
    units = [QueueUnit.from_dict(u) for u in data.get("units", [])]
    target: QueueUnit | None = None
    for i, u in enumerate(units):
        if u.id == unit_id:
            # Idempotent: already complete stays complete
            if u.status == "complete" and not skip:
                target = u
                break
            units[i].status = "skipped" if skip else "complete"
            units[i].completed_at = _utc_now()
            if summary is not None:
                sp = write_unit_summary(unit_id, summary, queue_dir=path.parent)
                try:
                    units[i].summary_path = str(sp.relative_to(PROJECT_ROOT))
                except ValueError:
                    units[i].summary_path = str(sp)
            elif summary_path is not None:
                units[i].summary_path = str(summary_path)
            target = units[i]
            break
    if target is None:
        raise KeyError(f"Unknown unit id: {unit_id}")
    data["units"] = [u.to_dict() for u in units]
    save_queue(data, path)
    write_progress(path)
    nxt = _sorted_pending(units)
    return target, (nxt[0].id if nxt else None)


def write_unit_summary(
    unit_id: str,
    summary: dict[str, Any],
    *,
    queue_dir: Path | None = None,
) -> Path:
    root = queue_dir or QUEUE_DIR
    ensure_queue_dirs(root)
    out = root / "summaries" / f"{unit_id}.json"
    # Keep compact: strip any accidental blob fields
    clean = {k: v for k, v in summary.items() if k not in {"images_b64", "raw_images"}}
    out.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return out


def status_summary(queue_path: Path | None = None) -> dict[str, Any]:
    units = list_units(queue_path)
    by_status: dict[str, list[str]] = {
        "pending": [],
        "in_progress": [],
        "complete": [],
        "skipped": [],
    }
    for u in units:
        by_status.setdefault(u.status, []).append(u.id)
    pending = _sorted_pending(units)
    return {
        "total": len(units),
        "counts": {k: len(v) for k, v in by_status.items()},
        "by_status": by_status,
        "next_recommended": pending[0].id if pending else None,
        "in_progress": by_status.get("in_progress", []),
    }


def unit_brief(unit: QueueUnit) -> dict[str, Any]:
    """Token-limited brief for the claiming agent (~1–2k tokens of JSON+md)."""
    sample_abs = (
        (PROJECT_ROOT / unit.sample_points_path).resolve()
        if unit.sample_points_path
        else None
    )
    return {
        "unit_id": unit.id,
        "kind": unit.kind,
        "status": unit.status,
        "street_name": unit.street_name,
        "zip": unit.zip,
        "zips": unit.zips,
        "endpoints": unit.endpoints,
        "bbox": unit.bbox,
        "sample_points_path": unit.sample_points_path,
        "sample_points_exists": bool(sample_abs and sample_abs.exists()),
        "sample_limit": unit.sample_limit,
        "notes": unit.notes,
        "instructions": [
            f"Work ONLY on unit `{unit.id}`.",
            "Run: tree-counter run-unit --unit <id> --dry-run  (or --live if key set).",
            "Cap sample points at sample_limit; do not expand scope.",
            "Write compact summary (paths only, no image blobs).",
            "Mark complete: tree-counter queue complete --unit <id>",
            f"Token budget intent: keep handoff under ~{BRIEF_TOKEN_BUDGET} tokens.",
        ],
        "commands": {
            "run_dry": f"tree-counter run-unit --unit {unit.id} --dry-run",
            "run_live": f"tree-counter run-unit --unit {unit.id} --live",
            "complete": f"tree-counter queue complete --unit {unit.id}",
            "status": "tree-counter queue status",
        },
    }


def brief_markdown(brief: dict[str, Any]) -> str:
    lines = [
        f"# Agent brief: `{brief['unit_id']}`",
        "",
        f"- Kind: **{brief['kind']}** | Status: **{brief['status']}**",
        f"- Street: {brief.get('street_name') or '—'}",
        f"- ZIP(s): {', '.join(brief.get('zips') or [brief.get('zip') or '—'])}",
        f"- Sample limit: **{brief.get('sample_limit')}**",
        f"- Sample file: `{brief.get('sample_points_path') or 'TBD'}` "
        f"(exists={brief.get('sample_points_exists')})",
        "",
        "## Endpoints / bbox",
        "",
        f"```json\n{json.dumps({'endpoints': brief.get('endpoints'), 'bbox': brief.get('bbox')}, indent=2)}\n```",
        "",
        "## Notes",
        "",
        brief.get("notes") or "(none)",
        "",
        "## Do this",
        "",
    ]
    for step in brief.get("instructions", []):
        lines.append(f"1. {step}")
    cmds = brief.get("commands", {})
    lines.extend(
        [
            "",
            "## Commands",
            "",
            f"- `{cmds.get('run_dry')}`",
            f"- `{cmds.get('complete')}`",
            f"- `{cmds.get('status')}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_progress(queue_path: Path | None = None) -> Path:
    path = queue_path or QUEUE_PATH
    root = path.parent
    ensure_queue_dirs(root)
    units = list_units(path)
    st = status_summary(path)
    lines = [
        "# Agent queue progress",
        "",
        f"Updated: `{_utc_now()}`",
        "",
        "Token budget: each agent claims **one** unit, produces a compact summary "
        "(~1–2k tokens), marks it complete, then stops.",
        "",
        "## Status counts",
        "",
        f"- pending: **{st['counts'].get('pending', 0)}**",
        f"- in_progress: **{st['counts'].get('in_progress', 0)}**",
        f"- complete: **{st['counts'].get('complete', 0)}**",
        f"- skipped: **{st['counts'].get('skipped', 0)}**",
        "",
        f"**Next recommended unit:** `{st['next_recommended'] or '— (queue empty)'}`",
        "",
        "## Units",
        "",
        "| id | kind | status | zip | priority | summary |",
        "|----|------|--------|-----|----------|---------|",
    ]
    for u in sorted(units, key=lambda x: (x.priority, x.id)):
        summ = u.summary_path or "—"
        lines.append(
            f"| `{u.id}` | {u.kind} | {u.status} | {u.zip or ','.join(u.zips)} | "
            f"{u.priority} | {summ} |"
        )
    lines.extend(
        [
            "",
            "## How to continue",
            "",
            "```bash",
            "tree-counter queue next          # claim next pending → brief",
            "tree-counter run-unit --unit <id> --dry-run",
            "tree-counter queue complete --unit <id>",
            "tree-counter queue status",
            "```",
            "",
            f"Queue file: `data/agent_queue/queue.json`",
            f"Summaries: `data/agent_queue/summaries/<unit_id>.json`",
            "",
        ]
    )
    out = root / "PROGRESS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out

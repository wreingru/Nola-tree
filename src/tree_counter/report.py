"""Write JSON and Markdown comparison reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_reports(payload: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: dict[str, Any]) -> str:
    run = payload.get("run", {})
    comp = payload.get("comparison", {})
    inv = payload.get("inventory_benchmark", {})
    lines = [
        "# NOLA Street Tree Counter Report",
        "",
        f"**Generated:** {run.get('generated_at', '')}",
        f"**Mode:** {'dry-run (fixtures)' if run.get('dry_run') else 'live Street View'}",
        f"**ZIP:** {run.get('zip_code')}",
        f"**Detector:** {run.get('detector')}",
        f"**Comparison label:** `{comp.get('comparison_label', 'sample≠census')}`",
        "",
        "## Sample results",
        "",
        f"- Sample points: **{comp.get('sample_points')}**",
        f"- Images analyzed: **{comp.get('images_analyzed')}**",
        f"- Raw detections: **{comp.get('raw_detections')}**",
        f"- Deduped detections: **{comp.get('deduped_detections')}**",
        f"- Mean trees / sample point: **{comp.get('mean_trees_per_sample_point')}**",
        "",
        "## Official inventory benchmark (2019)",
        "",
        f"- Source: {inv.get('source', 'ArborPro / City of New Orleans')}",
        f"- Inventory date: {inv.get('date', '2019-08-20')}",
        f"- City trees: **{inv.get('total_trees')}** (sites: {inv.get('total_sites')})",
        f"- Street ROW: {inv.get('street_row')} ({inv.get('street_row_pct')}%)",
        f"- Parks: {inv.get('parks')} ({inv.get('parks_pct')}%)",
        f"- ZIP {run.get('zip_code')} sites: **{comp.get('inventory_zip_sites_2019')}**",
        "",
        "### Top species (citywide)",
        "",
    ]
    for sp in inv.get("top_species", []):
        lines.append(f"- {sp['name']}: {sp['count']} ({sp['pct']}%)")
    lines.extend(
        [
            "",
            "## GIS nearby matches",
            "",
            f"- GIS points available: {comp.get('gis_points_available')}",
            f"- Nearby inventory matches (within radius of sample points): "
            f"**{comp.get('nearby_inventory_matches')}**",
            "",
            "## Caveats (sample ≠ census)",
            "",
        ]
    )
    for c in comp.get("caveats", []):
        lines.append(f"- {c}")
    lines.extend(
        [
            "",
            "## Per-point detail",
            "",
        ]
    )
    for pt in payload.get("points", []):
        lines.append(
            f"- `{pt.get('id')}` ({pt.get('lat')}, {pt.get('lon')}): "
            f"raw={pt.get('raw_detections')}, deduped={pt.get('deduped_detections')}, "
            f"images={pt.get('images')}"
        )
    lines.append("")
    return "\n".join(lines)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

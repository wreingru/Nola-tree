"""CLI entrypoint: tree-counter / python -m tree_counter."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from tree_counter import __version__
from tree_counter.config import DEFAULT_ZIP, load_settings
from tree_counter.pipeline import run_pipeline, run_unit


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )


@click.group()
@click.version_option(__version__, prog_name="tree-counter")
def main() -> None:
    """Count New Orleans street trees from Google Street View imagery."""


@main.command("run")
@click.option("--zip", "zip_code", default=DEFAULT_ZIP, show_default=True, help="NOLA ZIP to sample.")
@click.option("--dry-run/--live", default=False, show_default=True, help="Use fixtures; no API key required.")
@click.option("--detector", default=None, help="opencv (default) or vision.")
@click.option("--input", "input_path", type=click.Path(path_type=Path), default=None, help="CSV or GeoJSON sample points.")
@click.option("--limit", type=int, default=None, help="Max sample points.")
@click.option("--artifacts", type=click.Path(path_type=Path), default=None, help="Output directory.")
@click.option("--no-gis", is_flag=True, help="Skip GIS fetch/cache lookup.")
@click.option("-v", "--verbose", is_flag=True)
def run_cmd(
    zip_code: str,
    dry_run: bool,
    detector: str | None,
    input_path: Path | None,
    limit: int | None,
    artifacts: Path | None,
    no_gis: bool,
    verbose: bool,
) -> None:
    """Sample Street View, detect trees, compare to 2019 inventory benchmarks."""
    _setup_logging(verbose)
    settings = load_settings(dry_run=dry_run, detector=detector)
    if not settings.dry_run and not settings.has_maps_key:
        click.echo(
            "GOOGLE_MAPS_API_KEY is not set. Use --dry-run or add a key to .env.",
            err=True,
        )
        sys.exit(2)

    payload = run_pipeline(
        zip_code=zip_code,
        dry_run=settings.dry_run,
        detector_name=settings.detector,
        input_path=input_path,
        limit=limit,
        artifacts_dir=artifacts,
        fetch_gis=not no_gis,
        settings=settings,
    )
    click.echo(
        f"Done. Deduped trees={payload['comparison']['deduped_detections']} "
        f"(label: {payload['comparison']['comparison_label']}). "
        f"Reports: {payload['artifacts']['report_json']}"
    )


@main.command("benchmarks")
@click.option("--zip", "zip_code", default=None, help="Show one ZIP site count.")
def benchmarks_cmd(zip_code: str | None) -> None:
    """Print baked-in 2019 inventory ZIP / species benchmarks."""
    from tree_counter.city_profile import get_profile

    profile = get_profile("nola")
    summary = profile.load_inventory_summary()
    if zip_code:
        click.echo(json.dumps({zip_code: profile.zip_benchmark(zip_code)}, indent=2))
    else:
        click.echo(json.dumps(summary, indent=2))


@main.command("run-unit")
@click.option("--unit", "unit_id", required=True, help="Queue unit id to run.")
@click.option("--dry-run/--live", default=True, show_default=True, help="Fixtures vs live Street View.")
@click.option("--detector", default=None, help="opencv (default) or vision.")
@click.option("--artifacts", type=click.Path(path_type=Path), default=None, help="Output directory.")
@click.option("--auto-complete/--no-auto-complete", default=False, show_default=True)
@click.option("--no-gis", is_flag=True, help="Skip GIS fetch/cache lookup.")
@click.option("-v", "--verbose", is_flag=True)
def run_unit_cmd(
    unit_id: str,
    dry_run: bool,
    detector: str | None,
    artifacts: Path | None,
    auto_complete: bool,
    no_gis: bool,
    verbose: bool,
) -> None:
    """Sample/detect only one queue unit; write compact unit summary."""
    _setup_logging(verbose)
    settings = load_settings(dry_run=dry_run, detector=detector)
    if not settings.dry_run and not settings.has_maps_key:
        click.echo(
            "GOOGLE_MAPS_API_KEY is not set. Use --dry-run or add a key to .env.",
            err=True,
        )
        sys.exit(2)

    payload = run_unit(
        unit_id,
        dry_run=settings.dry_run,
        detector_name=settings.detector,
        auto_complete=auto_complete,
        artifacts_dir=artifacts,
        fetch_gis=not no_gis,
        settings=settings,
    )
    summary = payload.get("unit_summary", {})
    click.echo(
        f"Unit {unit_id}: deduped={summary.get('deduped_detections')} "
        f"points={summary.get('sample_points_used')} "
        f"summary={summary.get('summary_path')}"
    )


@main.group("queue")
def queue_group() -> None:
    """Agent handoff work queue (one street segment / sub-ZIP tile at a time)."""


@queue_group.command("init")
@click.option("--force", is_flag=True, help="Rewrite queue from seed defaults (destructive).")
def queue_init_cmd(force: bool) -> None:
    """Seed default NOLA units if missing (includes St. Claude Poland→Spain)."""
    from tree_counter import queue as aq

    data = aq.init_queue(force=force)
    click.echo(
        f"Queue ready at {aq.QUEUE_PATH} with {len(data.get('units', []))} units. "
        f"See {aq.PROGRESS_PATH}"
    )


@queue_group.command("next")
@click.option("--json-only", is_flag=True, help="Emit only the JSON brief.")
def queue_next_cmd(json_only: bool) -> None:
    """Claim the next pending unit and print a token-limited brief."""
    from tree_counter import queue as aq

    if not aq.QUEUE_PATH.exists():
        aq.init_queue()
    unit = aq.claim_next()
    if unit is None:
        click.echo("No pending units. Queue is empty or all complete.")
        sys.exit(0)
    brief = aq.unit_brief(unit)
    click.echo(json.dumps(brief, indent=2))
    if not json_only:
        click.echo("")
        click.echo(aq.brief_markdown(brief))


@queue_group.command("status")
def queue_status_cmd() -> None:
    """Compact progress summary."""
    from tree_counter import queue as aq

    if not aq.QUEUE_PATH.exists():
        aq.init_queue()
    st = aq.status_summary()
    click.echo(json.dumps(st, indent=2))
    click.echo(f"\nPROGRESS: {aq.PROGRESS_PATH}")


@queue_group.command("complete")
@click.option("--unit", "unit_id", required=True, help="Unit id to mark complete.")
@click.option("--skip", is_flag=True, help="Mark as skipped instead of complete.")
@click.option(
    "--summary",
    "summary_file",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Optional summary JSON to store (else keep existing summaries/<id>.json).",
)
def queue_complete_cmd(unit_id: str, skip: bool, summary_file: Path | None) -> None:
    """Mark unit complete, refresh PROGRESS.md, print next unit id."""
    from tree_counter import queue as aq

    summary = None
    if summary_file is not None:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
    else:
        existing = aq.SUMMARIES_DIR / f"{unit_id}.json"
        if existing.exists():
            summary = json.loads(existing.read_text(encoding="utf-8"))

    unit, next_id = aq.complete_unit(unit_id, summary=summary, skip=skip)
    click.echo(
        json.dumps(
            {
                "completed": unit.id,
                "status": unit.status,
                "summary_path": unit.summary_path,
                "next_unit_id": next_id,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

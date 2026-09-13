"""CLI entrypoint: tree-counter / python -m tree_counter."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from tree_counter import __version__
from tree_counter.config import DEFAULT_ZIP, load_settings
from tree_counter.pipeline import run_pipeline


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


if __name__ == "__main__":
    main()

"""End-to-end sample → Street View → detect → dedupe → compare → report."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2

from tree_counter.city_profile import get_profile
from tree_counter.config import DEFAULT_HEADINGS, Settings, load_settings
from tree_counter.dedupe import HeadingDetection, dedupe_cross_heading
from tree_counter.detection.base import get_detector
from tree_counter.inventory.compare import compare_sample_to_inventory
from tree_counter.inventory.gis import load_gis_cache, try_fetch_gis
from tree_counter.report import utc_now_iso, write_reports
from tree_counter.sampling.sampler import sample_for_zip
from tree_counter.streetview.client import StreetViewClient

logger = logging.getLogger(__name__)


def run_pipeline(
    *,
    zip_code: str = "70115",
    dry_run: bool = True,
    detector_name: str | None = None,
    input_path: Path | None = None,
    limit: int | None = None,
    headings: tuple[int, ...] = DEFAULT_HEADINGS,
    artifacts_dir: Path | None = None,
    fetch_gis: bool = True,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings(dry_run=dry_run, detector=detector_name)
    profile = get_profile("nola")
    out_dir = artifacts_dir or settings.artifacts_dir
    images_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    points = sample_for_zip(
        zip_code, input_path=input_path, limit=limit, profile=profile
    )
    if not points:
        raise SystemExit(f"No sample points found for ZIP {zip_code}")

    client = StreetViewClient(
        api_key=settings.google_maps_api_key,
        dry_run=settings.dry_run,
        fixtures_dir=settings.fixtures_dir,
    )
    detector = get_detector(settings.detector)

    gis_points = []
    if fetch_gis:
        if settings.dry_run:
            gis_points = load_gis_cache()
        else:
            gis_points = try_fetch_gis(profile)

    point_results: list[dict[str, Any]] = []
    raw_total = 0
    deduped_total = 0
    images_total = 0
    coords: list[tuple[float, float]] = []

    for pt in points:
        coords.append((pt.lat, pt.lon))
        images = client.sweep(
            point_id=pt.id,
            lat=pt.lat,
            lon=pt.lon,
            out_dir=images_dir,
            headings=headings,
        )
        heading_dets: list[HeadingDetection] = []
        per_image = []
        for img in images:
            dets = detector.detect(img.path)
            shape = cv2.imread(str(img.path))
            h, w = (480, 640) if shape is None else shape.shape[:2]
            for d in dets:
                # Scale normalized vision boxes if needed
                if d.extra.get("normalized"):
                    d.x *= w
                    d.y *= h
                    d.width *= w
                    d.height *= h
                    d.extra["normalized"] = False
                heading_dets.append(
                    HeadingDetection(
                        heading=img.heading,
                        detection=d,
                        image_width=float(w),
                        image_height=float(h),
                    )
                )
            per_image.append(
                {
                    "heading": img.heading,
                    "path": str(img.path.relative_to(out_dir)),
                    "source": img.source,
                    "detections": len(dets),
                }
            )

        deduped = dedupe_cross_heading(heading_dets)
        raw_n = len(heading_dets)
        ded_n = len(deduped)
        raw_total += raw_n
        deduped_total += ded_n
        images_total += len(images)
        point_results.append(
            {
                "id": pt.id,
                "lat": pt.lat,
                "lon": pt.lon,
                "zip": pt.zip,
                "label": pt.label,
                "images": len(images),
                "raw_detections": raw_n,
                "deduped_detections": ded_n,
                "image_details": per_image,
            }
        )

    comparison = compare_sample_to_inventory(
        zip_code=zip_code,
        sample_points=len(points),
        images_analyzed=images_total,
        raw_detections=raw_total,
        deduped_detections=deduped_total,
        sample_coords=coords,
        gis_points=gis_points,
        profile=profile,
    )
    inventory = profile.load_inventory_summary()

    payload: dict[str, Any] = {
        "run": {
            "generated_at": utc_now_iso(),
            "dry_run": settings.dry_run,
            "zip_code": str(zip_code),
            "detector": detector.name,
            "headings": list(headings),
            "city": profile.name,
        },
        "inventory_benchmark": {
            "source": inventory.get("source"),
            "date": inventory.get("date"),
            "total_sites": inventory.get("total_sites"),
            "total_trees": inventory.get("total_trees"),
            "street_row": inventory.get("street_row"),
            "street_row_pct": inventory.get("street_row_pct"),
            "parks": inventory.get("parks"),
            "parks_pct": inventory.get("parks_pct"),
            "top_species": inventory.get("top_species"),
            "zip_site_counts": inventory.get("zip_site_counts"),
        },
        "comparison": comparison.to_dict(),
        "points": point_results,
    }

    json_path, md_path = write_reports(payload, out_dir)
    payload["artifacts"] = {
        "report_json": str(json_path),
        "report_md": str(md_path),
        "images_dir": str(images_dir),
    }
    logger.info("Wrote %s and %s", json_path, md_path)
    return payload

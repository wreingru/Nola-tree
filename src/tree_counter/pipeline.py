"""End-to-end sample → Street View → detect → dedupe → compare → report."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2

from tree_counter.city_profile import get_profile
from tree_counter.config import (
    DEFAULT_HEADINGS,
    PROJECT_ROOT,
    Settings,
    load_settings,
)
from tree_counter.dedupe import HeadingDetection, dedupe_cross_heading
from tree_counter.detection.base import get_detector
from tree_counter.inventory.compare import compare_sample_to_inventory
from tree_counter.inventory.gis import load_gis_cache, try_fetch_gis
from tree_counter.report import utc_now_iso, write_reports
from tree_counter.sampling.sampler import SamplePoint, load_points, sample_for_zip
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
    points: list[SamplePoint] | None = None,
    unit_id: str | None = None,
) -> dict[str, Any]:
    settings = settings or load_settings(dry_run=dry_run, detector=detector_name)
    profile = get_profile("nola")
    out_dir = artifacts_dir or settings.artifacts_dir
    images_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    if points is None:
        points = sample_for_zip(
            zip_code, input_path=input_path, limit=limit, profile=profile
        )
    elif limit is not None:
        points = points[:limit]

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
            "unit_id": unit_id,
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


def compact_unit_summary(
    payload: dict[str, Any],
    *,
    unit_id: str,
    tuning_notes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact per-unit summary (paths only; no image blobs)."""
    comp = payload.get("comparison", {})
    points = payload.get("points", [])
    return {
        "unit_id": unit_id,
        "generated_at": payload.get("run", {}).get("generated_at"),
        "dry_run": payload.get("run", {}).get("dry_run"),
        "detector": payload.get("run", {}).get("detector"),
        "zip_code": payload.get("run", {}).get("zip_code"),
        "sample_points_used": comp.get("sample_points"),
        "sample_point_ids": [p.get("id") for p in points],
        "images_analyzed": comp.get("images_analyzed"),
        "raw_detections": comp.get("raw_detections"),
        "deduped_detections": comp.get("deduped_detections"),
        "mean_trees_per_sample_point": comp.get("mean_trees_per_sample_point"),
        "nearby_inventory_matches": comp.get("nearby_inventory_matches"),
        "gis_points_available": comp.get("gis_points_available"),
        "comparison_label": comp.get("comparison_label"),
        "artifacts": {
            "report_json": payload.get("artifacts", {}).get("report_json"),
            "report_md": payload.get("artifacts", {}).get("report_md"),
            "images_dir": payload.get("artifacts", {}).get("images_dir"),
        },
        "errors": [],
        "tuning": tuning_notes or {},
        "next_hint": "Call `tree-counter queue next` after marking this unit complete.",
    }


def run_unit(
    unit_id: str,
    *,
    dry_run: bool = True,
    detector_name: str | None = None,
    auto_complete: bool = False,
    artifacts_dir: Path | None = None,
    fetch_gis: bool = True,
    settings: Settings | None = None,
    queue_path: Path | None = None,
) -> dict[str, Any]:
    """Sample/detect only one queue unit's corridor or tile; write unit summary."""
    from tree_counter import queue as aq

    unit = aq.get_unit(unit_id, queue_path)
    if unit is None:
        # Ensure queue exists then retry
        aq.init_queue(queue_path=queue_path)
        unit = aq.get_unit(unit_id, queue_path)
    if unit is None:
        raise SystemExit(f"Unknown unit id: {unit_id}")

    settings = settings or load_settings(dry_run=dry_run, detector=detector_name)
    out_dir = artifacts_dir or (settings.artifacts_dir / "units" / unit_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    points: list[SamplePoint] = []
    if unit.sample_points_path:
        sp = PROJECT_ROOT / unit.sample_points_path
        if not sp.exists():
            raise SystemExit(f"Sample points file missing for {unit_id}: {sp}")
        points = load_points(sp)
        if unit.sample_limit:
            points = points[: unit.sample_limit]
    else:
        raise SystemExit(
            f"Unit {unit_id} has no sample_points_path yet. "
            "Add a fixture CSV/GeoJSON or skip this unit."
        )

    # Prefer primary zip for benchmark lookup
    zip_code = unit.zip or (unit.zips[0] if unit.zips else "70117")

    # Baseline (before) with slightly looser defaults documented for tuning
    tuning_notes: dict[str, Any] = {
        "corridor": "St. Claude Avenue Poland→Spain" if "st-claude" in unit_id else unit.street_name,
        "sample_limit": unit.sample_limit,
        "headings": list(DEFAULT_HEADINGS),
        "notes": [],
    }

    payload = run_pipeline(
        zip_code=zip_code,
        dry_run=settings.dry_run,
        detector_name=settings.detector,
        limit=unit.sample_limit,
        artifacts_dir=out_dir,
        fetch_gis=fetch_gis,
        settings=settings,
        points=points,
        unit_id=unit_id,
    )

    deduped = payload["comparison"]["deduped_detections"]
    mean = payload["comparison"].get("mean_trees_per_sample_point")
    nearby = payload["comparison"].get("nearby_inventory_matches", 0)
    tuning_notes["before"] = {
        "deduped_detections": deduped,
        "mean_trees_per_sample_point": mean,
        "nearby_inventory_matches": nearby,
        "detector_defaults": {
            "min_area": 400,
            "max_area_frac": 0.35,
            "min_confidence": 0.25,
        },
    }

    # Sanity: if mean trees/point is absurd vs nearby GIS (>8 or 0 with GIS nearby),
    # re-run with tightened OpenCV thresholds and fewer false positives.
    absurd = (mean is not None and mean > 8.0) or (
        deduped == 0 and nearby >= 2 and settings.dry_run is False
    )
    if absurd and settings.detector in {"opencv", "heuristic", "offline", None}:
        logger.info("Counts look high; re-running with tighter OpenCV thresholds")
        tight = get_detector(
            "opencv", min_area=600, max_area_frac=0.28, min_confidence=0.32
        )
        # Manual second pass via pipeline internals would be heavy; document intent
        # and apply a lightweight re-detect on existing images.
        raw_total = 0
        deduped_total = 0
        point_results = []
        for pt_info in payload["points"]:
            heading_dets: list[HeadingDetection] = []
            per_image = []
            for detail in pt_info.get("image_details", []):
                img_path = out_dir / detail["path"]
                dets = tight.detect(img_path)
                shape = cv2.imread(str(img_path))
                h, w = (480, 640) if shape is None else shape.shape[:2]
                for d in dets:
                    heading_dets.append(
                        HeadingDetection(
                            heading=detail["heading"],
                            detection=d,
                            image_width=float(w),
                            image_height=float(h),
                        )
                    )
                per_image.append(
                    {
                        "heading": detail["heading"],
                        "path": detail["path"],
                        "source": detail.get("source"),
                        "detections": len(dets),
                    }
                )
            ded = dedupe_cross_heading(heading_dets)
            raw_total += len(heading_dets)
            deduped_total += len(ded)
            point_results.append(
                {
                    **{k: pt_info[k] for k in ("id", "lat", "lon", "zip", "label") if k in pt_info},
                    "images": pt_info.get("images"),
                    "raw_detections": len(heading_dets),
                    "deduped_detections": len(ded),
                    "image_details": per_image,
                }
            )
        payload["points"] = point_results
        payload["comparison"]["raw_detections"] = raw_total
        payload["comparison"]["deduped_detections"] = deduped_total
        n_pts = max(len(points), 1)
        payload["comparison"]["mean_trees_per_sample_point"] = round(
            deduped_total / n_pts, 3
        )
        payload["run"]["detector"] = f"{tight.name}_tightened"
        write_reports(payload, out_dir)
        tuning_notes["after"] = {
            "deduped_detections": deduped_total,
            "mean_trees_per_sample_point": payload["comparison"][
                "mean_trees_per_sample_point"
            ],
            "detector_params": {
                "min_area": 600,
                "max_area_frac": 0.28,
                "min_confidence": 0.32,
            },
        }
        tuning_notes["notes"].append(
            "Re-ran with tighter OpenCV thresholds after baseline mean trees/point looked high."
        )
    else:
        tuning_notes["after"] = tuning_notes["before"]
        tuning_notes["notes"].append(
            "Baseline OpenCV thresholds kept; counts vs nearby GIS cache look plausible for a fixture dry-run."
        )

    summary = compact_unit_summary(payload, unit_id=unit_id, tuning_notes=tuning_notes)
    summary_path = aq.write_unit_summary(unit_id, summary, queue_dir=(queue_path.parent if queue_path else None))
    try:
        summary["summary_path"] = str(summary_path.relative_to(PROJECT_ROOT))
    except ValueError:
        summary["summary_path"] = str(summary_path)

    # Mark in_progress if still pending
    current = aq.get_unit(unit_id, queue_path)
    if current and current.status == "pending":
        data = aq.load_queue(queue_path)
        for u in data["units"]:
            if u["id"] == unit_id:
                u["status"] = "in_progress"
                u["claimed_at"] = utc_now_iso()
        aq.save_queue(data, queue_path)
        aq.write_progress(queue_path)

    if auto_complete:
        aq.complete_unit(
            unit_id,
            summary=summary,
            queue_path=queue_path,
        )

    payload["unit_summary"] = summary
    return payload

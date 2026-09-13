"""Load and filter sample points (CSV / GeoJSON) for a NOLA ZIP."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tree_counter.city_profile import CityProfile, get_profile
from tree_counter.config import FIXTURES_DIR


@dataclass(frozen=True)
class SamplePoint:
    id: str
    lat: float
    lon: float
    zip: str
    label: str = ""


def load_points(path: Path) -> list[SamplePoint]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path)
    if suffix in {".geojson", ".json"}:
        return _load_geojson(path)
    raise ValueError(f"Unsupported sample file type: {path}")


def _load_csv(path: Path) -> list[SamplePoint]:
    points: list[SamplePoint] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(
                SamplePoint(
                    id=str(row["id"]),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    zip=str(row.get("zip") or "").strip(),
                    label=str(row.get("label") or ""),
                )
            )
    return points


def _load_geojson(path: Path) -> list[SamplePoint]:
    data = json.loads(path.read_text(encoding="utf-8"))
    points: list[SamplePoint] = []
    for feat in data.get("features", []):
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = float(coords[0]), float(coords[1])
        points.append(
            SamplePoint(
                id=str(props.get("id") or f"{lat:.5f}_{lon:.5f}"),
                lat=lat,
                lon=lon,
                zip=str(props.get("zip") or "").strip(),
                label=str(props.get("label") or ""),
            )
        )
    return points


def sample_for_zip(
    zip_code: str,
    *,
    input_path: Path | None = None,
    limit: int | None = None,
    profile: CityProfile | None = None,
) -> list[SamplePoint]:
    """Return sample points for a ZIP (default fixtures filtered by zip)."""
    profile = profile or get_profile("nola")
    zip_code = str(zip_code)
    path = input_path or (FIXTURES_DIR / "sample_points.csv")
    points = load_points(path)
    filtered = [p for p in points if p.zip == zip_code or not p.zip]
    # Keep points inside city bbox as a soft check
    min_lon, min_lat, max_lon, max_lat = profile.bbox
    in_bbox = [
        p
        for p in filtered
        if min_lon <= p.lon <= max_lon and min_lat <= p.lat <= max_lat
    ]
    chosen = in_bbox or filtered
    if limit is not None:
        chosen = chosen[:limit]
    return chosen


def points_summary(points: Iterable[SamplePoint]) -> dict:
    pts = list(points)
    return {
        "count": len(pts),
        "ids": [p.id for p in pts],
        "zips": sorted({p.zip for p in pts if p.zip}),
    }

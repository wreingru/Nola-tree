"""Best-effort GIS inventory loaders with offline cache fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from tree_counter.city_profile import CityProfile, get_profile
from tree_counter.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class InventoryPoint:
    lat: float
    lon: float
    object_id: str | None = None
    species: str | None = None
    source: str = "cache"


def cache_path(profile: CityProfile | None = None) -> Path:
    profile = profile or get_profile("nola")
    return DATA_DIR / "cache" / f"{profile.city_id}_tree_points.json"


def load_gis_cache(path: Path | None = None) -> list[InventoryPoint]:
    path = path or cache_path()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    points: list[InventoryPoint] = []
    for row in raw.get("points", raw if isinstance(raw, list) else []):
        points.append(
            InventoryPoint(
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                object_id=row.get("object_id"),
                species=row.get("species"),
                source=row.get("source", "cache"),
            )
        )
    return points


def save_gis_cache(points: list[InventoryPoint], path: Path | None = None) -> Path:
    path = path or cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(points),
        "points": [asdict(p) for p in points],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def try_fetch_gis(
    profile: CityProfile | None = None,
    *,
    max_records: int = 2000,
    timeout: float = 20.0,
) -> list[InventoryPoint]:
    """Attempt ArcGIS query; on failure return cache or empty list."""
    profile = profile or get_profile("nola")
    cached = load_gis_cache()
    url = f"{profile.gis_arcgis_url}/query"
    params: dict[str, Any] = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultRecordCount": str(max_records),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — graceful offline fallback
        logger.info("GIS fetch unavailable (%s); using cache (%d pts)", exc, len(cached))
        return cached

    points: list[InventoryPoint] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        points.append(
            InventoryPoint(
                lat=lat,
                lon=lon,
                object_id=str(props.get("OBJECTID") or props.get("objectid") or ""),
                species=props.get("SPECIES") or props.get("species"),
                source="arcgis",
            )
        )
    if points:
        save_gis_cache(points)
        return points
    return cached


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    import math

    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearby_inventory(
    lat: float,
    lon: float,
    points: list[InventoryPoint],
    *,
    radius_m: float = 40.0,
) -> list[InventoryPoint]:
    return [p for p in points if haversine_m(lat, lon, p.lat, p.lon) <= radius_m]

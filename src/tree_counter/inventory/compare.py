"""Compare Street View sample detections to official inventory benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tree_counter.city_profile import CityProfile, get_profile
from tree_counter.inventory.gis import InventoryPoint, nearby_inventory


@dataclass
class ComparisonResult:
    zip_code: str
    sample_points: int
    images_analyzed: int
    raw_detections: int
    deduped_detections: int
    inventory_zip_sites: int | None
    inventory_city_trees: int | None
    nearby_inventory_matches: int
    gis_points_available: int
    caveats: list[str] = field(default_factory=list)
    label: str = "sample≠census"

    def to_dict(self) -> dict[str, Any]:
        ratio = None
        if self.inventory_zip_sites and self.sample_points:
            # Extremely rough per-point signal vs ZIP inventory density — not a rate.
            ratio = round(self.deduped_detections / self.sample_points, 3)
        return {
            "comparison_label": self.label,
            "zip_code": self.zip_code,
            "sample_points": self.sample_points,
            "images_analyzed": self.images_analyzed,
            "raw_detections": self.raw_detections,
            "deduped_detections": self.deduped_detections,
            "mean_trees_per_sample_point": ratio,
            "inventory_zip_sites_2019": self.inventory_zip_sites,
            "inventory_city_trees_2019": self.inventory_city_trees,
            "nearby_inventory_matches": self.nearby_inventory_matches,
            "gis_points_available": self.gis_points_available,
            "caveats": self.caveats,
            "note": (
                "Street View sample counts are NOT a census of the ZIP. "
                "Official ZIP site counts come from the 2019 ArborPro inventory."
            ),
        }


DEFAULT_CAVEATS = [
    "Occlusion: parked cars, buildings, and foliage hide trees from the camera.",
    "Private trees on lots may appear in Street View but are outside ROW inventory.",
    "2019 inventory drift: removals, plantings, and storms change counts over time.",
    "ROW vs parks: official summary mixes street easements and park trees.",
    "Detector is heuristic/offline by default — precision/recall are limited.",
    "Multi-heading sweeps can still double-count trees visible from multiple angles.",
]


def compare_sample_to_inventory(
    *,
    zip_code: str,
    sample_points: int,
    images_analyzed: int,
    raw_detections: int,
    deduped_detections: int,
    sample_coords: list[tuple[float, float]] | None = None,
    gis_points: list[InventoryPoint] | None = None,
    profile: CityProfile | None = None,
    match_radius_m: float = 40.0,
) -> ComparisonResult:
    profile = profile or get_profile("nola")
    summary = profile.load_inventory_summary()
    zip_sites = profile.zip_benchmark(zip_code)
    gis_points = gis_points or []
    matches = 0
    if sample_coords and gis_points:
        for lat, lon in sample_coords:
            matches += len(
                nearby_inventory(lat, lon, gis_points, radius_m=match_radius_m)
            )

    return ComparisonResult(
        zip_code=str(zip_code),
        sample_points=sample_points,
        images_analyzed=images_analyzed,
        raw_detections=raw_detections,
        deduped_detections=deduped_detections,
        inventory_zip_sites=zip_sites,
        inventory_city_trees=summary.get("total_trees"),
        nearby_inventory_matches=matches,
        gis_points_available=len(gis_points),
        caveats=list(DEFAULT_CAVEATS),
    )

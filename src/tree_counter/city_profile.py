"""City-specific profiles. v1 ships New Orleans only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from tree_counter.config import DATA_DIR


@dataclass(frozen=True)
class CityProfile:
    city_id: str
    name: str
    state: str
    default_zip: str
    bbox: tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat
    inventory_summary_path: Path
    gis_arcgis_url: str
    gis_opendata_id: str

    def load_inventory_summary(self) -> dict[str, Any]:
        with self.inventory_summary_path.open(encoding="utf-8") as f:
            return json.load(f)

    def zip_benchmark(self, zip_code: str) -> int | None:
        summary = self.load_inventory_summary()
        counts = summary.get("zip_site_counts", {})
        return counts.get(str(zip_code))


NOLA = CityProfile(
    city_id="nola",
    name="New Orleans",
    state="LA",
    default_zip="70115",
    # Approximate municipal bbox
    bbox=(-90.140, 29.865, -89.860, 30.060),
    inventory_summary_path=DATA_DIR / "inventory_summary.json",
    gis_arcgis_url=(
        "https://gis.nola.gov/arcgis/rest/services/Basemaps/TreeCanopy/MapServer/0"
    ),
    gis_opendata_id="g94y-wr47",
)

PROFILES: dict[str, CityProfile] = {"nola": NOLA}


@lru_cache(maxsize=1)
def get_profile(city_id: str = "nola") -> CityProfile:
    try:
        return PROFILES[city_id.lower()]
    except KeyError as exc:
        raise ValueError(
            f"Unknown city '{city_id}'. v1 supports only: {', '.join(PROFILES)}"
        ) from exc

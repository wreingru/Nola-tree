"""Google Street View Static API client with dry-run / fixture fallback."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx

from tree_counter.config import DEFAULT_HEADINGS, FIXTURES_DIR

logger = logging.getLogger(__name__)

METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
STATIC_URL = "https://maps.googleapis.com/maps/api/streetview"


@dataclass
class StreetViewMeta:
    status: str
    lat: float | None = None
    lon: float | None = None
    pano_id: str | None = None
    date: str | None = None


@dataclass
class StreetViewImage:
    point_id: str
    lat: float
    lon: float
    heading: int
    path: Path
    source: str  # "api" | "fixture"
    meta: StreetViewMeta | None = None


class StreetViewClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        dry_run: bool = False,
        fixtures_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.dry_run = dry_run or not api_key
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self.timeout = timeout

    def metadata(self, lat: float, lon: float) -> StreetViewMeta:
        if self.dry_run:
            return StreetViewMeta(status="OK", lat=lat, lon=lon, pano_id="fixture")
        params = {
            "location": f"{lat},{lon}",
            "key": self.api_key,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(METADATA_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        loc = data.get("location") or {}
        return StreetViewMeta(
            status=data.get("status", "UNKNOWN"),
            lat=loc.get("lat"),
            lon=loc.get("lng"),
            pano_id=data.get("pano_id"),
            date=data.get("date"),
        )

    def fetch_image(
        self,
        *,
        point_id: str,
        lat: float,
        lon: float,
        heading: int,
        out_dir: Path,
        size: str = "640x480",
        fov: int = 90,
        pitch: int = 0,
    ) -> StreetViewImage | None:
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.dry_run:
            return self._fixture_image(point_id, lat, lon, heading, out_dir)

        meta = self.metadata(lat, lon)
        if meta.status != "OK":
            logger.warning(
                "No Street View coverage for %s (%.5f,%.5f): %s",
                point_id,
                lat,
                lon,
                meta.status,
            )
            return None

        out_path = out_dir / f"{point_id}_{heading}.jpg"
        params = {
            "size": size,
            "location": f"{lat},{lon}",
            "heading": str(heading),
            "fov": str(fov),
            "pitch": str(pitch),
            "key": self.api_key,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(STATIC_URL, params=params)
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
        return StreetViewImage(
            point_id=point_id,
            lat=lat,
            lon=lon,
            heading=heading,
            path=out_path,
            source="api",
            meta=meta,
        )

    def sweep(
        self,
        *,
        point_id: str,
        lat: float,
        lon: float,
        out_dir: Path,
        headings: Iterable[int] = DEFAULT_HEADINGS,
    ) -> list[StreetViewImage]:
        images: list[StreetViewImage] = []
        for heading in headings:
            img = self.fetch_image(
                point_id=point_id,
                lat=lat,
                lon=lon,
                heading=int(heading),
                out_dir=out_dir,
            )
            if img is not None:
                images.append(img)
        return images

    def _fixture_image(
        self,
        point_id: str,
        lat: float,
        lon: float,
        heading: int,
        out_dir: Path,
    ) -> StreetViewImage:
        images_dir = self.fixtures_dir / "images"
        candidates = [
            images_dir / f"sv_{point_id}_{heading}.jpg",
            images_dir / f"sv_70115_{point_id}_{heading}.jpg",
            images_dir / f"sv_{point_id}_0.jpg",
            images_dir / "sv_empty_0.jpg",
        ]
        # Prefer zip-prefixed fixtures used by default sample ids a/b/empty
        preferred = images_dir / f"sv_70115_{point_id}_{heading}.jpg"
        if preferred.exists():
            src = preferred
        else:
            src = next((c for c in candidates if c.exists()), None)
            if src is None:
                # Deterministic empty placeholder from hash
                src = images_dir / "sv_empty_0.jpg"

        out_path = out_dir / f"{point_id}_{heading}.jpg"
        if src and src.exists():
            out_path.write_bytes(src.read_bytes())
        else:
            # Last resort: tiny valid JPEG bytes
            out_path.write_bytes(_minimal_jpeg())

        return StreetViewImage(
            point_id=point_id,
            lat=lat,
            lon=lon,
            heading=heading,
            path=out_path,
            source="fixture",
            meta=StreetViewMeta(status="OK", lat=lat, lon=lon, pano_id="fixture"),
        )


def _minimal_jpeg() -> bytes:
    """1x1 pixel JPEG if fixtures are missing."""
    # Precomputed minimal JPEG
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c"
        "1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d"
        "0d1832211c2132323232323232323232323232323232323232323232323232323232"
        "323232323232323232323232323232323232323232ffc00011080001000103011100"
        "02110311ffc4001f0000010501010101010100000000000000000102030405060708"
        "090a0bffc400b5100002010303020403050504040000017d01020300041105122131"
        "06415161071871132132411481a1b1c109233352f0156272d10a162434e125f11718"
        "191a262728292a35363738393a434445464748494a535455565758595a6364656667"
        "68696a737475767778797a82838485868788898a92939495969798999aa2a3a4a5a6"
        "a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3"
        "e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f01000301010101010101010100"
        "00000000000102030405060708090a0bffc400b51100020102040403040705040400"
        "01027700020102031104052131061241510761711322328108144191a1b1c1092335"
        "52f0156272d10a162434e125f11718191a262728292a35363738393a434445464748"
        "494a535455565758595a636465666768696a737475767778797a8283848586878889"
        "8a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7"
        "c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8f9faffda000c"
        "03010002110311003f00bf80001ffd9"
    )


def content_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

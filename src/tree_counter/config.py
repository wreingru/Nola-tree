"""Runtime configuration from environment and CLI flags."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root: .../Nola-tree (parent of src/)
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

DEFAULT_ZIP = "70115"
DEFAULT_HEADINGS = (0, 90, 180, 270)
DEFAULT_DETECTOR = "opencv"


@dataclass(frozen=True)
class Settings:
    google_maps_api_key: str | None
    detector: str
    dry_run: bool
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    fixtures_dir: Path = FIXTURES_DIR
    artifacts_dir: Path = ARTIFACTS_DIR

    @property
    def has_maps_key(self) -> bool:
        return bool(self.google_maps_api_key)


def load_settings(*, dry_run: bool = False, detector: str | None = None) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("GOOGLE_MAPS_API_KEY") or None
    det = (detector or os.getenv("TREE_DETECTOR") or DEFAULT_DETECTOR).lower()
    return Settings(
        google_maps_api_key=key,
        detector=det,
        dry_run=dry_run,
    )

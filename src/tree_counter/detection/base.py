"""Pluggable tree detector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Detection:
    x: float
    y: float
    width: float
    height: float
    confidence: float
    label: str = "tree"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def cx(self) -> float:
        return self.x + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.height / 2.0


class TreeDetector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, image_path: Path) -> list[Detection]:
        raise NotImplementedError


def get_detector(kind: str = "opencv", **kwargs: Any) -> TreeDetector:
    kind = (kind or "opencv").lower()
    if kind in {"opencv", "heuristic", "offline"}:
        from tree_counter.detection.opencv_heuristic import OpenCVHeuristicDetector

        return OpenCVHeuristicDetector(**kwargs)
    if kind in {"vision", "google_vision", "vision_api"}:
        from tree_counter.detection.vision_api import VisionAPIDetector

        return VisionAPIDetector(**kwargs)
    raise ValueError(f"Unknown detector '{kind}'. Use 'opencv' or 'vision'.")

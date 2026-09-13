"""Cross-heading detection deduplication for a single sample point."""

from __future__ import annotations

from dataclasses import dataclass

from tree_counter.detection.base import Detection


@dataclass
class HeadingDetection:
    heading: int
    detection: Detection
    image_width: float = 640.0
    image_height: float = 480.0


def dedupe_cross_heading(
    items: list[HeadingDetection],
    *,
    x_bin: float = 0.15,
    y_bin: float = 0.20,
) -> list[HeadingDetection]:
    """Collapse detections that likely show the same tree across headings.

    Uses coarse normalized position bins. Opposite headings (diff ~180°) that
    land in similar relative side-of-frame bins are treated as candidates for
    the same roadside tree when both are near the frame edge.
    """
    if not items:
        return []

    # Greedy: keep highest confidence, suppress neighbors in similar bins
    ordered = sorted(items, key=lambda h: h.detection.confidence, reverse=True)
    kept: list[HeadingDetection] = []
    for cand in ordered:
        if any(_same_tree(cand, k, x_bin=x_bin, y_bin=y_bin) for k in kept):
            continue
        kept.append(cand)
    return kept


def _same_tree(
    a: HeadingDetection,
    b: HeadingDetection,
    *,
    x_bin: float,
    y_bin: float,
) -> bool:
    if a.heading == b.heading:
        # Same frame: use IoU-ish center proximity
        ax = a.detection.cx / max(a.image_width, 1)
        ay = a.detection.cy / max(a.image_height, 1)
        bx = b.detection.cx / max(b.image_width, 1)
        by = b.detection.cy / max(b.image_height, 1)
        return abs(ax - bx) < x_bin and abs(ay - by) < y_bin

    heading_delta = abs(a.heading - b.heading) % 360
    heading_delta = min(heading_delta, 360 - heading_delta)
    # Adjacent headings (90°) or opposite (180°): compare vertical band + side
    ax = a.detection.cx / max(a.image_width, 1)
    ay = a.detection.cy / max(a.image_height, 1)
    bx = b.detection.cx / max(b.image_width, 1)
    by = b.detection.cy / max(b.image_height, 1)
    if abs(ay - by) > y_bin:
        return False
    if heading_delta >= 150:
        # Opposite views: left side <-> right side swap
        return abs((1.0 - ax) - bx) < x_bin * 1.5
    if heading_delta >= 60:
        # Adjacent: similar horizontal third
        return abs(ax - bx) < x_bin * 1.2
    return abs(ax - bx) < x_bin and abs(ay - by) < y_bin

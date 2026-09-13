"""Offline OpenCV color/shape heuristic tree detector.

Works on fixture images with green canopies and on many real Street View
frames where foliage is visible (best-effort; not a trained model).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from tree_counter.detection.base import Detection, TreeDetector


class OpenCVHeuristicDetector(TreeDetector):
    name = "opencv_heuristic"

    def __init__(
        self,
        *,
        min_area: int = 400,
        max_area_frac: float = 0.35,
        min_confidence: float = 0.25,
    ) -> None:
        self.min_area = min_area
        self.max_area_frac = max_area_frac
        self.min_confidence = min_confidence

    def detect(self, image_path: Path) -> list[Detection]:
        img = cv2.imread(str(image_path))
        if img is None:
            return []
        h, w = img.shape[:2]
        max_area = int(h * w * self.max_area_frac)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Two green ranges (bright foliage + darker canopy)
        mask1 = cv2.inRange(hsv, (35, 40, 40), (90, 255, 255))
        mask2 = cv2.inRange(hsv, (35, 25, 25), (95, 200, 180))
        mask = cv2.bitwise_or(mask1, mask2)

        # Suppress lower road band (bottom ~35%)
        mask[int(h * 0.65) :, :] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / max(bh, 1)
            if aspect > 3.5 or aspect < 0.2:
                continue
            # Prefer mid-upper image (street trees along sides / canopy)
            cy = y + bh / 2.0
            if cy > h * 0.75:
                continue
            circularity = 4 * np.pi * area / max((cv2.arcLength(cnt, True) ** 2), 1.0)
            conf = float(np.clip(0.35 + 0.4 * circularity + 0.15 * (area / max_area), 0, 1))
            if conf < self.min_confidence:
                continue
            detections.append(
                Detection(
                    x=float(x),
                    y=float(y),
                    width=float(bw),
                    height=float(bh),
                    confidence=conf,
                    label="tree",
                    extra={"area": float(area), "circularity": float(circularity)},
                )
            )

        return _nms(detections, iou_thresh=0.4)


def _nms(dets: list[Detection], iou_thresh: float = 0.4) -> list[Detection]:
    if not dets:
        return []
    ordered = sorted(dets, key=lambda d: d.confidence, reverse=True)
    keep: list[Detection] = []
    while ordered:
        best = ordered.pop(0)
        keep.append(best)
        ordered = [d for d in ordered if _iou(best, d) < iou_thresh]
    return keep


def _iou(a: Detection, b: Detection) -> float:
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0

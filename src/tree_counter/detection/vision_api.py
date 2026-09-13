"""Optional Google Cloud Vision API adapter (label + object localization).

Requires google-cloud-vision and credentials via GOOGLE_APPLICATION_CREDENTIALS.
Not installed by default — import fails gracefully with a clear error.
"""

from __future__ import annotations

from pathlib import Path

from tree_counter.detection.base import Detection, TreeDetector

TREE_LIKE = {
    "tree",
    "plant",
    "woody plant",
    "vegetation",
    "palm tree",
    "oak",
    "willow",
}


class VisionAPIDetector(TreeDetector):
    name = "vision_api"

    def __init__(self, *, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence
        try:
            from google.cloud import vision  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Vision API detector requires google-cloud-vision. "
                "Install it separately and set GOOGLE_APPLICATION_CREDENTIALS, "
                "or use --detector opencv (default)."
            ) from exc
        self._vision = vision
        self._client = vision.ImageAnnotatorClient()

    def detect(self, image_path: Path) -> list[Detection]:
        content = image_path.read_bytes()
        image = self._vision.Image(content=content)
        response = self._client.object_localization(image=image)
        detections: list[Detection] = []
        for obj in response.localized_object_annotations:
            name = (obj.name or "").lower()
            score = float(obj.score or 0.0)
            if score < self.min_confidence:
                continue
            if not any(t in name for t in TREE_LIKE):
                continue
            verts = obj.bounding_poly.normalized_vertices
            xs = [v.x for v in verts]
            ys = [v.y for v in verts]
            # Vision returns normalized coords; store as 0-1 box (caller may scale)
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            detections.append(
                Detection(
                    x=x0,
                    y=y0,
                    width=x1 - x0,
                    height=y1 - y0,
                    confidence=score,
                    label=obj.name or "tree",
                    extra={"normalized": True},
                )
            )
        return detections

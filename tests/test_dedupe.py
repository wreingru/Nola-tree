from tree_counter.dedupe import HeadingDetection, dedupe_cross_heading
from tree_counter.detection.base import Detection


def _hd(heading: int, x: float, y: float, conf: float = 0.8) -> HeadingDetection:
    return HeadingDetection(
        heading=heading,
        detection=Detection(x=x, y=y, width=40, height=50, confidence=conf),
        image_width=640,
        image_height=480,
    )


def test_dedupe_same_heading_overlap():
    items = [_hd(0, 100, 100, 0.9), _hd(0, 105, 102, 0.7)]
    kept = dedupe_cross_heading(items)
    assert len(kept) == 1


def test_dedupe_keeps_distinct():
    items = [_hd(0, 50, 100), _hd(0, 500, 100)]
    kept = dedupe_cross_heading(items)
    assert len(kept) == 2

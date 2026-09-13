from pathlib import Path

from tree_counter.detection.opencv_heuristic import OpenCVHeuristicDetector

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "data" / "fixtures" / "images"


def test_opencv_finds_trees_on_fixture():
    det = OpenCVHeuristicDetector(min_area=200)
    found = det.detect(IMG / "sv_70115_a_0.jpg")
    assert len(found) >= 1


def test_opencv_empty_image():
    det = OpenCVHeuristicDetector()
    found = det.detect(IMG / "sv_empty_0.jpg")
    assert found == []

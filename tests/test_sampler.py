from pathlib import Path

from tree_counter.sampling.sampler import load_points, sample_for_zip

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def test_load_csv_and_geojson():
    csv_pts = load_points(FIXTURES / "sample_points.csv")
    gj_pts = load_points(FIXTURES / "sample_points.geojson")
    assert len(csv_pts) == 3
    assert len(gj_pts) == 3
    assert {p.id for p in csv_pts} == {p.id for p in gj_pts}


def test_sample_for_zip_70115():
    pts = sample_for_zip("70115")
    assert pts
    assert all(p.zip == "70115" for p in pts)

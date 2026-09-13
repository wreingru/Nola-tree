from tree_counter.city_profile import get_profile
from tree_counter.inventory.compare import compare_sample_to_inventory
from tree_counter.inventory.gis import load_gis_cache


def test_zip_benchmark_70115():
    profile = get_profile("nola")
    assert profile.zip_benchmark("70115") == 13757


def test_comparison_label_and_caveats():
    gis = load_gis_cache()
    result = compare_sample_to_inventory(
        zip_code="70115",
        sample_points=3,
        images_analyzed=10,
        raw_detections=12,
        deduped_detections=8,
        sample_coords=[(29.9260, -90.1080)],
        gis_points=gis,
    )
    d = result.to_dict()
    assert d["comparison_label"] == "sample≠census"
    assert d["inventory_zip_sites_2019"] == 13757
    assert len(d["caveats"]) >= 4
    if gis:
        assert d["nearby_inventory_matches"] >= 1

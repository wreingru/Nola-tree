from pathlib import Path

from tree_counter.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_dry_run_writes_reports(tmp_path: Path):
    out = tmp_path / "artifacts"
    payload = run_pipeline(
        zip_code="70115",
        dry_run=True,
        detector_name="opencv",
        artifacts_dir=out,
        fetch_gis=True,
    )
    assert (out / "report.json").exists()
    assert (out / "report.md").exists()
    assert payload["run"]["dry_run"] is True
    assert payload["comparison"]["comparison_label"] == "sample≠census"
    assert payload["comparison"]["images_analyzed"] > 0
    assert payload["comparison"]["deduped_detections"] >= 1
    images = list((out / "images").glob("*.jpg"))
    assert images
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "sample≠census" in md or "sample" in md.lower()
    assert "70115" in md

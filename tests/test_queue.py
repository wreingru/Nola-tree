"""Tests for agent handoff queue claim/complete/idempotency and St. Claude unit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tree_counter import queue as aq
from tree_counter.sampling.sampler import load_points


@pytest.fixture()
def qpath(tmp_path: Path) -> Path:
    root = tmp_path / "agent_queue"
    root.mkdir()
    (root / "summaries").mkdir()
    return root / "queue.json"


def test_init_seeds_st_claude(qpath: Path):
    data = aq.init_queue(queue_path=qpath, force=True)
    ids = [u["id"] for u in data["units"]]
    assert "st-claude-poland-spain" in ids
    assert ids[0] == "st-claude-poland-spain" or data["units"][0]["priority"] == 1
    unit = next(u for u in data["units"] if u["id"] == "st-claude-poland-spain")
    assert unit["kind"] == "street_segment"
    assert unit["status"] == "pending"
    assert (qpath.parent / "PROGRESS.md").exists()


def test_claim_next_and_complete_idempotent(qpath: Path):
    aq.init_queue(queue_path=qpath, force=True)
    first = aq.claim_next(queue_path=qpath)
    assert first is not None
    assert first.status == "in_progress"
    assert first.id == "st-claude-poland-spain"

    # Second claim should get a different pending unit
    second = aq.claim_next(queue_path=qpath)
    assert second is not None
    assert second.id != first.id
    assert second.status == "in_progress"

    summary = {
        "unit_id": first.id,
        "deduped_detections": 3,
        "sample_points_used": 2,
        "errors": [],
    }
    done, next_id = aq.complete_unit(first.id, summary=summary, queue_path=qpath)
    assert done.status == "complete"
    assert done.summary_path is not None
    assert (qpath.parent / "summaries" / f"{first.id}.json").exists()

    # Idempotent complete
    done2, _ = aq.complete_unit(first.id, summary=summary, queue_path=qpath)
    assert done2.status == "complete"

    st = aq.status_summary(queue_path=qpath)
    assert first.id in st["by_status"]["complete"]
    assert st["counts"]["complete"] >= 1


def test_claim_empty_queue(qpath: Path):
    aq.init_queue(queue_path=qpath, force=True)
    data = aq.load_queue(qpath)
    for u in data["units"]:
        u["status"] = "complete"
    aq.save_queue(data, qpath)
    assert aq.claim_next(queue_path=qpath) is None


def test_unit_brief_is_compact(qpath: Path):
    aq.init_queue(queue_path=qpath, force=True)
    unit = aq.get_unit("st-claude-poland-spain", qpath)
    assert unit is not None
    brief = aq.unit_brief(unit)
    text = json.dumps(brief) + aq.brief_markdown(brief)
    # Rough token proxy: ~4 chars/token → 2k tokens ≈ 8k chars
    assert len(text) < 8000
    assert brief["unit_id"] == "st-claude-poland-spain"
    assert "run_dry" in brief["commands"]


def test_load_st_claude_fixture_points():
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "data" / "fixtures" / "st_claude_poland_spain.csv"
    gj_path = root / "data" / "fixtures" / "st_claude_poland_spain.geojson"
    assert csv_path.exists()
    pts = load_points(csv_path)
    assert len(pts) == 10
    assert pts[0].id == "sc01"
    assert pts[-1].id == "sc10"
    # Poland (east) → Spain (west): longitude decreases
    assert pts[0].lon > pts[-1].lon
    assert {p.zip for p in pts} == {"70117", "70116"}
    gj = load_points(gj_path)
    assert len(gj) == 10
    assert {p.id for p in pts} == {p.id for p in gj}


def test_st_claude_unit_in_default_seed():
    units = aq.default_seed_units()
    sc = next(u for u in units if u.id == "st-claude-poland-spain")
    assert sc.sample_points_path.endswith("st_claude_poland_spain.csv")
    assert sc.sample_limit <= 12
    assert sc.endpoints["start"]["lat"] == pytest.approx(29.96438, abs=1e-4)
    assert sc.endpoints["end"]["lon"] == pytest.approx(-90.05346, abs=1e-4)

"""End-to-end integration test for Rosetta Board ADK Agent Pipeline."""

from pathlib import Path
import pytest

from app.agent import ingest_storyboard_file, check_revision_deltas, root_agent
from app.config import SAMPLES_DIR
from app.tools.clickhouse_db import db


def test_agent_structure():
    """Verify ADK root agent configuration."""
    assert root_agent.name == "rosetta_board_agent"
    assert len(root_agent.tools) >= 5


def test_end_to_end_ingestion_pipeline():
    """Test full pipeline ingestion of Scene 42 V1 and Scene 42 V2."""
    pdf_v1 = SAMPLES_DIR / "Scene_42_V1.pdf"
    pdf_v2 = SAMPLES_DIR / "Scene_42_V2.pdf"

    assert pdf_v1.exists(), "Scene_42_V1.pdf must exist"
    assert pdf_v2.exists(), "Scene_42_V2.pdf must exist"

    # Step 1: Ingest Scene 42 V1
    res_v1 = ingest_storyboard_file(str(pdf_v1), scene="42", version="v1")
    assert res_v1["status"] == "success"
    assert res_v1["panels_processed"] >= 3
    assert Path(res_v1["csv_export_path"]).exists()
    assert Path(res_v1["pdf_export_path"]).exists()

    # Verify panels stored in database
    v1_panels = db.get_panels_for_scene("42", version="v1")
    assert len(v1_panels) >= 3

    # PRD Success Metric 3: Verify at least one implied visual prop detected
    has_implied_prop = any(len(p.props_implied_visual) > 0 for p in v1_panels)
    assert has_implied_prop, "Must identify at least one visual prop drawn in sketch"

    # Step 2: Ingest Scene 42 V2 (Revision)
    res_v2 = ingest_storyboard_file(str(pdf_v2), scene="42", version="v2")
    assert res_v2["status"] == "success"
    assert res_v2["panels_processed"] >= 3

    # PRD Feature 3: Verify 1st AD summary alerts generated
    alerts = res_v2["1st_ad_alerts"]
    assert len(alerts) > 0, "Must generate 1st AD revision alerts between V1 and V2"

    # Step 3: Run explicit revision comparison
    diff = check_revision_deltas(scene="42", old_version="v1", new_version="v2")
    assert diff["status"] == "success"
    assert len(diff["ad_alerts"]) > 0

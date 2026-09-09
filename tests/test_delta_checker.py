"""Unit tests for Revision & Delta Checker Agent."""

import pytest
from app.models import NormalizedPanel
from app.tools.delta_checker import DeltaChecker


@pytest.fixture
def checker():
    return DeltaChecker()


def test_delta_checker_detects_prop_and_framing_changes(checker):
    """Test revision comparison generates 1st AD alerts for added props and changed framing."""
    old_panels = [
        NormalizedPanel(
            panel_id="S42_V1_1", scene="42", shot="1", panel_number=1, version="v1",
            camera_angle="High Angle", shot_size="Medium Close Up",
            props=["Coffee Cup"], props_implied_visual=["Coffee Cup"],
        ),
        NormalizedPanel(
            panel_id="S42_V1_2", scene="42", shot="2", panel_number=1, version="v1",
            camera_angle="Eye Level", shot_size="Extreme Close Up",
            props=[], props_implied_visual=[],
        ),
        NormalizedPanel(
            panel_id="S42_V1_3", scene="42", shot="3", panel_number=1, version="v1",
            camera_angle="Dutch Angle", shot_size="Wide Shot",
            props=["Getaway Car"], vfx_tags=["Pyrotechnics / FX Explosions"],
        ),
    ]

    new_panels = [
        # Shot 1: Now requires a prop gun
        NormalizedPanel(
            panel_id="S42_V2_1", scene="42", shot="1", panel_number=1, version="v2",
            camera_angle="High Angle", shot_size="Medium Close Up",
            props=["Coffee Cup", "Prop Gun"], props_implied_visual=["Prop Gun"],
        ),
        # Shot 2: Framing changed from Extreme Close Up to Close Up
        NormalizedPanel(
            panel_id="S42_V2_2", scene="42", shot="2", panel_number=1, version="v2",
            camera_angle="Eye Level", shot_size="Close Up",  # Changed!
            props=[], props_implied_visual=[],
        ),
        # Shot 3: Deleted!
        # Shot 4: Added!
        NormalizedPanel(
            panel_id="S42_V2_4", scene="42", shot="4", panel_number=1, version="v2",
            camera_angle="Bird's Eye View", shot_size="Extreme Wide Shot",
            props=["Helicopter"], vfx_tags=["Chroma Key / Green Screen"],
        ),
    ]

    report = checker.compare_revisions(
        scene="42",
        old_version="v1",
        new_version="v2",
        old_panels=old_panels,
        new_panels=new_panels,
    )

    # Verify structural counts
    assert report.total_shots_old == 3
    assert report.total_shots_new == 3
    assert "4" in report.shots_added
    assert "3" in report.shots_deleted
    assert "1" in report.shots_modified
    assert "2" in report.shots_modified

    # Verify 1st AD Summary Alerts (PRD Feature 3 requirement)
    alert_text = " ".join(report.ad_alerts)
    assert "Shot 1 now requires a prop 'Prop Gun'" in alert_text or "prop gun" in alert_text.lower()
    assert "Shot 2 changed from Extreme Close Up to Close Up" in alert_text
    assert "Shot 4 added" in alert_text
    assert "Shot 3 has been removed" in alert_text


def test_unchanged_revision(checker):
    """Verify unchanged shots report UNCHANGED status without spurious alerts."""
    panel = NormalizedPanel(
        panel_id="S10_V1_1", scene="10", shot="1", panel_number=1, version="v1",
        camera_angle="Eye Level", shot_size="Medium Shot",
        props=["Briefcase"],
    )
    report = checker.compare_revisions(
        scene="10",
        old_version="v1",
        new_version="v2",
        old_panels=[panel],
        new_panels=[panel],
    )
    assert len(report.ad_alerts) == 0
    assert len(report.shots_modified) == 0
    assert report.deltas[0].status == "UNCHANGED"

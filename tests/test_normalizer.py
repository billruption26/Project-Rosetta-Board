"""Unit tests for Studio Taxonomy Normalizer Agent."""

import pytest
from app.models import RawPanelExtraction
from app.tools.taxonomy_normalizer import TaxonomyNormalizer


@pytest.fixture
def normalizer():
    return TaxonomyNormalizer()


def test_camera_angle_normalization(normalizer):
    """Verify camera angle shorthand is correctly mapped to standard terms."""
    test_cases = [
        ("HA", "High Angle"),
        ("HIGH ANGLE", "High Angle"),
        ("LA", "Low Angle"),
        ("LOW ANGLE", "Low Angle"),
        ("DUTCH", "Dutch Angle"),
        ("DUTCH ANGLE", "Dutch Angle"),
        ("canted", "Dutch Angle"),
        ("EYE", "Eye Level"),
        ("BIRD", "Bird's Eye View"),
        ("bird's eye", "Bird's Eye View"),
        ("TOP DOWN", "Bird's Eye View"),
        ("WORM", "Worm's Eye View"),
    ]
    correct = 0
    for raw, expected in test_cases:
        norm, conf, flag = normalizer.normalize_camera_angle(raw)
        assert norm == expected, f"Failed mapping '{raw}': got '{norm}', expected '{expected}'"
        assert conf >= 0.8
        correct += 1

    # PRD Metric: > 85% accuracy
    accuracy = correct / len(test_cases)
    assert accuracy >= 0.85


def test_shot_size_normalization(normalizer):
    """Verify shot size abbreviations are mapped to studio schema."""
    test_cases = [
        ("ECU", "Extreme Close Up"),
        ("XCU", "Extreme Close Up"),
        ("Extreme CU", "Extreme Close Up"),
        ("CU", "Close Up"),
        ("Close Up", "Close Up"),
        ("MCU", "Medium Close Up"),
        ("Medium CU", "Medium Close Up"),
        ("BUST", "Medium Close Up"),
        ("MS", "Medium Shot"),
        ("Cowboy", "Cowboy Shot"),
        ("FS", "Full Shot"),
        ("WS", "Wide Shot"),
        ("LS", "Wide Shot"),
        ("EWS", "Extreme Wide Shot"),
        ("XLS", "Extreme Wide Shot"),
        ("OTS", "Over The Shoulder"),
        ("O/S", "Over The Shoulder"),
        ("POV", "Point of View"),
        ("TWO SHOT", "Two Shot"),
        ("2-SHOT", "Two Shot"),
    ]
    correct = 0
    for raw, expected in test_cases:
        norm, conf, flag = normalizer.normalize_shot_size(raw)
        assert norm == expected, f"Failed mapping '{raw}': got '{norm}', expected '{expected}'"
        assert conf >= 0.85
        correct += 1

    accuracy = correct / len(test_cases)
    assert accuracy >= 0.85


def test_vfx_cue_normalization(normalizer):
    """Verify raw VFX tags are standardized."""
    cues = ["green screen backdrop", "explosion with debris", "safety wire removal", "set extension"]
    normalized = normalizer.normalize_vfx_cues(cues)
    assert "Chroma Key / Green Screen" in normalized
    assert "Pyrotechnics / FX Explosions" in normalized
    assert "Rig / Wire Removal" in normalized
    assert "Digital Matte Painting" in normalized


def test_unresolvable_anomaly_flagging(normalizer):
    """Verify unresolvable abbreviations are flagged for human review."""
    norm, conf, flag = normalizer.normalize_shot_size("XYZZY_UNKNOWN_CODE")
    assert flag is not None
    assert "Non-standard shot size abbreviation" in flag
    assert conf < 0.75

    raw_panel = RawPanelExtraction(
        scene="10",
        shot="1",
        panel_number=1,
        camera_angle_raw="STRANGE_ANOMALOUS_ANGLE",
        shot_size_raw="WEIRD_SHOT_SIZE",
    )
    panel = normalizer.normalize_panel(raw_panel)
    assert panel.flagged_for_review is True
    assert len(panel.review_reasons) >= 1

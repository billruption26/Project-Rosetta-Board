"""Unit tests for Production Exporter Engine."""

from pathlib import Path
import pandas as pd
import pytest

from app.models import NormalizedPanel
from app.tools.exporter import StoryboardExporter


@pytest.fixture
def sample_panels():
    return [
        NormalizedPanel(
            panel_id="S42_V1_1", scene="42", shot="1", panel_number=1, version="v1",
            dialogue="Where is the package?",
            action_notes="John talks to teller.",
            camera_angle="High Angle", shot_size="Medium Close Up", camera_movement="Static",
            characters=["John", "Teller"],
            props=["Coffee Cup"], props_implied_visual=["Coffee Cup"],
            vfx_tags=[],
        ),
        NormalizedPanel(
            panel_id="S42_V1_2", scene="42", shot="2", panel_number=1, version="v1",
            dialogue="I told you, it hasn't arrived.",
            action_notes="Teller nervous.",
            camera_angle="Eye Level", shot_size="Extreme Close Up", camera_movement="Push In",
            characters=["Teller"],
            props=[], props_implied_visual=[],
            vfx_tags=[],
        ),
    ]


def test_csv_export(sample_panels, tmp_path):
    """Test CSV generation conforms to production scheduling schemas."""
    exporter = StoryboardExporter(export_dir=tmp_path)
    csv_file = exporter.export_csv(sample_panels, filename="test_shotlist.csv")

    assert Path(csv_file).exists()
    df = pd.read_csv(csv_file)
    assert len(df) == 2
    assert "Scene" in df.columns
    assert "Shot" in df.columns
    assert "Shot Size" in df.columns
    assert "Camera Angle" in df.columns
    assert "Props (All)" in df.columns
    assert "Implied Visual Props" in df.columns
    assert df.iloc[0]["Implied Visual Props"] == "Coffee Cup"


def test_pdf_grid_export(sample_panels, tmp_path):
    """Test Grid-Format PDF contact sheet generation."""
    exporter = StoryboardExporter(export_dir=tmp_path)
    pdf_file = exporter.export_grid_pdf(sample_panels, filename="test_grid.pdf")

    assert Path(pdf_file).exists()
    assert Path(pdf_file).stat().st_size > 1000  # Non-trivial PDF size

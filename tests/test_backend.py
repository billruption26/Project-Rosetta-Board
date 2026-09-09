"""Integration and unit tests for Vertex AI Agent Engine Backend."""

import pytest
from fastapi.testclient import TestClient

from app.agent_engine import agent_engine, RosettaBoardAgentEngine
from app.backend.server import create_app
from app.tools.clickhouse_db import db


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_check(client):
    """Verify backend health endpoint reports healthy status and agent_engines framework."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "agent_engines" in data["framework"]
    assert "database_backend" in data


def test_taxonomy_endpoint(client):
    """Verify taxonomy endpoint exposes the master studio rules."""
    response = client.get("/api/storyboards/taxonomy")
    assert response.status_code == 200
    data = response.json()
    assert "camera_angles" in data
    assert "shot_sizes" in data
    assert "vfx_categories" in data
    assert "ECU" in data["shot_sizes"]


def test_prop_lookup_endpoint(client):
    """Verify Parallel API prop intelligence lookup endpoint."""
    response = client.get("/api/props/lookup?item_name=1967+Mustang")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    prop_info = data["prop_info"]
    assert "Mustang" in prop_info["item_name"]
    assert prop_info["daily_rental_est"] > 0
    assert prop_info["category"] == "Picture Vehicle"


def test_storyboards_scenes_endpoint(client):
    """Verify scenes listing endpoint."""
    response = client.get("/api/storyboards/scenes")
    assert response.status_code == 200
    scenes = response.json()
    assert isinstance(scenes, list)
    if scenes:
        assert "42" in scenes


def test_revision_comparison_endpoint(client):
    """Verify revision comparison endpoint returns 1st AD alerts."""
    scenes = db.get_all_scenes()
    if "42" in scenes:
        req_data = {
            "scene": "42",
            "old_version": "v1",
            "new_version": "v2",
        }
        response = client.post("/api/storyboards/compare", json=req_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["ad_alerts"]) > 0


def test_export_endpoint(client):
    """Verify export endpoint produces CSV."""
    scenes = db.get_all_scenes()
    if "42" in scenes:
        req_data = {
            "scene": "42",
            "version": "v1",
            "format": "csv",
        }
        response = client.post("/api/storyboards/export", json=req_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "file_path" in data


def test_agent_engine_class_methods():
    """Verify RosettaBoardAgentEngine domain methods."""
    engine = RosettaBoardAgentEngine()
    prop_res = engine.lookup_prop("Prop Gun")
    assert prop_res["status"] == "success"
    assert prop_res["prop_info"]["daily_rental_est"] > 0

    scenes = db.get_all_scenes()
    if "42" in scenes:
        shotlist = engine.get_shotlist("42", "v1")
        assert len(shotlist) >= 3

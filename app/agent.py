"""Project Rosetta Board Root ADK Agent & Workflow Orchestration.

An autonomous multi-agent system built on the Google Cloud Agent Development Kit (ADK)
for storyboard ingestion, multimodal vision extraction, taxonomy normalization,
revision delta checking, Parallel API prop intelligence, and ClickHouse persistence.
"""

from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.apps import App

from app.config import config
from app.models import NormalizedPanel, RawPanelExtraction
from app.tools.clickhouse_db import db
from app.tools.delta_checker import DeltaChecker
from app.tools.exporter import exporter
from app.tools.imagen_tool import concept_renderer
from app.tools.parallel_intel import parallel_client
from app.tools.pdf_processor import storyboard_processor
from app.tools.taxonomy_normalizer import TaxonomyNormalizer
from app.tools.vision_extractor import vision_extractor

normalizer = TaxonomyNormalizer()
delta_checker = DeltaChecker()


# ==========================================
# ADK Tool Definitions
# ==========================================

def ingest_storyboard_file(file_path: str, scene: str, version: str) -> Dict[str, Any]:
    """Ingests a storyboard PDF or image, runs multimodal extraction, normalizes nomenclature,
    checks revision deltas against prior versions, queries Parallel API prop pricing,
    and commits the structured shot list to ClickHouse.

    Args:
        file_path: Absolute or relative path to the storyboard PDF or image file.
        scene: Scene identifier, e.g. '42' or 'Scene 42'.
        version: Version identifier, e.g. 'v1' or 'v2'.

    Returns:
        Summary dict containing parsed panels count, delta alerts, and export paths.
    """
    try:
        # 1. Segment file into panels
        panel_refs = storyboard_processor.process_file(file_path, scene_name=f"scene_{scene}_{version}")

        # 2. Extract multimodal features & implied props
        normalized_panels: List[NormalizedPanel] = []
        for idx, (img_path, page_num, panel_idx) in enumerate(panel_refs):
            raw = vision_extractor.extract_panel(
                image_path=img_path,
                scene_hint=scene,
                shot_hint=str(idx + 1),
                panel_number=panel_idx,
            )
            raw.page_number = page_num
            # 3. Normalize against studio taxonomy
            norm_panel = normalizer.normalize_panel(raw, version=version)
            
            # 4. If napkin scribble / low fidelity, trigger concept sketch
            if raw.visual_fidelity_score < 0.6:
                render_path = concept_renderer.render_concept_sketch(norm_panel)
                norm_panel.concept_render_path = render_path

            normalized_panels.append(norm_panel)

        # 5. Enrich with Parallel API Prop Intelligence
        normalized_panels = parallel_client.enrich_panels(normalized_panels)

        # 6. Check for Revisions if prior version exists in database
        prior_versions = db.get_available_versions(scene)
        revision_alerts: List[str] = []
        if prior_versions:
            # Pick latest previous version (e.g. v1 if current is v2)
            prev_ver = [v for v in prior_versions if v.lower() != version.lower()]
            if prev_ver:
                old_ver = prev_ver[-1]
                old_panels = db.get_panels_for_scene(scene, version=old_ver)
                report = delta_checker.compare_revisions(
                    scene=scene,
                    old_version=old_ver,
                    new_version=version,
                    old_panels=old_panels,
                    new_panels=normalized_panels,
                )
                db.record_revision_report(report)
                revision_alerts = report.ad_alerts

        # 7. Commit to ClickHouse / analytical database
        commit_res = db.insert_panels(normalized_panels)

        # 8. Generate standardized exports
        csv_path = exporter.export_csv(normalized_panels)
        pdf_path = exporter.export_grid_pdf(normalized_panels)

        return {
            "status": "success",
            "scene": scene,
            "version": version,
            "panels_processed": len(normalized_panels),
            "database_backend": commit_res.get("backend", "analytical_store"),
            "1st_ad_alerts": revision_alerts,
            "csv_export_path": csv_path,
            "pdf_export_path": pdf_path,
            "panels": [p.model_dump() for p in normalized_panels],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_revision_deltas(scene: str, old_version: str, new_version: str) -> Dict[str, Any]:
    """Compares two existing storyboard revisions for a scene and produces 1st AD summary alerts.

    Args:
        scene: Scene number or name, e.g. '42'.
        old_version: Prior version identifier, e.g. 'v1'.
        new_version: Current version identifier, e.g. 'v2'.

    Returns:
        Dict detailing added, deleted, and modified shots, plus high-priority AD alerts.
    """
    old_panels = db.get_panels_for_scene(scene, version=old_version)
    new_panels = db.get_panels_for_scene(scene, version=new_version)

    if not old_panels or not new_panels:
        return {
            "status": "error",
            "message": f"Could not find panels for both {old_version} (count={len(old_panels)}) and {new_version} (count={len(new_panels)})"
        }

    report = delta_checker.compare_revisions(
        scene=scene,
        old_version=old_version,
        new_version=new_version,
        old_panels=old_panels,
        new_panels=new_panels,
    )
    db.record_revision_report(report)

    return {
        "status": "success",
        "scene": scene,
        "old_version": old_version,
        "new_version": new_version,
        "shots_added": report.shots_added,
        "shots_deleted": report.shots_deleted,
        "shots_modified": report.shots_modified,
        "ad_alerts": report.ad_alerts,
        "deltas": [d.model_dump() for d in report.deltas],
    }


def query_scene_shotlist(scene: str, version: str) -> Dict[str, Any]:
    """Queries ClickHouse for the normalized shot list of a specific scene and version.

    Args:
        scene: Scene identifier, e.g. '42'.
        version: Version identifier, e.g. 'v1'.

    Returns:
        Dict containing the list of panels and metadata.
    """
    panels = db.get_panels_for_scene(scene, version=version)
    return {
        "status": "success",
        "scene": scene,
        "version": version,
        "total_shots": len(panels),
        "panels": [p.model_dump() for p in panels],
    }


def lookup_prop_intelligence(item_name: str) -> Dict[str, Any]:
    """Queries the Parallel API for real-time rental pricing, supplier availability,
    and replacement costs for a prop or picture vehicle.

    Args:
        item_name: Name of the prop or vehicle (e.g. '1967 Mustang', 'prop gun', 'vintage typewriter').

    Returns:
        Dict with rental rates, vendor, and availability status.
    """
    info = parallel_client.lookup_prop(item_name)
    return {
        "status": "success",
        "prop_info": info.model_dump(),
    }


def export_storyboard_shotlist(scene: str, version: str, export_format: str) -> Dict[str, Any]:
    """Generates a standardized production export (CSV or Grid PDF) for a scene version.

    Args:
        scene: Scene identifier, e.g. '42'.
        version: Version identifier, e.g. 'v1'.
        export_format: Desired format, either 'csv' or 'pdf'.

    Returns:
        Dict containing status and file path.
    """
    panels = db.get_panels_for_scene(scene, version=version)
    if not panels:
        return {"status": "error", "message": f"No panels found for Scene {scene} {version}"}

    fmt = export_format.lower().strip()
    if fmt == "csv":
        path = exporter.export_csv(panels)
        return {"status": "success", "format": "csv", "file_path": path}
    elif fmt == "pdf":
        path = exporter.export_grid_pdf(panels)
        return {"status": "success", "format": "pdf", "file_path": path}
    else:
        return {"status": "error", "message": f"Unsupported format '{export_format}'. Choose 'csv' or 'pdf'."}


# ==========================================
# Root Agent Configuration
# ==========================================

AGENT_INSTRUCTION = """You are Rosetta Board, the universal autonomous storyboard ingestion and analysis agent for feature film productions.

Your mission is to automate the extraction, nomenclature normalization, and revision tracking of storyboards for:
1. 1st Assistant Directors (identifying shots, camera angles, schedule impact, and revision alerts).
2. Art Directors & Prop Masters (tracking physical items, implied props, and rental rates).
3. Line Producers (monitoring VFX cues, budget requirements, and vehicle costs).

CAPABILITIES:
- Ingest storyboard PDFs or sketches and run multimodal analysis.
- Identify implied/drawn props that are visible in the frame even if omitted from dialogue or action text.
- Normalize varied artist shorthand (ECU, XCU, OTS, HA) to studio master nomenclature with 85%+ accuracy.
- Compare scene revisions (V1 vs V2) and proactively generate 1st AD alerts (e.g., 'Alert: Shot 4A now requires a prop gun; previously unarmed').
- Enrich high-value props with real-time market pricing via the Parallel API.
- Query and persist all data in ClickHouse.
- Export standardized production CSVs and contact sheet Grid PDFs.

When interacting with the user, be professional, concise, and structured like an experienced Hollywood 1st AD or Production Coordinator.
"""

root_agent = Agent(
    name="rosetta_board_agent",
    model=config.DEFAULT_MODEL,
    instruction=AGENT_INSTRUCTION,
    description="Universal Storyboard Ingestor & Analytical Production Agent",
    tools=[
        ingest_storyboard_file,
        check_revision_deltas,
        query_scene_shotlist,
        lookup_prop_intelligence,
        export_storyboard_shotlist,
    ],
)

# Application container matching the agent directory name 'app'
app = App(name="app", root_agent=root_agent)

"""FastAPI Backend Server for Project Rosetta Board.

Exposes REST and Streaming APIs connecting frontend clients and external production pipelines
to the Vertex AI Agent Engine (google-cloud-aiplatform[agent_engines,adk]) and ClickHouse database.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agent_engine import agent_engine
from app.config import OUTPUTS_DIR, config
from app.tools.clickhouse_db import db
from app.tools.taxonomy_normalizer import TaxonomyNormalizer


# ==========================================
# Request / Response Schemas
# ==========================================

class QueryRequest(BaseModel):
    message: str = Field(..., description="Prompt or query to the Rosetta Board agent")
    user_id: str = Field(default="crew_user", description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Optional conversational session ID")


class CompareRequest(BaseModel):
    scene: str = Field(..., description="Scene identifier, e.g. '42'")
    old_version: str = Field(..., description="Prior version, e.g. 'v1'")
    new_version: str = Field(..., description="New revision version, e.g. 'v2'")


class ExportRequest(BaseModel):
    scene: str = Field(..., description="Scene identifier")
    version: str = Field(..., description="Version identifier")
    format: str = Field(default="csv", description="'csv' or 'pdf'")


# ==========================================
# App Factory
# ==========================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Rosetta Board Backend API",
        description="Vertex AI Agent Engine & ADK multi-agent backend for storyboard ingestion, normalization, and revision tracking.",
        version="0.1.0",
    )

    # Enable CORS for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------
    # Health and Diagnostics
    # -------------------------------------------------------------
    @app.get("/healthz")
    def health_check() -> Dict[str, Any]:
        """Health check endpoint confirming Agent Engine and Database status."""
        return {
            "status": "healthy",
            "framework": "google-cloud-aiplatform[agent_engines,adk]",
            "database_backend": "clickhouse_cloud" if db.use_clickhouse else "local_sqlite",
            "multimodal_model": config.DEFAULT_MODEL,
        }

    # -------------------------------------------------------------
    # Agent Engine Query Endpoints
    # -------------------------------------------------------------
    @app.post("/api/agent/query")
    def query_agent(req: QueryRequest) -> Dict[str, Any]:
        """Invoke the Rosetta Board Agent Engine with a natural language query."""
        try:
            return agent_engine.query(
                message=req.message,
                user_id=req.user_id,
                session_id=req.session_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/agent/stream")
    def stream_agent(req: QueryRequest):
        """Stream events from the Rosetta Board Agent Engine via Server-Sent Events (SSE)."""
        def event_generator():
            try:
                for event in agent_engine.stream_query(
                    message=req.message,
                    user_id=req.user_id,
                    session_id=req.session_id,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # -------------------------------------------------------------
    # Storyboard Ingestion & Parsing
    # -------------------------------------------------------------
    @app.post("/api/storyboards/ingest")
    async def ingest_storyboard(
        file: UploadFile = File(...),
        scene: str = Form("42"),
        version: str = Form("v1"),
    ) -> Dict[str, Any]:
        """Upload and ingest a storyboard PDF or image file through the multi-agent pipeline."""
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        save_path = OUTPUTS_DIR / file.filename
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)

        result = agent_engine.ingest_storyboard(
            file_path=str(save_path),
            scene=scene,
            version=version,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result

    # -------------------------------------------------------------
    # Revision Delta Checker & 1st AD Alerts
    # -------------------------------------------------------------
    @app.post("/api/storyboards/compare")
    def compare_storyboards(req: CompareRequest) -> Dict[str, Any]:
        """Compare two storyboard revisions and return 1st AD alerts."""
        res = agent_engine.compare_revisions(
            scene=req.scene,
            old_version=req.old_version,
            new_version=req.new_version,
        )
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res

    # -------------------------------------------------------------
    # Shot List & Database Queries
    # -------------------------------------------------------------
    @app.get("/api/storyboards/scenes")
    def get_scenes() -> List[str]:
        """Get list of all indexed scenes."""
        return db.get_all_scenes()

    @app.get("/api/storyboards/versions")
    def get_versions(scene: str = Query(..., description="Scene identifier")) -> List[str]:
        """Get available versions for a scene."""
        return db.get_available_versions(scene)

    @app.get("/api/storyboards/{scene}/{version}")
    def get_shotlist(scene: str, version: str) -> List[Dict[str, Any]]:
        """Fetch normalized shot list from ClickHouse."""
        return agent_engine.get_shotlist(scene=scene, version=version)

    # -------------------------------------------------------------
    # Prop Intelligence & Taxonomy
    # -------------------------------------------------------------
    @app.get("/api/props/lookup")
    def lookup_prop(item_name: str = Query(..., description="Name of prop or vehicle")) -> Dict[str, Any]:
        """Query Parallel API live prop rental and replacement estimates."""
        return agent_engine.lookup_prop(item_name)

    @app.get("/api/storyboards/taxonomy")
    def get_taxonomy() -> Dict[str, Any]:
        """Get the master studio filmmaking nomenclature dictionary."""
        norm = TaxonomyNormalizer()
        return norm.rules

    # -------------------------------------------------------------
    # Export & Downloads
    # -------------------------------------------------------------
    @app.post("/api/storyboards/export")
    def export_storyboard(req: ExportRequest) -> Dict[str, Any]:
        """Generate standardized production CSV or Grid PDF."""
        res = agent_engine.export_shotlist(
            scene=req.scene,
            version=req.version,
            export_format=req.format,
        )
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res

    @app.get("/api/download/{filename}")
    def download_file(filename: str):
        """Download an exported CSV or Grid PDF artifact."""
        target = OUTPUTS_DIR / filename
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")

        media_type = "application/pdf" if target.suffix.lower() == ".pdf" else "text/csv"
        return FileResponse(
            path=str(target),
            filename=target.name,
            media_type=media_type,
        )

    return app


# Default ASGI application
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.backend.server:app", host="0.0.0.0", port=8000, reload=True)

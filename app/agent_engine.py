"""Vertex AI Agent Engine & Reasoning Engine Integration for Project Rosetta Board.

Leverages google-cloud-aiplatform[agent_engines,adk] to provide enterprise-grade
runtime orchestration, session management, and deployment capabilities for the
Rosetta Board ADK multi-agent pipeline.
"""

from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
import vertexai
from vertexai.agent_engines import AdkApp

from app.agent import app, root_agent
from app.config import config
from app.tools.clickhouse_db import db
from app.tools.delta_checker import DeltaChecker
from app.tools.exporter import exporter
from app.tools.parallel_intel import parallel_client
from app.tools.pdf_processor import storyboard_processor
from app.tools.taxonomy_normalizer import TaxonomyNormalizer
from app.tools.vision_extractor import vision_extractor


class RosettaBoardAgentEngine:
    """Vertex AI Agent Engine wrapper for the Rosetta Board agent pipeline.
    
    Compatible with google-cloud-aiplatform's Agent Engine runtime and Vertex AI
    Reasoning Engines deployment specifications.
    """

    def __init__(
        self,
        project: Optional[str] = None,
        location: Optional[str] = None,
        enable_tracing: bool = False,
    ):
        self.project = project or config.GCP_PROJECT
        self.location = location or config.GCP_LOCATION
        self.enable_tracing = enable_tracing

        # Initialize Vertex AI SDK if credentials/project configured
        if self.project:
            vertexai.init(project=self.project, location=self.location)

        # Initialize Vertex AI AdkApp adapter from google-cloud-aiplatform[agent_engines,adk]
        self.adk_app = AdkApp(
            app=app,
            enable_tracing=self.enable_tracing,
        )

        self.normalizer = TaxonomyNormalizer()
        self.delta_checker = DeltaChecker()

    def set_up(self):
        """Lifecycle hook invoked by Vertex AI Agent Engine on container startup."""
        self.adk_app.set_up()

    def query(
        self,
        message: str,
        user_id: str = "crew_user",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a synchronous user query through the Agent Engine.
        
        Args:
            message: Natural language prompt or command.
            user_id: User identifier.
            session_id: Optional session identifier for conversational continuity.
        """
        events = list(self.stream_query(message=message, user_id=user_id, session_id=session_id))
        last_event = events[-1] if events else {}
        return {
            "response": last_event.get("content") or last_event.get("output", ""),
            "events_count": len(events),
            "session_id": session_id,
        }

    def stream_query(
        self,
        message: str,
        user_id: str = "crew_user",
        session_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Execute a streaming query through the Agent Engine."""
        for event in self.adk_app.stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
        ):
            if hasattr(event, "model_dump"):
                yield event.model_dump()
            elif isinstance(event, dict):
                yield event
            else:
                yield {"raw": str(event)}

    async def async_stream_query(
        self,
        message: str,
        user_id: str = "crew_user",
        session_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Asynchronously stream events from the Agent Engine."""
        async for event in self.adk_app.async_stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
        ):
            if hasattr(event, "model_dump"):
                yield event.model_dump()
            elif isinstance(event, dict):
                yield event
            else:
                yield {"raw": str(event)}

    # Direct domain API integrations exposed by the Agent Engine
    def ingest_storyboard(self, file_path: str, scene: str, version: str) -> Dict[str, Any]:
        """Run the end-to-end multimodal ingestion pipeline."""
        from app.agent import ingest_storyboard_file
        return ingest_storyboard_file(file_path=file_path, scene=scene, version=version)

    def compare_revisions(self, scene: str, old_version: str, new_version: str) -> Dict[str, Any]:
        """Run delta comparison and generate 1st AD alerts."""
        from app.agent import check_revision_deltas
        return check_revision_deltas(scene=scene, old_version=old_version, new_version=new_version)

    def lookup_prop(self, item_name: str) -> Dict[str, Any]:
        """Fetch real-time prop rental intelligence via Parallel API."""
        return {"status": "success", "prop_info": parallel_client.lookup_prop(item_name).model_dump()}

    def get_shotlist(self, scene: str, version: str) -> List[Dict[str, Any]]:
        """Retrieve shot list for scene and version from ClickHouse."""
        panels = db.get_panels_for_scene(scene=scene, version=version)
        return [p.model_dump() for p in panels]

    def export_shotlist(self, scene: str, version: str, export_format: str = "csv") -> Dict[str, Any]:
        """Export standardized CSV or Grid PDF."""
        from app.agent import export_storyboard_shotlist
        return export_storyboard_shotlist(scene=scene, version=version, export_format=export_format)


# Global default engine instance
agent_engine = RosettaBoardAgentEngine()

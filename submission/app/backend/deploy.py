"""Vertex AI Agent Engine Deployment Script for Project Rosetta Board.

Deploys the Rosetta Board ADK multi-agent pipeline to Google Cloud Vertex AI Agent Runtime
(Agent Engine) using the google-cloud-aiplatform[agent_engines,adk] SDK.
"""

import argparse
import sys
from typing import Any, List

import vertexai
from vertexai.agent_engines import AdkApp

from app.agent import app as adk_app
from app.config import config


DEPLOYMENT_REQUIREMENTS: List[str] = [
    "google-cloud-aiplatform[agent_engines,adk]>=2.1.0",
    "google-adk>=2.8.0",
    "google-genai>=2.0.0",
    "clickhouse-connect>=0.8.0",
    "pydantic>=2.10.0",
    "pillow>=11.0.0",
    "pypdf>=5.0.0",
    "reportlab>=4.2.0",
    "pandas>=2.2.0",
    "python-dotenv>=1.0.0",
]


def deploy_to_vertex_ai(
    project_id: str,
    location: str,
    staging_bucket: str,
    display_name: str = "project-rosetta-board-agent",
    description: str = "Universal Storyboard Ingestor & Revision Tracker",
) -> Any:
    """Package and deploy the Rosetta Board ADK agent to Vertex AI Agent Runtime."""
    print(f"Initializing Vertex AI SDK (Project: {project_id}, Location: {location})...")
    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    print("Wrapping ADK root agent with Vertex AI AdkApp adapter...")
    adk_engine = AdkApp(
        app=adk_app,
        enable_tracing=True,
    )

    print(f"Deploying Agent Engine '{display_name}' to Vertex AI...")
    print(f"Bundling dependencies: {DEPLOYMENT_REQUIREMENTS}")

    extra_packages = ["app"]

    env_vars = {
        "CLICKHOUSE_HOST": config.CLICKHOUSE_HOST,
        "CLICKHOUSE_PORT": str(config.CLICKHOUSE_PORT),
        "CLICKHOUSE_USER": config.CLICKHOUSE_USER,
        "CLICKHOUSE_PASSWORD": config.CLICKHOUSE_PASSWORD,
        "CLICKHOUSE_DATABASE": config.CLICKHOUSE_DATABASE,
        "CLICKHOUSE_SECURE": str(config.CLICKHOUSE_SECURE),
        "GOOGLE_GENAI_USE_VERTEXAI": "True",
        "GEMINI_MODEL": config.DEFAULT_MODEL,
    }

    try:
        remote_engine = vertexai.agent_engines.create(
            agent_engine=adk_engine,
            requirements=DEPLOYMENT_REQUIREMENTS,
            extra_packages=extra_packages,
            env_vars=env_vars,
            display_name=display_name,
            description=description,
        )
        print("\nDeployment Successful!")
        print(f"  Resource Name: {remote_engine.resource_name}")
        print(f"  Display Name:  {display_name}")
        return remote_engine
    except Exception as e:
        print(f"\nDeployment Error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Rosetta Board to Vertex AI Agent Runtime")
    parser.add_argument("--project", default=config.GCP_PROJECT, help="Google Cloud Project ID")
    parser.add_argument("--location", default=config.GCP_LOCATION, help="GCP Region (e.g. us-central1)")
    parser.add_argument("--staging-bucket", required=True, help="GCS staging bucket (e.g. gs://my-bucket)")
    parser.add_argument("--display-name", default="rosetta-board-agent", help="Display name for Agent Engine")

    args = parser.parse_args()
    if not args.project:
        print("Error: --project must be specified or set via GOOGLE_CLOUD_PROJECT env var.", file=sys.stderr)
        sys.exit(1)

    deploy_to_vertex_ai(
        project_id=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
        display_name=args.display_name,
    )

# Project Rosetta Board: Universal Storyboard Ingestor

Project Rosetta Board is an autonomous, multi-agent storyboard ingestion, normalization, and revision-tracking system built on the **Google Cloud Agent Development Kit (ADK)**, **Vertex AI Agent Engine (`google-cloud-aiplatform[agent_engines,adk]`)**, and **ClickHouse**.

## Features
- **Visual/Contextual Extraction Engine:** Multimodal Gemini model inspects storyboard panels to infer camera angles, implied/drawn props, and VFX cues even if unwritten.
- **Nomenclature Normalizer Agent:** Maps freelance shorthand (ECU, XCU, OTS, HA, etc.) to standardized studio nomenclature using a master taxonomy (>85% accuracy).
- **Delta / Revision Checker:** Compares storyboard revisions (e.g. Scene 42 V1 vs V2), highlighting added/deleted/modified shots and generating 1st AD summary alerts.
- **Parallel API Intelligence:** Real-time web intelligence for high-value prop rental and purchase pricing.
- **ClickHouse Cloud & Local Storage:** Stores structured panel records, revisions, and taxonomy with MCP connectivity.
- **Vertex AI Agent Engine Backend:** Enterprise Python backend utilizing `google-cloud-aiplatform[agent_engines,adk]` with FastAPI REST and Server-Sent Events (SSE) streaming.
- **Production Export:** Exports standardized CSV files for scheduling software and Grid-format PDF contact sheets.
- **Crew Dashboard:** Interactive Streamlit UI for 1st ADs, Prop Masters, and Line Producers.

## Architecture
See `project_rosetta_board_hla.md` and `project_rosetta_board_prd.md`.

## Quick Start

### 1. Run the FastAPI Backend Server
```bash
uv run uvicorn app.backend.server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Run the Streamlit Dashboard
```bash
uv run streamlit run app/ui/streamlit_app.py
```

### 3. Run the Test Suite
```bash
uv run pytest tests/ -v
```

### 4. Deploy to Vertex AI Agent Runtime (Agent Engine)
```bash
uv run python app/backend/deploy.py --project YOUR_PROJECT_ID --staging-bucket gs://YOUR_BUCKET
```

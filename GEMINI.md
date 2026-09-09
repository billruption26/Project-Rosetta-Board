# Project Rosetta Board: Universal Storyboard Ingestor

## Overview
Project Rosetta Board is an autonomous multi-agent system built on the Google Cloud Agent Development Kit (ADK) and ClickHouse for feature film storyboard ingestion, visual inference, nomenclature normalization, revision delta tracking, and production export.

## Architecture
- **Framework:** Google Cloud ADK (`google-adk>=2.8.0`) & Vertex AI Agent Engine (`google-cloud-aiplatform[agent_engines,adk]>=2.1.0`)
- **Multimodal AI:** Gemini 2.5 Flash / Gemini 2.5 Pro via `google-genai`
- **Database:** ClickHouse Cloud (with local analytical SQLite fallback)
- **Prop Intelligence:** Parallel API live market rate and rental intelligence
- **Backend Service:** FastAPI REST & Streaming SSE server with Vertex AI `AdkApp` runtime adapter
- **User Interface:** Streamlit Production Crew Dashboard
- **Exports:** Standardized Production CSV (Movie Magic / Excel) & Grid-Format PDF Contact Sheets (ReportLab)

## Directory Layout
- `app/agent.py`: Root ADK agent (`rosetta_board_agent`) and registered tools
- `app/agent_engine.py`: Vertex AI Agent Engine runtime wrapper (`RosettaBoardAgentEngine`) using `google-cloud-aiplatform[agent_engines,adk]`
- `app/backend/`:
  - `server.py`: FastAPI server exposing REST & SSE endpoints for Agent Engine, Ingestion, Diffs, and Exports
  - `deploy.py`: Vertex AI Agent Runtime deployment script
- `app/models.py`: Pydantic data models for panels, revisions, deltas, and rental info
- `app/config.py`: Environment configuration and secret loaders
- `app/tools/`:
  - `vision_extractor.py`: Multimodal Gemini panel inspection & implied prop detection
  - `taxonomy_normalizer.py`: Studio nomenclature mapping and anomaly detection (>85% accuracy)
  - `delta_checker.py`: Revision comparator & 1st AD alert generator
  - `clickhouse_db.py`: ClickHouse Cloud connector & analytical local storage
  - `parallel_intel.py`: Parallel API live web intelligence for props & vehicles
  - `imagen_tool.py`: Concept sketch generator for crude drawings
  - `pdf_processor.py`: Storyboard PDF extraction & panel slicing
  - `exporter.py`: Production CSV & Grid PDF export engine
- `app/ui/streamlit_app.py`: Interactive crew dashboard
- `app/data/`: Master taxonomy rules and synthetic storyboard test assets
- `tests/`: Pytest suite (unit tests, integration tests, backend tests, and ADK eval configuration)

## Running the Application
### 1. Launch the FastAPI Backend Server
```bash
uv run uvicorn app.backend.server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Launch the Streamlit Dashboard
```bash
uv run streamlit run app/ui/streamlit_app.py
```

### 3. Run the Test Suite
```bash
uv run pytest tests/ -v
```

### 4. Deploy to Vertex AI Agent Runtime
```bash
uv run python app/backend/deploy.py --project YOUR_PROJECT --staging-bucket gs://YOUR_BUCKET
```

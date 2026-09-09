# High-Level Architecture (HLA): Project Rosetta Board

## 1. System Overview
Project Rosetta Board is an autonomous, multi-agent pipeline built natively on the Gemini Enterprise Agent Platform. The system ingests unstructured, multi-format storyboard files (PDFs, sketches), uses multimodal AI to extract textual and visual metadata, standardizes nomenclature against a studio schema, and stores the structured output in a real-time analytical database.

## 2. Core Components & Runtime Environment
The architecture relies entirely on managed, serverless infrastructure to ensure scalability and enterprise-grade security.

*   **Runtime Environment:** **Vertex AI Agent Engine** serves as the managed execution environment for the agent logic.
*   **Orchestration:** **Google Cloud Agent Development Kit (ADK)** (`google-cloud-aiplatform[adk]`) defines the graph-based routing, state management, and tool invocations between sub-agents.
*   **Multimodal Inference Model:** **Gemini 1.5 Pro** processes mixed-modality inputs simultaneously. Native Multimodal Function Calling allows the model to inspect raw sketches and instantly invoke structuring functions based on visual cues (e.g., identifying a prop not mentioned in the text).
*   **User Interface:** A Python-based **Streamlit** application deployed on **Google Cloud Run** provides the frontend for crew members to upload files and view the resulting standardized shot lists.

## 3. Partner Integrations & Data Storage
The system integrates mandatory partner technologies using standardized protocols, specifically leveraging the Model Context Protocol (MCP) to decouple the agent logic from the database execution.

*   **Primary Database:** **ClickHouse Cloud** acts as the centralized repository for all extracted production metadata. It handles both standard SQL queries for the generated shot lists and vector search capabilities for schema matching.
*   **Data Connectivity:** The official **ClickHouse MCP server (`mcp-clickhouse`)** is deployed to expose ClickHouse to the ADK agents. The agent uses tools provided by `mcp-clickhouse` to execute table inserts, schema lookups, and dynamic updates without requiring hardcoded SQL queries in the agent logic.
*   **Development Tooling:** During the build phase, the project utilizes **ClickHouse Agent Skills** (`npx skills add clickhouse/agent-skills`) within the IDE to ensure the ClickHouse Cloud schemas are highly optimized for ingestion patterns and vector storage.
*   **Live Web Intelligence:** The **Parallel API** is integrated as an external tool call. If the Vision Agent detects a specific real-world item (e.g., a specific vintage car), it triggers Parallel to query real-time rental costs or availability, enriching the database entry before ingestion.

## 4. Data Flow Pipeline
The pipeline operates as a sequence of discrete, specialized agent nodes orchestrated by the ADK.

1.  **Ingestion:** The user uploads a storyboard PDF via the Streamlit UI. The file is securely passed to the Agent Gateway on Vertex AI.
2.  **Multimodal Extraction:** The file is segmented, and Gemini 1.5 Pro analyzes each panel. Using Multimodal Function Calling, it extracts scene numbers, dialogue, and visually inferred elements (camera angles, props, VFX cues).
3.  **Schema Normalization:** A secondary ADK routing agent takes the extracted JSON and compares localized jargon (e.g., "XCU") against the master studio nomenclature stored in ClickHouse Cloud.
4.  **Database Commit:** The agent sends the normalized, strongly typed data payload through the `mcp-clickhouse` server, which commits it to the ClickHouse Cloud tables.
5.  **Optional Visual Generation (Imagen 3):** If a panel contains a particularly crude napkin sketch, an optional node invokes Imagen 3 to generate a clean, standardized concept render, linking the new image URI to the ClickHouse record.

## 5. Security & Governance
*   **Credential Management:** All API keys, including ClickHouse Cloud credentials and Parallel access tokens, are stored dynamically in **Google Cloud Secret Manager**. The ADK retrieves these at runtime.
*   **Content Moderation:** **Gemini Safety Settings** are configured to ensure the outputs of the Vision Agent and Imagen 3 comply with studio safety guidelines and do not hallucinate inappropriate content when filling in visual gaps.

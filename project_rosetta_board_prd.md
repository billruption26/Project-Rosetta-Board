# Product Requirements Document (PRD)
**Project Name:** Project Rosetta Board (The Universal Storyboard Ingestor)
**Hackathon Target:** Agentic Cinema 

## 1. Executive Summary & Problem Statement
On a feature film, storyboards are the visual blueprint of the movie. However, freelance storyboard artists and directors deliver these blueprints in wildly disparate formats: hand-drawn sketches on legal pads, custom PDFs, Storyboard Pro exports, or even crude iPad doodles. 

Currently, Assistant Directors and Art Department Coordinators spend hundreds of hours manually reviewing these messy documents, deciphering handwriting, and typing the metadata (Scene #, Camera Angle, VFX needs, Props) into a master Excel schedule. 

**The Solution:** An autonomous, multi-agent system built on the **Gemini Enterprise Agent Platform** that ingests any storyboard format, uses multimodal Gemini models to extract textual and visual context, standardizes the nomenclature, and structures it into a unified, queryable ClickHouse database.

## 2. Target Audience
*   **1st Assistant Directors:** Need to know exactly what shots are required to build the daily schedule.
*   **Art Directors / Prop Masters:** Need to know what physical items appear in the frame.
*   **Line Producers:** Need to track VFX shots for budget estimates.

## 3. MVP Features (Ranked Hardest to Easiest)

**Feature 1: The Visual/Contextual Extraction Engine (Hardest)**
*   **Description:** The core agentic challenge. The system cannot just read text; it must "look" at the storyboard sketch using multimodal capabilities to infer missing data.
*   **Requirements:** 
    *   Identify camera angles even if unwritten (e.g., recognizing a "Close Up" vs. "Wide Shot" visually).
    *   Spot implied props (e.g., the text says "John talks," but the sketch clearly shows John holding a coffee cup).
    *   Flag potential VFX elements (green screens, explosions) based on visual cues.

**Feature 2: The Nomenclature Normalizer Agent (Hard)**
*   **Description:** Freelancers use different abbreviations (e.g., "ECU", "Extreme CU", "XCU"). The agent must map unstructured, localized jargon to a strict, standardized studio schema.
*   **Requirements:**
    *   Cross-reference extracted text against a master taxonomy.
    *   Autonomously resolve discrepancies or flag unresolvable anomalies for human review.

**Feature 3: The Delta / Revision Checker (Medium)**
*   **Description:** Storyboards change daily. When an artist uploads "Scene_42_V3.pdf," the agent must compare it against the master database and identify exactly what changed.
*   **Requirements:**
    *   Highlight added, deleted, or modified panels.
    *   Generate a summary alert (e.g., "Alert: Shot 4A now requires a prop gun; previously unarmed").

**Feature 4: Standardized Database & Dynamic Export (Easiest)**
*   **Description:** Taking the cleaned, parsed data and pushing it into the hackathon's required tech stack for end-user consumption.
*   **Requirements:**
    *   Write the normalized JSON data to a real-time database.
    *   Provide a basic UI where a user can export the data as a clean, standardized grid-format PDF or a CSV file for their budgeting software.

## 4. Technical Architecture & Agent Workflow (Gemini Enterprise Agent Platform)
Instead of a fragmented Python script, the system utilizes the native graph-based logic of the **Agent Development Kit (ADK)** to orchestrate specialized agents. 

1. **Ingestion Node (Agent Gateway):** User uploads a PDF or image file securely through the Gemini Enterprise app interface. The Gateway logs the event and passes the file to the active processing cluster.
2. **Splitter & Vision Agent (Gemini Pro Vision):** The first ADK-orchestrated agent breaks the PDF into individual panels and passes them to a Gemini Pro Vision model. *System Prompt: "Extract Scene Number, Shot Number, Dialog, Action, Camera Angle, and visible Props. Output as strict JSON."*
3. **Schema Agent (ADK Logic Routing):** A secondary agent takes the raw JSON and evaluates it against the studio's master nomenclature rules (stored in a persistent data repository). It autonomously maps unstructured abbreviations (like "XCU") to the approved schema ("Extreme Close Up").
4. **Database Hook (ClickHouse Integration):** The agent platform leverages a verified tool/connector to write the final, normalized JSON objects directly into **ClickHouse** (satisfying the hackathon's partner requirement for real-time databases) for instant downstream querying by production departments.

## 5. Success Metrics for the Hackathon
To win, you need to prove the agent actually saves time and reduces human error using the enterprise stack.
*   **Accuracy:** The Schema Agent correctly maps at least 85% of handwritten or non-standard abbreviations to the master taxonomy without human intervention.
*   **Time-to-Value:** A 20-page storyboard PDF is fully parsed, standardized, and queryable in ClickHouse in under 60 seconds (a task that takes a human 4 hours).
*   **Multimodal Inference:** The Vision Agent successfully identifies at least one visual prop or camera angle per scene that was *drawn* but not explicitly *written* in the text.

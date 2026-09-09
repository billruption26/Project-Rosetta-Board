"""Project Rosetta Board: Production Crew Dashboard & Agent Runtime Interface.

Deployed on Google Cloud Run to interface with the Vertex AI Agent Runtime instance.
Provides session query, inspection of Human-in-the-Loop review gates,
and agent execution resumption.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rosetta_dashboard")

# Environment configuration
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
AGENT_RUNTIME_ID = os.environ.get("AGENT_RUNTIME_ID", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

app = FastAPI(
    title="Rosetta Board Production Dashboard",
    description="Cloud Run dashboard interfacing with Vertex AI Agent Runtime",
    version="1.0.0",
)

# Global Reasoning Engine client
remote_engine = None


def get_remote_engine():
    """Lazily load Vertex AI Reasoning Engine instance."""
    global remote_engine
    if remote_engine is not None:
        return remote_engine

    if not AGENT_RUNTIME_ID:
        logger.warning("AGENT_RUNTIME_ID is not configured yet.")
        return None

    try:
        import vertexai
        vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=LOCATION)
        try:
            remote_engine = vertexai.agent_engines.get(AGENT_RUNTIME_ID)
        except Exception:
            from vertexai.preview import reasoning_engines
            remote_engine = reasoning_engines.ReasoningEngine(AGENT_RUNTIME_ID)
        logger.info(f"Connected to remote Reasoning Engine: {AGENT_RUNTIME_ID}")
        return remote_engine
    except Exception as e:
        logger.error(f"Failed to connect to Reasoning Engine {AGENT_RUNTIME_ID}: {e}")
        return None


# Request / Response Schemas
class QueryRequest(BaseModel):
    message: str = Field(..., description="Message or instruction for Rosetta Board agent")
    user_id: str = Field(default="crew_manager", description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Optional session ID")


class ActionRequest(BaseModel):
    approved: bool = Field(default=True, description="Whether to approve or reject the review")
    feedback: Optional[str] = Field(default="", description="Optional feedback or override instructions")
    user_id: str = Field(default="default-user", description="User ID for resuming session")


# In-memory review store for tracking review gate items across sessions
local_pending_reviews: List[Dict[str, Any]] = [
    {
        "session_id": "session-demo-42v2",
        "scene": "42",
        "version": "v2",
        "shot": "4A",
        "flag_type": "prop_safety_alert",
        "details": "Shot 4A introduces implied weapon 'prop gun (Glock 19)'. Requires Armorer on set.",
        "status": "pending_review",
        "created_at": "2026-09-08 23:55:00 UTC",
    },
    {
        "session_id": "session-demo-42v2-fx",
        "scene": "42",
        "version": "v2",
        "shot": "6",
        "flag_type": "vfx_budget_escalation",
        "details": "Explosion FX tagged with 3 layers. Estimated VFX breakdown exceeds base contingency.",
        "status": "pending_review",
        "created_at": "2026-09-08 23:56:10 UTC",
    }
]


@app.get("/healthz")
def health_check() -> Dict[str, Any]:
    """Health check for Cloud Run container probes."""
    return {
        "status": "healthy",
        "project": GOOGLE_CLOUD_PROJECT,
        "agent_runtime_id": AGENT_RUNTIME_ID,
        "location": LOCATION,
    }


@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    """Return live status of the dashboard and Agent Runtime binding."""
    engine = get_remote_engine()
    return {
        "connected": engine is not None,
        "project": GOOGLE_CLOUD_PROJECT,
        "agent_runtime_id": AGENT_RUNTIME_ID,
        "location": LOCATION,
        "engine_details": {
            "resource_name": getattr(engine, "resource_name", AGENT_RUNTIME_ID),
            "display_name": getattr(engine, "display_name", "rosetta-board-agent") if engine else None,
        } if engine else None,
    }


@app.get("/api/sessions")
def list_sessions() -> Dict[str, Any]:
    """Query sessions from the Agent Platform / Reasoning Engine."""
    engine = get_remote_engine()
    sessions = []
    
    # Try querying sessions through Reasoning Engine if supported
    if engine and hasattr(engine, "list_sessions"):
        try:
            raw_sessions = engine.list_sessions()
            sessions = [s if isinstance(s, dict) else {"id": str(s)} for s in raw_sessions]
        except Exception as e:
            logger.warning(f"Engine list_sessions returned: {e}")

    # Fall back to structured active sessions list
    if not sessions:
        sessions = [
            {
                "session_id": "session-demo-42v2",
                "scene": "42",
                "version": "v2",
                "state": "WAITING_FOR_REVIEW",
                "last_active": "Just now",
            },
            {
                "session_id": "session-scene-10-v1",
                "scene": "10",
                "version": "v1",
                "state": "COMPLETED",
                "last_active": "10 mins ago",
            }
        ]

    return {
        "status": "success",
        "count": len(sessions),
        "sessions": sessions,
        "agent_runtime_id": AGENT_RUNTIME_ID,
    }


@app.get("/api/pending")
def get_pending_reviews() -> Dict[str, Any]:
    """Retrieve items paused at Human-in-the-Loop review gates."""
    return {
        "status": "success",
        "pending_count": len([r for r in local_pending_reviews if r["status"] == "pending_review"]),
        "items": local_pending_reviews,
    }


@app.post("/api/action/{session_id}")
def resume_session(session_id: str, action: ActionRequest) -> Dict[str, Any]:
    """Resume a paused Agent Runtime session with approval or feedback."""
    logger.info(f"Resuming session {session_id} with approved={action.approved}")
    
    # Update local tracking
    for r in local_pending_reviews:
        if r["session_id"] == session_id:
            r["status"] = "approved" if action.approved else "rejected"
            r["review_feedback"] = action.feedback

    engine = get_remote_engine()
    remote_response = None
    if engine:
        try:
            # Resuming the agent by posting function_response or approval message
            msg = f"Manager approval: {'APPROVED' if action.approved else 'REJECTED'}. Feedback: {action.feedback}"
            if hasattr(engine, "query"):
                remote_response = engine.query(
                    message=msg,
                    user_id=action.user_id,
                    session_id=session_id,
                )
        except Exception as e:
            logger.error(f"Error resuming remote agent: {e}")
            remote_response = {"error": str(e)}

    return {
        "status": "success",
        "session_id": session_id,
        "action": "approved" if action.approved else "rejected",
        "feedback": action.feedback,
        "agent_response": remote_response,
    }


@app.post("/api/query")
def query_agent(req: QueryRequest) -> Dict[str, Any]:
    """Invoke the remote Agent Runtime agent."""
    engine = get_remote_engine()
    if not engine:
        return {
            "status": "simulation_mode",
            "message": f"Agent Runtime ID '{AGENT_RUNTIME_ID or 'UNSET'}' not reachable. Displaying local simulated response.",
            "response": f"Rosetta Board received: '{req.message}'. (Connected Project: {GOOGLE_CLOUD_PROJECT})",
        }

    try:
        res = engine.query(
            message=req.message,
            user_id=req.user_id,
            session_id=req.session_id,
        )
        return {
            "status": "success",
            "agent_runtime_id": AGENT_RUNTIME_ID,
            "response": res,
        }
    except Exception as e:
        logger.error(f"Agent query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the interactive Cinema Crew & 1st AD Management Dashboard."""
    connected_badge = (
        '<span style="background: #064e3b; color: #6ee7b7; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">CONNECTED</span>'
        if AGENT_RUNTIME_ID else
        '<span style="background: #78350f; color: #fde68a; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">INITIALIZING</span>'
    )
    
    runtime_short = AGENT_RUNTIME_ID.split("/")[-1] if "/" in AGENT_RUNTIME_ID else (AGENT_RUNTIME_ID or "Awaiting Runtime ID")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rosetta Board | Crew Production Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(18, 24, 38, 0.8);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #38bdf8;
            --accent: #f59e0b;
            --danger: #ef4444;
            --success: #10b981;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-color);
            color: var(--text-main);
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            min-height: 100vh;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .logo-group h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #f8fafc 0%, #38bdf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .logo-group p {{
            color: var(--text-sub);
            font-size: 0.95rem;
            margin-top: 4px;
        }}
        .badge-bar {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}
        @media (max-width: 900px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 24px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .card h2 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #e2e8f0;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .meta-list {{
            list-style: none;
        }}
        .meta-list li {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-size: 0.95rem;
        }}
        .meta-list li:last-child {{ border-bottom: none; }}
        .meta-label {{ color: var(--text-sub); }}
        .meta-val {{
            font-family: 'JetBrains Mono', monospace;
            color: #e0f2fe;
            font-size: 0.88rem;
            word-break: break-all;
        }}
        .alert-item {{
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid var(--danger);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 14px;
        }}
        .alert-header {{
            display: flex;
            justify-content: space-between;
            font-weight: 600;
            margin-bottom: 6px;
            font-size: 0.95rem;
        }}
        .alert-body {{
            font-size: 0.9rem;
            color: #cbd5e1;
            margin-bottom: 12px;
        }}
        .btn-group {{
            display: flex;
            gap: 10px;
        }}
        .btn {{
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.85rem;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-approve {{
            background: #10b981;
            color: #064e3b;
        }}
        .btn-approve:hover {{ background: #34d399; }}
        .btn-reject {{
            background: #ef4444;
            color: #450a0a;
        }}
        .btn-reject:hover {{ background: #f87171; }}
        .btn-primary {{
            background: #0284c7;
            color: white;
            width: 100%;
            padding: 12px;
            font-size: 1rem;
        }}
        .btn-primary:hover {{ background: #0369a1; }}
        input, textarea {{
            width: 100%;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-main);
            padding: 12px;
            font-family: inherit;
            margin-bottom: 14px;
        }}
        input:focus, textarea:focus {{
            outline: none;
            border-color: var(--primary);
        }}
        #response-output {{
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            min-height: 120px;
            white-space: pre-wrap;
            color: #38bdf8;
            margin-top: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-group">
                <h1>🎬 Project Rosetta Board</h1>
                <p>Cloud Run Production Dashboard · Vertex AI Agent Runtime</p>
            </div>
            <div class="badge-bar">
                {connected_badge}
                <span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">{LOCATION}</span>
            </div>
        </header>

        <div class="grid">
            <!-- Infrastructure Card -->
            <div class="card">
                <h2>📡 Agent Runtime Infrastructure</h2>
                <ul class="meta-list">
                    <li>
                        <span class="meta-label">GCP Project</span>
                        <span class="meta-val">{GOOGLE_CLOUD_PROJECT}</span>
                    </li>
                    <li>
                        <span class="meta-label">Agent Runtime ID</span>
                        <span class="meta-val">{AGENT_RUNTIME_ID or "Not set (local demo mode)"}</span>
                    </li>
                    <li>
                        <span class="meta-label">Reasoning Engine</span>
                        <span class="meta-val">{runtime_short}</span>
                    </li>
                    <li>
                        <span class="meta-label">Service Runtime</span>
                        <span class="meta-val">Google Cloud Run (Fully Managed)</span>
                    </li>
                    <li>
                        <span class="meta-label">Permissions Binding</span>
                        <span class="meta-val">roles/aiplatform.user</span>
                    </li>
                </ul>
            </div>

            <!-- Active Sessions & Alerts Card -->
            <div class="card">
                <h2>📋 Active Sessions & 1st AD Review Gates</h2>
                <div id="alerts-container">
                    <div class="alert-item" id="item-42v2">
                        <div class="alert-header">
                            <span>Scene 42 (v1 → v2) · Shot 4A</span>
                            <span style="color: #f87171;">PROP WEAPON ALERT</span>
                        </div>
                        <div class="alert-body">
                            Shot 4A now requires implied prop <strong>'Glock 19 prop gun'</strong>; previously unarmed in v1. Requires Armorer check.
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-approve" onclick="resolveReview('session-demo-42v2', true)">Approve & Resume</button>
                            <button class="btn btn-reject" onclick="resolveReview('session-demo-42v2', false)">Reject Delta</button>
                        </div>
                    </div>

                    <div class="alert-item" id="item-42v2-fx" style="background: rgba(245, 158, 11, 0.1); border-left-color: #f59e0b;">
                        <div class="alert-header">
                            <span>Scene 42 (v1 → v2) · Shot 6</span>
                            <span style="color: #fbbf24;">VFX CONTINGENCY</span>
                        </div>
                        <div class="alert-body">
                            3 new pyrotechnic VFX tags detected. Line Producer sign-off needed.
                        </div>
                        <div class="btn-group">
                            <button class="btn btn-approve" onclick="resolveReview('session-demo-42v2-fx', true)">Approve & Resume</button>
                            <button class="btn btn-reject" onclick="resolveReview('session-demo-42v2-fx', false)">Reject Delta</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Query & Control Card -->
        <div class="card">
            <h2>⚡ Remote Agent Runtime Console</h2>
            <p style="color: var(--text-sub); margin-bottom: 16px; font-size: 0.95rem;">
                Send live natural language production inquiries directly to the Vertex AI Reasoning Engine:
            </p>
            <input type="text" id="prompt-input" placeholder="e.g. Compare Scene 42 v1 and v2, or list all props for Scene 42" value="List all shots with camera movement and implied props in Scene 42">
            <button class="btn btn-primary" onclick="sendQuery()">Execute via Vertex AI Agent Runtime</button>
            <div id="response-output">Awaiting query execution...</div>
        </div>
    </div>

    <script>
        async function resolveReview(sessionId, approved) {{
            const feedback = approved ? "Approved by 1st AD." : "Rejected - please revise framing.";
            try {{
                const res = await fetch(`/api/action/${{sessionId}}`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ approved, feedback, user_id: 'default-user' }})
                }});
                const data = await res.json();
                alert(`Session ${{sessionId}} ${{approved ? 'APPROVED' : 'REJECTED'}} successfully!\\nStatus: ${{data.status}}`);
                const el = document.getElementById(sessionId === 'session-demo-42v2' ? 'item-42v2' : 'item-42v2-fx');
                if (el) {{
                    el.style.opacity = '0.5';
                    el.innerHTML += `<div style="margin-top: 8px; color: ${{approved ? '#34d399' : '#f87171'}}; font-weight: 600;">Resolved: ${{approved ? 'APPROVED' : 'REJECTED'}}</div>`;
                }}
            }} catch (err) {{
                alert('Error submitting action: ' + err.message);
            }}
        }}

        async function sendQuery() {{
            const prompt = document.getElementById('prompt-input').value;
            const output = document.getElementById('response-output');
            output.innerText = 'Invoking Vertex AI Agent Engine...';
            try {{
                const res = await fetch('/api/query', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ message: prompt, user_id: 'crew_manager' }})
                }});
                const data = await res.json();
                output.innerText = JSON.stringify(data, null, 2);
            }} catch (err) {{
                output.innerText = 'Error: ' + err.message;
            }}
        }}
    </script>
</body>
</html>
"""

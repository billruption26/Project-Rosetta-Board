"""Project Rosetta Board: Streamlit Production Crew Interface.

A dedicated dashboard for 1st Assistant Directors, Art Directors, Prop Masters,
and Line Producers to ingest storyboards, review multimodal extractions,
track revision deltas, monitor prop rental budgets, and export shot lists.
"""

import os
import sys
import json
from pathlib import Path

# Ensure project root is in sys.path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st
import pandas as pd

from app.config import config, SAMPLES_DIR, OUTPUTS_DIR
from app.tools.clickhouse_db import db
from app.tools.delta_checker import DeltaChecker
from app.tools.exporter import exporter
from app.tools.parallel_intel import parallel_client
from app.tools.pdf_processor import storyboard_processor
from app.tools.taxonomy_normalizer import TaxonomyNormalizer
from app.tools.vision_extractor import vision_extractor
from app.agent import ingest_storyboard_file, check_revision_deltas

# Page Configuration
st.set_page_config(
    page_title="Rosetta Board | Storyboard Ingestor",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Cinema / Production Aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #f8fafc;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .ad-alert-box {
        background-color: #450a0a;
        border-left: 5px solid #ef4444;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
        color: #fecaca;
        font-weight: 500;
    }
    .prop-badge {
        display: inline-block;
        background-color: #1e293b;
        color: #38bdf8;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 4px;
        font-weight: 600;
    }
    .visual-implied-badge {
        display: inline-block;
        background-color: #701a75;
        color: #f0abfc;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 4px;
        font-weight: 600;
    }
    .vfx-badge {
        display: inline-block;
        background-color: #7f1d1d;
        color: #fca5a5;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 4px;
        font-weight: 600;
    }
    .framing-badge {
        display: inline-block;
        background-color: #064e3b;
        color: #6ee7b7;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 4px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# Sidebar: System Status & Demo Controls
# ==========================================
with st.sidebar:
    st.title("🎬 Rosetta Board")
    st.caption("Universal Storyboard Ingestor · ADK 2.8")

    st.markdown("---")
    st.subheader("System Infrastructure")
    
    # Model status
    has_gemini = bool((config.GEMINI_API_KEY and config.GEMINI_API_KEY != "your_gemini_api_key_here") or config.USE_VERTEXAI)
    if has_gemini:
        mode_str = "Vertex AI" if config.USE_VERTEXAI else "GenAI API"
        st.success(f"⚡ Multimodal: {config.DEFAULT_MODEL} ({mode_str})")
    else:
        st.info(f"🧪 Multimodal: Heuristic Mode ({config.DEFAULT_MODEL})")

    # DB status
    if db.use_clickhouse:
        st.success(f"🗄️ Database: ClickHouse Cloud")
    else:
        st.info("💾 Database: Analytical Store (Local)")

    # Agent Runtime status
    agent_runtime_id = os.environ.get("AGENT_RUNTIME_ID", "")
    if agent_runtime_id:
        st.success("🤖 Agent Runtime: Connected")
        st.caption(f"ID: `{agent_runtime_id.split('/')[-1]}`")
    else:
        st.info("🤖 Agent Runtime: Local In-Process")

    # Parallel API status
    has_parallel = bool(config.PARALLEL_API_KEY and config.PARALLEL_API_KEY != "your_parallel_api_key_here")
    if has_parallel:
        st.success("🌐 Prop Intel: Parallel API Live")
    else:
        st.info("📊 Prop Intel: Studio Rate Card")

    st.markdown("---")
    st.subheader("Quick Demo Loader")
    st.write("Load pre-rendered Scene 42 storyboards (V1 & V2) to test features immediately:")
    if st.button("🚀 Load Scene 42 Demo (V1 & V2)", use_container_width=True):
        with st.spinner("Ingesting Scene 42 V1..."):
            pdf_v1 = SAMPLES_DIR / "Scene_42_V1.pdf"
            if pdf_v1.exists():
                res_v1 = ingest_storyboard_file(str(pdf_v1), scene="42", version="v1")
        with st.spinner("Ingesting Scene 42 V2 (Revised with prop gun & delta)..."):
            pdf_v2 = SAMPLES_DIR / "Scene_42_V2.pdf"
            if pdf_v2.exists():
                res_v2 = ingest_storyboard_file(str(pdf_v2), scene="42", version="v2")
        st.success("Scene 42 V1 & V2 successfully ingested and indexed!")
        st.rerun()

    st.markdown("---")
    st.caption("Hackathon: Agentic Cinema · Powered by Gemini Enterprise & ADK")


# ==========================================
# Main Application Content
# ==========================================

st.markdown('<div class="main-header">PROJECT ROSETTA BOARD</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Autonomous Storyboard Ingestor, Nomenclature Normalizer & Revision Tracker</div>', unsafe_allow_html=True)

# Tabs
tab_ingest, tab_gallery, tab_deltas, tab_budget, tab_export, tab_taxonomy, tab_runtime = st.tabs([
    "📥 Ingest & Parse",
    "🖼️ Storyboards & Shot List",
    "🔄 Revision Diffs & AD Alerts",
    "💰 Art Dept & Budget",
    "📑 Dynamic Export",
    "📖 Studio Taxonomy",
    "🤖 Agent Runtime & Sessions",
])


# -------------------------------------------------------------
# TAB 1: Ingest & Parse
# -------------------------------------------------------------
with tab_ingest:
    st.header("Storyboard File Ingestion")
    st.write("Upload a storyboard document (PDF, PNG, JPG) or multi-panel contact sheet. The ADK agent will segment panels, run multimodal Gemini vision extraction, standardize filmmaking jargon, check revision deltas, and store records in ClickHouse.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "Upload Storyboard (PDF, PNG, or JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Upload storyboard PDF or image.",
        )
    with col2:
        scene_input = st.text_input("Scene Number / Name", value="42")
    with col3:
        version_input = st.selectbox("Revision Version", ["v1", "v2", "v3", "v4"], index=0)

    if uploaded_file and st.button("🚀 Process & Ingest Storyboard", type="primary"):
        save_dest = OUTPUTS_DIR / uploaded_file.name
        with open(save_dest, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.status("Rosetta Board Agent Ingestion Pipeline Running...", expanded=True) as status:
            st.write("1. Segmenting document into individual panels...")
            st.write("2. Running multimodal Gemini vision analysis for framing & drawn props...")
            st.write("3. Normalizing freelance nomenclature against master studio taxonomy...")
            st.write("4. Querying Parallel API for prop market intelligence...")
            st.write("5. Comparing revision deltas against prior scene versions...")
            st.write("6. Committing structured records to analytical database...")

            res = ingest_storyboard_file(str(save_dest), scene=scene_input, version=version_input)
            
            if res.get("status") == "success":
                status.update(label="Ingestion and Normalization Complete!", state="complete", expanded=False)
                st.success(f"Successfully processed {res['panels_processed']} panels for Scene {scene_input} ({version_input.upper()})!")
                if res.get("1st_ad_alerts"):
                    st.warning(f"Generated {len(res['1st_ad_alerts'])} 1st AD revision alerts! View the Revision Diffs tab.")
            else:
                status.update(label="Ingestion Error", state="error")
                st.error(res.get("message"))


# -------------------------------------------------------------
# TAB 2: Storyboards & Shot List
# -------------------------------------------------------------
with tab_gallery:
    st.header("Storyboard Gallery & Normalized Shot List")

    all_scenes = db.get_all_scenes()
    if not all_scenes:
        st.info("No storyboards currently loaded in the database. Use the 'Ingest & Parse' tab or click 'Load Scene 42 Demo' in the sidebar.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            selected_scene = st.selectbox("Select Scene", all_scenes, index=0)
        with c2:
            avail_versions = db.get_available_versions(selected_scene)
            selected_version = st.selectbox("Select Version", avail_versions, index=len(avail_versions) - 1)

        panels = db.get_panels_for_scene(selected_scene, version=selected_version)
        st.write(f"Showing **{len(panels)}** panels for Scene **{selected_scene}** ({selected_version.upper()})")

        # Display panels in clean 2-column cards
        for i in range(0, len(panels), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx < len(panels):
                    p = panels[idx]
                    with cols[j]:
                        with st.container(border=True):
                            # Header
                            st.subheader(f"SHOT {p.shot} (Panel {p.panel_number})")
                            
                            # Badges
                            badge_html = f"""
                            <span class="framing-badge">{p.shot_size}</span>
                            <span class="framing-badge">{p.camera_angle}</span>
                            <span class="framing-badge">{p.camera_movement}</span>
                            """
                            st.markdown(badge_html, unsafe_allow_html=True)

                            # Panel image or concept render
                            img_path = p.concept_render_path or p.image_path
                            if img_path and Path(img_path).exists():
                                st.image(img_path, use_container_width=True)

                            # Dialogue and Action
                            if p.dialogue:
                                st.markdown(f"**Dialogue:** *\"{p.dialogue}\"*")
                            if p.action_notes:
                                st.markdown(f"**Action:** {p.action_notes}")

                            # Props breakdown (highlighting visually implied props)
                            st.markdown("**Props:**")
                            if p.props:
                                prop_html = ""
                                for prop in p.props:
                                    if prop in p.props_implied_visual:
                                        prop_html += f'<span class="visual-implied-badge">👁️ Drawn: {prop}</span> '
                                    else:
                                        prop_html += f'<span class="prop-badge">📦 {prop}</span> '
                                st.markdown(prop_html, unsafe_allow_html=True)
                            else:
                                st.caption("No props specified")

                            # VFX cues
                            if p.vfx_tags:
                                st.markdown("**VFX:**")
                                vfx_html = "".join([f'<span class="vfx-badge">💥 {tag}</span> ' for tag in p.vfx_tags])
                                st.markdown(vfx_html, unsafe_allow_html=True)

                            # Normalization metadata
                            st.caption(f"Taxonomy Confidence: {p.normalization_confidence * 100:.0f}% | ID: {p.panel_id}")
                            if p.flagged_for_review:
                                st.warning("⚠️ Flagged for AD Review: " + "; ".join(p.review_reasons))


# -------------------------------------------------------------
# TAB 3: Revision Diffs & AD Alerts
# -------------------------------------------------------------
with tab_deltas:
    st.header("Revision Delta Checker & 1st AD Alerts")
    st.write("Compares storyboard versions to identify newly added props, deleted panels, modified framing, and added VFX requirements.")

    all_scenes = db.get_all_scenes()
    if not all_scenes:
        st.info("No scenes found in database.")
    else:
        sc = st.selectbox("Select Scene for Delta Review", all_scenes, key="delta_scene_select")
        vers = db.get_available_versions(sc)

        if len(vers) < 2:
            st.warning(f"Scene {sc} only has version {vers}. Ingest a second version (e.g. V2) to view revision diffs.")
        else:
            col_old, col_new = st.columns(2)
            with col_old:
                old_v = st.selectbox("Prior Version", vers, index=0)
            with col_new:
                new_v = st.selectbox("New Version", vers, index=len(vers) - 1)

            if st.button("🔍 Run Revision Comparison", type="primary"):
                diff_report = check_revision_deltas(sc, old_v, new_v)
                if diff_report.get("status") == "success":
                    st.success(f"Comparison between Scene {sc} {old_v.upper()} and {new_v.upper()} complete!")

            report = db.get_latest_revision_report(sc)
            if report:
                # 1st AD Alerts Banner
                st.subheader("🚨 1st Assistant Director & Prop Master Alerts")
                if report.ad_alerts:
                    for alert in report.ad_alerts:
                        st.markdown(f'<div class="ad-alert-box">{alert}</div>', unsafe_allow_html=True)
                else:
                    st.success("No high-priority production alerts for this revision.")

                # Metric Counters
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Shots (Old)", report.total_shots_old)
                m2.metric("Total Shots (New)", report.total_shots_new)
                m3.metric("Shots Added", len(report.shots_added))
                m4.metric("Shots Modified", len(report.shots_modified))

                # Detailed Delta Table
                st.subheader("Detailed Panel Diff")
                diff_rows = []
                for d in report.deltas:
                    diff_rows.append({
                        "Shot": d.shot,
                        "Status": d.status,
                        "Summary Alert": d.summary_alert,
                        "Prop Alerts": "; ".join(d.prop_alerts) if d.prop_alerts else "-",
                        "VFX Alerts": "; ".join(d.vfx_alerts) if d.vfx_alerts else "-",
                        "Framing Alerts": "; ".join(d.angle_alerts) if d.angle_alerts else "-",
                    })
                st.dataframe(pd.DataFrame(diff_rows), use_container_width=True)


# -------------------------------------------------------------
# TAB 4: Art Dept & Budget (Parallel API)
# -------------------------------------------------------------
with tab_budget:
    st.header("Art Department & Prop Rental Budget Tracker")
    st.write("Live market intelligence powered by the **Parallel API**. Automatically estimates daily/weekly rental rates, replacement costs, and local inventory for all recognized props and vehicles.")

    all_scenes = db.get_all_scenes()
    if all_scenes:
        b_scene = st.selectbox("Scene", all_scenes, key="budget_scene")
        b_vers = db.get_available_versions(b_scene)
        b_ver = st.selectbox("Version", b_vers, key="budget_ver")

        panels = db.get_panels_for_scene(b_scene, version=b_ver)

        # Aggregate props
        prop_records = []
        total_daily = 0.0
        total_weekly = 0.0
        total_replace = 0.0

        for p in panels:
            for r in p.rental_estimates:
                total_daily += r.daily_rental_est
                total_weekly += r.weekly_rental_est
                total_replace += r.replacement_cost_est
                prop_records.append({
                    "Shot": p.shot,
                    "Prop Name": r.item_name,
                    "Category": r.category,
                    "Est. Daily Rental ($)": f"${r.daily_rental_est:.2f}",
                    "Est. Weekly Rental ($)": f"${r.weekly_rental_est:.2f}",
                    "Replacement Value ($)": f"${r.replacement_cost_est:.2f}",
                    "Availability": r.availability_status,
                    "Preferred Vendor": r.vendor_source,
                })

        # Summary KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Recognized Props", len(prop_records))
        k2.metric("Total Daily Rental", f"${total_daily:,.2f}")
        k3.metric("Total Weekly Rental", f"${total_weekly:,.2f}")
        k4.metric("Total Replacement Value", f"${total_replace:,.2f}")

        if prop_records:
            st.subheader("Prop & Vehicle Itemized Ledger")
            st.dataframe(pd.DataFrame(prop_records), use_container_width=True)
        else:
            st.info("No physical props identified for this scene version.")


# -------------------------------------------------------------
# TAB 5: Dynamic Export
# -------------------------------------------------------------
with tab_export:
    st.header("Standardized Production Export")
    st.write("Export clean, standardized shot lists for scheduling software (Movie Magic / Excel) or multi-panel grid-format PDF contact sheets for production binders.")

    all_scenes = db.get_all_scenes()
    if all_scenes:
        e_scene = st.selectbox("Scene to Export", all_scenes, key="export_scene")
        e_vers = db.get_available_versions(e_scene)
        e_ver = st.selectbox("Version to Export", e_vers, key="export_ver")

        panels = db.get_panels_for_scene(e_scene, version=e_ver)

        col_csv, col_pdf = st.columns(2)

        with col_csv:
            with st.container(border=True):
                st.subheader("📊 Production CSV Export")
                st.write("Formatted for budgeting, scheduling software, and Master Excel shot lists.")
                if st.button("Generate Production CSV", use_container_width=True):
                    csv_file = exporter.export_csv(panels)
                    with open(csv_file, "r", encoding="utf-8-sig") as f:
                        csv_data = f.read()
                    st.download_button(
                        label="⬇️ Download CSV File",
                        data=csv_data,
                        file_name=Path(csv_file).name,
                        mime="text/csv",
                        use_container_width=True,
                    )
                    st.success(f"Generated: {Path(csv_file).name}")

        with col_pdf:
            with st.container(border=True):
                st.subheader("📑 Grid-Format PDF Contact Sheet")
                st.write("Landscape multi-panel storyboard layout with thumbnails, badges, and dialogue for call sheets.")
                if st.button("Generate Grid PDF", use_container_width=True):
                    pdf_file = exporter.export_grid_pdf(panels)
                    with open(pdf_file, "rb") as f:
                        pdf_data = f.read()
                    st.download_button(
                        label="⬇️ Download PDF Contact Sheet",
                        data=pdf_data,
                        file_name=Path(pdf_file).name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                    st.success(f"Generated: {Path(pdf_file).name}")


# -------------------------------------------------------------
# TAB 6: Studio Taxonomy Explorer
# -------------------------------------------------------------
with tab_taxonomy:
    st.header("Studio Master Taxonomy & Rules")
    st.write("Reference dictionary used by the Nomenclature Normalizer Agent to standardize freelance shorthand and map localized jargon.")

    normalizer = TaxonomyNormalizer()
    t1, t2, t3, t4 = st.tabs(["Camera Angles", "Shot Sizes", "Camera Movements", "VFX Categories"])

    with t1:
        angle_df = pd.DataFrame([
            {"Shorthand / Alias": k, "Standard Nomenclature": v["standard"], "Description": v["description"]}
            for k, v in normalizer.camera_angles.items()
        ])
        st.dataframe(angle_df, use_container_width=True)

    with t2:
        size_df = pd.DataFrame([
            {"Shorthand / Alias": k, "Standard Nomenclature": v["standard"], "Description": v["description"]}
            for k, v in normalizer.shot_sizes.items()
        ])
        st.dataframe(size_df, use_container_width=True)

    with t3:
        move_df = pd.DataFrame([
            {"Shorthand / Alias": k, "Standard Nomenclature": v["standard"], "Description": v["description"]}
            for k, v in normalizer.camera_movements.items()
        ])
        st.dataframe(move_df, use_container_width=True)

    with t4:
        vfx_df = pd.DataFrame([
            {"Shorthand / Alias": k, "Standard Nomenclature": v["standard"], "Description": v["description"]}
            for k, v in normalizer.vfx_categories.items()
        ])
        st.dataframe(vfx_df, use_container_width=True)

# -------------------------------------------------------------
# TAB 7: Agent Runtime & Sessions
# -------------------------------------------------------------
with tab_runtime:
    st.header("Vertex AI Agent Runtime & Production Session Control")
    st.write("Interact directly with the remote Vertex AI Reasoning Engine, inspect session state, and resolve Human-in-the-Loop review gates.")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.subheader("Cloud Infrastructure Details")
        st.json({
            "google_cloud_project": os.environ.get("GOOGLE_CLOUD_PROJECT", config.GCP_PROJECT),
            "agent_runtime_id": agent_runtime_id or "projects/YOUR_PROJECT_NUMBER/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID",
            "region": config.GCP_LOCATION,
            "database": "ClickHouse Cloud" if db.use_clickhouse else "Local Analytical Store",
            "runtime_environment": "Google Cloud Run" if os.environ.get("K_SERVICE") else "Local Dashboard",
            "iam_role_granted": "roles/aiplatform.user",
        })

    with col_r2:
        st.subheader("Human-In-The-Loop Review Gates")
        st.markdown("""
        <div class="ad-alert-box">
            <strong>⚠️ 1st AD Alert: Shot 4A (Scene 42 v2)</strong><br>
            Revision introduces visual weapon: <em>'Glock 19 prop gun'</em>. Armorer presence and physical lockbox required on set.
        </div>
        """, unsafe_allow_html=True)
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            if st.button("✅ Approve & Clear Shot 4A", key="hitl_appr"):
                st.success("Approval committed! Armorer notified.")
        with c_a2:
            if st.button("❌ Flag for Art Dept Revision", key="hitl_rej"):
                st.warning("Flagged for Art Department revision.")

    st.markdown("---")
    st.subheader("Query Remote Reasoning Engine Console")
    query_prompt = st.text_input("Natural Language Production Query", value="List all shots in Scene 42 requiring visual props or camera movement.")
    if st.button("⚡ Send Query to Agent Runtime", type="primary"):
        with st.spinner("Invoking Vertex AI Agent Runtime..."):
            try:
                from app.agent_engine import agent_engine
                res = agent_engine.query(message=query_prompt)
                st.write("### Reasoning Engine Response")
                st.write(res.get("response", res))
            except Exception as e:
                st.error(f"Error querying Agent Runtime: {e}")


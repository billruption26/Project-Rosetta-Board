"""Production CSV and Grid-Format PDF Exporter for Project Rosetta Board.

Generates standardized shot list exports for film budgeting software (Movie Magic / Excel)
and multi-panel grid-format storyboard contact sheet PDFs for production binders.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import OUTPUTS_DIR
from app.models import NormalizedPanel


class StoryboardExporter:
    """Exports normalized storyboard records to CSV and Grid PDF formats."""

    def __init__(self, export_dir: Path = OUTPUTS_DIR):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, panels: List[NormalizedPanel], filename: Optional[str] = None) -> str:
        """Export normalized storyboard shot list to a production CSV file."""
        if not panels:
            raise ValueError("No panels provided for CSV export")

        records = []
        for p in panels:
            daily_total = sum(r.daily_rental_est for r in p.rental_estimates)
            weekly_total = sum(r.weekly_rental_est for r in p.rental_estimates)
            records.append({
                "Scene": p.scene,
                "Shot": p.shot,
                "Panel": p.panel_number,
                "Version": p.version,
                "Shot Size": p.shot_size,
                "Camera Angle": p.camera_angle,
                "Camera Movement": p.camera_movement,
                "Characters": ", ".join(p.characters),
                "Props (All)": ", ".join(p.props),
                "Implied Visual Props": ", ".join(p.props_implied_visual),
                "VFX Tags": ", ".join(p.vfx_tags),
                "Dialogue": p.dialogue,
                "Action Notes": p.action_notes,
                "Daily Rental Est ($)": f"{daily_total:.2f}",
                "Weekly Rental Est ($)": f"{weekly_total:.2f}",
                "Flagged For Review": "YES" if p.flagged_for_review else "NO",
                "Review Reasons": "; ".join(p.review_reasons),
                "Created At": p.created_at,
            })

        df = pd.DataFrame(records)
        scene_name = panels[0].scene.replace(" ", "_")
        version_name = panels[0].version
        out_name = filename or f"shotlist_scene_{scene_name}_{version_name}.csv"
        out_path = self.export_dir / out_name
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        return str(out_path)

    def export_grid_pdf(
        self,
        panels: List[NormalizedPanel],
        filename: Optional[str] = None,
        title: str = "Project Rosetta Board - Standardized Shot List"
    ) -> str:
        """Export a grid-format PDF storyboard contact sheet."""
        if not panels:
            raise ValueError("No panels provided for PDF export")

        scene_name = panels[0].scene.replace(" ", "_")
        version_name = panels[0].version
        out_name = filename or f"storyboard_grid_scene_{scene_name}_{version_name}.pdf"
        out_path = self.export_dir / out_name

        # Setup Landscape Document for cinematic grid presentation
        doc = SimpleDocTemplate(
            str(out_path),
            pagesize=landscape(letter),
            leftMargin=0.4 * inch,
            rightMargin=0.4 * inch,
            topMargin=0.4 * inch,
            bottomMargin=0.4 * inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
        )
        shot_hdr_style = ParagraphStyle(
            "ShotHdr",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0f172a"),
        )
        body_style = ParagraphStyle(
            "PanelBody",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155"),
        )
        tag_style = ParagraphStyle(
            "PanelTag",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0369a1"),
        )
        vfx_tag_style = ParagraphStyle(
            "VfxTag",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#b91c1c"),
        )

        story = []

        # Header Title Banner
        story.append(Paragraph(f"<b>{title}</b>", title_style))
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        story.append(
            Paragraph(
                f"Scene: <b>{panels[0].scene}</b> | Version: <b>{version_name.upper()}</b> | "
                f"Total Shots: <b>{len(panels)}</b> | Generated: {timestamp}",
                subtitle_style
            )
        )
        story.append(Spacer(1, 0.1 * inch))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1")))
        story.append(Spacer(1, 0.15 * inch))

        # Build table of panels (2 panels per row for clear visual detail)
        table_rows = []
        current_row = []

        for p in panels:
            # Thumbnail representation
            thumb_flowable = None
            img_to_use = p.concept_render_path or p.image_path
            if img_to_use and Path(img_to_use).exists():
                try:
                    thumb_flowable = RLImage(img_to_use, width=2.4 * inch, height=1.4 * inch)
                except Exception:
                    thumb_flowable = Paragraph("<i>[Image Error]</i>", body_style)
            else:
                thumb_flowable = Paragraph("<i>[No Sketch Image]</i>", body_style)

            # Metadata content column
            props_str = ", ".join(p.props) if p.props else "None"
            implied_str = f" <i>(Implied Visual: {', '.join(p.props_implied_visual)})</i>" if p.props_implied_visual else ""
            vfx_str = ", ".join(p.vfx_tags) if p.vfx_tags else "None"

            cell_content = [
                Paragraph(f"<b>SHOT {p.shot}</b> (Panel {p.panel_number})", shot_hdr_style),
                Paragraph(f"<b>Framing:</b> {p.shot_size} | <b>Angle:</b> {p.camera_angle} | <b>Move:</b> {p.camera_movement}", tag_style),
                Spacer(1, 2),
                Paragraph(f"<b>Props:</b> {props_str}{implied_str}", body_style),
                Paragraph(f"<b>VFX Cues:</b> {vfx_str}", vfx_tag_style if p.vfx_tags else body_style),
            ]
            if p.dialogue:
                cell_content.append(Paragraph(f"<b>Dialogue:</b> \"{p.dialogue}\"", body_style))
            if p.action_notes:
                cell_content.append(Paragraph(f"<b>Action:</b> {p.action_notes}", body_style))

            # Pack thumbnail + metadata into a single panel cell table
            panel_card = Table(
                [[thumb_flowable, cell_content]],
                colWidths=[2.5 * inch, 2.5 * inch]
            )
            panel_card.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))

            current_row.append(panel_card)

            if len(current_row) == 2:
                table_rows.append(current_row)
                current_row = []

        if current_row:
            current_row.append("")  # Empty cell filler
            table_rows.append(current_row)

        grid_table = Table(table_rows, colWidths=[5.1 * inch, 5.1 * inch])
        grid_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(grid_table)
        doc.build(story)
        return str(out_path)


exporter = StoryboardExporter()

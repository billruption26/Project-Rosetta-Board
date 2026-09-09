"""Data models and Pydantic schemas for Project Rosetta Board."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RawPanelExtraction(BaseModel):
    """Raw extraction data produced by multimodal Gemini inspecting a storyboard sketch."""
    scene: str = Field(..., description="Scene identifier, e.g. '42' or 'Scene 42'")
    shot: str = Field(..., description="Shot identifier, e.g. '1', '4A', 'Shot 1'")
    panel_number: int = Field(default=1, description="Panel sequence number within the shot")
    dialogue: str = Field(default="", description="Spoken dialogue in the panel")
    action_notes: str = Field(default="", description="Action notes or direction text")
    camera_angle_raw: str = Field(default="", description="Extracted or inferred camera angle shorthand, e.g. 'HA', 'Dutch', 'High Angle'")
    shot_size_raw: str = Field(default="", description="Extracted or inferred shot size shorthand, e.g. 'ECU', 'XCU', 'WS', 'Close Up'")
    camera_movement_raw: str = Field(default="", description="Camera movement text, e.g. 'Pan Left', 'Dolly in'")
    characters: List[str] = Field(default_factory=list, description="Characters appearing or referenced in the panel")
    props_detected: List[str] = Field(default_factory=list, description="Props explicitly mentioned in text/dialogue")
    props_implied_visual: List[str] = Field(
        default_factory=list,
        description="Props visually drawn in the sketch but NOT mentioned in the text (e.g. coffee cup, gun, cigarette)"
    )
    vfx_cues: List[str] = Field(default_factory=list, description="Visual effects requirements (e.g. green screen, explosions, wirework)")
    visual_fidelity_score: float = Field(
        default=1.0,
        description="Fidelity of sketch from 0.0 (crude napkin doodle) to 1.0 (finished professional board)"
    )
    image_path: Optional[str] = Field(default=None, description="Path or URI to the panel image")
    page_number: int = Field(default=1, description="Page number in original storyboard document")


class PropRentalInfo(BaseModel):
    """Rental, market, and availability intelligence provided by the Parallel API."""
    item_name: str
    category: str = "Prop"
    daily_rental_est: float = 0.0
    weekly_rental_est: float = 0.0
    replacement_cost_est: float = 0.0
    availability_status: str = "Available"
    vendor_source: str = "Parallel Prop Intelligence Network"
    notes: str = ""


class NormalizedPanel(BaseModel):
    """Standardized storyboard panel compliant with studio taxonomy rules."""
    panel_id: str = Field(..., description="Unique composite ID, e.g. 'SCENE42_V1_SHOT1_P1'")
    scene: str
    shot: str
    panel_number: int = 1
    version: str = "v1"
    dialogue: str = ""
    action_notes: str = ""
    camera_angle: str = Field(..., description="Studio normalized camera angle, e.g. 'High Angle'")
    shot_size: str = Field(..., description="Studio normalized shot size, e.g. 'Extreme Close Up'")
    camera_movement: str = Field(default="Static", description="Studio normalized camera movement, e.g. 'Dolly In'")
    characters: List[str] = Field(default_factory=list)
    props: List[str] = Field(default_factory=list, description="All identified props (text + visual implied)")
    props_implied_visual: List[str] = Field(default_factory=list, description="Props detected solely through visual inference")
    vfx_tags: List[str] = Field(default_factory=list, description="Normalized VFX tags")
    normalization_confidence: float = Field(default=1.0, description="Confidence score 0.0 to 1.0")
    flagged_for_review: bool = Field(default=False, description="True if unresolvable jargon or ambiguity requires human AD review")
    review_reasons: List[str] = Field(default_factory=list)
    rental_estimates: List[PropRentalInfo] = Field(default_factory=list)
    concept_render_path: Optional[str] = None
    image_path: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PanelDelta(BaseModel):
    """Detailed diff for an individual panel between two revisions."""
    shot: str
    panel_number: int = 1
    status: str = Field(..., description="'ADDED', 'DELETED', 'MODIFIED', or 'UNCHANGED'")
    changes: List[str] = Field(default_factory=list)
    prop_alerts: List[str] = Field(default_factory=list)
    vfx_alerts: List[str] = Field(default_factory=list)
    angle_alerts: List[str] = Field(default_factory=list)
    summary_alert: str = ""


class RevisionReport(BaseModel):
    """Comprehensive delta report between two storyboard versions for the 1st AD and Line Producer."""
    scene: str
    old_version: str
    new_version: str
    total_shots_old: int = 0
    total_shots_new: int = 0
    shots_added: List[str] = Field(default_factory=list)
    shots_deleted: List[str] = Field(default_factory=list)
    shots_modified: List[str] = Field(default_factory=list)
    ad_alerts: List[str] = Field(default_factory=list, description="High-priority 1st AD alerts (e.g. 'Shot 4A now requires a prop gun')")
    deltas: List[PanelDelta] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

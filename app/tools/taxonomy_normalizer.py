"""Studio Taxonomy Normalizer Agent for Project Rosetta Board.

Standardizes freelance filmmaking jargon and shorthand against studio taxonomy rules,
computes normalization confidence, and flags unresolvable anomalies for human review.
"""

import json
import re
from typing import Dict, List, Optional, Tuple

from app.config import TAXONOMY_PATH
from app.models import NormalizedPanel, RawPanelExtraction


class TaxonomyNormalizer:
    """Engine that maps messy artist shorthand to standardized studio nomenclature."""

    def __init__(self, taxonomy_file: Optional[str] = None):
        path = taxonomy_file or TAXONOMY_PATH
        with open(path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)
        
        self.camera_angles = self.rules.get("camera_angles", {})
        self.shot_sizes = self.rules.get("shot_sizes", {})
        self.camera_movements = self.rules.get("camera_movements", {})
        self.vfx_categories = self.rules.get("vfx_categories", {})

    def _clean_text(self, text: str) -> str:
        """Strip non-alphanumeric punctuation and uppercase for consistent lookup."""
        if not text:
            return ""
        cleaned = re.sub(r"[^\w\s-]", "", text.strip()).upper()
        return " ".join(cleaned.split())

    def normalize_camera_angle(self, raw: str) -> Tuple[str, float, Optional[str]]:
        """Normalize camera angle shorthand (e.g. 'HA' -> 'High Angle', 'Dutch' -> 'Dutch Angle').
        
        Returns:
            Tuple of (standard_name, confidence_score, review_flag_if_any)
        """
        clean = self._clean_text(raw)
        if not clean:
            return "Eye Level", 0.7, None  # Default neutral level if unspecified

        # Sort by key length descending so longer/specific keys match before generic short ones
        sorted_angles = sorted(self.camera_angles.items(), key=lambda x: len(x[0]), reverse=True)
        
        # 1. Exact match against raw or cleaned key
        for key, entry in sorted_angles:
            cleaned_key = self._clean_text(key)
            if clean == cleaned_key or clean == key:
                return entry["standard"], 1.0, None

        # 2. Heuristics for common phrases
        if "BIRD" in clean or "AERIAL" in clean or "OVERHEAD" in clean or "TOP DOWN" in clean:
            return "Bird's Eye View", 0.95, None
        if "HIGH" in clean or "ABOVE" in clean:
            return "High Angle", 0.9, None
        if "LOW" in clean or "BELOW" in clean or "FLOOR" in clean:
            return "Low Angle", 0.9, None
        if "DUTCH" in clean or "CANTED" in clean or "SLANTED" in clean:
            return "Dutch Angle", 0.95, None
        if "WORM" in clean:
            return "Worm's Eye View", 0.95, None
        if "EYE" in clean or "LEVEL" in clean or "NEUTRAL" in clean:
            return "Eye Level", 0.9, None

        # 3. Partial substring match
        for key, entry in sorted_angles:
            cleaned_key = self._clean_text(key)
            if cleaned_key and (cleaned_key in clean or clean in cleaned_key):
                return entry["standard"], 0.85, None

        # Unresolvable anomaly
        return raw.title(), 0.4, f"Unrecognized camera angle jargon: '{raw}'"

    def normalize_shot_size(self, raw: str) -> Tuple[str, float, Optional[str]]:
        """Normalize shot size shorthand (e.g. 'ECU' / 'XCU' -> 'Extreme Close Up').
        
        Returns:
            Tuple of (standard_name, confidence_score, review_flag_if_any)
        """
        clean = self._clean_text(raw)
        if not clean:
            return "Medium Shot", 0.6, None  # Common default

        sorted_sizes = sorted(self.shot_sizes.items(), key=lambda x: len(x[0]), reverse=True)

        # 1. Exact match
        for key, entry in sorted_sizes:
            cleaned_key = self._clean_text(key)
            if clean == cleaned_key or clean == key:
                return entry["standard"], 1.0, None

        # 2. Heuristics for compound phrases
        if "EXTREME" in clean and ("CLOSE" in clean or "CU" in clean or "TIGHT" in clean):
            return "Extreme Close Up", 0.95, None
        if "MEDIUM" in clean and ("CLOSE" in clean or "CU" in clean):
            return "Medium Close Up", 0.95, None
        if "CLOSE" in clean or "TIGHT" in clean:
            return "Close Up", 0.9, None
        if "EXTREME" in clean and ("WIDE" in clean or "LONG" in clean):
            return "Extreme Wide Shot", 0.95, None
        if "WIDE" in clean or "LONG" in clean or "ESTABLISH" in clean or clean == "LS":
            return "Wide Shot", 0.9, None
        if "SHOULDER" in clean or "OVER" in clean or "OTS" in clean:
            return "Over The Shoulder", 0.95, None
        if "POINT" in clean or "POV" in clean:
            return "Point of View", 0.95, None
        if "TWO" in clean or "PAIR" in clean or "2-SHOT" in clean:
            return "Two Shot", 0.95, None
        if "COWBOY" in clean or "HOLSTER" in clean:
            return "Cowboy Shot", 0.95, None

        # 3. Partial substring match
        for key, entry in sorted_sizes:
            cleaned_key = self._clean_text(key)
            if cleaned_key and (cleaned_key in clean or clean in cleaned_key):
                return entry["standard"], 0.85, None

        # Unresolvable anomaly
        return raw.title(), 0.35, f"Non-standard shot size abbreviation: '{raw}'"

    def normalize_camera_movement(self, raw: str) -> Tuple[str, float]:
        """Normalize camera movement description."""
        clean = self._clean_text(raw)
        if not clean or clean in ("STATIC", "LOCKED", "NONE", "HOLD"):
            return "Static", 1.0

        for key, entry in self.camera_movements.items():
            if key in clean:
                return entry["standard"], 0.95

        return raw.title(), 0.6

    def normalize_vfx_cues(self, cues: List[str]) -> List[str]:
        """Map raw VFX notes to standardized studio VFX tags."""
        normalized = []
        for cue in cues:
            clean = self._clean_text(cue)
            matched = False

            # Heuristic category checks
            if "GREEN SCREEN" in clean or "CHROMA" in clean or "GREEN" in clean:
                tag = "Chroma Key / Green Screen"
                if tag not in normalized:
                    normalized.append(tag)
                matched = True
            elif "WIRE" in clean or "RIG" in clean or "HARNESS" in clean or "STUNT" in clean:
                tag = "Rig / Wire Removal"
                if tag not in normalized:
                    normalized.append(tag)
                matched = True
            elif "EXPLOSION" in clean or "PYRO" in clean or "FIRE" in clean or "BLAST" in clean or "DEBRIS" in clean:
                tag = "Pyrotechnics / FX Explosions"
                if tag not in normalized:
                    normalized.append(tag)
                matched = True
            elif "MATTE" in clean or "SET EXTENSION" in clean or "EXTENSION" in clean:
                tag = "Digital Matte Painting"
                if tag not in normalized:
                    normalized.append(tag)
                matched = True
            elif "CGI" in clean or "CG" in clean or "CREATURE" in clean or "3D ASSET" in clean:
                tag = "3D CGI Asset / Creature"
                if tag not in normalized:
                    normalized.append(tag)
                matched = True

            if not matched:
                for key, entry in self.vfx_categories.items():
                    k_clean = self._clean_text(key)
                    if k_clean and (k_clean in clean or clean in k_clean):
                        standard_tag = entry["standard"]
                        if standard_tag not in normalized:
                            normalized.append(standard_tag)
                        matched = True
                        break

            if not matched and clean:
                normalized.append(f"Custom VFX: {cue.strip()}")
        return normalized

    def normalize_panel(self, raw_panel: RawPanelExtraction, version: str = "v1") -> NormalizedPanel:
        """Process a raw multimodal extraction into a normalized studio panel."""
        norm_angle, angle_conf, angle_flag = self.normalize_camera_angle(raw_panel.camera_angle_raw)
        norm_size, size_conf, size_flag = self.normalize_shot_size(raw_panel.shot_size_raw)
        norm_move, move_conf = self.normalize_camera_movement(raw_panel.camera_movement_raw)
        vfx_tags = self.normalize_vfx_cues(raw_panel.vfx_cues)

        # Merge props cleanly (text + visually inferred)
        all_props = []
        seen = set()
        for p in raw_panel.props_detected + raw_panel.props_implied_visual:
            p_clean = p.strip().title()
            if p_clean and p_clean.lower() not in seen:
                all_props.append(p_clean)
                seen.add(p_clean.lower())

        # Review flags & confidence calculation
        review_reasons = []
        if angle_flag:
            review_reasons.append(angle_flag)
        if size_flag:
            review_reasons.append(size_flag)
        
        # Weighted confidence score
        overall_confidence = round((angle_conf * 0.45) + (size_conf * 0.45) + (move_conf * 0.1), 2)
        flagged = bool(review_reasons) or overall_confidence < 0.75

        # Unique panel ID
        clean_scene = re.sub(r"[^\w]", "", raw_panel.scene.upper())
        clean_shot = re.sub(r"[^\w]", "", raw_panel.shot.upper())
        panel_id = f"SCENE_{clean_scene}_{version.upper()}_SHOT_{clean_shot}_P{raw_panel.panel_number}"

        return NormalizedPanel(
            panel_id=panel_id,
            scene=raw_panel.scene,
            shot=raw_panel.shot,
            panel_number=raw_panel.panel_number,
            version=version,
            dialogue=raw_panel.dialogue,
            action_notes=raw_panel.action_notes,
            camera_angle=norm_angle,
            shot_size=norm_size,
            camera_movement=norm_move,
            characters=[c.strip().title() for c in raw_panel.characters if c.strip()],
            props=all_props,
            props_implied_visual=[p.strip().title() for p in raw_panel.props_implied_visual if p.strip()],
            vfx_tags=vfx_tags,
            normalization_confidence=overall_confidence,
            flagged_for_review=flagged,
            review_reasons=review_reasons,
            image_path=raw_panel.image_path,
        )

"""Revision & Delta Checker Agent for Project Rosetta Board.

Compares storyboard revisions (e.g. Scene 42 V1 vs V2), identifies added, deleted,
or modified shots, and generates high-priority 1st AD alerts for prop additions,
VFX changes, and framing alterations.
"""

from typing import Dict, List, Tuple
from app.models import NormalizedPanel, PanelDelta, RevisionReport


class DeltaChecker:
    """Compares two storyboard scene revisions and produces actionable production alerts."""

    def compare_revisions(
        self,
        scene: str,
        old_version: str,
        new_version: str,
        old_panels: List[NormalizedPanel],
        new_panels: List[NormalizedPanel],
    ) -> RevisionReport:
        """Compare old and new panels for a scene and compile a revision delta report."""
        # Index panels by (shot, panel_number)
        old_map: Dict[Tuple[str, int], NormalizedPanel] = {
            (p.shot.upper(), p.panel_number): p for p in old_panels
        }
        new_map: Dict[Tuple[str, int], NormalizedPanel] = {
            (p.shot.upper(), p.panel_number): p for p in new_panels
        }

        old_keys = set(old_map.keys())
        new_keys = set(new_map.keys())

        added_keys = new_keys - old_keys
        deleted_keys = old_keys - new_keys
        common_keys = new_keys & old_keys

        deltas: List[PanelDelta] = []
        ad_alerts: List[str] = []
        shots_added: List[str] = []
        shots_deleted: List[str] = []
        shots_modified: List[str] = []

        # 1. Process Added Panels
        for key in sorted(added_keys):
            shot, panel_num = key
            panel = new_map[key]
            shots_added.append(shot)

            prop_list = ", ".join(panel.props) if panel.props else "None"
            vfx_list = ", ".join(panel.vfx_tags) if panel.vfx_tags else "None"

            summary = f"NEW SHOT: Shot {shot} ({panel.shot_size}, {panel.camera_angle}) added."
            if panel.props:
                summary += f" Props: {prop_list}."
            if panel.vfx_tags:
                summary += f" VFX: {vfx_list}."

            ad_alerts.append(f"Alert [Added Shot]: Shot {shot} added to Scene {scene} ({panel.shot_size}). Props: {prop_list}.")
            if panel.vfx_tags:
                ad_alerts.append(f"Alert [VFX Added]: Shot {shot} requires VFX: {vfx_list}.")

            deltas.append(
                PanelDelta(
                    shot=shot,
                    panel_number=panel_num,
                    status="ADDED",
                    changes=["Shot added in this revision"],
                    prop_alerts=[f"Requires props: {prop_list}"] if panel.props else [],
                    vfx_alerts=[f"Requires VFX: {vfx_list}"] if panel.vfx_tags else [],
                    angle_alerts=[f"Framing: {panel.shot_size}, {panel.camera_angle}"],
                    summary_alert=summary,
                )
            )

        # 2. Process Deleted Panels
        for key in sorted(deleted_keys):
            shot, panel_num = key
            panel = old_map[key]
            shots_deleted.append(shot)

            summary = f"DELETED SHOT: Shot {shot} was removed from Scene {scene}."
            ad_alerts.append(f"Alert [Deleted Shot]: Shot {shot} has been removed from Scene {scene}.")

            deltas.append(
                PanelDelta(
                    shot=shot,
                    panel_number=panel_num,
                    status="DELETED",
                    changes=["Shot removed from storyboard in this revision"],
                    summary_alert=summary,
                )
            )

        # 3. Process Common Panels (Check for Modifications)
        for key in sorted(common_keys):
            shot, panel_num = key
            old_p = old_map[key]
            new_p = new_map[key]

            changes: List[str] = []
            prop_alerts: List[str] = []
            vfx_alerts: List[str] = []
            angle_alerts: List[str] = []

            # Check Framing & Angle
            if old_p.shot_size != new_p.shot_size or old_p.camera_angle != new_p.camera_angle:
                framing_msg = f"Framing changed from {old_p.shot_size} ({old_p.camera_angle}) to {new_p.shot_size} ({new_p.camera_angle})"
                changes.append(framing_msg)
                angle_alerts.append(framing_msg)
                ad_alerts.append(f"Alert [Framing]: Shot {shot} changed from {old_p.shot_size} to {new_p.shot_size} ({new_p.camera_angle}).")

            # Check Props
            old_props_set = {p.lower() for p in old_p.props}
            new_props_set = {p.lower() for p in new_p.props}

            added_props = [p for p in new_p.props if p.lower() not in old_props_set]
            removed_props = [p for p in old_p.props if p.lower() not in new_props_set]

            for p in added_props:
                msg = f"Shot {shot} now requires a prop '{p}'; previously unarmed/unassigned."
                changes.append(f"Added prop: {p}")
                prop_alerts.append(msg)
                ad_alerts.append(f"Alert [Prop Added]: {msg}")

            for p in removed_props:
                msg = f"Shot {shot} prop '{p}' was removed."
                changes.append(f"Removed prop: {p}")
                prop_alerts.append(msg)

            # Check VFX Tags
            old_vfx_set = {v.lower() for v in old_p.vfx_tags}
            new_vfx_set = {v.lower() for v in new_p.vfx_tags}

            added_vfx = [v for v in new_p.vfx_tags if v.lower() not in old_vfx_set]
            removed_vfx = [v for v in old_p.vfx_tags if v.lower() not in new_vfx_set]

            for v in added_vfx:
                msg = f"Shot {shot} now requires new VFX element: '{v}'."
                changes.append(f"Added VFX: {v}")
                vfx_alerts.append(msg)
                ad_alerts.append(f"Alert [VFX Added]: {msg}")

            for v in removed_vfx:
                changes.append(f"Removed VFX: {v}")

            # Check Dialogue & Action Notes
            if old_p.dialogue.strip() != new_p.dialogue.strip() and new_p.dialogue.strip():
                changes.append(f"Dialogue updated: '{new_p.dialogue}'")
            if old_p.action_notes.strip() != new_p.action_notes.strip() and new_p.action_notes.strip():
                changes.append(f"Action direction updated: '{new_p.action_notes}'")

            # Status determination
            if changes:
                shots_modified.append(shot)
                summary = f"MODIFIED: Shot {shot} has {len(changes)} update(s). " + "; ".join(changes[:2])
                deltas.append(
                    PanelDelta(
                        shot=shot,
                        panel_number=panel_num,
                        status="MODIFIED",
                        changes=changes,
                        prop_alerts=prop_alerts,
                        vfx_alerts=vfx_alerts,
                        angle_alerts=angle_alerts,
                        summary_alert=summary,
                    )
                )
            else:
                deltas.append(
                    PanelDelta(
                        shot=shot,
                        panel_number=panel_num,
                        status="UNCHANGED",
                        summary_alert=f"Shot {shot} unchanged.",
                    )
                )

        return RevisionReport(
            scene=scene,
            old_version=old_version,
            new_version=new_version,
            total_shots_old=len(old_panels),
            total_shots_new=len(new_panels),
            shots_added=sorted(list(set(shots_added))),
            shots_deleted=sorted(list(set(shots_deleted))),
            shots_modified=sorted(list(set(shots_modified))),
            ad_alerts=ad_alerts,
            deltas=deltas,
        )

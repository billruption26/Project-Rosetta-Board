"""ClickHouse Cloud & Analytical Database Toolset for Project Rosetta Board.

Supports ClickHouse Cloud via clickhouse-connect, mcp-clickhouse MCP adapter,
and a seamless SQLite fallback for local offline testing and prototyping.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import BASE_DIR, config
from app.models import NormalizedPanel, PanelDelta, PropRentalInfo, RevisionReport


class ClickHouseDatabase:
    """Manages analytical persistence for storyboard panels, revisions, and taxonomy."""

    def __init__(self):
        self.use_clickhouse = False
        self.client = None
        self.db_path = BASE_DIR / "rosetta_board_local.db"
        self._init_connection()
        self._create_tables()

    def _init_connection(self):
        """Attempt ClickHouse connection; fall back to local store if unavailable."""
        if config.CLICKHOUSE_HOST and config.CLICKHOUSE_HOST != "localhost":
            try:
                import clickhouse_connect
                self.client = clickhouse_connect.get_client(
                    host=config.CLICKHOUSE_HOST,
                    port=config.CLICKHOUSE_PORT,
                    username=config.CLICKHOUSE_USER,
                    password=config.CLICKHOUSE_PASSWORD,
                    database=config.CLICKHOUSE_DATABASE,
                    secure=config.CLICKHOUSE_SECURE,
                )
                self.use_clickhouse = True
                return
            except Exception:
                self.use_clickhouse = False

        # Fallback to local analytical SQLite engine
        self.use_clickhouse = False

    def _create_tables(self):
        """Initialize required analytical tables."""
        if self.use_clickhouse and self.client:
            try:
                self.client.command(f"CREATE DATABASE IF NOT EXISTS {config.CLICKHOUSE_DATABASE}")
                self.client.command(f"""
                CREATE TABLE IF NOT EXISTS {config.CLICKHOUSE_DATABASE}.storyboard_panels (
                    panel_id String,
                    scene String,
                    shot String,
                    panel_number Int32,
                    version String,
                    dialogue String,
                    action_notes String,
                    camera_angle String,
                    shot_size String,
                    camera_movement String,
                    characters Array(String),
                    props Array(String),
                    props_implied_visual Array(String),
                    vfx_tags Array(String),
                    normalization_confidence Float32,
                    flagged_for_review UInt8,
                    review_reasons Array(String),
                    rental_estimates_json String,
                    image_path String,
                    created_at String
                ) ENGINE = MergeTree()
                ORDER BY (scene, version, shot, panel_number)
                """)
                self.client.command(f"""
                CREATE TABLE IF NOT EXISTS {config.CLICKHOUSE_DATABASE}.storyboard_revisions (
                    scene String,
                    old_version String,
                    new_version String,
                    total_shots_old Int32,
                    total_shots_new Int32,
                    shots_added Array(String),
                    shots_deleted Array(String),
                    shots_modified Array(String),
                    ad_alerts Array(String),
                    deltas_json String,
                    created_at String
                ) ENGINE = MergeTree()
                ORDER BY (scene, new_version)
                """)
                return
            except Exception:
                self.use_clickhouse = False

        # Local SQLite schema
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS storyboard_panels (
                panel_id TEXT PRIMARY KEY,
                scene TEXT,
                shot TEXT,
                panel_number INTEGER,
                version TEXT,
                dialogue TEXT,
                action_notes TEXT,
                camera_angle TEXT,
                shot_size TEXT,
                camera_movement TEXT,
                characters TEXT,
                props TEXT,
                props_implied_visual TEXT,
                vfx_tags TEXT,
                normalization_confidence REAL,
                flagged_for_review INTEGER,
                review_reasons TEXT,
                rental_estimates_json TEXT,
                image_path TEXT,
                created_at TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS storyboard_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene TEXT,
                old_version TEXT,
                new_version TEXT,
                total_shots_old INTEGER,
                total_shots_new INTEGER,
                shots_added TEXT,
                shots_deleted TEXT,
                shots_modified TEXT,
                ad_alerts TEXT,
                deltas_json TEXT,
                created_at TEXT
            )
            """)
            conn.commit()

    def insert_panels(self, panels: List[NormalizedPanel]) -> Dict[str, Any]:
        """Commit normalized storyboard panels into the analytical database."""
        if not panels:
            return {"status": "success", "count": 0}

        if self.use_clickhouse and self.client:
            data = []
            for p in panels:
                data.append([
                    p.panel_id,
                    p.scene,
                    p.shot,
                    p.panel_number,
                    p.version,
                    p.dialogue,
                    p.action_notes,
                    p.camera_angle,
                    p.shot_size,
                    p.camera_movement,
                    p.characters,
                    p.props,
                    p.props_implied_visual,
                    p.vfx_tags,
                    p.normalization_confidence,
                    1 if p.flagged_for_review else 0,
                    p.review_reasons,
                    json.dumps([r.model_dump() for r in p.rental_estimates]),
                    p.image_path or "",
                    p.created_at,
                ])
            column_names = [
                "panel_id", "scene", "shot", "panel_number", "version",
                "dialogue", "action_notes", "camera_angle", "shot_size", "camera_movement",
                "characters", "props", "props_implied_visual", "vfx_tags",
                "normalization_confidence", "flagged_for_review", "review_reasons",
                "rental_estimates_json", "image_path", "created_at"
            ]
            self.client.insert(f"{config.CLICKHOUSE_DATABASE}.storyboard_panels", data, column_names=column_names)
            return {"status": "success", "backend": "clickhouse_cloud", "count": len(panels)}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for p in panels:
                cursor.execute("""
                INSERT OR REPLACE INTO storyboard_panels (
                    panel_id, scene, shot, panel_number, version,
                    dialogue, action_notes, camera_angle, shot_size, camera_movement,
                    characters, props, props_implied_visual, vfx_tags,
                    normalization_confidence, flagged_for_review, review_reasons,
                    rental_estimates_json, image_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.panel_id,
                    p.scene,
                    p.shot,
                    p.panel_number,
                    p.version,
                    p.dialogue,
                    p.action_notes,
                    p.camera_angle,
                    p.shot_size,
                    p.camera_movement,
                    json.dumps(p.characters),
                    json.dumps(p.props),
                    json.dumps(p.props_implied_visual),
                    json.dumps(p.vfx_tags),
                    p.normalization_confidence,
                    1 if p.flagged_for_review else 0,
                    json.dumps(p.review_reasons),
                    json.dumps([r.model_dump() for r in p.rental_estimates]),
                    p.image_path or "",
                    p.created_at,
                ))
            conn.commit()

        return {"status": "success", "backend": "local_sqlite", "count": len(panels)}

    def get_panels_for_scene(self, scene: str, version: Optional[str] = None) -> List[NormalizedPanel]:
        """Fetch panels for a scene, optionally filtered by version."""
        results: List[NormalizedPanel] = []

        if self.use_clickhouse and self.client:
            query = f"SELECT * FROM {config.CLICKHOUSE_DATABASE}.storyboard_panels WHERE scene = %(scene)s"
            params = {"scene": scene}
            if version:
                query += " AND version = %(version)s"
                params["version"] = version
            query += " ORDER BY shot, panel_number"
            res = self.client.query(query, parameters=params)
            for row in res.result_rows:
                rental_data = [PropRentalInfo(**item) for item in json.loads(row[17])] if row[17] else []
                results.append(NormalizedPanel(
                    panel_id=row[0], scene=row[1], shot=row[2], panel_number=row[3], version=row[4],
                    dialogue=row[5], action_notes=row[6], camera_angle=row[7], shot_size=row[8], camera_movement=row[9],
                    characters=list(row[10]) if row[10] else [],
                    props=list(row[11]) if row[11] else [],
                    props_implied_visual=list(row[12]) if row[12] else [],
                    vfx_tags=list(row[13]) if row[13] else [],
                    normalization_confidence=row[14], flagged_for_review=bool(row[15]),
                    review_reasons=list(row[16]) if row[16] else [],
                    rental_estimates=rental_data, image_path=row[18] or None, created_at=row[19]
                ))
            return results

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM storyboard_panels WHERE scene = ?"
            params = [scene]
            if version:
                query += " AND version = ?"
                params.append(version)
            query += " ORDER BY shot, panel_number"
            cursor.execute(query, params)
            for row in cursor.fetchall():
                rental_data = [PropRentalInfo(**item) for item in json.loads(row[17])] if row[17] else []
                results.append(NormalizedPanel(
                    panel_id=row[0], scene=row[1], shot=row[2], panel_number=row[3], version=row[4],
                    dialogue=row[5], action_notes=row[6], camera_angle=row[7], shot_size=row[8], camera_movement=row[9],
                    characters=json.loads(row[10]) if row[10] else [],
                    props=json.loads(row[11]) if row[11] else [],
                    props_implied_visual=json.loads(row[12]) if row[12] else [],
                    vfx_tags=json.loads(row[13]) if row[13] else [],
                    normalization_confidence=row[14],
                    flagged_for_review=bool(row[15]),
                    review_reasons=json.loads(row[16]) if row[16] else [],
                    rental_estimates=rental_data,
                    image_path=row[18] or None,
                    created_at=row[19],
                ))

        return results

    def get_available_versions(self, scene: str) -> List[str]:
        """Return list of distinct versions for a given scene."""
        if self.use_clickhouse and self.client:
            res = self.client.query(
                f"SELECT DISTINCT version FROM {config.CLICKHOUSE_DATABASE}.storyboard_panels WHERE scene = %(scene)s",
                parameters={"scene": scene}
            )
            return [r[0] for r in res.result_rows]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT version FROM storyboard_panels WHERE scene = ?", (scene,))
            return [r[0] for r in cursor.fetchall()]

    def record_revision_report(self, report: RevisionReport) -> Dict[str, Any]:
        """Save a revision report with delta comparison and 1st AD alerts."""
        deltas_json = json.dumps([d.model_dump() for d in report.deltas])

        if self.use_clickhouse and self.client:
            self.client.insert(
                f"{config.CLICKHOUSE_DATABASE}.storyboard_revisions",
                [[
                    report.scene, report.old_version, report.new_version,
                    report.total_shots_old, report.total_shots_new,
                    report.shots_added, report.shots_deleted, report.shots_modified,
                    report.ad_alerts, deltas_json, report.created_at
                ]],
                column_names=[
                    "scene", "old_version", "new_version", "total_shots_old",
                    "total_shots_new", "shots_added", "shots_deleted", "shots_modified",
                    "ad_alerts", "deltas_json", "created_at"
                ]
            )
            return {"status": "success", "backend": "clickhouse_cloud"}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO storyboard_revisions (
                scene, old_version, new_version, total_shots_old, total_shots_new,
                shots_added, shots_deleted, shots_modified, ad_alerts, deltas_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report.scene, report.old_version, report.new_version,
                report.total_shots_old, report.total_shots_new,
                json.dumps(report.shots_added),
                json.dumps(report.shots_deleted),
                json.dumps(report.shots_modified),
                json.dumps(report.ad_alerts),
                deltas_json,
                report.created_at,
            ))
            conn.commit()

        return {"status": "success", "backend": "local_sqlite"}

    def get_latest_revision_report(self, scene: str) -> Optional[RevisionReport]:
        """Fetch the most recent revision delta report for a scene."""
        if self.use_clickhouse and self.client:
            query = (
                f"SELECT scene, old_version, new_version, total_shots_old, total_shots_new, "
                f"shots_added, shots_deleted, shots_modified, ad_alerts, deltas_json, created_at "
                f"FROM {config.CLICKHOUSE_DATABASE}.storyboard_revisions WHERE scene = %(scene)s "
                f"ORDER BY created_at DESC LIMIT 1"
            )
            res = self.client.query(query, parameters={"scene": scene})
            if not res.result_rows:
                return None
            row = res.result_rows[0]
            deltas = [PanelDelta(**d) for d in json.loads(row[9])] if row[9] else []
            return RevisionReport(
                scene=row[0],
                old_version=row[1],
                new_version=row[2],
                total_shots_old=row[3],
                total_shots_new=row[4],
                shots_added=list(row[5]) if row[5] else [],
                shots_deleted=list(row[6]) if row[6] else [],
                shots_modified=list(row[7]) if row[7] else [],
                ad_alerts=list(row[8]) if row[8] else [],
                deltas=deltas,
                created_at=row[10],
            )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT scene, old_version, new_version, total_shots_old, total_shots_new, "
                "shots_added, shots_deleted, shots_modified, ad_alerts, deltas_json, created_at "
                "FROM storyboard_revisions WHERE scene = ? ORDER BY id DESC LIMIT 1",
                (scene,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            deltas = [PanelDelta(**d) for d in json.loads(row[9])] if row[9] else []
            return RevisionReport(
                scene=row[0],
                old_version=row[1],
                new_version=row[2],
                total_shots_old=row[3],
                total_shots_new=row[4],
                shots_added=json.loads(row[5]) if row[5] else [],
                shots_deleted=json.loads(row[6]) if row[6] else [],
                shots_modified=json.loads(row[7]) if row[7] else [],
                ad_alerts=json.loads(row[8]) if row[8] else [],
                deltas=deltas,
                created_at=row[10],
            )

    def get_all_scenes(self) -> List[str]:
        """Get unique scene identifiers stored in the database."""
        if self.use_clickhouse and self.client:
            res = self.client.query(
                f"SELECT DISTINCT scene FROM {config.CLICKHOUSE_DATABASE}.storyboard_panels ORDER BY scene"
            )
            return [r[0] for r in res.result_rows]

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT scene FROM storyboard_panels ORDER BY scene")
            return [r[0] for r in cursor.fetchall()]


# Global database instance
db = ClickHouseDatabase()

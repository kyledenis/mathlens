"""FTS5 full-text search index for MathLens explorations."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    slug: str
    topic: str
    snippet: str
    rank: float


class SearchIndex:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS explorations_fts USING fts5(slug, topic, content, tokenize='porter unicode61');
            CREATE TABLE IF NOT EXISTS exploration_meta(slug TEXT PRIMARY KEY, topic TEXT NOT NULL, indexed_at TEXT NOT NULL);
        """
        )
        self._conn.commit()

    def index_exploration(self, slug: str, workspace_dir: Path) -> None:
        parts: list[str] = []
        summary = workspace_dir / "summary.md"
        if summary.exists():
            parts.append(summary.read_text())
        plan = workspace_dir / "plan.json"
        if plan.exists():
            try:
                for s in json.loads(plan.read_text()).get("theorem_statements", []):
                    parts.append(s)
            except json.JSONDecodeError:
                pass
        proof = workspace_dir / "proof.lean"
        if proof.exists():
            parts.append(proof.read_text())
        content = "\n".join(parts)
        topic = slug
        meta_path = workspace_dir / "meta.json"
        if meta_path.exists():
            try:
                topic = json.loads(meta_path.read_text()).get("topic", slug)
            except json.JSONDecodeError:
                pass
        self.remove_exploration(slug)
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO explorations_fts(slug, topic, content) VALUES (?, ?, ?)",
            (slug, topic, content),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO exploration_meta(slug, topic, indexed_at) VALUES (?, ?, ?)",
            (slug, topic, now),
        )
        self._conn.commit()

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        if not query.strip():
            return []
        cursor = self._conn.execute(
            "SELECT slug, topic, snippet(explorations_fts, 2, '<b>', '</b>', '...', 32), rank FROM explorations_fts WHERE explorations_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, limit),
        )
        return [
            SearchResult(slug=r[0], topic=r[1], snippet=r[2], rank=r[3])
            for r in cursor.fetchall()
        ]

    def remove_exploration(self, slug: str) -> None:
        self._conn.execute("DELETE FROM explorations_fts WHERE slug = ?", (slug,))
        self._conn.execute("DELETE FROM exploration_meta WHERE slug = ?", (slug,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

from __future__ import annotations

import sqlite3
from pathlib import Path

from distill.indexing.graph_builder import GraphEdge, GraphNode

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
  id            TEXT PRIMARY KEY,
  kind          TEXT NOT NULL,
  name          TEXT NOT NULL,
  file_path     TEXT NOT NULL,
  language      TEXT NOT NULL,
  start_line    INT,
  end_line      INT,
  docstring     TEXT,
  content_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
  src_id  TEXT NOT NULL,
  dst_id  TEXT NOT NULL,
  kind    TEXT NOT NULL,
  PRIMARY KEY (src_id, dst_id, kind)
);

CREATE TABLE IF NOT EXISTS cache (
  content_hash TEXT PRIMARY KEY,
  parsed_json  TEXT,
  embedding    BLOB
);

CREATE INDEX IF NOT EXISTS idx_nodes_file_path ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id);
"""


class GraphStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM nodes")
        self.conn.execute("DELETE FROM edges")
        self.conn.commit()

    def clear_file(self, file_path: str) -> None:
        """Remove every node belonging to `file_path` (and edges touching them),
        used by incremental re-indexing before re-inserting fresh nodes."""
        ids = [
            row[0]
            for row in self.conn.execute(
                "SELECT id FROM nodes WHERE file_path = ?", (file_path,)
            )
        ]
        self.conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
        if ids:
            placeholders = ",".join("?" * len(ids))
            self.conn.execute(
                f"DELETE FROM edges WHERE src_id IN ({placeholders}) OR dst_id IN ({placeholders})",
                ids + ids,
            )
        self.conn.commit()

    def upsert_nodes(self, nodes: list[GraphNode]) -> None:
        self.conn.executemany(
            """INSERT INTO nodes (id, kind, name, file_path, language, start_line, end_line, docstring, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 kind=excluded.kind, name=excluded.name, file_path=excluded.file_path,
                 language=excluded.language, start_line=excluded.start_line,
                 end_line=excluded.end_line, docstring=excluded.docstring,
                 content_hash=excluded.content_hash""",
            [
                (n.id, n.kind, n.name, n.file_path, n.language, n.start_line, n.end_line, n.docstring, n.content_hash)
                for n in nodes
            ],
        )
        self.conn.commit()

    def insert_edges(self, edges: list[GraphEdge]) -> None:
        self.conn.executemany(
            "INSERT OR IGNORE INTO edges (src_id, dst_id, kind) VALUES (?, ?, ?)",
            [(e.src_id, e.dst_id, e.kind) for e in edges],
        )
        self.conn.commit()

    def all_nodes(self) -> list[GraphNode]:
        rows = self.conn.execute(
            "SELECT id, kind, name, file_path, language, start_line, end_line, docstring, content_hash FROM nodes"
        ).fetchall()
        return [GraphNode(*row) for row in rows]

    def all_edges(self) -> list[GraphEdge]:
        rows = self.conn.execute("SELECT src_id, dst_id, kind FROM edges").fetchall()
        return [GraphEdge(*row) for row in rows]

    def node_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def edge_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    def get_node(self, node_id: str) -> GraphNode | None:
        row = self.conn.execute(
            "SELECT id, kind, name, file_path, language, start_line, end_line, docstring, content_hash FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return GraphNode(*row) if row else None

    def content_hash_for_file(self, file_path: str) -> str | None:
        row = self.conn.execute(
            "SELECT content_hash FROM nodes WHERE file_path = ? AND kind = 'FILE'",
            (file_path,),
        ).fetchone()
        return row[0] if row else None

    def cache_get(self, content_hash: str) -> tuple[str | None, bytes | None] | None:
        row = self.conn.execute(
            "SELECT parsed_json, embedding FROM cache WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row if row else None

    def cache_put(self, content_hash: str, parsed_json: str | None, embedding: bytes | None) -> None:
        self.conn.execute(
            """INSERT INTO cache (content_hash, parsed_json, embedding) VALUES (?, ?, ?)
               ON CONFLICT(content_hash) DO UPDATE SET
                 parsed_json=excluded.parsed_json, embedding=excluded.embedding""",
            (content_hash, parsed_json, embedding),
        )
        self.conn.commit()

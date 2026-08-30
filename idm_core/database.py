"""
SQLite Database Layer for IDM Linux State Persistence
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def init_db(self):
        """Initialize database schema with tables and indexes."""
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    total_bytes INTEGER DEFAULT 0,
                    downloaded_bytes INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'queued',
                    category TEXT DEFAULT 'General',
                    connections_count INTEGER DEFAULT 8,
                    speed_limit INTEGER DEFAULT 0,
                    speed INTEGER DEFAULT 0,
                    eta INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    completed_at REAL DEFAULT NULL,
                    headers_json TEXT DEFAULT '{}',
                    error_msg TEXT DEFAULT '',
                    queue_id TEXT DEFAULT NULL,
                    resumable INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    download_id TEXT NOT NULL,
                    segment_index INTEGER NOT NULL,
                    start_byte INTEGER NOT NULL,
                    current_byte INTEGER NOT NULL,
                    end_byte INTEGER NOT NULL,
                    status TEXT DEFAULT 'queued',
                    temp_path TEXT NOT NULL,
                    UNIQUE(download_id, segment_index),
                    FOREIGN KEY(download_id) REFERENCES downloads(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS queues (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    max_concurrent INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 0,
                    start_time TEXT DEFAULT NULL,
                    stop_time TEXT DEFAULT NULL,
                    post_action TEXT DEFAULT 'none'
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_downloads_status ON downloads(status);
                CREATE INDEX IF NOT EXISTS idx_downloads_category ON downloads(category);
                CREATE INDEX IF NOT EXISTS idx_segments_download_id ON segments(download_id);
            """)
            self._conn.commit()
            
            # Ensure default main queue exists
            cur.execute("SELECT id FROM queues WHERE id = 'main'")
            if not cur.fetchone():
                cur.execute("INSERT INTO queues (id, name, max_concurrent, is_active) VALUES ('main', 'Main Download Queue', 1, 0)")
                self._conn.commit()

    def add_download(
        self,
        url: str,
        filename: str,
        save_path: str,
        total_bytes: int = 0,
        category: str = "General",
        connections_count: int = 8,
        headers: Optional[Dict[str, str]] = None,
        queue_id: Optional[str] = None,
        status: str = "queued",
        resumable: bool = True
    ) -> str:
        """Insert a new download record and return its generated ID."""
        download_id = f"dl-{uuid.uuid4().hex[:12]}"
        headers_json = json.dumps(headers or {})
        now = time.time()
        
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT INTO downloads (
                    id, url, filename, save_path, total_bytes, downloaded_bytes,
                    status, category, connections_count, created_at, headers_json,
                    queue_id, resumable
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
            """, (
                download_id, url, filename, save_path, total_bytes,
                status, category, connections_count, now, headers_json,
                queue_id, 1 if resumable else 0
            ))
            self._conn.commit()
        return download_id

    def update_download(self, download_id: str, **kwargs) -> bool:
        """Update fields of a download record."""
        if not kwargs:
            return False
            
        fields = []
        values = []
        for k, v in kwargs.items():
            if k == "headers":
                fields.append("headers_json = ?")
                values.append(json.dumps(v))
            elif k == "resumable":
                fields.append("resumable = ?")
                values.append(1 if v else 0)
            else:
                fields.append(f"{k} = ?")
                values.append(v)
                
        values.append(download_id)
        query = f"UPDATE downloads SET {', '.join(fields)} WHERE id = ?"
        
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, values)
            self._conn.commit()
            return cur.rowcount > 0

    def get_download(self, download_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single download record as dictionary."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_download_dict(row)

    def list_downloads(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        queue_id: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List downloads matching filter criteria."""
        clauses = []
        params = []
        
        if category and category != "All Downloads":
            if category in ["Finished", "completed"]:
                clauses.append("status = 'completed'")
            elif category in ["Unfinished", "active"]:
                clauses.append("status != 'completed'")
            else:
                clauses.append("category = ?")
                params.append(category)
                
        if status:
            clauses.append("status = ?")
            params.append(status)
            
        if queue_id:
            clauses.append("queue_id = ?")
            params.append(queue_id)
            
        if search:
            clauses.append("(filename LIKE ? OR url LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
            
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM downloads {where} ORDER BY created_at DESC"
        
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [self._row_to_download_dict(r) for r in rows]

    def delete_download(self, download_id: str) -> bool:
        """Delete download record and its segments."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM segments WHERE download_id = ?", (download_id,))
            cur.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def save_segments(self, download_id: str, segments: List[Dict[str, Any]]):
        """Save or replace all segments for a download."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM segments WHERE download_id = ?", (download_id,))
            for s in segments:
                cur.execute("""
                    INSERT INTO segments (
                        download_id, segment_index, start_byte, current_byte, end_byte, status, temp_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    download_id,
                    s.get("index", s.get("segment_index", 0)),
                    s["start_byte"],
                    s.get("current_byte", s["start_byte"]),
                    s["end_byte"],
                    s.get("status", "queued"),
                    s.get("temp_path", "")
                ))
            self._conn.commit()

    def get_segments(self, download_id: str) -> List[Dict[str, Any]]:
        """Retrieve segments for a download ordered by index."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM segments WHERE download_id = ? ORDER BY segment_index ASC", (download_id,))
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "download_id": r["download_id"],
                    "index": r["segment_index"],
                    "start_byte": r["start_byte"],
                    "current_byte": r["current_byte"],
                    "end_byte": r["end_byte"],
                    "status": r["status"],
                    "temp_path": r["temp_path"],
                }
                for r in rows
            ]

    def update_segment(self, download_id: str, segment_index: int, **kwargs) -> bool:
        """Update a specific segment's current byte or status."""
        if not kwargs:
            return False
        fields = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values()) + [download_id, segment_index]
        query = f"UPDATE segments SET {', '.join(fields)} WHERE download_id = ? AND segment_index = ?"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(query, values)
            self._conn.commit()
            return cur.rowcount > 0

    def delete_segments(self, download_id: str):
        """Delete all segment records for a download."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM segments WHERE download_id = ?", (download_id,))
            self._conn.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieve configuration value by key."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT value_json FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value_json"])
            except Exception:
                return default

    def set_setting(self, key: str, value: Any):
        """Store configuration value by key."""
        with self._lock:
            cur = self._conn.cursor()
            val_json = json.dumps(value)
            cur.execute("""
                INSERT INTO settings (key, value_json) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
            """, (key, val_json))
            self._conn.commit()

    def list_queues(self) -> List[Dict[str, Any]]:
        """List all download queues."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM queues")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def create_queue(self, name: str, max_concurrent: int = 1) -> str:
        """Create a new download queue."""
        queue_id = f"q-{uuid.uuid4().hex[:8]}"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO queues (id, name, max_concurrent, is_active) VALUES (?, ?, ?, 0)",
                (queue_id, name, max_concurrent)
            )
            self._conn.commit()
        return queue_id

    def _row_to_download_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        try:
            d["headers"] = json.loads(d.get("headers_json") or "{}")
        except Exception:
            d["headers"] = {}
        d["resumable"] = bool(d.get("resumable", 1))
        return d

    def close(self):
        """Close SQLite database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()

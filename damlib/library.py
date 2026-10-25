"""Core library: asset ingestion, metadata, taxonomy, search, reuse, publishing.

Storage is SQLite. Binary file contents are never parsed: for images and
other binary files only file metadata (name, size, type by extension,
modification date, SHA-256 checksum) is recorded. Text files are not read
into the index either; search runs over the metadata (title, description,
tags, category) supplied at ingest or edited later.

Status transitions (enforced):
    draft -> published, draft -> archived,
    published -> archived, archived -> draft
Any other transition raises ValueError.
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Extension -> broad media type. Used for metadata only, not content parsing.
_TYPE_BY_EXT = {
    ".txt": "text", ".md": "text", ".markdown": "text", ".html": "text",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image",
    ".svg": "image", ".webp": "image",
    ".mp4": "video", ".mov": "video", ".webm": "video",
    ".mp3": "audio", ".wav": "audio",
    ".pdf": "document", ".docx": "document",
}

ALLOWED_TRANSITIONS = {
    "draft": {"published", "archived"},
    "published": {"archived"},
    "archived": {"draft"},
}


@dataclass
class Asset:
    id: int
    filename: str
    source_path: str
    size_bytes: int
    filetype: str
    created_date: str
    checksum: str
    title: str
    description: str = ""
    tags: list = field(default_factory=list)
    category: str = ""
    licence: str = ""
    status: str = "draft"
    reuse_count: int = 0

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row[0], filename=row[1], source_path=row[2], size_bytes=row[3],
            filetype=row[4], created_date=row[5], checksum=row[6],
            title=row[7], description=row[8] or "",
            tags=json.loads(row[9]) if row[9] else [],
            category=row[10] or "", licence=row[11] or "",
            status=row[12], reuse_count=row[13],
        )


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _filetype(path: Path) -> str:
    return _TYPE_BY_EXT.get(path.suffix.lower(), "other")


class Library:
    """A SQLite-backed searchable asset library."""

    def __init__(self, db_path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                filetype TEXT NOT NULL,
                created_date TEXT NOT NULL,
                checksum TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                category TEXT DEFAULT '',
                licence TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                reuse_count INTEGER DEFAULT 0
            )"""
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    # -- ingestion ------------------------------------------------------
    def add_asset(self, filepath, title=None, description="", tags=None,
                  category="", licence=""):
        """Add a file. Returns (Asset, is_new). Identical content dedups
        on SHA-256: the existing asset is returned with is_new=False."""
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"no such file: {filepath}")
        checksum = _checksum(path)
        existing = self.get_by_checksum(checksum)
        if existing is not None:
            return existing, False
        stat = path.stat()
        created = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        asset_title = title or path.stem
        cur = self.conn.execute(
            """INSERT INTO assets
               (filename, source_path, size_bytes, filetype, created_date,
                checksum, title, description, tags, category, licence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (path.name, str(path), stat.st_size, _filetype(path), created,
             checksum, asset_title, description,
             json.dumps(list(tags or [])), category, licence),
        )
        self.conn.commit()
        return self.get(cur.lastrowid), True

    def get(self, asset_id):
        row = self.conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return Asset.from_row(row) if row else None

    def get_by_checksum(self, checksum):
        row = self.conn.execute(
            "SELECT * FROM assets WHERE checksum = ?", (checksum,)).fetchone()
        return Asset.from_row(row) if row else None

    # -- metadata -------------------------------------------------------
    def update_asset(self, asset_id, title=None, description=None, tags=None,
                     category=None, licence=None):
        asset = self.get(asset_id)
        if asset is None:
            raise KeyError(f"no asset with id {asset_id}")
        updates, values = [], []
        for field, value in (("title", title), ("description", description),
                             ("category", category), ("licence", licence)):
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)
        if tags is not None:
            updates.append("tags = ?")
            values.append(json.dumps(list(tags)))
        if not updates:
            return asset
        values.append(asset_id)
        self.conn.execute(
            f"UPDATE assets SET {', '.join(updates)} WHERE id = ?", values)
        self.conn.commit()
        return self.get(asset_id)

    # -- status / reuse -------------------------------------------------
    def set_status(self, asset_id, new_status):
        asset = self.get(asset_id)
        if asset is None:
            raise KeyError(f"no asset with id {asset_id}")
        if new_status not in ALLOWED_TRANSITIONS.get(asset.status, set()):
            raise ValueError(
                f"cannot move asset {asset_id} from {asset.status} "
                f"to {new_status}")
        self.conn.execute("UPDATE assets SET status = ? WHERE id = ?",
                          (new_status, asset_id))
        self.conn.commit()
        return self.get(asset_id)

    def publish(self, asset_id):
        return self.set_status(asset_id, "published")

    def record_reuse(self, asset_id):
        asset = self.get(asset_id)
        if asset is None:
            raise KeyError(f"no asset with id {asset_id}")
        self.conn.execute(
            "UPDATE assets SET reuse_count = reuse_count + 1 WHERE id = ?",
            (asset_id,))
        self.conn.commit()
        return self.get(asset_id)

    # -- listing / search ----------------------------------------------
    def list_assets(self, status=None, category=None, tag=None):
        rows = self.conn.execute("SELECT * FROM assets ORDER BY title").fetchall()
        assets = [Asset.from_row(r) for r in rows]
        if status:
            assets = [a for a in assets if a.status == status]
        if category:
            assets = [a for a in assets if a.category.lower() == category.lower()]
        if tag:
            assets = [a for a in assets
                      if tag.lower() in (t.lower() for t in a.tags)]
        return assets

    def search(self, query="", tag=None, category=None):
        """Ranked search over metadata. Scoring per query token:
        title hit +10, exact tag hit +5, description hit +3, category hit +2.
        Results are score-descending, then title-ascending. With an empty
        query, filtered assets are returned in title order."""
        tokens = [t for t in query.lower().split() if t]
        candidates = self.list_assets(category=category, tag=tag)
        if not tokens:
            return [(a, 0) for a in candidates]
        scored = []
        for asset in candidates:
            title, desc = asset.title.lower(), asset.description.lower()
            tags_lower = [t.lower() for t in asset.tags]
            score = 0
            for token in tokens:
                if token in title:
                    score += 10
                if token in tags_lower:
                    score += 5
                if token in desc:
                    score += 3
                if token in asset.category.lower():
                    score += 2
            if score > 0:
                scored.append((asset, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].title.lower()))
        return scored

    # -- stats ----------------------------------------------------------
    def stats(self):
        assets = self.list_assets()
        by_status, by_category = {}, {}
        for asset in assets:
            by_status[asset.status] = by_status.get(asset.status, 0) + 1
            key = asset.category or "(uncategorised)"
            by_category[key] = by_category.get(key, 0) + 1
        return {
            "total": len(assets),
            "by_status": by_status,
            "by_category": by_category,
            "total_reuses": sum(a.reuse_count for a in assets),
        }

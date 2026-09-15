from __future__ import annotations
from typing import Any

def ensure_build250_schema(db: Any) -> None:
    # Production-freeze marker only: no feature tables, no destructive migration.
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','250.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('application_build','250.0')")
    db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('release_line','EagleEye Intelligence Platform 1.0 RC')")
    db.conn.commit()

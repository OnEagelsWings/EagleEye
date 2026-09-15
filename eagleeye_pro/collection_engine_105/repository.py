from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .orm import CollectionJobORM, CollectionPageORM, RobotsDecisionORM


class CollectionRepository105:
    def __init__(self, db_path: str | Path):
        self.engine = create_engine(f"sqlite:///{Path(db_path)}", future=True, connect_args={"check_same_thread": False})
        self.Session = sessionmaker(self.engine, expire_on_commit=False, class_=Session)

    def close(self) -> None:
        self.engine.dispose()

    def save_job(self, data: dict[str, Any]) -> dict[str, Any]:
        with self.Session.begin() as session:
            row = session.get(CollectionJobORM, data["job_id"])
            if not row:
                row = CollectionJobORM(job_id=data["job_id"], case_id=data["case_id"], engine=data["engine"], title=data.get("title", ""),
                                       status=data["status"], seed_urls_json=json.dumps(data.get("seed_urls") or []),
                                       policy_json=json.dumps(data.get("policy") or {}, sort_keys=True), stats_json=json.dumps(data.get("stats") or {}),
                                       notes=data.get("notes", ""), error=data.get("error", ""), worker_pid=data.get("worker_pid"),
                                       created_at=data["created_at"], started_at=data.get("started_at"), completed_at=data.get("completed_at"))
                session.add(row)
            else:
                for key, value in {
                    "status": data.get("status", row.status), "stats_json": json.dumps(data.get("stats") or json.loads(row.stats_json or "{}")),
                    "error": data.get("error", row.error), "worker_pid": data.get("worker_pid", row.worker_pid),
                    "started_at": data.get("started_at", row.started_at), "completed_at": data.get("completed_at", row.completed_at),
                }.items():
                    setattr(row, key, value)
        return self.get_job(data["job_id"])

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.Session() as session:
            row = session.get(CollectionJobORM, job_id)
            if not row:
                raise KeyError(job_id)
            return self._job(row)

    def list_jobs(self, case_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self.Session() as session:
            stmt = select(CollectionJobORM)
            if case_id:
                stmt = stmt.where(CollectionJobORM.case_id == case_id)
            rows = session.scalars(stmt.order_by(CollectionJobORM.created_at.desc()).limit(limit)).all()
            return [self._job(row) for row in rows]

    def get_page_by_url(self, job_id: str, canonical_url: str) -> dict[str, Any] | None:
        with self.Session() as session:
            row = session.scalar(select(CollectionPageORM).where(CollectionPageORM.job_id == job_id, CollectionPageORM.canonical_url == canonical_url))
            return self._page(row) if row else None

    def add_page(self, data: dict[str, Any]) -> dict[str, Any]:
        with self.Session.begin() as session:
            existing = session.scalar(select(CollectionPageORM).where(CollectionPageORM.job_id == data["job_id"], CollectionPageORM.canonical_url == data["canonical_url"]))
            if existing:
                return self._page(existing)
            row = CollectionPageORM(
                page_id=data["page_id"], job_id=data["job_id"], case_id=data["case_id"], url=data["url"],
                canonical_url=data["canonical_url"], final_url=data.get("final_url") or data["canonical_url"], parent_url=data.get("parent_url", ""),
                depth=int(data.get("depth", 0)), status_code=int(data.get("status_code", 0)), mime_type=data.get("mime_type", "application/octet-stream"),
                byte_size=int(data.get("byte_size", 0)), sha256=data["sha256"], body_path=data["body_path"],
                screenshot_path=data.get("screenshot_path", ""), capture_id=data.get("capture_id"), artifact_id=data.get("artifact_id"),
                finding_id=data.get("finding_id"), title=data.get("title", ""), headers_json=json.dumps(data.get("headers") or {}, sort_keys=True),
                links_json=json.dumps(data.get("links") or []), metadata_json=json.dumps(data.get("metadata") or {}, sort_keys=True, default=str),
                fetched_at=data["fetched_at"],
            )
            session.add(row)
        return data

    def list_pages(self, job_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        with self.Session() as session:
            rows = session.scalars(select(CollectionPageORM).where(CollectionPageORM.job_id == job_id).order_by(CollectionPageORM.fetched_at).limit(limit)).all()
            return [self._page(row) for row in rows]

    def add_robots_decision(self, data: dict[str, Any]) -> None:
        with self.Session.begin() as session:
            session.add(RobotsDecisionORM(**data))

    def list_robots_decisions(self, job_id: str) -> list[dict[str, Any]]:
        with self.Session() as session:
            rows = session.scalars(select(RobotsDecisionORM).where(RobotsDecisionORM.job_id == job_id).order_by(RobotsDecisionORM.created_at)).all()
            return [{"decision_id": r.decision_id, "job_id": r.job_id, "case_id": r.case_id, "url": r.url,
                     "policy": r.policy, "allowed": bool(r.allowed), "reason": r.reason, "created_at": r.created_at} for r in rows]

    @staticmethod
    def _job(row: CollectionJobORM) -> dict[str, Any]:
        return {"job_id": row.job_id, "case_id": row.case_id, "engine": row.engine, "title": row.title, "status": row.status,
                "seed_urls": json.loads(row.seed_urls_json), "policy": json.loads(row.policy_json), "stats": json.loads(row.stats_json or "{}"),
                "notes": row.notes, "error": row.error, "worker_pid": row.worker_pid, "created_at": row.created_at,
                "started_at": row.started_at, "completed_at": row.completed_at}

    @staticmethod
    def _page(row: CollectionPageORM) -> dict[str, Any]:
        return {"page_id": row.page_id, "job_id": row.job_id, "case_id": row.case_id, "url": row.url,
                "canonical_url": row.canonical_url, "final_url": row.final_url, "parent_url": row.parent_url, "depth": row.depth,
                "status_code": row.status_code, "mime_type": row.mime_type, "byte_size": row.byte_size, "sha256": row.sha256,
                "body_path": row.body_path, "screenshot_path": row.screenshot_path, "capture_id": row.capture_id,
                "artifact_id": row.artifact_id, "finding_id": row.finding_id, "title": row.title,
                "headers": json.loads(row.headers_json or "{}"), "links": json.loads(row.links_json or "[]"),
                "metadata": json.loads(row.metadata_json or "{}"), "fetched_at": row.fetched_at}

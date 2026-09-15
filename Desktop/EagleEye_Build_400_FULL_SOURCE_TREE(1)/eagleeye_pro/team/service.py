from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

ROLE_PERMISSIONS = {
    "admin": ["case:*", "team:*", "approval:*", "export:*", "audit:read"],
    "case_manager": ["case:read", "case:update", "team:assign", "approval:request", "comment:*", "report:prepare"],
    "analyst": ["case:read", "research:*", "review:write", "evidence:candidate", "comment:*"],
    "senior_analyst": ["case:read", "research:*", "review:*", "evidence:promote", "approval:request", "comment:*", "report:prepare"],
    "legal_reviewer": ["case:read", "privacy:review", "export:approve", "approval:decide", "comment:*", "audit:read"],
    "auditor": ["case:read", "audit:read", "export:read", "comment:read"],
    "client_viewer": ["case:read_redacted", "report:read_redacted", "comment:limited"],
}

class TeamMandateService:
    """Build 29.0: Team, client/mandate separation and approval governance.

    The service intentionally does not create covert collection powers. It only controls who may
    access a case, who may approve releases, and how team decisions are documented.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def seed_defaults(self) -> None:
        for role, permissions in ROLE_PERMISSIONS.items():
            self.db.execute("""INSERT OR IGNORE INTO case_role_policies(policy_id, role_key, permissions_json, requires_four_eyes, can_export, can_assign, created_at, notes)
            VALUES(?,?,?,?,?,?,?,?)""", [
                f"pol_{role}", role, dumps(permissions), int(role in {"legal_reviewer", "admin"}), int("export:approve" in permissions or role == "admin"), int("team:assign" in permissions or role == "admin"), now_ts(), "Build 29 default role policy."
            ])

    def create_client(self, name: str, client_type: str = "mandant", contact: str = "", jurisdiction: str = "DE/EU", notes: str = "") -> Dict[str, Any]:
        if not name.strip():
            raise ValueError("Mandantenname ist erforderlich.")
        cid = new_id("client")
        self.db.execute("""INSERT INTO clients(client_id,name,client_type,contact,jurisdiction,status,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?)""", [cid, name.strip(), client_type, contact, jurisdiction, "active", now_ts(), notes])
        self.audit.log("create", "client", cid, None, {"name": name, "client_type": client_type})
        return self.get_client(cid)

    def get_client(self, client_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM clients WHERE client_id=?", [client_id])
        if not row:
            raise KeyError(f"Mandant nicht gefunden: {client_id}")
        return row

    def list_clients(self, active_only: bool = True) -> List[Dict[str, Any]]:
        if active_only:
            return self.db.all("SELECT * FROM clients WHERE status='active' ORDER BY created_at DESC")
        return self.db.all("SELECT * FROM clients ORDER BY created_at DESC")

    def assign_case_to_client(self, case_id: str, client_id: str, assignment_type: str = "primary", data_boundary: str = "strict_client_boundary", notes: str = "") -> Dict[str, Any]:
        aid = new_id("clientassign")
        self.db.execute("""INSERT INTO case_client_assignments(assignment_id,case_id,client_id,assignment_type,data_boundary,active,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?)""", [aid, case_id, client_id, assignment_type, data_boundary, 1, now_ts(), notes])
        self.audit.log("assign_client", "case_client_assignment", aid, case_id, {"client_id": client_id, "assignment_type": assignment_type})
        return self.db.one("SELECT * FROM case_client_assignments WHERE assignment_id=?", [aid])

    def create_member(self, username: str, display_name: str, email: str = "", organization: str = "internal", role_key: str = "analyst", notes: str = "") -> Dict[str, Any]:
        if role_key not in ROLE_PERMISSIONS:
            raise ValueError(f"Unbekannte Rolle: {role_key}")
        if not username.strip() or not display_name.strip():
            raise ValueError("Benutzername und Anzeigename sind Pflichtfelder.")
        mid = new_id("member")
        self.db.execute("""INSERT INTO team_members(member_id,username,display_name,email,organization,role_key,active,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?)""", [mid, username.strip(), display_name.strip(), email, organization, role_key, 1, now_ts(), notes])
        self.audit.log("create", "team_member", mid, None, {"username": username, "role_key": role_key})
        return self.get_member(mid)

    def get_member(self, member_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM team_members WHERE member_id=?", [member_id])
        if not row:
            raise KeyError(f"Teammitglied nicht gefunden: {member_id}")
        return row

    def get_member_by_username(self, username: str) -> Dict[str, Any] | None:
        return self.db.one("SELECT * FROM team_members WHERE username=? AND active=1", [username])

    def list_members(self, active_only: bool = True) -> List[Dict[str, Any]]:
        if active_only:
            return self.db.all("SELECT * FROM team_members WHERE active=1 ORDER BY created_at DESC")
        return self.db.all("SELECT * FROM team_members ORDER BY created_at DESC")

    def grant_case_access(self, case_id: str, member_id: str, role_key: str, granted_by: str = "local-admin", permissions: List[str] | None = None, notes: str = "") -> Dict[str, Any]:
        if role_key not in ROLE_PERMISSIONS:
            raise ValueError(f"Unbekannte Rolle: {role_key}")
        perms = permissions if permissions is not None else ROLE_PERMISSIONS[role_key]
        access_id = new_id("access")
        self.db.execute("""INSERT INTO case_access_assignments(access_id,case_id,member_id,role_key,permissions_json,granted_by,granted_at,active,notes)
        VALUES(?,?,?,?,?,?,?,?,?)""", [access_id, case_id, member_id, role_key, dumps(perms), granted_by, now_ts(), 1, notes])
        self.audit.log("grant_access", "case_access_assignment", access_id, case_id, {"member_id": member_id, "role_key": role_key, "permissions": perms})
        return self.db.one("SELECT * FROM case_access_assignments WHERE access_id=?", [access_id])

    def list_case_access(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("""SELECT ca.*, tm.username, tm.display_name, tm.email, tm.organization
        FROM case_access_assignments ca JOIN team_members tm ON tm.member_id=ca.member_id
        WHERE ca.case_id=? AND ca.active=1 ORDER BY ca.granted_at DESC""", [case_id])
        for r in rows:
            r["permissions_json"] = loads(r.get("permissions_json"), [])
        return rows

    def check_case_permission(self, case_id: str, username: str, permission: str) -> Dict[str, Any]:
        member = self.get_member_by_username(username)
        if not member:
            return {"allowed": False, "reason": "unknown_or_inactive_user", "permissions": []}
        rows = self.db.all("""SELECT * FROM case_access_assignments WHERE case_id=? AND member_id=? AND active=1""", [case_id, member["member_id"]])
        permissions: List[str] = []
        for r in rows:
            permissions.extend(loads(r.get("permissions_json"), []))
        allowed = permission in permissions or any(p.endswith(':*') and permission.startswith(p[:-1]) for p in permissions) or "case:*" in permissions
        return {"allowed": bool(allowed), "reason": "matched_permission" if allowed else "permission_missing", "permissions": sorted(set(permissions)), "member": member}

    def request_approval(self, case_id: str, request_type: str, object_type: str, object_id: str, title: str, reason: str, requested_by: str, required_role: str = "legal_reviewer", min_approvals: int = 1, notes: str = "") -> Dict[str, Any]:
        if not title.strip() or not reason.strip():
            raise ValueError("Titel und Begründung sind Pflichtfelder.")
        rid = new_id("approval")
        ts = now_ts()
        self.db.execute("""INSERT INTO approval_requests(request_id,case_id,request_type,object_type,object_id,title,reason,required_role,min_approvals,status,requested_by,created_at,updated_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [rid, case_id, request_type, object_type, object_id, title, reason, required_role, int(min_approvals), "pending", requested_by, ts, ts, notes])
        self.audit.log("request_approval", "approval_request", rid, case_id, {"request_type": request_type, "object_type": object_type, "required_role": required_role})
        return self.get_approval_request(rid)

    def get_approval_request(self, request_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM approval_requests WHERE request_id=?", [request_id])
        if not row:
            raise KeyError(f"Freigabeanfrage nicht gefunden: {request_id}")
        return row

    def list_approval_requests(self, case_id: str, status: str | None = None) -> List[Dict[str, Any]]:
        if status:
            return self.db.all("SELECT * FROM approval_requests WHERE case_id=? AND status=? ORDER BY created_at DESC", [case_id, status])
        return self.db.all("SELECT * FROM approval_requests WHERE case_id=? ORDER BY created_at DESC", [case_id])

    def record_approval_decision(self, request_id: str, decision: str, decided_by: str, decider_role: str, comment: str = "") -> Dict[str, Any]:
        if decision not in {"approved", "rejected", "needs_changes"}:
            raise ValueError("Entscheidung muss approved, rejected oder needs_changes sein.")
        req = self.get_approval_request(request_id)
        if decided_by == req.get("requested_by") and decision == "approved":
            raise ValueError("Vier-Augen-Prinzip: Antragsteller darf die eigene Freigabe nicht selbst final genehmigen.")
        did = new_id("decision")
        self.db.execute("""INSERT INTO approval_decisions(decision_id,request_id,case_id,decision,decided_by,decider_role,comment,decided_at)
        VALUES(?,?,?,?,?,?,?,?)""", [did, request_id, req["case_id"], decision, decided_by, decider_role, comment, now_ts()])
        approved_count = self.db.one("SELECT COUNT(*) AS c FROM approval_decisions WHERE request_id=? AND decision='approved'", [request_id])["c"]
        rejected_count = self.db.one("SELECT COUNT(*) AS c FROM approval_decisions WHERE request_id=? AND decision='rejected'", [request_id])["c"]
        if rejected_count:
            new_status = "rejected"
        elif approved_count >= int(req.get("min_approvals") or 1):
            new_status = "approved"
        elif decision == "needs_changes":
            new_status = "needs_changes"
        else:
            new_status = "pending"
        self.db.execute("UPDATE approval_requests SET status=?, updated_at=? WHERE request_id=?", [new_status, now_ts(), request_id])
        self.audit.log("approval_decision", "approval_decision", did, req["case_id"], {"request_id": request_id, "decision": decision, "new_status": new_status, "decided_by": decided_by})
        return self.db.one("SELECT * FROM approval_decisions WHERE decision_id=?", [did])

    def create_release_record(self, case_id: str, request_id: str, release_type: str, audience: str, content_hash: str, approved_by: List[str], status: str = "released", notes: str = "") -> Dict[str, Any]:
        req = self.get_approval_request(request_id)
        if req.get("status") != "approved":
            raise ValueError("Release darf erst nach genehmigter Freigabeanfrage erstellt werden.")
        rid = new_id("release")
        self.db.execute("""INSERT INTO release_history(release_id,case_id,request_id,release_type,audience,approved_by_json,content_hash,status,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [rid, case_id, request_id, release_type, audience, dumps(approved_by), content_hash, status, now_ts(), notes])
        self.audit.log("create_release", "release_history", rid, case_id, {"request_id": request_id, "release_type": release_type, "audience": audience})
        return self.db.one("SELECT * FROM release_history WHERE release_id=?", [rid])

    def add_comment(self, case_id: str, object_type: str, object_id: str, author: str, body: str, visibility: str = "internal", notes: str = "") -> Dict[str, Any]:
        if not body.strip():
            raise ValueError("Kommentar darf nicht leer sein.")
        cid = new_id("comment")
        self.db.execute("""INSERT INTO team_comments(comment_id,case_id,object_type,object_id,author,visibility,body,created_at,resolved,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [cid, case_id, object_type, object_id, author, visibility, body.strip(), now_ts(), 0, notes])
        self.audit.log("team_comment", "team_comment", cid, case_id, {"object_type": object_type, "object_id": object_id, "visibility": visibility})
        return self.db.one("SELECT * FROM team_comments WHERE comment_id=?", [cid])

    def list_comments(self, case_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM team_comments WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, limit])

    def list_releases(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM release_history WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["approved_by_json"] = loads(r.get("approved_by_json"), [])
        return rows

    def team_dashboard(self, case_id: str) -> Dict[str, Any]:
        clients = self.db.all("""SELECT c.*, cca.assignment_type, cca.data_boundary FROM clients c
        JOIN case_client_assignments cca ON cca.client_id=c.client_id WHERE cca.case_id=? AND cca.active=1""", [case_id])
        access = self.list_case_access(case_id)
        approvals = self.list_approval_requests(case_id)
        comments = self.list_comments(case_id, limit=20)
        releases = self.list_releases(case_id)
        pending = [a for a in approvals if a.get("status") in {"pending", "needs_changes"}]
        legal_reviewers = [a for a in access if a.get("role_key") == "legal_reviewer"]
        blockers = []
        warnings = []
        if not clients:
            blockers.append("Kein Mandant/Client dem Fall zugeordnet.")
        if not access:
            blockers.append("Keine fallbezogene Zugriffszuweisung vorhanden.")
        if not legal_reviewers:
            warnings.append("Kein Legal Reviewer für den Fall zugewiesen.")
        if pending:
            warnings.append(f"{len(pending)} offene Freigabe-/Änderungsanfragen.")
        roles = sorted({a.get("role_key") for a in access})
        return {
            "case_id": case_id,
            "clients": clients,
            "access_count": len(access),
            "roles": roles,
            "pending_approvals": len(pending),
            "approval_count": len(approvals),
            "release_count": len(releases),
            "comment_count": len(comments),
            "blockers": blockers,
            "warnings": warnings,
            "status": "blocked" if blockers else ("review_required" if warnings else "team_ready"),
        }

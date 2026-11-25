"""Account self-service and account administration on the canonical Build-359 identity store.

* Everybody changes their own password (current password required). Other sessions of
  the account end; the session in use stays valid.
* The office management resets passwords (the account must choose a new one at the next
  login) and locks or unlocks accounts. Locking ends all sessions at once. The last active
  office-management account cannot be locked, nor can one lock oneself.

Password rules, Argon2 hashing and the access log are those of ``team_identity_359``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .service import BueroError, _is_admin


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(ctx, *, user_id: str = "", username: str = "") -> dict:
    if user_id:
        row = ctx.db.one("SELECT * FROM phase15_team_users WHERE user_id=?", (user_id,))
    else:
        row = ctx.db.one("SELECT * FROM phase15_team_users WHERE username=? COLLATE NOCASE", (str(username or "").strip(),))
    if not row:
        raise BueroError("Benutzer nicht gefunden.")
    return dict(row)


def _log(ctx, actor: dict, event: str, target: dict, reason: str) -> None:
    ctx.team_identity_359.record_access(user_id=actor["user_id"], username=actor["username"],
                                        session_id=actor.get("session_id", ""), event_type=event,
                                        capability="user.manage" if target["user_id"] != actor["user_id"] else "user.self",
                                        allowed=True, reason=reason, object_type="team_user", object_id=target["user_id"])


def _validated(ctx, row: dict, new: str, repeat: str) -> str:
    if new != repeat:
        raise BueroError("Die beiden neuen Passwörter stimmen nicht überein.")
    try:
        ctx.team_identity_359.validate_password(new, username=row["username"], display_name=row["display_name"])
    except ValueError as exc:
        raise BueroError(str(exc)) from None
    return ctx.team_identity_359.hasher.hash(new)


def change_own_password(ctx, user: dict, form: dict) -> None:
    row = _row(ctx, user_id=user["user_id"])
    current = str(form.get("current") or "")
    try:
        ok = bool(ctx.team_identity_359.hasher.verify(row["password_hash"], current))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        ok = False
    if not ok:
        raise BueroError("Das bisherige Passwort stimmt nicht.")
    new = str(form.get("new") or "")
    if new == current:
        raise BueroError("Das neue Passwort muss sich vom bisherigen unterscheiden.")
    encoded = _validated(ctx, row, new, str(form.get("repeat") or ""))
    generation = int(row.get("session_generation") or 0) + 1
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE phase15_team_users SET password_hash=?, must_change_password=0, session_generation=?, "
                       "updated_at=? WHERE user_id=?", (encoded, generation, _now(), row["user_id"]))
        # Keep the session in use, end all others.
        ctx.db.execute("UPDATE phase15_team_sessions SET session_generation=? WHERE session_id=?",
                       (generation, user.get("session_id", "")))
        _log(ctx, user, "password_changed", row, "self_service")


def reset_password(ctx, admin: dict, form: dict) -> dict:
    if not _is_admin(admin):
        raise PermissionError("Passwörter setzt die Büroleitung (Administration) zurück.")
    row = _row(ctx, username=form.get("username", ""))
    if row["user_id"] == admin["user_id"]:
        raise BueroError("Das eigene Passwort bitte unter „Mein Konto“ ändern.")
    new = str(form.get("password") or "")
    encoded = _validated(ctx, row, new, new)
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE phase15_team_users SET password_hash=?, must_change_password=1, session_generation=session_generation+1, "
                       "failed_attempts=0, lock_until_epoch=0, updated_at=? WHERE user_id=?", (encoded, _now(), row["user_id"]))
        _log(ctx, admin, "password_reset", row, "office_management")
    return row


def set_active(ctx, admin: dict, form: dict) -> dict:
    if not _is_admin(admin):
        raise PermissionError("Konten sperrt die Büroleitung (Administration).")
    row = _row(ctx, username=form.get("username", ""))
    active = str(form.get("active") or "") == "1"
    if not active:
        if row["user_id"] == admin["user_id"]:
            raise BueroError("Das eigene Konto kann nicht gesperrt werden.")
        if row["global_role"] == "system_administrator":
            others = ctx.db.one("SELECT COUNT(*) AS n FROM phase15_team_users WHERE global_role='system_administrator' AND active=1 "
                                "AND user_id<>?", (row["user_id"],))
            if int(others["n"]) == 0:
                raise BueroError("Das letzte aktive Konto der Büroleitung kann nicht gesperrt werden.")
    with ctx.db.transaction(immediate=True):
        ctx.db.execute("UPDATE phase15_team_users SET active=?, session_generation=session_generation+1, updated_at=? WHERE user_id=?",
                       (1 if active else 0, _now(), row["user_id"]))
        _log(ctx, admin, "account_unlocked" if active else "account_locked", row, "office_management")
    return row


def must_change(ctx, user: dict | None) -> bool:
    return bool(user and user.get("must_change_password"))

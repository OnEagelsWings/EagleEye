from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)

def _hash(value: Any) -> str:
    data = value if isinstance(value, str) else _canon(value)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def _safe_json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


class Build295DurableContinuityService:
    BUILD = '295.0'
    GATE_THRESHOLD = 0.88

    def __init__(self, db: Any, audit: Any, *, build294: Any, build293: Any, build281: Any,
                 runtime_dir: Path, install_dir: Path, actor: str = 'local-analyst'):
        self.db = db
        self.audit = audit
        self.build294 = build294
        self.build293 = build293
        self.build281 = build281
        self.runtime_dir = Path(runtime_dir)
        self.install_dir = Path(install_dir)
        self.actor = actor
        self.backup_dir = self.runtime_dir / 'data' / 'phase12_backups_295'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ---------- durable state / continuity ----------
    def _state_snapshot(self, case_id: str = '') -> dict:
        case_where = ' WHERE case_id=?' if case_id else ''
        case_args = (case_id,) if case_id else ()
        cases = self.db.all('SELECT case_id,status,created_at,updated_at FROM cases' + case_where + ' ORDER BY case_id', case_args)
        missions = self.db.all('SELECT mission_id,case_id,mission_type,status,approved_by,approved_at,payload_sha256 FROM phase12_missions_281' + case_where + ' ORDER BY mission_id', case_args)
        jobs = self.db.all('SELECT op_job_id,case_id,mission_id,work_kind,priority,status,attempt_count,max_attempts,consumed_local_steps,max_local_steps,last_checkpoint_id,payload_sha256 FROM phase12_ops_jobs_293' + case_where + ' ORDER BY op_job_id', case_args)
        checkpoints = self.db.all('SELECT checkpoint_id,case_id,mission_id,op_job_id,reason,job_status,checkpoint_hash FROM phase12_ops_checkpoints_293' + case_where + ' ORDER BY checkpoint_id', case_args)
        schedulers = self.db.all('SELECT case_id,claim_count,fault_state,fault_reason FROM phase12_case_scheduler_294' + case_where + ' ORDER BY case_id', case_args)
        state = {
            'scope': 'case' if case_id else 'system',
            'case_id': case_id,
            'cases': cases,
            'missions': missions,
            'ops_jobs': jobs,
            'ops_checkpoints': checkpoints,
            'case_scheduler': schedulers,
        }
        state['counts'] = {
            'cases': len(cases), 'missions': len(missions), 'ops_jobs': len(jobs),
            'ops_checkpoints': len(checkpoints), 'case_scheduler': len(schedulers),
        }
        state['fingerprint'] = _hash(state)
        return state

    def create_continuity_anchor(self, *, case_id: str = '', actor: str | None = None) -> dict:
        actor = actor or self.actor
        state = self._state_snapshot(case_id)
        scope = 'case' if case_id else 'system'
        prev = self.db.one('SELECT anchor_hash FROM phase12_continuity_anchors_295 WHERE scope=? AND case_id=? ORDER BY rowid DESC LIMIT 1', (scope, case_id))
        previous_hash = prev['anchor_hash'] if prev else 'GENESIS'
        anchor_id = _id('anchor295')
        created_at = _now()
        payload = {
            'anchor_id': anchor_id, 'scope': scope, 'case_id': case_id,
            'state': state, 'state_fingerprint': state['fingerprint'],
            'created_by': actor, 'created_at': created_at, 'previous_hash': previous_hash,
        }
        anchor_hash = _hash(payload)
        self.db.execute('INSERT INTO phase12_continuity_anchors_295 VALUES(?,?,?,?,?,?,?,?,?)', (
            anchor_id, scope, case_id, _canon(state), state['fingerprint'], actor, created_at, previous_hash, anchor_hash
        ))
        return {'anchor_id': anchor_id, 'scope': scope, 'case_id': case_id, 'state_fingerprint': state['fingerprint'], 'counts': state['counts'], 'anchor_hash': anchor_hash}

    def verify_anchor_chain(self, *, case_id: str = '') -> bool:
        scope = 'case' if case_id else 'system'
        rows = self.db.all('SELECT * FROM phase12_continuity_anchors_295 WHERE scope=? AND case_id=? ORDER BY rowid', (scope, case_id))
        previous_hash = 'GENESIS'
        for row in rows:
            state = _safe_json(row['state_json'], {})
            payload = {
                'anchor_id': row['anchor_id'], 'scope': row['scope'], 'case_id': row['case_id'],
                'state': state, 'state_fingerprint': row['state_fingerprint'], 'created_by': row['created_by'],
                'created_at': row['created_at'], 'previous_hash': row['previous_hash'],
            }
            if row['previous_hash'] != previous_hash or _hash(payload) != row['anchor_hash']:
                return False
            previous_hash = row['anchor_hash']
        return True

    def _compare_anchor(self, anchored: dict, current: dict) -> dict:
        def by_id(rows: list[dict], key: str) -> dict[str, dict]:
            return {str(r[key]): r for r in rows}
        a_cases, c_cases = by_id(anchored.get('cases', []), 'case_id'), by_id(current.get('cases', []), 'case_id')
        a_missions, c_missions = by_id(anchored.get('missions', []), 'mission_id'), by_id(current.get('missions', []), 'mission_id')
        a_jobs, c_jobs = by_id(anchored.get('ops_jobs', []), 'op_job_id'), by_id(current.get('ops_jobs', []), 'op_job_id')
        missing_cases = sorted(set(a_cases) - set(c_cases))
        missing_missions = sorted(set(a_missions) - set(c_missions))
        missing_jobs = sorted(set(a_jobs) - set(c_jobs))
        job_mismatches = []
        for jid, before in a_jobs.items():
            after = c_jobs.get(jid)
            if not after:
                continue
            for field in ('case_id', 'mission_id', 'work_kind', 'payload_sha256'):
                if before.get(field) != after.get(field):
                    job_mismatches.append({'op_job_id': jid, 'field': field, 'before': before.get(field), 'after': after.get(field)})
        return {
            'missing_cases': missing_cases, 'missing_missions': missing_missions, 'missing_jobs': missing_jobs,
            'job_identity_mismatches': job_mismatches,
            'continuity_ok': not (missing_cases or missing_missions or missing_jobs or job_mismatches),
        }

    def reconcile_after_restart(self, *, anchor_id: str = '', actor: str | None = None) -> dict:
        actor = actor or self.actor
        if anchor_id:
            anchor = self.db.one('SELECT * FROM phase12_continuity_anchors_295 WHERE anchor_id=?', (anchor_id,))
        else:
            anchor = self.db.one("SELECT * FROM phase12_continuity_anchors_295 WHERE scope='system' AND case_id='' ORDER BY rowid DESC LIMIT 1")
        if not anchor:
            raise ValueError('Kein Continuity-Anchor vorhanden. Vor geplantem Neustart zuerst einen Anchor anlegen.')
        anchored = _safe_json(anchor['state_json'], {})
        before = self._state_snapshot(anchor['case_id'])
        comparison_before = self._compare_anchor(anchored, before)
        running = self.db.all("SELECT * FROM phase12_ops_jobs_293 WHERE status='running'" + (" AND case_id=?" if anchor['case_id'] else ''), (anchor['case_id'],) if anchor['case_id'] else ())
        moved = []
        now = _now()
        for job in running:
            owner = str(job.get('lease_owner') or '')
            self.db.execute("UPDATE phase12_ops_jobs_293 SET status='recovery_pending',lease_owner='',lease_expires_at='',heartbeat_at='',last_error='full process restart: in-flight state requires review',updated_at=? WHERE op_job_id=?", (now, job['op_job_id']))
            if owner:
                self.db.execute('INSERT OR REPLACE INTO phase12_worker_health_293 VALUES(?,?,?,?,?,?)', (owner, 'stale', '', now, '', now))
            cp = self.build293.create_checkpoint(job_id=job['op_job_id'], reason='full_process_restart_295', actor=actor)
            moved.append({'op_job_id': job['op_job_id'], 'checkpoint_id': cp['checkpoint_id'], 'new_ok_required': True})
        after = self._state_snapshot(anchor['case_id'])
        comparison_after = self._compare_anchor(anchored, after)
        queued_preserved = sum(1 for j in anchored.get('ops_jobs', []) if j.get('status') == 'queued' and any(x.get('op_job_id') == j.get('op_job_id') and x.get('status') == 'queued' for x in after.get('ops_jobs', [])))
        recovery_preserved = sum(1 for j in anchored.get('ops_jobs', []) if j.get('status') == 'recovery_pending' and any(x.get('op_job_id') == j.get('op_job_id') and x.get('status') == 'recovery_pending' for x in after.get('ops_jobs', [])))
        # Running -> recovery_pending is an expected restart transition, not unexpected drift.
        unexpected_drift = not comparison_after['continuity_ok']
        previous = self.db.one('SELECT reconcile_hash FROM phase12_restart_reconciliations_295 ORDER BY rowid DESC LIMIT 1')
        previous_hash = previous['reconcile_hash'] if previous else 'GENESIS'
        reconcile_id = _id('reconcile295')
        created_at = _now()
        details = {
            'comparison_before': comparison_before, 'comparison_after': comparison_after,
            'expected_restart_transition': 'running_to_recovery_pending', 'moved_jobs': moved,
            'network_access': False, 'automatic_resume': False, 'new_ok_required_for_moved_jobs': True,
        }
        payload = {
            'reconcile_id': reconcile_id, 'anchor_id': anchor['anchor_id'], 'pre_fingerprint': anchored.get('fingerprint', anchor['state_fingerprint']),
            'post_fingerprint': after['fingerprint'], 'running_jobs_found': len(running), 'running_jobs_moved_to_recovery': len(moved),
            'queued_jobs_preserved': queued_preserved, 'recovery_jobs_preserved': recovery_preserved,
            'unexpected_drift': unexpected_drift, 'continuity_ok': comparison_after['continuity_ok'], 'details': details,
            'created_by': actor, 'created_at': created_at, 'previous_hash': previous_hash,
        }
        reconcile_hash = _hash(payload)
        self.db.execute('INSERT INTO phase12_restart_reconciliations_295 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            reconcile_id, anchor['anchor_id'], payload['pre_fingerprint'], payload['post_fingerprint'], len(running), len(moved),
            queued_preserved, recovery_preserved, 1 if unexpected_drift else 0, 1 if comparison_after['continuity_ok'] else 0,
            _canon(details), actor, created_at, previous_hash, reconcile_hash
        ))
        return {
            'reconcile_id': reconcile_id, 'anchor_id': anchor['anchor_id'], 'running_jobs_found': len(running),
            'running_jobs_moved_to_recovery': len(moved), 'queued_jobs_preserved': queued_preserved,
            'recovery_jobs_preserved': recovery_preserved, 'unexpected_drift': unexpected_drift,
            'continuity_ok': comparison_after['continuity_ok'], 'moved_jobs': moved, 'network_access': False,
            'automatic_resume': False, 'new_ok_required': bool(moved), 'reconcile_hash': reconcile_hash,
        }

    def verify_reconcile_chain(self) -> bool:
        rows = self.db.all('SELECT * FROM phase12_restart_reconciliations_295 ORDER BY rowid')
        previous_hash = 'GENESIS'
        for row in rows:
            details = _safe_json(row['details_json'], {})
            payload = {
                'reconcile_id': row['reconcile_id'], 'anchor_id': row['anchor_id'], 'pre_fingerprint': row['pre_fingerprint'],
                'post_fingerprint': row['post_fingerprint'], 'running_jobs_found': int(row['running_jobs_found']),
                'running_jobs_moved_to_recovery': int(row['running_jobs_moved_to_recovery']),
                'queued_jobs_preserved': int(row['queued_jobs_preserved']), 'recovery_jobs_preserved': int(row['recovery_jobs_preserved']),
                'unexpected_drift': bool(row['unexpected_drift']), 'continuity_ok': bool(row['continuity_ok']), 'details': details,
                'created_by': row['created_by'], 'created_at': row['created_at'], 'previous_hash': row['previous_hash'],
            }
            if row['previous_hash'] != previous_hash or _hash(payload) != row['reconcile_hash']:
                return False
            previous_hash = row['reconcile_hash']
        return True

    # ---------- backup / restore ----------
    def create_backup(self, *, actor: str | None = None) -> dict:
        actor = actor or self.actor
        backup_id = _id('backup295')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        bundle_dir = self.backup_dir / f'{stamp}_{backup_id}'
        bundle_dir.mkdir(parents=True, exist_ok=False)
        backup_path = bundle_dir / 'eagleeye.db'
        key_source = self.runtime_dir / 'data' / 'security_124_0' / 'vault_master.key'
        key_backup = bundle_dir / 'vault_master.key'
        manifest_path = bundle_dir / 'manifest.json'
        if not key_source.exists():
            raise RuntimeError('Lokales Vault-Master-Key-Material fehlt; ein vollständiges Continuity-Backup kann nicht erstellt werden.')
        # sqlite3.Connection.backup creates a transactionally consistent snapshot, including WAL-visible state.
        dest = sqlite3.connect(str(backup_path))
        try:
            with self.db._lock:
                self.db.conn.backup(dest)
            dest.commit()
        finally:
            dest.close()
        shutil.copy2(key_source, key_backup)
        for secure_path in (bundle_dir, backup_path, key_backup):
            try:
                os.chmod(secure_path, 0o700 if secure_path == bundle_dir else 0o600)
            except OSError:
                pass
        check = sqlite3.connect(str(backup_path))
        try:
            quick = str(check.execute('PRAGMA quick_check').fetchone()[0])
            fk = len(check.execute('PRAGMA foreign_key_check').fetchall())
            meta = dict(check.execute("SELECT key,value FROM meta WHERE key IN ('schema_version','application_build')").fetchall())
            case_count = int(check.execute('SELECT COUNT(*) FROM cases').fetchone()[0])
            mission_count = int(check.execute('SELECT COUNT(*) FROM phase12_missions_281').fetchone()[0])
            job_count = int(check.execute('SELECT COUNT(*) FROM phase12_ops_jobs_293').fetchone()[0])
        finally:
            check.close()
        state = self._state_snapshot()
        db_sha = _file_sha(backup_path)
        key_sha = _file_sha(key_backup)
        raw_prefix = key_backup.read_bytes()[:16]
        key_protection = 'dpapi_user_bound' if raw_prefix.startswith(b'DPAPI1:') else ('raw_local_key' if raw_prefix.startswith(b'RAW1:') else 'unknown')
        created_at = _now()
        status = 'verified' if quick.lower() == 'ok' and fk == 0 and key_protection != 'unknown' else 'invalid'
        manifest = {
            'backup_id': backup_id, 'build': '295.0', 'bundle_dir': str(bundle_dir),
            'db_file': 'eagleeye.db', 'db_sha256': db_sha, 'db_size_bytes': backup_path.stat().st_size,
            'vault_key_file': 'vault_master.key', 'vault_key_sha256': key_sha, 'vault_key_protection': key_protection,
            'restore_scope': 'same-user/same-machine for DPAPI protected key material',
            'sqlite_quick_check': quick, 'foreign_key_violations': fk, 'schema_version': meta.get('schema_version',''),
            'application_build': meta.get('application_build',''), 'case_count': case_count, 'mission_count': mission_count,
            'ops_job_count': job_count, 'continuity_fingerprint': state['fingerprint'], 'status': status,
            'created_by': actor, 'created_at': created_at, 'network_access': False,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
        try:
            os.chmod(manifest_path, 0o600)
        except OSError:
            pass
        payload_sha = _hash(manifest)
        self.db.execute('INSERT INTO phase12_durable_backups_295 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            backup_id, str(backup_path), str(manifest_path), db_sha, backup_path.stat().st_size, quick, fk,
            meta.get('schema_version',''), meta.get('application_build',''), case_count, mission_count, job_count,
            state['fingerprint'], status, actor, created_at, payload_sha
        ))
        return {**manifest, 'backup_path': str(backup_path), 'manifest_path': str(manifest_path), 'vault_key_path': str(key_backup), 'payload_sha256': payload_sha}

    def verify_backup(self, backup_id: str) -> dict:
        row = self.db.one('SELECT * FROM phase12_durable_backups_295 WHERE backup_id=?', (backup_id,))
        if not row:
            raise KeyError('backup not found')
        path = Path(row['backup_path'])
        manifest_path = Path(row['manifest_path'])
        result = {'backup_id': backup_id, 'exists': path.exists(), 'manifest_exists': manifest_path.exists(), 'hash_ok': False, 'key_exists': False, 'key_hash_ok': False, 'manifest_hash_ok': False, 'sqlite_quick_check': 'missing', 'foreign_key_violations': -1, 'valid': False}
        if not path.exists() or not manifest_path.exists():
            return result
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            result['manifest_hash_ok'] = _hash(manifest) == row['payload_sha256']
            actual = _file_sha(path)
            result['actual_sha256'] = actual
            result['hash_ok'] = actual == row['db_sha256'] == manifest.get('db_sha256')
            key_path = manifest_path.parent / str(manifest.get('vault_key_file','vault_master.key'))
            result['key_exists'] = key_path.exists()
            if key_path.exists():
                key_sha = _file_sha(key_path)
                result['key_sha256'] = key_sha
                result['key_hash_ok'] = key_sha == manifest.get('vault_key_sha256')
                result['vault_key_protection'] = manifest.get('vault_key_protection','unknown')
            conn = sqlite3.connect(str(path))
            try:
                quick = str(conn.execute('PRAGMA quick_check').fetchone()[0])
                fk = len(conn.execute('PRAGMA foreign_key_check').fetchall())
            finally:
                conn.close()
            result['sqlite_quick_check'] = quick
            result['foreign_key_violations'] = fk
            result['valid'] = bool(result['hash_ok'] and result['key_exists'] and result['key_hash_ok'] and result['manifest_hash_ok'] and quick.lower() == 'ok' and fk == 0 and row['status'] == 'verified')
        except Exception as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
        return result

    def prepare_restore(self, *, backup_id: str, confirmation: str, approved_by: str) -> dict:
        if str(confirmation).strip().upper() != 'OK':
            raise PermissionError("Restore-Vorbereitung erfordert ausdrückliches 'OK' des Hauptermittlers.")
        verification = self.verify_backup(backup_id)
        if not verification['valid']:
            raise ValueError('Backup ist nicht vollständig verifiziert und darf nicht für Restore freigegeben werden.')
        row = self.db.one('SELECT * FROM phase12_durable_backups_295 WHERE backup_id=?', (backup_id,))
        plan_id = _id('restore295')
        approved_at = _now()
        payload = {
            'restore_plan_id': plan_id, 'backup_id': backup_id, 'backup_sha256': row['db_sha256'],
            'verification': verification, 'decision': 'approved_for_offline_restore', 'approved_by': approved_by,
            'approved_at': approved_at, 'offline_restore_required': True, 'target_hint': str(self.db.path),
        }
        self.db.execute('INSERT INTO phase12_restore_plans_295 VALUES(?,?,?,?,?,?,?,?,?,?)', (
            plan_id, backup_id, row['db_sha256'], _canon(verification), 'approved_for_offline_restore', approved_by,
            approved_at, 1, str(self.db.path), _hash(payload)
        ))
        return {**payload, 'live_database_overwritten': False, 'next_step': 'App beenden und RESTORE_EAGLEEYE_BUILD_295.py mit --confirm OK verwenden.'}

    def restore_to_sandbox(self, *, backup_id: str, target_db_path: str | Path) -> dict:
        verification = self.verify_backup(backup_id)
        if not verification['valid']:
            raise ValueError('invalid backup')
        target = Path(target_db_path).resolve()
        live = Path(self.db.path).resolve()
        if target == live:
            raise PermissionError('Sandbox-Restore darf niemals die aktive Datenbank überschreiben.')
        if target.exists():
            raise FileExistsError('Sandbox-Ziel existiert bereits.')
        target.parent.mkdir(parents=True, exist_ok=True)
        row = self.db.one('SELECT backup_path,manifest_path FROM phase12_durable_backups_295 WHERE backup_id=?', (backup_id,))
        source = Path(row['backup_path'])
        manifest_path = Path(row['manifest_path'])
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        key_source = manifest_path.parent / str(manifest.get('vault_key_file','vault_master.key'))
        key_target = target.parent / 'security_124_0' / 'vault_master.key'
        key_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        shutil.copy2(key_source, key_target)
        try:
            os.chmod(key_target.parent,0o700); os.chmod(key_target,0o600); os.chmod(target,0o600)
        except OSError:
            pass
        conn = sqlite3.connect(str(target))
        try:
            quick = str(conn.execute('PRAGMA quick_check').fetchone()[0])
            fk = len(conn.execute('PRAGMA foreign_key_check').fetchall())
        finally:
            conn.close()
        key_ok = _file_sha(key_target) == manifest.get('vault_key_sha256')
        return {'backup_id': backup_id, 'target_db_path': str(target), 'target_vault_key_path': str(key_target), 'sqlite_quick_check': quick, 'foreign_key_violations': fk, 'vault_key_hash_ok': key_ok, 'restored': quick.lower() == 'ok' and fk == 0 and key_ok, 'live_database_overwritten': False}

    # ---------- operator UX / training / release ----------
    def continuity_status(self, case_id: str = '') -> dict:
        backup = self.db.one('SELECT backup_id,status,created_at,db_sha256 FROM phase12_durable_backups_295 ORDER BY rowid DESC LIMIT 1')
        anchor = self.db.one('SELECT anchor_id,created_at,state_fingerprint FROM phase12_continuity_anchors_295 WHERE scope=? AND case_id=? ORDER BY rowid DESC LIMIT 1', ('case' if case_id else 'system', case_id))
        counts = {r['status']: int(r['n']) for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_ops_jobs_293 GROUP BY status')}
        recovery = counts.get('recovery_pending', 0)
        if recovery:
            stand = f'{recovery} Ermittlungsjob(s) warten auf Recovery-Prüfung. Letztes Backup: {backup["status"] if backup else "noch keines"}.'
            meaning = 'Unterbrochene Arbeit wird nach Neustart nicht automatisch fortgesetzt. Der Zustand bleibt erhalten, bis ein Mensch den Checkpoint prüft.'
            nxt = "Recovery-Checkpoint prüfen und nur den betroffenen Job mit 'OK' freigeben."
        elif not backup:
            stand = 'Operational Continuity ist bereit, aber es wurde in diesem Runtime-Verzeichnis noch kein Build-295-Backup erstellt.'
            meaning = 'Die laufende Datenbank ist intakt, aber ein eigener verifizierter Wiederherstellungspunkt fehlt noch.'
            nxt = 'Ein verifiziertes lokales Backup erstellen; danach bei geplantem Neustart einen Continuity-Anchor setzen.'
        else:
            stand = f'Continuity bereit. Letztes Backup: {backup["status"]} vom {backup["created_at"]}. Recovery offen: 0.'
            meaning = 'EagleEye kann den aktuellen Datenbestand sichern und unsichere In-Flight-Arbeit nach einem Neustart kontrolliert in Recovery überführen.'
            nxt = 'Vor geplantem Neustart einen Continuity-Anchor erstellen; Backups regelmäßig verifizieren.'
        return {'stand': stand, 'meaning': meaning, 'next': nxt, 'backup': backup, 'anchor': anchor, 'queue_counts': counts, 'recovery_pending': recovery}

    def startup_contract_status(self) -> dict:
        import eagleeye_pro.version as v
        generic = self.install_dir / 'START_EAGLEEYE_PRO.bat'
        generic_text = generic.read_text(encoding='utf-8', errors='replace') if generic.exists() else ''
        checks = {
            'version_build': tuple(map(int,v.BUILD.split('.'))) >= (295,0), 'version_schema': tuple(map(int,v.SCHEMA_VERSION.split('.'))) >= (295,0),
            'project_entrypoint': (self.install_dir / 'EAGLEEYE_PRO_295_0.py').exists(),
            'startup_acceptance_script': (self.install_dir / 'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_295_0.py').exists(),
            'generic_windows_starter': generic.exists(), 'generic_windows_starter_current_or_newer': ('EAGLEEYE_PRO_295_0.py' in generic_text and 'Build 295.0' in generic_text) or tuple(map(int,v.BUILD.split('.'))) > (295,0),
            'versioned_windows_starter': (self.install_dir / 'START_EAGLEEYE_PRO_295_0.bat').exists(),
            'offline_restore_tool': (self.install_dir / 'RESTORE_EAGLEEYE_BUILD_295.py').exists(),
            'setup_script': (self.install_dir / 'SETUP_EAGLEEYE_WINDOWS.bat').exists(),
            'requirements_windows': (self.install_dir / 'requirements-windows.txt').exists(),
        }
        return {'build': '295.0', 'checks': checks, 'contract_ready': all(checks.values()), 'actual_loopback_boot_required_for_release': True, 'packaged_boot_required': True, 'windows_launcher_content_checked': True}

    def all_training_cases(self) -> list[dict]:
        out = self.build294.all_training_cases()
        rows = self.db.all("SELECT * FROM ai_hard_training_delta_295 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for row in rows:
            out.append({'benchmark_id': row['benchmark_id'], 'track': row['track'], 'difficulty': row['difficulty'], 'prompt': row['prompt'], 'expected_controls': json.loads(row['expected_controls_json'])})
        return out

    def training_metrics(self) -> dict:
        base = self.build294.training_metrics()
        delta = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_295 WHERE review_status='reviewed'")['n'])
        extreme = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_295 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases': int(base['reviewed_hard_cases']) + delta, 'adversarial_extreme_cases': int(base['adversarial_extreme_cases']) + extreme, 'build295_delta_cases': delta, 'build295_delta_extreme': extreme, 'performance_gate_threshold': self.GATE_THRESHOLD, 'automatic_model_activation': False, 'build300_case_target': 360}

    def create_evaluation_batch(self, *, model_label: str = 'mistral:latest', actor: str | None = None) -> dict:
        actor = actor or self.actor
        cases = self.all_training_cases()
        manifest = {'build': '295.0', 'model_label': model_label, 'corpus_size': len(cases), 'required_coverage': 1.0, 'minimum_mean_score': self.GATE_THRESHOLD, 'maximum_critical_failures': 0, 'independent_evaluator_required': True, 'automatic_model_activation': False, 'cases': cases}
        manifest_sha = _hash(manifest)
        existing = self.db.one('SELECT * FROM ai_evaluation_batches_295 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1', (model_label, manifest_sha))
        if existing:
            return {'batch_id': existing['batch_id'], 'corpus_size': int(existing['corpus_size']), 'minimum_mean_score': float(existing['threshold']), 'independent_evaluator_required': bool(existing['independent_evaluator_required']), 'cases': cases, 'deduplicated': True}
        batch_id = _id('eval295')
        created_at = _now()
        payload = {'batch_id': batch_id, **manifest, 'created_by': actor, 'created_at': created_at}
        self.db.execute('INSERT INTO ai_evaluation_batches_295 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (batch_id, model_label, len(cases), self.GATE_THRESHOLD, 1.0, 0, 'prepared', 1, manifest_sha, actor, created_at, _hash(payload)))
        return {'batch_id': batch_id, 'corpus_size': len(cases), 'minimum_mean_score': self.GATE_THRESHOLD, 'independent_evaluator_required': True, 'cases': cases, 'deduplicated': False}

    def performance_status(self, model_label: str = 'mistral:latest') -> dict:
        parent = self.build294.performance_status(model_label)
        return {'model_label': model_label, 'status': parent.get('status', 'not_run'), 'qualified': False, 'required_corpus_size': 256, 'minimum_mean_score': self.GATE_THRESHOLD, 'note': 'Build 295 beansprucht keine ≥88%-Leistung ohne vollständigen unabhängigen 256-Fälle-Lauf.'}

    def qualified_gate(self) -> dict:
        parent = self.build294.qualified_gate()
        tm = self.training_metrics()
        batch = self.create_evaluation_batch()
        startup = self.startup_contract_status()
        gates = {
            'build': '295.0', 'parent_gate': bool(parent['release_ready']), 'durable_backup_engine': True,
            'backup_hash_and_sqlite_validation': True, 'restart_reconciliation': True, 'offline_restore_gate': True,
            'live_database_restore_from_ui': False, 'continuity_anchor_chain_ok': self.verify_anchor_chain(),
            'restart_reconcile_chain_ok': self.verify_reconcile_chain(), 'foreign_keys_ok': len(self.db.all('PRAGMA foreign_key_check')) == 0,
            'network_access': False, 'external_collection_auto_execution': False,
            'hard_training_corpus_256': tm['reviewed_hard_cases'] >= 256 and tm['build295_delta_cases'] >= 16 and tm['build295_delta_extreme'] >= 4,
            'evaluation_batch_256_ready': batch['corpus_size'] == 256 and abs(batch['minimum_mean_score'] - 0.88) < 1e-9,
            'startup_contract_ready': startup['contract_ready'], 'actual_startup_release_test_required': True,
            'automatic_model_activation': False, 'human_authority_preserved': True,
        }
        gates['release_ready'] = all([
            gates['parent_gate'], gates['durable_backup_engine'], gates['backup_hash_and_sqlite_validation'], gates['restart_reconciliation'],
            gates['offline_restore_gate'], not gates['live_database_restore_from_ui'], gates['continuity_anchor_chain_ok'], gates['restart_reconcile_chain_ok'],
            gates['foreign_keys_ok'], not gates['network_access'], not gates['external_collection_auto_execution'], gates['hard_training_corpus_256'],
            gates['evaluation_batch_256_ready'], gates['startup_contract_ready'], not gates['automatic_model_activation'], gates['human_authority_preserved'],
        ])
        return gates

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        esc = lambda v: html.escape(str(v or ''), quote=True)
        status = self.continuity_status(case_id)
        tm = self.training_metrics()
        perf = self.performance_status()
        backup = status['backup'] or {}
        backup_id = backup.get('backup_id', '')
        actions = f"""
<form method='post' action='/build295/backup/create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Verifiziertes Backup erstellen</button></form>
<form method='post' action='/build295/anchor/create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Continuity-Anchor vor Neustart erstellen</button></form>
<form method='post' action='/build295/reconcile'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Neustart-Zustand prüfen/reconciliieren</button></form>
"""
        if backup_id:
            actions += f"<form method='post' action='/build295/restore/prepare'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input type='hidden' name='backup_id' value='{esc(backup_id)}'><label>Restore vorbereiten <input name='confirmation' placeholder='OK'></label> <button>Backup mit OK für Offline-Restore prüfen</button></form>"
        return f"""
<section class='card'><h2>Operational Continuity · Build 295</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{esc(status['stand'])}<br><br><b>Was bedeutet das?</b><br>{esc(status['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{esc(status['next'])}</div>
<p><b>Letztes Backup:</b> {esc(backup.get('status','noch keines'))} {esc(backup.get('created_at',''))} · <b>Recovery offen:</b> {esc(status['recovery_pending'])}.</p>{actions}
<details><summary>Analyst/Experte: Backup-Integrität, Restart-Reconciliation und AI-Gate</summary><p>Anchor-Chain: <b>{'OK' if self.verify_anchor_chain(case_id=case_id) else 'FEHLER'}</b> · Reconcile-Chain: <b>{'OK' if self.verify_reconcile_chain() else 'FEHLER'}</b> · Live-DB-Restore aus UI: <b>aus</b> · Netzwerkzugriff: <b>aus</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{esc(perf['status'])}</b>. AI-Gate: 256/256 Fälle, ≥88%, 0 kritische Fehler, unabhängige Evaluation.</p></details>
</section>"""

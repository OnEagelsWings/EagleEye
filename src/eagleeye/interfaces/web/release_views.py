from __future__ import annotations

import json
from typing import Any, Callable


def render_release(
    ctx: Any,
    case_id: str,
    csrf: str,
    *,
    esc: Callable[[Any], str],
    table: Callable[..., str],
) -> str:
    svc = ctx.production_candidate_126
    runs = svc.recent_runs(case_id, 20)
    freezes = svc.recent_freezes(20)
    latest = runs[0] if runs else {}
    report = json.loads(latest.get("report_json") or "{}") if latest else {}
    checks = report.get("checks") or []
    check_rows = [
        {
            "title": item.get("title", ""),
            "severity": item.get("severity", ""),
            "status": item.get("status", ""),
            "details": json.dumps(item.get("details") or {}, ensure_ascii=False, default=str),
        }
        for item in checks
    ]
    shortcut = ctx.db.one("SELECT * FROM windows_shortcut_installs_126 ORDER BY created_at DESC LIMIT 1") or {}
    policy = ctx.db.one("SELECT * FROM production_policy_126 WHERE policy_id='phase2'") or {}
    latest_status = esc(latest.get("status") or "noch nicht geprüft")
    latest_score = esc(latest.get("score") if latest else "–")
    shortcut_status = esc(shortcut.get("status") or "nicht eingerichtet")
    return f'''
<div class="notice"><b>Phase-2 Production Candidate:</b> Build 126 fügt keine neue Ermittlungsreichweite hinzu. Es friert den kanonischen Firefox-Workflow ein und prüft Datenintegrität, Investigator Protection, Recovery, Evidence und Releasezustand.</div>
<div class="metrics"><div class="metric"><div class="label">Letztes Production Gate</div><div class="value">{latest_status}</div></div><div class="metric"><div class="label">Readiness Score</div><div class="value">{latest_score}</div></div><div class="metric"><div class="label">Feature Freeze</div><div class="value">{'aktiv' if policy.get('feature_freeze') else 'offen'}</div></div><div class="metric"><div class="label">Windows-Verknüpfung</div><div class="value">{shortcut_status}</div></div></div>
<div class="two-col"><div class="panel"><h2>Production Gate</h2><p>Prüft Schema, SQLite, Fremdschlüssel, Fallgrenzen, Reliability, Investigator Protection, offene Restore-Zustände und den kanonischen Serviceverbund.</p><form method="post" action="/release/gate"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button>Production Gate ausführen</button></p></form></div>
<div class="panel"><h2>Phase-2 Freeze</h2><p>Erzeugt zuerst ein verschlüsseltes, verifiziertes Backup, gegebenenfalls einen Evidence-Checkpoint und anschließend einen nachvollziehbaren Freeze-Eintrag.</p><form method="post" action="/release/freeze"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Freigabenotiz</label><textarea name="notes" rows="3" placeholder="Abnahme, Einschränkungen und verantwortliche Prüfung dokumentieren"></textarea></div><div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="PHASE 2 EINFRIEREN" required></div><p><button>Backup, Gate und Freeze ausführen</button></p></form></div></div>
<div class="panel"><h2>Windows-Schnellstart</h2><p>Im Release liegt <code>INSTALL_WINDOWS_SHORTCUT.bat</code>. Ein einmaliger Doppelklick erzeugt eine portable Desktop-Verknüpfung und optional einen Startmenüeintrag. Die Verknüpfung zeigt auf das entpackte EagleEye-Verzeichnis; verschiebe den Ordner danach nicht mehr.</p><form method="post" action="/release/install-shortcut"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="inline"><label><input type="checkbox" name="include_start_menu" checked> Zusätzlich im Startmenü anlegen</label></div><div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="VERKNÜPFUNG ERSTELLEN" required></div><p><button>Windows-Verknüpfung einrichten</button></p></form><p class="footer">Der Browseraufruf bleibt lokal. Ist EagleEye bereits aktiv, öffnet ein weiterer Doppelklick den bestehenden Workspace statt einen zweiten Server zu starten.</p></div>
<div class="panel"><h2>Letzte Gate-Prüfung</h2>{table(check_rows, [("title","Prüfung"),("severity","Schwere"),("status","Status"),("details","Details")])}</div>
<div class="two-col"><div class="panel"><h2>Gate-Läufe</h2>{table(runs, [("created_at","Zeit"),("status","Status"),("score","Score"),("blocker_count","Blocker"),("warning_count","Hinweise")])}</div><div class="panel"><h2>Phase-2 Freezes</h2>{table(freezes, [("created_at","Zeit"),("status","Status"),("backup_id","Backup"),("manifest_sha256","Manifest"),("created_by","Erstellt von")])}</div></div>
'''

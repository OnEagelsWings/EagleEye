from __future__ import annotations

import json
from typing import Any, Callable


def render_phase3_release(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    svc = ctx.phase3_production_candidate_133
    runs = svc.recent_runs(case_id, 20)
    freezes = svc.recent_freezes(20)
    fields = svc.field_validations()
    latest = runs[0] if runs else {}
    report = json.loads(latest.get("report_json") or "{}") if latest else {}
    check_rows = [
        {
            "title": item.get("title", ""),
            "severity": item.get("severity", ""),
            "status": item.get("status", ""),
            "details": json.dumps(item.get("details") or {}, ensure_ascii=False, default=str),
        }
        for item in report.get("checks") or []
    ]
    profile = svc.source_release_profile()
    return f'''
<div class="notice"><b>Phase-3 Production Candidate:</b> Feature Freeze ist aktiv. Build 133 ergänzt keine Ermittlungsreichweite, sondern prüft den vollständigen Phase-3-Verbund, AI-Governance, OPSEC, Recovery, Windows-/Firefox-Verträge und das schlanke Produktionsprofil.</div>
<div class="metrics"><div class="metric"><div class="label">Phase-3 Gate</div><div class="value">{esc(latest.get('status') or 'noch nicht geprüft')}</div></div><div class="metric"><div class="label">Readiness Score</div><div class="value">{esc(latest.get('score') if latest else '–')}</div></div><div class="metric"><div class="label">Release-Profil</div><div class="value">{esc(profile.get('profile'))}</div></div><div class="metric"><div class="label">Historische Top-Level-Dateien</div><div class="value">{esc(profile.get('historical_top_level_files'))}</div></div></div>
<div class="two-col"><div class="panel"><h2>Phase-3 Production Gate</h2><p>Prüft Build 127–132, Candidate-only- und Review-first-Grenzen, Connectorverträge, Investigator Protection, Governance, Launcher, Firefox-Companion, Datenintegrität und reale Feldabnahmen.</p><form method="post" action="/phase3-release/gate"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button>Phase-3 Gate ausführen</button></p></form></div>
<div class="panel"><h2>AI-/OPSEC-Abnahmebrief</h2><p>Erzeugt eine rein lokale, quellengebundene Readiness-Einschätzung. Keine externen Aktionen, keine Freigaben und keine Tatsachenpromotion.</p><form method="post" action="/phase3-release/ai-opsec"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button>Lokalen AI-/OPSEC-Brief erzeugen</button></p></form></div></div>
<div class="panel"><h2>Reale Feldabnahme dokumentieren</h2><p>Nur tatsächlich durchgeführte Prüfungen als <code>pass</code> eintragen. Notizen werden im Audit nur als SHA-256-Fingerprint referenziert.</p><form method="post" action="/phase3-release/field-validation"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="form-grid"><div class="field"><label>Komponente</label><select name="component_key">{''.join(f'<option value="{esc(key)}">{esc(key)}</option>' for key in svc.FIELD_COMPONENTS)}</select></div><div class="field"><label>Plattform</label><input name="platform_key" placeholder="Windows 11 24H2 / Firefox 141"></div><div class="field"><label>Status</label><select name="status"><option value="not_run">nicht durchgeführt</option><option value="pass">bestanden</option><option value="fail">fehlgeschlagen</option></select></div><div class="field"><label>SHA-256-Nachweis, optional</label><input name="evidence_fingerprint" maxlength="64"></div></div><div class="field"><label>Notiz</label><textarea name="notes" rows="3"></textarea></div><p><button>Feldabnahme speichern</button></p></form></div>
<div class="panel"><h2>Phase-3 Freeze</h2><p>Erzeugt ein verschlüsseltes Backup und führt das Phase-3-Gate aus. Ohne reale Feldabnahmen entsteht transparent nur ein <code>candidate_conditional</code>-Freeze.</p><form method="post" action="/phase3-release/freeze"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Freigabenotiz</label><textarea name="notes" rows="3"></textarea></div><div class="field"><label>Bestätigung</label><input name="confirmation" placeholder="PHASE 3 EINFRIEREN" required></div><p><button>Backup, Gate und Freeze ausführen</button></p></form></div>
<div class="panel"><h2>Letzte Phase-3-Gate-Prüfung</h2>{table(check_rows, [("title","Prüfung"),("severity","Schwere"),("status","Status"),("details","Details")])}</div>
<div class="two-col"><div class="panel"><h2>Feldabnahmen</h2>{table(fields, [("validated_at","Zeit"),("component_key","Komponente"),("platform_key","Plattform"),("status","Status"),("validated_by","Prüfer")])}</div><div class="panel"><h2>Phase-3 Freezes</h2>{table(freezes, [("created_at","Zeit"),("status","Status"),("backup_id","Backup"),("manifest_sha256","Manifest"),("created_by","Erstellt von")])}</div></div>
'''

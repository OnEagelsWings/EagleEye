from __future__ import annotations
from typing import Any, Callable


def render_final144(ctx: Any, case_id: str, csrf: str, *, esc: Callable[[Any], str], table: Callable[..., str]) -> str:
    data = ctx.build144.dashboard(case_id)
    latest = data.get("latest_audit") or {}
    return f'''
<div class="notice"><b>Build 144 · Phase-4 Release Candidate:</b> Vollständiges lokales Audit von Datenbank, Belegketten, Foto- und Berichtsintegrität, OPSEC-Sitzungen, Sicherheitsvertrag, Codepaket und Performance. Reale Windows- und externe Feldabnahmen bleiben gesondert.</div>
<div class="metrics"><div class="metric"><div class="label">Letzter Score</div><div class="value">{esc(latest.get("score", "–"))}</div></div><div class="metric"><div class="label">Blocker</div><div class="value">{esc(latest.get("blocker_count", 0))}</div></div><div class="metric"><div class="label">Warnungen</div><div class="value">{esc(latest.get("warning_count", 0))}</div></div><div class="metric"><div class="label">Verifizierte Backups</div><div class="value">{esc(data["metrics"]["verified_backups"])}</div></div></div>
<div class="two-col"><div class="panel"><h2>Vollständiges RC-Audit</h2><p>Führt alle verfügbaren lokalen Pflicht- und Optionalprüfungen einschließlich Benchmark aus.</p><form method="post" action="/final144/audit"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><label><input type="checkbox" name="include_optional" value="1" checked> Optionale Prüfungen einbeziehen</label><p><button>Vollständiges Audit ausführen</button></p></form></div>
<div class="panel"><h2>Verifiziertes Backup</h2><p>Erzeugt eine Online-SQLite-Sicherung, kopiert fallbezogene Foto- und Berichtartefakte und prüft den Sicherungsstand in einer getrennten Datenbankverbindung.</p><form method="post" action="/final144/backup"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="VERIFIZIERTES PHASE-4-BACKUP ERZEUGEN" required></div><p><button>Backup erzeugen und prüfen</button></p></form></div></div>
<div class="panel"><h2>Release-Candidate-Audits</h2>{table(data.get("audits", []), [("completed_at","Zeit"),("status","Status"),("score","Score"),("blocker_count","Blocker"),("warning_count","Warnungen"),("pass_count","Bestanden")])}</div>
<div class="two-col"><div class="panel"><h2>Backups</h2>{table(data.get("backups", []), [("created_at","Zeit"),("status","Status"),("restore_status","Restore"),("artifact_count","Artefakte"),("byte_size","DB-Bytes")])}</div><div class="panel"><h2>Benchmarks</h2>{table(data.get("benchmarks", []), [("created_at","Zeit"),("status","Status"),("iterations","Iterationen"),("operations_per_second","Ops/s"),("p95_ms","P95 ms")])}</div></div>
<div class="panel"><h2>Offene Phase-4-Risiken</h2>{table(data.get("risks", []), [("severity","Schwere"),("domain","Bereich"),("summary","Prüfung"),("status","Status"),("remediation","Maßnahme"),("updated_at","Aktualisiert")])}</div>
<p class="footer">Automatische Außenaktionen: 0 · Biometrische Identifizierung: 0 · Verdeckte Bilduploads: 0 · Audit ersetzt keinen unabhängigen Penetrationstest.</p>
'''

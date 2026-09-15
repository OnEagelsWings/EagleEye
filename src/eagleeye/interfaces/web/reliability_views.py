from __future__ import annotations

import json
from typing import Any, Callable


def render_reliability(
    ctx: Any,
    case_id: str,
    csrf: str,
    *,
    esc: Callable[[Any], str],
    table: Callable[..., str],
) -> str:
    svc = ctx.reliability_quality_125
    dashboard = svc.dashboard(case_id)
    latest = dashboard["latest_integrity"]
    report = {}
    if latest:
        try:
            report = json.loads(latest.get("report_json") or "{}")
        except Exception:
            report = {}
    issues = report.get("issues") or []
    issue_html = "".join(
        f'<div class="metric"><div class="label">{esc(item.get("severity", "info"))}</div>'
        f'<div class="value" style="font-size:16px">{esc(item.get("key", "issue"))}</div>'
        f'<div class="footer">{esc(item.get("detail") or item.get("count") or item.get("errors") or "Prüfung erforderlich")}</div></div>'
        for item in issues[:12]
    ) or '<div class="empty">Noch keine offenen Integritätsbefunde.</div>'
    score = int(latest.get("score") or 0) if latest else 0
    status = str(latest.get("status") or "not_run")
    protection = dashboard["protection"]
    return f'''
<div class="notice"><b>Build 125 Reliability Gate:</b> Backups, Wiederherstellung und Recovery werden lokal, explizit und auditierbar ausgeführt. Es gibt keine versteckten Hintergrundjobs.</div>
<div class="metrics">
  <div class="metric"><div class="label">Letzte Integritätsprüfung</div><div class="value">{esc(status)}</div><div class="footer">Score {score}/100</div></div>
  <div class="metric"><div class="label">Ermittlerschutz</div><div class="value">{int(protection.get("score") or 0)}/100</div><div class="footer">{esc(protection.get("level"))}</div></div>
  <div class="metric"><div class="label">Verifizierte Backups</div><div class="value">{sum(1 for row in dashboard["backups"] if row.get("status") == "verified")}</div></div>
  <div class="metric"><div class="label">Unsaubere Starts</div><div class="value">{sum(1 for row in dashboard["startup_sessions"] if not row.get("clean_shutdown") and row.get("recovered_at"))}</div></div>
</div>
<div class="two-col"><div class="panel"><h2>Integrität und Recovery</h2>
<form method="post" action="/reliability/check"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button>Vollständige Integritätsprüfung</button></form>
<form method="post" action="/reliability/recover"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button class="ghost">Verwaiste Jobs und Operationen wiederherstellen</button></p></form>
<p class="footer">Geprüft werden SQLite-Integrität, Fremdschlüssel, Fallgrenzen, laufende Jobs, Evidence-Checkpoints, Backupstatus und Investigator Protection.</p></div>
<div class="panel"><h2>Verschlüsseltes Komplettbackup</h2>
<form method="post" action="/reliability/backup"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><label><input type="checkbox" name="include_evidence" value="1" checked style="width:auto"> Evidence-Dateien einbeziehen</label><p><button>Backup erstellen und verifizieren</button></p></form>
<p class="footer">Das Paket wird AES-GCM-verschlüsselt. Der Schlüssel liegt im Build-124-Vault und ist unter Windows durch DPAPI an das Benutzerkonto gebunden.</p></div></div>
<div class="panel"><h2>Aktuelle Befunde</h2><div class="metrics">{issue_html}</div></div>
<div class="panel"><h2>Backup-Katalog</h2>{table(dashboard["backups"], [("created_at","Zeit"),("backup_id","Backup"),("status","Status"),("includes_evidence","Evidence"),("size_bytes","Bytes"),("package_sha256","Paket-Hash")])}
{''.join(f'''<form class="inline" method="post" action="/reliability/verify-backup"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="backup_id" value="{esc(row["backup_id"])}"><button class="ghost small">{esc(row["backup_id"])} verifizieren</button></form><form class="inline" method="post" action="/reliability/stage-restore"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="backup_id" value="{esc(row["backup_id"])}"><button class="ghost small">Restore-Stufe erzeugen</button></form>''' for row in dashboard["backups"][:10])}</div>
<div class="two-col"><div class="panel"><h2>Operation Journal</h2>{table(dashboard["operations"], [("started_at","Start"),("operation_type","Operation"),("state","Status"),("attempt","Versuch"),("error_text","Fehler")])}</div>
<div class="panel"><h2>Restore-Stufen</h2>{table(dashboard["restore_stages"], [("created_at","Zeit"),("stage_id","Stufe"),("backup_id","Backup"),("status","Status"),("database_sha256","DB-Hash")])}</div></div>
<div class="panel"><h2>Start- und Shutdown-Protokoll</h2>{table(dashboard["startup_sessions"], [("started_at","Start"),("process_id","PID"),("clean_shutdown","Sauber beendet"),("recovered_at","Recovery"),("notes","Hinweis")])}</div>
'''

from __future__ import annotations

from typing import Any, Callable


def render_security(
    ctx: Any,
    case_id: str,
    csrf: str,
    *,
    esc: Callable[[Any], str],
    table: Callable[..., str],
) -> str:
    svc = ctx.investigator_protection_124
    assessment = svc.assess(case_id)
    settings = assessment["settings"]
    findings = "".join(
        f'<div class="metric"><div class="label">{esc(item["key"])}</div>'
        f'<div class="value" style="font-size:18px">{"OK" if item["ok"] else "PRÜFEN"}</div>'
        f'<div class="footer">{esc(item["detail"])}</div></div>'
        for item in assessment["findings"]
    )
    limitations = "".join(f"<li>{esc(item)}</li>" for item in assessment["limitations"])
    events = svc.security_events(case_id, 80)
    launches = svc.launches(case_id, 80)
    approvals = svc.active_egress_approvals(case_id, 30)
    checkpoints = ctx.db.all(
        "SELECT * FROM evidence_trust_checkpoints_124 WHERE case_id=? ORDER BY created_at DESC LIMIT 30",
        (case_id,),
    )
    configured = ctx.db.all("SELECT secret_name,updated_at FROM encrypted_secrets_124 ORDER BY secret_name")
    secret_status = {row["secret_name"]: row["updated_at"] for row in configured}
    connector_providers = []
    try:
        connector_providers = sorted({row.get("provider_key", "") for row in ctx.research_strategy_128.list_connectors() if row.get("provider_key")})
    except Exception:
        connector_providers = []
    egress_provider_options = "".join(f'<option value="{esc(provider)}">{esc(provider)}</option>' for provider in ["searxng", "brave", "ollama_web", *connector_providers])

    mode_options = "".join(
        f'<option value="{mode}" {"selected" if settings.get("protection_mode") == mode else ""}>{mode}</option>'
        for mode in ("hardened", "proxy_required", "standard")
    )
    browser_options = "".join(
        f'<option value="{mode}" {"selected" if settings.get("research_browser_mode") == mode else ""}>{mode}</option>'
        for mode in ("isolated_firefox", "system_browser")
    )
    proxy_options = "".join(
        f'<option value="{mode}" {"selected" if settings.get("proxy_mode") == mode else ""}>{mode}</option>'
        for mode in ("none", "socks5", "http")
    )

    lock_status = (
        "Passphrasensperre aktiv"
        if settings.get("access_lock_enabled")
        else "Noch nicht aktiviert – lokaler Zugriff ist nur durch das zufällige Sitzungstoken und die Windows-Dateirechte begrenzt."
    )
    disable_form = ""
    if settings.get("access_lock_enabled"):
        disable_form = f'''
        <form method="post" action="/security/disable-lock">
          <input type="hidden" name="csrf" value="{esc(csrf)}">
          <input type="hidden" name="case_id" value="{esc(case_id)}">
          <div class="field"><label>Aktuelle Passphrase</label><input type="password" name="current_passphrase" required autocomplete="current-password"></div>
          <p><button class="danger">Zugriffssperre deaktivieren</button></p>
        </form>'''

    verification = svc.verify_evidence_checkpoints(case_id)
    return f'''
<div class="notice warn"><b>Ermittlerschutz reduziert digitale Spuren, garantiert aber keine Unverfolgbarkeit.</b><ul>{limitations}</ul></div>
<div class="panel"><h2>Schutzlage · {assessment["score"]}/100</h2><div class="metrics"><div class="metric"><div class="label">Gesamtstufe</div><div class="value">{esc(assessment["level"])}</div></div>{findings}</div></div>
<div class="panel"><h2>Lokaler Zugriffsschutz</h2><div class="notice {"" if settings.get("access_lock_enabled") else "warn"}"><b>Status:</b> {esc(lock_status)}</div>
<form method="post" action="/security/passphrase">
  <input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
  <div class="form-grid"><div class="field"><label>Aktuelle Passphrase – bei erstmaliger Aktivierung leer</label><input type="password" name="current_passphrase" autocomplete="current-password"></div>
  <div class="field"><label>Neue Passphrase – mindestens 12 Zeichen</label><input type="password" name="new_passphrase" autocomplete="new-password" required></div></div>
  <p><button>Passphrasensperre aktivieren/ändern</button></p>
</form>{disable_form}</div>
<div class="two-col"><div class="panel"><h2>Investigator Protection Mode</h2>
<form method="post" action="/security/config">
  <input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
  <div class="form-grid">
    <div class="field"><label>Schutzmodus</label><select name="protection_mode">{mode_options}</select></div>
    <div class="field"><label>Recherchebrowser</label><select name="research_browser_mode">{browser_options}</select></div>
    <div class="field"><label>Proxymodus</label><select name="proxy_mode">{proxy_options}</select></div>
    <div class="field"><label>Proxy-Host</label><input name="proxy_host" value="{esc(settings.get("proxy_host"))}"></div>
    <div class="field"><label>Proxy-Port</label><input type="number" min="0" max="65535" name="proxy_port" value="{int(settings.get("proxy_port") or 0)}"></div>
    <div class="field"><label>Sitzungs-Timeout in Minuten</label><input type="number" min="5" max="240" name="session_timeout_minutes" value="{int(settings.get("session_timeout_minutes") or 20)}"></div>
  </div>
  <div class="inline">
    <label><input type="checkbox" name="proxy_remote_dns" value="1" {"checked" if settings.get("proxy_remote_dns") else ""}> DNS über SOCKS-Proxy</label>
    <label><input type="checkbox" name="block_external_provider_network" value="1" {"checked" if settings.get("block_external_provider_network") else ""}> Externe Provider standardmäßig blockieren</label>
    <label><input type="checkbox" name="clear_profile_before_launch" value="1" {"checked" if settings.get("clear_profile_before_launch") else ""}> Profil vor jeder Recherche bereinigen</label>
    <label><input type="checkbox" name="ephemeral_profile_per_launch" value="1" {"checked" if settings.get("ephemeral_profile_per_launch") else ""}> Neues Firefox-Profil je Recherchelauf</label>
    <label><input type="checkbox" name="session_bind_client" value="1" {"checked" if settings.get("session_bind_client") else ""}> Sitzung an lokalen Browser binden</label>
    <label><input type="checkbox" name="panic_purge_profiles" value="1" {"checked" if settings.get("panic_purge_profiles") else ""}> Notfallsperre löscht Profilreste</label>
    <label><input type="checkbox" name="allow_default_browser_fallback" value="1" {"checked" if settings.get("allow_default_browser_fallback") else ""}> Systembrowser-Fallback erlauben</label>
  </div><p><button>Schutzkonfiguration speichern</button></p>
</form></div>
<div class="panel"><h2>Sofortschutz</h2><p>Die Notfallsperre verwirft aktive Sitzungen, kurzlebige Recherche-Weiterleitungen und externe Netzfreigaben. Optional werden alle fallbezogenen Firefox-Profilreste entfernt.</p>
<form method="post" action="/security/rotate-profile"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button class="ghost">Fallprofil jetzt rotieren</button></form>
<form method="post" action="/security/lockdown"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button class="danger">Notfallsperre auslösen</button></p></form>
<p class="footer">Eine Löschung kann auf SSDs keine forensisch garantierte physische Überschreibung versprechen. Sie reduziert jedoch unmittelbar die in EagleEye gehaltenen Sitzungs- und Profilreste.</p></div></div>
<div class="two-col"><div class="panel"><h2>Verschlüsselter Provider-Vault</h2><p class="footer">Secrets werden AES-GCM-verschlüsselt gespeichert; unter Windows ist der Master-Key über DPAPI an das Windows-Benutzerkonto gebunden.</p>
<form method="post" action="/security/secrets"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
  <div class="field"><label>Brave API-Key – {"konfiguriert" if "brave_api_key" in secret_status else "nicht konfiguriert"}</label><input type="password" name="brave_api_key" autocomplete="off" placeholder="Leer lassen = unverändert"></div>
  <div class="field"><label>Ollama API-Key – {"konfiguriert" if "ollama_api_key" in secret_status else "nicht konfiguriert"}</label><input type="password" name="ollama_api_key" autocomplete="off" placeholder="Leer lassen = unverändert"></div>
  <p><button>Secrets verschlüsselt speichern</button></p>
</form></div></div>
<div class="two-col"><div class="panel"><h2>Einmalige externe Netzfreigabe</h2>
<form method="post" action="/security/egress"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}">
  <div class="field"><label>Provider</label><select name="provider">{egress_provider_options}</select></div>
  <div class="field"><label>Freigebender Ermittler</label><input name="approved_by" value="{esc(ctx.actor)}" required></div>
  <div class="field"><label>Dokumentierter Zweck</label><textarea name="purpose" rows="3" required></textarea></div>
  <div class="field"><label>Freigabephrase</label><input name="confirmation" placeholder="NETZZUGRIFF FREIGEBEN" required></div>
  <p><button>Netzzugriff einmalig freigeben</button></p>
</form></div>
<div class="panel"><h2>Evidence Trust Checkpoint</h2><p>Erzeugt einen lokal signierten Hashketten-Checkpoint über alle Evidence Packages des Falls. Dies erkennt nachträgliche lokale Manipulation, ersetzt aber keinen unabhängigen externen Zeitstempel.</p>
<form method="post" action="/security/checkpoint"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><button>Checkpoint erzeugen</button></form>
<p class="footer">Kette gültig: {"ja" if verification["valid"] else "nein"} · {verification["checkpoint_count"]} Checkpoints · {esc(verification["limitation"])}</p></div></div>
<div class="panel"><h2>Netzfreigaben</h2>{table(approvals, [("created_at","Zeit"),("provider","Provider"),("approved_by","Freigabe"),("status","Status"),("expires_epoch","Ablauf")])}</div>
<div class="panel"><h2>Geschützte Rechercheausstiege</h2>{table(launches, [("launched_at","Zeit"),("destination_host","Zielhost"),("browser_mode","Modus"),("status","Status"),("error_text","Fehler")])}</div>
<div class="panel"><h2>Trust Checkpoints</h2>{table(checkpoints, [("created_at","Zeit"),("package_count","Pakete"),("checkpoint_sha256","Checkpoint"),("previous_sha256","Vorgänger")])}</div>
<div class="panel"><h2>Sicherheitsereignisse</h2>{table(events, [("created_at","Zeit"),("event_type","Ereignis"),("severity","Stufe"),("details_json","Details")])}</div>
'''

from __future__ import annotations

import json
from typing import Any, Callable


def render_capture_identity(
    ctx: Any,
    case_id: str,
    csrf: str,
    *,
    esc: Callable[[Any], str],
    table: Callable[..., str],
) -> str:
    svc = ctx.capture_identity_129
    data = svc.dashboard(case_id)
    targets = ctx.targets.list_targets(case_id)
    target_options = '<option value="">Ohne Zielbindung</option>' + "".join(
        f'<option value="{esc(row["target_id"])}">{esc(row["name"])}</option>' for row in targets
    )
    entities = data.get("entities") or []
    entity_options = "".join(
        f'<option value="{esc(row["resolution_entity_id"])}">{esc(row["display_name"])} · {esc(row["entity_type"])}</option>'
        for row in entities
    )
    metrics = data["metrics"]
    metric_html = "".join(
        f'<div class="metric"><div class="label">{esc(label)}</div><div class="value">{int(metrics.get(key, 0))}</div></div>'
        for key, label in (
            ("captures", "Browser-Captures"),
            ("changed_pages", "Veränderte Seiten"),
            ("quarantined_captures", "Injection-Quarantäne"),
            ("identity_hypotheses", "Identitätshypothesen"),
            ("pending_identity_reviews", "Offene Identity-Reviews"),
            ("pending_ai_suggestions", "AI-Vorschläge offen"),
        )
    )

    capture_cards: list[str] = []
    for row in data.get("captures") or []:
        flags = json.loads(row.get("injection_flags_json") or "[]")
        capture_cards.append(
            f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("title"))}</h3><p>{esc(row.get("source_host"))}</p></div><span class="badge {"candidate" if row.get("status") != "candidate_captured" else "ok"}">{esc(row.get("status"))}</span></div>
<p>Änderungsstatus: <b>{esc(row.get("change_state"))}</b> · Artefakte: {int(row.get("artifact_count") or 0)} · Evidence: {esc(row.get("evidence_package_id"))}</p>
{f'<div class="notice error">Untrusted-Inhalte quarantänisiert: {esc(", ".join(flags))}</div>' if flags else ''}
<p class="footer">URL-Fingerprint/Hashes werden geprüft; automatische Wahrheits- oder Identitätspromotion findet nicht statt. Erfasst: {esc(row.get("captured_at"))}</p></div>'''
        )

    hypothesis_cards: list[str] = []
    for row in data.get("hypotheses") or []:
        form = ""
        if row.get("state") == "candidate":
            form = f'''<form method="post" action="/capture-identity/review"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><input type="hidden" name="hypothesis_id" value="{esc(row["hypothesis_id"])}"><div class="decision"><select name="decision"><option value="needs_more_evidence">Mehr Evidence erforderlich</option><option value="same_person">Als gleiche Person geprüft</option><option value="distinct_person">Als verschiedene Personen geprüft</option><option value="deferred">Zurückstellen</option><option value="rejected">Hypothese verwerfen</option></select><input name="reason" minlength="12" required placeholder="Substanzielle Reviewbegründung"><button>Review speichern</button></div></form>'''
        hypothesis_cards.append(
            f'''<div class="intake-card"><div class="intake-head"><div><h3>{esc(row.get("recommendation"))}</h3><p>{esc(row.get("left_entity_id"))} ↔ {esc(row.get("right_entity_id"))}</p></div><span class="badge candidate">{esc(row.get("state"))}</span></div><p>Positive Komponenten: {int(row.get("positive_component_count") or 0)} · Konflikte: {int(row.get("conflict_component_count") or 0)} · unabhängige Quellen: {int(row.get("independent_source_count") or 0)}</p><div class="notice warn">Empfehlung ist keine Identitätsbestätigung. Precision-first: falsche Zusammenführungen werden stärker gewichtet als getrennte Kandidaten.</div>{form}</div>'''
        )

    benchmark = data.get("latest_benchmark")
    benchmark_html = '<div class="empty">Noch kein synthetischer Golden-Case-Benchmark ausgeführt.</div>'
    if benchmark:
        benchmark_html = f'''<div class="metrics"><div class="metric"><div class="label">Precision</div><div class="value">{float(benchmark.get("precision") or 0)*100:.1f}%</div></div><div class="metric"><div class="label">Recall</div><div class="value">{float(benchmark.get("recall") or 0)*100:.1f}%</div></div><div class="metric"><div class="label">False-Merge-Rate</div><div class="value">{float(benchmark.get("false_merge_rate") or 0)*100:.1f}%</div></div><div class="metric"><div class="label">Fälle</div><div class="value">{int(benchmark.get("case_count") or 0)}</div></div></div>'''

    return f'''
<div class="notice warn"><b>Build 129 · Evidence Capture & Identity Resolution Pro:</b> Browserinhalte gelten als untrusted und werden candidate-only gesichert. Identitätshypothesen führen niemals automatisch zu einem Merge. AI-Ausgaben bleiben <code>suggestions_only</code>.</div>
<div class="metrics">{metric_html}</div>
<div class="two-col"><div class="panel"><h2>Firefox Capture Companion koppeln</h2><p>Erzeuge ein einmaliges Ticket und trage es im lokalen Firefox-Companion ein. Das Ticket ist gehasht gespeichert, läuft ab und kann nur einmal verwendet werden.</p><form method="post" action="/capture-identity/ticket"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Person/Entität optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Dokumentierter Capture-Zweck</label><textarea name="purpose" rows="3" required>Öffentliche Webseite als candidate-only Evidence sichern.</textarea></div><div class="field"><label>Gültigkeit in Sekunden</label><input type="number" name="ttl_seconds" min="60" max="1800" value="600"></div><p><button>Einmaliges Companion-Ticket erzeugen</button></p></form><p class="footer">Companion-Quellcode: <code>tools/firefox_companion_136</code>. Installation als temporäres Add-on über <code>about:debugging</code>; für produktiven Rollout ist später eine signierte Firefox-Erweiterung erforderlich.</p></div>
<div class="panel"><h2>Manueller Capture-Fallback</h2><p>Dieser Pfad funktioniert ohne Add-on und nutzt dieselbe Evidence-, Change-Detection-, AI-Triage- und OPSEC-Pipeline.</p><form method="post" action="/capture-identity/manual"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Person/Entität optional</label><select name="target_id">{target_options}</select></div><div class="field"><label>Öffentliche HTTPS-URL</label><input name="url" required placeholder="https://..."></div><div class="field"><label>Titel</label><input name="title" required></div><div class="field"><label>Sichtbarer Text</label><textarea name="visible_text" rows="7" required></textarea></div><div class="field"><label>HTML optional</label><textarea name="html" rows="4"></textarea></div><p><button>Candidate-only Capture sichern</button></p></form></div></div>
<div class="panel"><h2>Evidence Captures und Veränderungserkennung</h2>{''.join(capture_cards) or '<div class="empty">Noch keine Build-129-Captures.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Identity Hypothesis Workspace</h2><form method="post" action="/capture-identity/hypothesis"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><div class="field"><label>Entität A</label><select name="left_entity_id" required>{entity_options}</select></div><div class="field"><label>Entität B</label><select name="right_entity_id" required>{entity_options}</select></div><p><button>Precision-first Identitätshypothese erzeugen</button></p></form><p class="footer">Berücksichtigt getrennte Komponenten: Name, Aliasse, starke Anker, Zeit, Ort, Organisation, Domains, Quellenunabhängigkeit und Gegenbelege.</p></div><div class="panel"><h2>Golden Identity Suite</h2>{benchmark_html}<form method="post" action="/capture-identity/benchmark"><input type="hidden" name="csrf" value="{esc(csrf)}"><input type="hidden" name="case_id" value="{esc(case_id)}"><p><button class="ghost">Synthetischen 40-Fälle-Benchmark ausführen</button></p></form></div></div>
<div class="panel"><h2>Identitätshypothesen und Human Review</h2>{''.join(hypothesis_cards) or '<div class="empty">Noch keine Identitätshypothesen.</div>'}</div>
<div class="two-col"><div class="panel"><h2>Change Sets</h2>{table(data.get("changes") or [], [("created_at","Zeit"),("change_state","Status"),("canonical_url","URL"),("previous_capture_id","Vorher"),("current_capture_id","Aktuell"),("review_status","Review")])}</div><div class="panel"><h2>AI-Ermittlung 129</h2>{table(data.get("suggestions") or [], [("created_at","Zeit"),("suggestion_type","Typ"),("trust_state","Trust"),("review_status","Review"),("model_key","Modell")])}</div></div>
'''

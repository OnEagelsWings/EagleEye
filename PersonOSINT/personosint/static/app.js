/* EagleEye PersonOSINT – Weboberfläche */
(function () {
  "use strict";

  // ------------------------------------------------------------------ Hilfsfunktionen
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const COLORS = window.NetworkGraph.colors();
  const state = { meta: null, cases: [], caseId: null, tab: "overview", graph: null, map: null, findingFilter: "neu", selEntity: null, searchEntity: null, lastSearch: null, auth: null, view: "", users: [], presenceTimer: null };

  async function api(method, url, body) {
    const opts = { method, headers: { "X-Requested-With": "EagleEye" } };
    if (state.auth && state.auth.csrf) opts.headers["X-CSRF-Token"] = state.auth.csrf;
    if (body instanceof FormData) opts.body = body;
    else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const r = await fetch(url, opts);
    if (r.status === 204) return null;
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : `Fehler ${r.status}`;
      if (r.status === 401 && !url.startsWith("/api/auth/")) { showAuth(); }
      const err = new Error(msg); err.status = r.status;
      throw err;
    }
    return data;
  }

  function toast(msg, type = "") {
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = msg;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), type === "err" ? 7000 : 3800);
  }

  async function guard(fn, okMsg) {
    try { const r = await fn(); if (okMsg) toast(okMsg, "ok"); return r; }
    catch (e) { toast(e.message || String(e), "err"); throw e; }
  }

  function fmtTs(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function fmtLocal(s) { return (s || "").replace("T", " "); }
  function fmtDate(d) { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d || ""); return m ? `${m[3]}.${m[2]}.${m[1]}` : (d || ""); }

  function modal(title, body, foot, opts = {}) {
    const root = $("#modal-root");
    const bg = document.createElement("div");
    bg.className = "modal-bg";
    bg.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}" style="${opts.width ? "width:min(" + opts.width + ",100%)" : ""}">
      <div class="modal-head"><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Schließen">✕</button></div>
      <div class="modal-body">${body}</div>${foot ? `<div class="modal-foot">${foot}</div>` : ""}</div>`;
    root.appendChild(bg);
    const close = () => { bg.remove(); document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    bg.addEventListener("mousedown", (e) => { if (e.target === bg) close(); });
    $$("[data-close]", bg).forEach((b) => b.addEventListener("click", close));
    const first = $("input, select, textarea", bg);
    if (first) setTimeout(() => first.focus(), 30);
    return { el: bg, close };
  }

  function confirmDlg(text, okLabel = "Löschen") {
    return new Promise((resolve) => {
      const m = modal("Bitte bestätigen", `<p>${esc(text)}</p>`, `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="dlg-ok">${esc(okLabel)}</button>`);
      $("#dlg-ok", m.el).onclick = () => { m.close(); resolve(true); };
      $$("[data-close]", m.el).forEach((b) => b.addEventListener("click", () => resolve(false)));
    });
  }

  function formData(form) {
    const out = {};
    new FormData(form).forEach((v, k) => { out[k] = typeof v === "string" ? v.trim() : v; });
    return out;
  }

  const opt = (value, label, sel) => `<option value="${esc(value)}"${String(value) === String(sel) ? " selected" : ""}>${esc(label)}</option>`;
  const typeBadge = (t) => ({ vermisst: "b-red", personensuche: "b-blue", verbindungen: "b-purple" }[t] || "");
  const statusBadge = (s) => ({ neu: "b-blue", "bestätigt": "b-green", verworfen: "b-grey" }[s] || "");
  const scoreColor = (s) => (s >= 75 ? "#059669" : s >= 45 ? "#d97706" : s >= 20 ? "#64748b" : "#cbd5e1");
  const EXPO_BADGE = { lokal: "b-purple", passiv: "b-green", plattform: "b-blue", sichtbar: "b-amber", zielkontakt: "b-red" };
  const relBadge = (r) => r ? `<span class="badge b-grey" title="Verlässlichkeit der Quelle (Admiralty-Code): ${esc({ A: "vollkommen zuverlässig", B: "in der Regel zuverlässig", C: "ziemlich zuverlässig", D: "in der Regel nicht zuverlässig", E: "unzuverlässig", F: "nicht beurteilbar" }[r] || "")}">${esc(r)}</span>` : "";
  const period = (a, b) => (a || b) ? `<span class="muted">(${esc(a || "?")}${b ? " – " + esc(b) : a ? " – heute?" : ""})</span>` : "";
  const expoBadge = (key) => `<span class="badge ${EXPO_BADGE[key] || ""}" title="${esc(state.meta.exposure[key].help)}">${esc(state.meta.exposure[key].label)}</span>`;
  const opsecBadge = (lvl) => `<span class="badge opsec-${lvl}" title="${esc(state.meta.opsec_levels[lvl].summary)}">OPSEC ${lvl} · ${esc(state.meta.opsec_levels[lvl].name)}</span>`;
  const help = (title, items, open = false) => `<details class="help"${open ? " open" : ""}><summary>💡 ${esc(title)}</summary><ul>${items.map((i) => `<li>${i}</li>`).join("")}</ul></details>`;

  // ------------------------------------------------------------------ Seitenleiste
  async function loadCases() {
    state.cases = await api("GET", "/api/cases" + (state.view ? "?view=" + state.view : ""));
    renderCaseList();
  }

  function renderCaseList() {
    const q = ($("#case-filter").value || "").toLowerCase();
    const list = state.cases.filter((c) => !q || `${c.title} ${c.reference} ${c.subject_label || ""}`.toLowerCase().includes(q));
    $("#case-list").innerHTML = list.length ? list.map((c) => `
      <a class="case-item ${c.id === state.caseId ? "active" : ""}" href="#/case/${c.id}/overview">
        <span class="t">${c.opsec_level >= 2 ? "🛡 " : ""}${esc(c.display_name || c.subject_label || c.title)}</span>
        <span class="m"><span class="badge ${typeBadge(c.case_type)}">${esc(c.case_type_label)}</span>${esc(c.reference)}
        ${c.restricted ? '<span class="badge b-grey" title="Vertraulicher Fall – nur für das Fallteam sichtbar">🔒</span>' : ""}
        ${c.opsec_level >= 2 ? `<span class="badge opsec-${c.opsec_level}">OPSEC ${c.opsec_level}</span>` : ""}
        ${c.open_findings ? `<span class="badge b-amber" title="Ungeprüfte Treffer">${c.open_findings} offen</span>` : ""}
        ${c.status === "zur Prüfung" ? '<span class="badge b-purple">zur Prüfung</span>' : c.status === "freigegeben" ? '<span class="badge b-green">freigegeben</span>' : c.status === "abgeschlossen" ? '<span class="badge b-green">abgeschlossen</span>' : ""}
        ${c.overdue ? `<span class="badge b-red" title="Fällig am ${esc(c.due_date)}">überfällig</span>` : ""}
        ${c.priority === "dringend" ? '<span class="badge b-red">dringend</span>' : ""}</span>
        ${c.owner_name ? `<span class="m">👤 ${esc(c.owner_name)}${c.reviewer_name ? " · Prüfung: " + esc(c.reviewer_name) : ""}</span>` : ""}
      </a>`).join("") : `<div class="empty small">${state.cases.length ? "Kein Fall passt zum Filter." : "Noch keine Fälle.<br><br>Legen Sie oben rechts einen <b>neuen Fall</b> an oder laden Sie den Beispielfall."}</div>`;
    $("#sidebar-foot").innerHTML = `${state.cases.length} Fälle · v${esc(state.meta ? state.meta.version : "")}<br><span>${state.meta && state.meta.database === "postgres" ? "Teamserver (PostgreSQL)" : "Einzelplatz (lokal)"}</span>`;
  }

  // ------------------------------------------------------------------ Routing
  function route() {
    const m = location.hash.match(/^#\/case\/(\d+)(?:\/(\w+))?/);
    if (state.graph) { state.graph.destroy(); state.graph = null; }
    if (state.map) { state.map.remove(); state.map = null; }
    $("#sidebar").classList.remove("open");
    stopPresence();
    document.body.classList.remove("readonly");
    if (location.hash.startsWith("#/admin")) { state.caseId = null; renderAdmin(location.hash.split("/")[2] || "users"); renderCaseList(); return; }
    if (location.hash.startsWith("#/account")) { state.caseId = null; renderAccount(); renderCaseList(); return; }
    if (m) {
      const id = Number(m[1]);
      if (id !== state.caseId) { state.selEntity = null; state.searchEntity = null; state.lastSearch = null; state.findingFilter = "neu"; }
      state.caseId = id; state.tab = m[2] || "overview";
      renderCase().catch((e) => { toast(e.message, "err"); location.hash = "#/"; });
    } else {
      state.caseId = null;
      renderWelcome();
    }
    renderCaseList();
  }

  // ------------------------------------------------------------------ Startseite
  function renderWelcome() {
    $("#main").innerHTML = `
      <section class="hero">
        <h1>Personen finden. Verbindungen verstehen. Klar dokumentieren.</h1>
        <p>EagleEye PersonOSINT bündelt öffentliche Quellen für die <b>Personensuche</b>, die <b>Recherche nach vermissten Menschen</b> und die <b>Analyse von Verbindungen</b>. Jeder Treffer wird nachvollziehbar bewertet, von Ihnen geprüft und als Word-Dossier exportiert.</p>
        <div class="row"><button class="btn btn-primary btn-lg" id="w-new">＋ Neuen Fall anlegen</button>
        <button class="btn btn-ghost-light btn-lg" id="w-demo">Beispielfall ansehen</button></div>
      </section>
      <h2>So funktioniert es</h2>
      <div class="steps-intro">
        ${[["Fall anlegen", "Fallart wählen, Zweck und Rechtsgrundlage dokumentieren."],
           ["Person erfassen", "Namen, Aliasse, Benutzernamen, E-Mail, Telefon, Orte und Foto hinterlegen."],
           ["Quellen durchsuchen", "Ein Klick fragt öffentliche Quellen ab – Treffer werden automatisch bewertet."],
           ["Treffer prüfen", "Bestätigen oder verwerfen. Bestätigtes wandert automatisch in den Graphen."],
           ["Verbindungen analysieren", "Netzwerkgraph, Pfadsuche zwischen Personen, Vorschläge und Schlüsselakteure."],
           ["Dossier exportieren", "Klares Word-Dossier mit Netzwerkgrafik, Zeitleiste und Quellenverzeichnis."]]
          .map((s, i) => `<div class="step-card"><div class="n">${i + 1}</div><b>${s[0]}</b><div class="muted small">${s[1]}</div></div>`).join("")}
      </div>
      <div class="card" style="margin-top:1.25rem">
        <h3>Grundsätze</h3>
        <ul class="small">
          <li>Nur <b>öffentlich zugängliche</b> Quellen, keine Umgehung von Logins oder Zugangsschranken.</li>
          <li>Automatische Treffer sind <b>Kandidaten</b> – erst Ihre Prüfung macht sie zu Erkenntnissen. Gleicher Name ≠ gleiche Person.</li>
          <li>Jeder Fall verlangt <b>Zweck und Rechtsgrundlage</b>; alle Schritte werden protokolliert (DSGVO: Zweckbindung, Datenminimierung).</li>
          <li>Bei Vermisstenfällen gilt: <b>Polizei zuerst</b> – die Plattform unterstützt Angehörige und Fachstellen, ersetzt aber keine Ermittlungen.</li>
        </ul>
      </div>`;
    $("#w-new").onclick = openNewCase;
    $("#w-demo").onclick = loadDemo;
  }

  async function loadDemo() {
    const existing = state.cases.find((c) => c.title.startsWith("Beispiel:"));
    if (existing) { location.hash = `#/case/${existing.id}/overview`; return; }
    const c = await guard(() => api("POST", "/api/demo"), "Beispielfall geladen");
    await loadCases();
    location.hash = `#/case/${c.id}/overview`;
  }

  // ------------------------------------------------------------------ Neuer Fall (Assistent)
  async function openNewCase() {
    try { state.users = await api("GET", "/api/users"); state.egress = await api("GET", "/api/egress-profiles"); } catch (_) { /* vorhandene Listen nutzen */ }
    const types = [
      ["investigativ", "📰", "Investigativrecherche", "Akteure, Netzwerke und Belege für eine Recherche – mit Quellenschutz und Gegenrecherche."],
      ["personensuche", "🔎", "Personensuche", "Eine Person identifizieren, Online-Präsenz und Lebensumfeld aufklären."],
      ["vermisst", "🆘", "Vermisstenfall", "Vermisste Person: letzte Sichtung, Zeitleiste & Karte, Gefährdung, Suchplakat."],
      ["verbindungen", "🕸️", "Verbindungsanalyse", "Beziehungen zwischen mehreren Personen und Organisationen aufdecken."],
    ];
    const bases = ["Einwilligung der betroffenen Person", "Auftrag von Angehörigen (Vermisstensuche)", "Berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO)",
      "Behördlicher Auftrag / Ermittlungsverfahren", "Journalistische Recherche (Medienprivileg)", "Anschriftenermittlung im Forderungsmanagement", "Sonstige (bitte beschreiben)"];
    const m = modal("Neuen Fall anlegen", `
      <div class="wizard-steps"><span class="on">1 · Fallart</span><span>2 · Auftrag</span><span>3 · Zielperson</span></div>
      <form id="nc">
        <section data-step="1">
          <p class="muted">Welche Art von Recherche möchten Sie durchführen?</p>
          <div class="type-cards">${types.map((t, i) => `<button type="button" class="type-card ${i === 0 ? "selected" : ""}" data-type="${t[0]}"><div class="ic">${t[1]}</div><b>${t[2]}</b><div class="small muted">${t[3]}</div></button>`).join("")}</div>
          <input type="hidden" name="case_type" value="investigativ">
        </section>
        <section data-step="2" class="hidden">
          <label class="field"><span>Falltitel *</span><input name="title" required placeholder="z. B. Aufenthaltsermittlung Max Mustermann"></label>
          <label class="field"><span>Zweck der Recherche *</span><textarea name="purpose" required placeholder="Warum wird recherchiert? Welches Ergebnis wird benötigt?"></textarea><small>Pflichtangabe – wird im Dossier und Protokoll dokumentiert.</small></label>
          <label class="field"><span>Rechtsgrundlage / Auftrag *</span><select name="legal_basis_sel">${bases.map((b) => opt(b, b)).join("")}</select></label>
          <label class="field hidden" id="lb-other"><span>Rechtsgrundlage beschreiben</span><input name="legal_basis_other"></label>
          <div class="grid g2"><label class="field"><span>Auftraggeber / Redaktion</span><input name="client"></label>
            <label class="field"><span>Prüfperson (Vier-Augen)</span><select name="reviewer_id">${opt("", "– später festlegen –")}${state.users.filter((u) => u.id !== state.auth.user.id && u.role !== "leser").map((u) => opt(u.id, `${u.display_name} (${u.role_label})`)).join("")}</select></label>
            <label class="field"><span>Fällig am</span><input type="date" name="due_date"></label>
            <label class="field"><span>Priorität</span><select name="priority">${["normal", "hoch", "dringend", "niedrig"].map((x) => opt(x, x)).join("")}</select></label></div>
          <label class="field"><span>🛡 OPSEC-Stufe</span></label>
          <div class="type-cards opsec-cards">${[1, 2, 3].map((k) => `<button type="button" class="type-card" data-lvl="${k}">${opsecBadge(k)}<div class="small muted" style="margin-top:.35rem">${esc(state.meta.opsec_levels[k].summary)}</div></button>`).join("")}</div>
          <input type="hidden" name="opsec_level" value="2">
          <label class="field" style="margin-top:.6rem"><span>Netzausgang für automatische Abfragen</span><select name="egress_profile">${opt("", "Voreinstellung der Organisation")}${(state.egress || []).map((e) => opt(e.id, e.name + (e.kind === "direkt" ? " – ohne Anonymisierung" : ""))).join("")}</select>
            <small>Ab Stufe 2 nur über einen Anonymisierungs-Ausgang (Proxy/Tor); fehlt er, werden Abfragen blockiert statt direkt gesendet.</small></label>
          <label class="check"><input type="checkbox" name="restricted" checked> <span><b>🔒 Vertraulicher Fall (Quellenschutz)</b><br><span class="small muted">Nur das Fallteam sieht den Fall – auch Teamleitung und Administration nicht. Empfohlen für investigative Recherchen.</span></span></label>
          <div class="mandate" id="mandate">
            <h3 style="margin:.9rem 0 .2rem">⚖ Auftragsprüfung</h3>
            <p class="small muted" style="margin:0 0 .4rem">Schutz vor Missbrauch (Stalking, häusliche Gewalt, Umgehung von Schutzanordnungen). Die Antworten werden im Fall und im Dossier dokumentiert.</p>
            ${(state.meta.mandate_questions || []).map((q) => `<div class="mq" data-mq="${esc(q.key)}" data-risk="${q.risk ? 1 : 0}"><div class="small">${esc(q.text)}</div>
              <div class="mq-ans"><label><input type="radio" name="mq_${esc(q.key)}" value="1"> Ja</label><label><input type="radio" name="mq_${esc(q.key)}" value="0"> Nein</label></div></div>`).join("")}
            <div id="mq-warn" class="bad-box hidden small"></div>
            <label class="field hidden" id="mq-reason"><span>Begründung, warum der Auftrag trotz Warnsignalen zulässig ist (mind. 30 Zeichen)</span><textarea name="mandate_reason"></textarea></label>
          </div>
        </section>
        <section data-step="3" class="hidden">
          <p class="muted small">Optional – Sie können die Person auch später erfassen. Mehr Angaben = bessere Treffer.</p>
          <label class="field"><span>Vollständiger Name der Zielperson</span><input name="s_name" placeholder="Vorname Nachname"></label>
          <div class="grid g2">
            <label class="field"><span>Geburtsdatum</span><input type="date" name="s_birth"></label>
            <label class="field"><span>Wohnort / letzter bekannter Ort</span><input name="s_loc" placeholder="z. B. Hamburg"></label>
            <label class="field"><span>Benutzername (Social Media)</span><input name="s_user" placeholder="ohne @"></label>
            <label class="field"><span>E-Mail-Adresse</span><input type="email" name="s_email"></label>
            <label class="field"><span>Telefonnummer</span><input name="s_phone"></label>
            <label class="field"><span>Arbeitgeber / Schule</span><input name="s_emp"></label>
          </div>
        </section>
      </form>`,
      `<button class="btn" id="nc-back" style="margin-right:auto" disabled>← Zurück</button><button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="nc-next">Weiter →</button>`);
    let step = 1;
    const form = $("#nc", m.el);
    $$(".type-card", m.el).forEach((b) => b.onclick = () => {
      $$(".type-card", m.el).forEach((x) => x.classList.remove("selected")); b.classList.add("selected");
      form.case_type.value = b.dataset.type;
      if (b.dataset.type === "vermisst") form.legal_basis_sel.value = "Auftrag von Angehörigen (Vermisstensuche)";
      if (b.dataset.type === "investigativ") form.legal_basis_sel.value = "Journalistische Recherche (Medienprivileg)";
      form.restricted.checked = b.dataset.type === "investigativ";
      mqVisible();
      setLvl(b.dataset.type === "investigativ" ? Math.max(2, state.meta.opsec_defaults.default_level) : state.meta.opsec_defaults.default_level);
    });
    form.legal_basis_sel.value = "Journalistische Recherche (Medienprivileg)";
    const setLvl = (k) => {
      form.opsec_level.value = k;
      $$(".opsec-cards .type-card", m.el).forEach((x) => x.classList.toggle("selected", Number(x.dataset.lvl) === Number(k)));
      if (Number(k) === 3) { form.restricted.checked = true; form.restricted.disabled = true; } else form.restricted.disabled = false;
    };
    $$(".opsec-cards .type-card", m.el).forEach((b) => (b.onclick = () => setLvl(b.dataset.lvl)));
    setLvl(Math.max(2, state.meta.opsec_defaults.default_level));
    form.legal_basis_sel.onchange = () => $("#lb-other", m.el).classList.toggle("hidden", !form.legal_basis_sel.value.startsWith("Sonstige"));
    function mqVisible() {
      $$("[data-mq]", m.el).forEach((q) => q.classList.toggle("hidden", q.dataset.mq === "freiwillig" && form.case_type.value !== "vermisst"));
      mqEval();
    }
    function mqEval() {
      const answers = {}, warnings = [];
      let missing = 0;
      $$("[data-mq]", m.el).forEach((q) => {
        if (q.classList.contains("hidden")) return;
        const v = $("input:checked", q);
        if (!v) { missing++; return; }
        answers[q.dataset.mq] = v.value === "1";
        if (answers[q.dataset.mq] === (q.dataset.risk === "1")) warnings.push($(".small", q).textContent);
        q.classList.toggle("mq-risk", answers[q.dataset.mq] === (q.dataset.risk === "1"));
      });
      const lead = ["leitung", "admin"].includes(state.auth.user.role);
      const box = $("#mq-warn", m.el);
      box.classList.toggle("hidden", !warnings.length);
      box.innerHTML = warnings.length ? `<b>⚠ ${warnings.length} Warnsignal(e).</b> ${lead ? "Der Auftrag darf nur nach eigener Prüfung und mit ausführlicher Begründung angenommen werden." : "Solche Aufträge darf nur die Teamleitung annehmen. Bitte Teamleitung einbinden oder den Auftrag ablehnen."}` : "";
      $("#mq-reason", m.el).classList.toggle("hidden", !(warnings.length && lead));
      return { answers, warnings, missing, lead };
    }
    $$("[data-mq] input", m.el).forEach((i) => (i.onchange = mqEval));
    mqVisible();
    const show = () => {
      $$("[data-step]", m.el).forEach((s) => s.classList.toggle("hidden", Number(s.dataset.step) !== step));
      $$(".wizard-steps span", m.el).forEach((s, i) => s.classList.toggle("on", i < step));
      $("#nc-back", m.el).disabled = step === 1;
      $("#nc-next", m.el).textContent = step === 3 ? "✓ Fall anlegen" : "Weiter →";
    };
    $("#nc-back", m.el).onclick = () => { step--; show(); };
    $("#nc-next", m.el).onclick = async () => {
      const d = formData(form);
      if (step === 2) {
        if (!d.title) return toast("Bitte einen Falltitel angeben.", "err");
        if ((d.purpose || "").length < 10) return toast("Bitte den Zweck nachvollziehbar beschreiben (mind. 10 Zeichen).", "err");
        const mq = mqEval();
        if (mq.missing) return toast("Bitte alle Fragen der Auftragsprüfung beantworten.", "err");
        if (mq.warnings.length && !mq.lead) return toast("Auftragsprüfung: Warnsignale – nur die Teamleitung darf diesen Auftrag annehmen.", "err");
        if (mq.warnings.length && (d.mandate_reason || "").trim().length < 30) return toast("Bitte die Annahme trotz Warnsignalen ausführlich begründen (mind. 30 Zeichen).", "err");
      }
      if (step < 3) { step++; show(); return; }
      const legal = d.legal_basis_sel.startsWith("Sonstige") ? d.legal_basis_other : d.legal_basis_sel;
      const idents = [["location", d.s_loc], ["username", d.s_user], ["email", d.s_email], ["phone", d.s_phone], ["employer", d.s_emp]]
        .filter((x) => x[1]).map(([kind, value]) => ({ kind, value }));
      const payload = { case_type: d.case_type, title: d.title, purpose: d.purpose, legal_basis: legal, client: d.client,
        due_date: d.due_date, priority: d.priority, restricted: form.restricted.checked || d.opsec_level === "3",
        opsec_level: Number(d.opsec_level), egress_profile: d.egress_profile,
        mandate_check: (state.meta.mandate_questions || []).length ? { answers: mqEval().answers, override_reason: d.mandate_reason || "" } : null,
        subject: d.s_name ? { label: d.s_name, data: { geburtsdatum: d.s_birth, wohnort: d.s_loc, vermisst_status: d.case_type === "vermisst" ? "vermisst" : "" }, identifiers: idents } : null };
      const c = await guard(() => api("POST", "/api/cases", payload), "Fall angelegt");
      if (d.reviewer_id) await guard(() => api("PATCH", `/api/cases/${c.id}`, { reviewer_id: Number(d.reviewer_id) }));
      m.close();
      await loadCases();
      location.hash = `#/case/${c.id}/${d.s_name ? "overview" : "persons"}`;
    };
  }

  // ------------------------------------------------------------------ Fallansicht
  const TABS = [
    ["overview", "Übersicht"], ["persons", "Personen & Profile"], ["search", "Suche & Treffer"], ["graph", "Verbindungen"], ["facts", "📊 Fakten & Bewertung"],
    ["timeline", "Zeitleiste & Karte"], ["tasks", "Aufgaben"], ["dossier", "Dossier & Export"], ["opsec", "🛡 OPSEC"], ["audit", "Protokoll"],
  ];

  async function renderCase() {
    const ov = await api("GET", `/api/cases/${state.caseId}/overview`);
    state.ov = ov;
    const c = ov.case;
    $("#main").innerHTML = `
      <div class="case-header">
        <div><div class="ref">${esc(c.reference)} · <span class="badge ${typeBadge(c.case_type)}">${esc(c.case_type_label)}</span></div>
          ${c.codename && c.opsec_level >= 2 ? `<h1>${esc(c.codename)} <span class="small muted veil" style="font-weight:400" title="Klartitel – zum Anzeigen klicken" tabindex="0">${esc(c.title)}</span></h1>` : `<h1>${esc(c.title)}</h1>`}</div>
        <div class="actions">
          <a href="#/case/${c.id}/opsec" style="text-decoration:none">${opsecBadge(c.opsec_level)}</a>
          ${c.restricted ? '<span class="badge b-grey" title="Nur das Fallteam sieht diesen Fall">🔒 vertraulich</span>' : ""}
          ${c.retention_until ? `<span class="badge ${c.retention_until <= new Date().toISOString().slice(0, 10) ? "b-red" : "b-grey"}" title="Löschfrist laut Löschkonzept – danach Fall löschen oder Verlängerung begründen">🗑 Löschfrist ${esc(fmtDate(c.retention_until))}</span>` : ""}
          <select id="case-status" aria-label="Fallstatus" style="width:auto" ${ov.permissions.includes("write") || ov.permissions.includes("review") ? "" : "disabled"}>${state.meta.case_statuses.map((s) => opt(s, "Status: " + s, c.status)).join("")}</select>
          <button class="btn ${ov.permissions.includes("manage") ? "" : "hidden"}" id="case-edit">✎ Fall & Team</button>
          <a class="btn btn-primary" href="#/case/${c.id}/dossier">⬇ Dossier</a>
        </div>
      </div>
      <nav class="tabs" role="tablist">${TABS.filter((t) => t[0] !== "timeline" || true).map(([k, l]) => `<a role="tab" class="tab ${state.tab === k ? "active" : ""}" href="#/case/${c.id}/${k}">${l}${k === "search" && ov.counts.open_findings ? `<span class="count">${ov.counts.open_findings}</span>` : ""}</a>`).join("")}</nav>
      <div id="presence"></div>
      ${ov.permissions.includes("write") ? "" : `<div class="readonly-note">👁 Sie haben für diesen Fall ${ov.permissions.includes("review") ? "Prüf- und Leserechte" : "nur Leserechte"}.</div>`}
      <section id="tab"></section>`;
    document.body.classList.toggle("readonly", !ov.permissions.includes("write"));
    $("#case-status").onchange = async (e) => {
      try { await guard(() => api("PATCH", `/api/cases/${c.id}`, { status: e.target.value }), "Status gespeichert"); } catch (_) { /* Meldung bereits angezeigt */ }
      loadCases(); renderCase();
    };
    startPresence(c.id);
    $$(".veil").forEach((v) => (v.onclick = () => v.classList.toggle("open")));
    $("#case-edit").onclick = () => editCase(c);
    document.title = "EagleEye";  // Browsertitel verrät nie Fall- oder Personennamen
    const r = { overview: tabOverview, persons: tabPersons, search: tabSearch, graph: tabGraph, facts: tabFacts, timeline: tabTimeline, tasks: tabTasks, dossier: tabDossier, opsec: tabOpsec, audit: tabAudit }[state.tab] || tabOverview;
    await r($("#tab"), ov);
    markWrite();
  }

  /* Schreibende Bedienelemente markieren, damit sie bei Leserechten ausgeblendet werden (Server prüft zusätzlich). */
  function markWrite() {
    ["#ent-new", "#ed-del", "#add-ident", "#ed-form button", "#ed-photo", "label:has(#ed-photo)", "[data-del-ident]", "#s-run", "#f-manual", "#f-bulk",
     "#l-form", "#l-newent", "[data-sugg]", "[data-del-link]", "#ev-new", "[data-del-ev]", "#t-gen", "#t-form", "[data-del-task]", "#sel-link"]
      .forEach((sel) => { try { $$(sel, $("#main")).forEach((x) => x.classList.add("w")); } catch (_) { /* Selektor nicht unterstützt */ } });
    if (state.ov && !state.ov.permissions.includes("review")) $$("[data-review], .finding .actions input", $("#main")).forEach((x) => x.classList.add("w"));
    if (state.ov && !state.ov.permissions.includes("write")) $$("[data-task], #ed-form input, #ed-form textarea, #ed-form select", $("#main")).forEach((x) => (x.disabled = true));
  }

  function stopPresence() { if (state.presenceTimer) { clearInterval(state.presenceTimer); state.presenceTimer = null; } }
  function startPresence(cid) {
    stopPresence();
    const beat = async () => {
      if (document.hidden || state.caseId !== cid) return;
      try {
        const r = await api("POST", `/api/cases/${cid}/presence`, { tab: state.tab });
        const box = $("#presence");
        if (box) box.innerHTML = r.others.length ? `<div class="presence">👥 Gerade ebenfalls im Fall: ${r.others.map((o) => `<b>${esc(o.name)}</b> (${esc((TABS.find((t) => t[0] === o.tab) || [0, o.tab])[1])})`).join(", ")} – Änderungen können sich überschneiden.</div>` : "";
        if (state.ov && r.version !== state.ov.case.version && box) box.innerHTML += `<div class="presence">↻ Der Fall wurde inzwischen geändert. <a href="#" id="pr-reload">Neu laden</a></div>`;
        const rl = $("#pr-reload"); if (rl) rl.onclick = (e) => { e.preventDefault(); renderCase(); };
      } catch (_) { /* still */ }
    };
    beat();
    state.presenceTimer = setInterval(beat, 30000);
  }

  async function editCase(c) {
    try { state.users = await api("GET", "/api/users"); } catch (_) { /* vorhandene Liste nutzen */ }
    const ov = state.ov, team = ov.team, users = state.users;
    const canDelete = ov.permissions.includes("delete");
    const userOpts = (sel, filter = () => true) => opt("", "– niemand –") + users.filter(filter).map((u) => opt(u.id, `${u.display_name} (${u.role_label})`, sel)).join("");
    const memberRow = (m) => `<div class="team-row" data-uid="${m.user_id}"><span class="grow">${esc(m.display_name)}</span>
      <select data-mrole style="width:auto">${Object.entries(state.meta.member_roles).map(([k, l]) => opt(k, l, m.role)).join("")}</select>
      <button type="button" class="btn btn-sm btn-danger" data-mdel>×</button></div>`;
    const m = modal("Fall & Team bearbeiten", `<form id="ec">
      <h3>Stammdaten</h3>
      <label class="field"><span>Titel</span><input name="title" value="${esc(c.title)}"></label>
      <label class="field"><span>Zweck</span><textarea name="purpose">${esc(c.purpose)}</textarea></label>
      <label class="field"><span>Rechtsgrundlage / Auftrag</span><input name="legal_basis" value="${esc(c.legal_basis)}"></label>
      <label class="field"><span>Auftraggeber / Redaktion</span><input name="client" value="${esc(c.client)}"></label>
      <label class="field"><span>Notizen</span><textarea name="notes">${esc(c.notes)}</textarea></label>
      <h3>Team & Prüfung</h3>
      <div class="grid g2">
        <label class="field"><span>Verantwortlich (Bearbeitung)</span><select name="owner_id">${userOpts(c.owner_id, (u) => u.role !== "leser" && u.role !== "pruefer")}</select></label>
        <label class="field"><span>Prüfperson (Vier-Augen)</span><select name="reviewer_id">${userOpts(c.reviewer_id, (u) => u.role !== "leser")}</select></label>
        <label class="field"><span>Fällig am</span><input type="date" name="due_date" value="${esc(c.due_date)}"></label>
        <label class="field"><span>Priorität</span><select name="priority">${["niedrig", "normal", "hoch", "dringend"].map((x) => opt(x, x, c.priority)).join("")}</select></label>
        <label class="field"><span>🗑 Löschfrist</span><input type="date" name="retention_until" value="${esc(c.retention_until || "")}"><small>Wird beim Abschluss automatisch gesetzt (Standard der Organisation). Verlängerung bitte in den Notizen begründen.</small></label>
      </div>
      <label class="check"><input type="checkbox" name="restricted" ${c.restricted ? "checked" : ""}> <span><b>🔒 Vertraulich (Quellenschutz)</b> – nur das Fallteam hat Zugriff, auch nicht Teamleitung/Administration.</span></label>
      <h4 style="margin:.8rem 0 .3rem">Weitere Teammitglieder</h4>
      <div id="members">${team.members.map(memberRow).join("") || '<div class="small muted" id="no-members">Keine.</div>'}</div>
      <div class="row" style="margin-top:.4rem"><select id="m-add" class="grow">${opt("", "Person hinzufügen …")}${users.filter((u) => u.id !== c.owner_id && u.id !== c.reviewer_id && !team.members.some((x) => x.user_id === u.id)).map((u) => opt(u.id, `${u.display_name} (${u.role_label})`)).join("")}</select></div>
      </form>`,
      `${canDelete ? '<button class="btn btn-danger" id="ec-del" style="margin-right:auto">Fall löschen</button>' : ""}<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="ec-save">Speichern</button>`, { width: "720px" });
    const wire = () => $$("[data-mdel]", m.el).forEach((b) => (b.onclick = () => b.closest(".team-row").remove()));
    wire();
    $("#m-add", m.el).onchange = (e) => {
      const u = users.find((x) => String(x.id) === e.target.value);
      if (!u) return;
      const nm = $("#no-members", m.el); if (nm) nm.remove();
      $("#members", m.el).insertAdjacentHTML("beforeend", memberRow({ user_id: u.id, display_name: u.display_name, role: u.role === "leser" ? "leser" : "bearbeiter" }));
      e.target.querySelector(`option[value="${u.id}"]`).remove(); e.target.value = ""; wire();
    };
    $("#ec-save", m.el).onclick = async () => {
      const f = $("#ec", m.el), d = formData(f);
      const payload = { title: d.title, purpose: d.purpose, legal_basis: d.legal_basis, client: d.client, notes: d.notes, due_date: d.due_date, priority: d.priority, retention_until: d.retention_until || "",
        owner_id: d.owner_id ? Number(d.owner_id) : 0, reviewer_id: d.reviewer_id ? Number(d.reviewer_id) : 0, restricted: f.restricted.checked, version: c.version };
      if (payload.restricted && !c.restricted && !(await confirmDlg("Fall als vertraulich markieren? Teamleitung und Administration verlieren dann den Zugriff (Notfallzugriff nur mit protokollierter Begründung).", "Vertraulich machen"))) return;
      try {
        await guard(() => api("PATCH", `/api/cases/${c.id}`, payload));
        const members = $$(".team-row", m.el).map((r) => ({ user_id: Number(r.dataset.uid), role: $("[data-mrole]", r).value }));
        await guard(() => api("PUT", `/api/cases/${c.id}/members`, { members }), "Gespeichert");
      } catch (e) { if (e.status === 409) { m.close(); renderCase(); } return; }
      m.close(); loadCases();
      try { await renderCase(); } catch (_) { location.hash = "#/"; }
    };
    const del = $("#ec-del", m.el);
    if (del) del.onclick = async () => {
      if (!(await confirmDlg(`Fall „${c.title}“ mit allen Personen, Treffern und Fotos endgültig löschen? Protokolltexte werden geschwärzt.`))) return;
      await guard(() => api("DELETE", `/api/cases/${c.id}`), "Fall gelöscht");
      m.close(); await loadCases(); location.hash = "#/";
    };
  }

  async function setStatus(cid, status, msg) {
    try { await guard(() => api("PATCH", `/api/cases/${cid}`, { status }), msg); } catch (_) { return; }
    loadCases(); renderCase();
  }

  // ------------------------------------------------------------------ Tab: Übersicht
  async function tabOverview(el, ov) {
    const s = ov.subject, c = ov.counts, missing = ov.case.case_type === "vermisst";
    const d = s ? s.data || {} : {};
    const photo = s && s.photo ? `style="background-image:url('/api/cases/${ov.case.id}/entities/${s.id}/photo?${encodeURIComponent(s.photo)}')"` : "";
    el.innerHTML = `
      ${ov.next_step ? `<div class="next-step"><div><div class="small muted">Nächster Schritt</div><b>${esc(ov.next_step.label)}</b></div>
        <a class="btn btn-success" style="margin-left:auto" href="#/case/${ov.case.id}/${ov.next_step.tab}">Jetzt erledigen →</a></div>` :
        `<div class="next-step"><b>✓ Alle Schritte erledigt.</b> Sie können das Dossier jederzeit erneut exportieren.</div>`}
      <div class="grid g4" style="margin:1rem 0">
        <div class="kpi"><div class="v">${c.persons}</div><div class="k">Personen</div></div>
        <div class="kpi"><div class="v" style="color:${c.open_findings ? "var(--amber)" : "inherit"}">${c.open_findings}</div><div class="k">ungeprüfte Treffer</div></div>
        <div class="kpi"><div class="v" style="color:var(--green)">${c.confirmed}</div><div class="k">bestätigte Erkenntnisse</div></div>
        <div class="kpi"><div class="v">${c.links}</div><div class="k">Verbindungen</div></div>
      </div>
      <div class="grid g2">
        <div>
          <div class="card">
            <div class="card-head"><h2>${missing ? "Vermisste Person" : "Zielperson"}</h2><div class="right">${s ? `<a class="btn btn-sm" href="#/case/${ov.case.id}/persons" data-ent="${s.id}">Profil bearbeiten</a>` : ""}</div></div>
            ${s ? `<div class="profile-card"><div class="avatar" ${photo}>${photo ? "" : "👤"}</div><div>
              <h2 style="margin:0">${esc(s.label)}</h2>
              <div class="muted small">${[s.risk && s.risk.age != null ? s.risk.age + " Jahre" : "", d.wohnort, d.beruf].filter(Boolean).map(esc).join(" · ")}</div>
              <div style="margin-top:.4rem">${s.identifiers.filter((i) => i.kind !== "name").slice(0, 8).map((i) => `<span class="ident-chip"><b>${esc(state.meta.identifier_kinds[i.kind])}</b>${esc(i.value)}</span>`).join("")}</div>
              ${missing ? `<div class="small"><b>Vermisst seit:</b> ${esc(d.vermisst_seit || "–")} · <b>Zuletzt gesehen:</b> ${esc([d.zuletzt_gesehen_zeit, d.zuletzt_gesehen_ort].filter(Boolean).join(", ") || "–")}</div>` : ""}
            </div></div>
            ${missing && s.risk ? `<div class="risk risk-${esc(s.risk.level)}"><b>Gefährdung: ${esc(s.risk.level.toUpperCase())}</b> – ${esc(s.risk.advice)}${s.risk.factors.length ? `<div class="small">${s.risk.factors.map((f) => esc(f.label)).join(" · ")}</div>` : ""}</div>` : ""}`
            : `<div class="empty"><div class="big">👤</div>Noch keine Zielperson erfasst.<br><br><a class="btn btn-primary" href="#/case/${ov.case.id}/persons">Person erfassen</a></div>`}
          </div>
          ${teamCard(ov)}
          <div class="card"><h3>Auftrag</h3>
            <div class="small"><b>Zweck:</b> ${esc(ov.case.purpose)}</div>
            <div class="small"><b>Rechtsgrundlage:</b> ${esc(ov.case.legal_basis)}</div>
            ${ov.case.client ? `<div class="small"><b>Auftraggeber:</b> ${esc(ov.case.client)}</div>` : ""}
            ${ov.case.notes ? `<div class="small muted" style="margin-top:.4rem">${esc(ov.case.notes)}</div>` : ""}
          </div>
        </div>
        <div>
          <div class="card">
            <div class="card-head"><h2>Fortschritt</h2><span class="right muted">${ov.progress} %</span></div>
            <div class="progress"><div style="width:${ov.progress}%"></div></div>
            <ul class="checklist">${ov.steps.map((st) => `<li class="${st.done ? "done" : ""}" data-tab="${st.tab}"><span class="dot">${st.done ? "✓" : ""}</span><span class="l">${esc(st.label)}</span></li>`).join("")}</ul>
          </div>
          <div class="card"><h3>Letzte Aktivitäten</h3>
            <ul class="activity" style="padding-left:1rem">${ov.recent.map((a) => `<li><span class="muted">${fmtTs(a.ts)}</span> · <b>${esc(a.action)}</b> <span class="muted">${esc(a.detail.slice(0, 90))}</span></li>`).join("") || "<li class='muted'>–</li>"}</ul>
            <a class="small" href="#/case/${ov.case.id}/audit">Ganzes Protokoll →</a>
          </div>
        </div>
      </div>`;
    $$(".checklist li", el).forEach((li) => li.onclick = () => { location.hash = `#/case/${ov.case.id}/${li.dataset.tab}`; });
    $$("[data-status]", el).forEach((b) => (b.onclick = () => setStatus(ov.case.id, b.dataset.status, b.dataset.msg)));
    const te = $("#team-edit", el); if (te) te.onclick = () => editCase(ov.case);
    $$("[data-ent]", el).forEach((a) => a.addEventListener("click", () => { state.selEntity = Number(a.dataset.ent); }));
  }

  function teamCard(ov) {
    const c = ov.case, t = ov.team, me = state.auth.user, perms = ov.permissions;
    const isOwner = c.owner_id === me.id;
    const btns = [];
    if (["offen", "in Bearbeitung"].includes(c.status) && perms.includes("write")) btns.push(`<button class="btn btn-sm btn-primary" data-status="zur Prüfung" data-msg="Zur Prüfung übergeben">➜ Zur Prüfung übergeben</button>`);
    if (c.status === "offen" && perms.includes("write")) btns.push(`<button class="btn btn-sm" data-status="in Bearbeitung" data-msg="Status: in Bearbeitung">In Bearbeitung</button>`);
    if (c.status === "zur Prüfung" && perms.includes("review") && !isOwner) {
      btns.push(`<button class="btn btn-sm btn-success" data-status="freigegeben" data-msg="Freigegeben">✓ Freigeben</button>`);
      btns.push(`<button class="btn btn-sm" data-status="in Bearbeitung" data-msg="Zurück an die Bearbeitung">↩ Zurück an Bearbeitung</button>`);
    }
    if (c.status === "freigegeben" && perms.includes("write")) btns.push(`<button class="btn btn-sm" data-status="abgeschlossen" data-msg="Abgeschlossen">Abschließen</button>`);
    const hint = c.status === "zur Prüfung" && isOwner ? "Wartet auf Freigabe durch " + esc(t.reviewer ? t.reviewer.display_name : "die Prüfperson") + "." :
      c.status === "freigegeben" ? "Im Vier-Augen-Verfahren freigegeben – das Dossier trägt keinen Entwurfsvermerk mehr." : "";
    return `<div class="card"><div class="card-head"><h3>👥 Team & Prüfung</h3><div class="right">${perms.includes("manage") ? '<button class="btn btn-sm" id="team-edit">Bearbeiten</button>' : ""}</div></div>
      <table class="tbl"><tr><td>Status</td><td><b>${esc(c.status)}</b></td></tr>
      <tr><td>Verantwortlich</td><td>${t.owner ? esc(t.owner.display_name) : '<span class="muted">nicht zugewiesen</span>'}</td></tr>
      <tr><td>Prüfung (Vier-Augen)</td><td>${t.reviewer ? esc(t.reviewer.display_name) : '<span class="muted">nicht zugewiesen</span>'}</td></tr>
      ${t.members.length ? `<tr><td>Weitere</td><td>${t.members.map((m) => `${esc(m.display_name)} <span class="muted small">(${esc(state.meta.member_roles[m.role])})</span>`).join(", ")}</td></tr>` : ""}
      <tr><td>Fällig</td><td>${c.due_date ? esc(new Date(c.due_date).toLocaleDateString("de-DE")) : "–"} · Priorität ${esc(c.priority)}</td></tr>
      <tr><td>Vertraulich</td><td>${c.restricted ? "🔒 ja – nur Fallteam" : "nein"}</td></tr>
      <tr><td>OPSEC</td><td>${opsecBadge(c.opsec_level)} <a class="small" href="#/case/${c.id}/opsec">Regeln & Spuren →</a></td></tr></table>
      ${hint ? `<div class="small muted" style="margin-top:.4rem">${hint}</div>` : ""}
      ${btns.length ? `<div class="workflow">${btns.join("")}</div>` : ""}</div>`;
  }

  // ------------------------------------------------------------------ Tab: Personen
  async function tabPersons(el, ov) {
    const ents = await api("GET", `/api/cases/${ov.case.id}/entities`);
    if (state.selEntity && !ents.find((e) => e.id === state.selEntity)) state.selEntity = null;
    if (!state.selEntity && ents.length) state.selEntity = ents[0].id;
    const groups = {};
    ents.forEach((e) => (groups[e.type_label] = groups[e.type_label] || []).push(e));
    el.innerHTML = `
      ${help("So erfassen Sie Personen und weitere Einträge", [
        "Links wählen Sie einen Eintrag – rechts bearbeiten Sie Profil, <b>Identifikatoren</b> und Foto.",
        "Identifikatoren (Benutzernamen, E-Mail, Telefon, Orte, Aliasse) sind die Grundlage der automatischen Suche – je mehr, desto besser.",
        "Unter <b>Recherchelinks</b> finden Sie vorbereitete Suchen für Suchmaschinen, soziale Netzwerke, Register und Vermisstenportale.",
        "Organisationen, Orte, Konten, Fahrzeuge usw. legen Sie ebenfalls hier an, um sie im Graphen zu verbinden."])}
      <div class="split">
        <div class="card">
          <div class="card-head"><h3>Einträge (${ents.length})</h3><div class="right"><button class="btn btn-sm btn-primary" id="ent-new">＋ Neu</button></div></div>
          <div class="entity-list">${Object.entries(groups).map(([g, list]) => `<div class="small muted" style="margin:.5rem 0 .2rem;font-weight:600">${esc(g)}</div>` +
            list.map((e) => `<div class="entity-item ${e.id === state.selEntity ? "active" : ""}" data-id="${e.id}"><span class="type-dot" style="background:${COLORS[e.type]}"></span>
              <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${e.is_subject ? "★ " : ""}${esc(e.label)}</span>
              ${e.finding_count ? `<span class="badge b-grey" title="Treffer">${e.finding_count}</span>` : ""}</div>`).join("")).join("") || '<div class="empty small">Noch keine Einträge.</div>'}</div>
        </div>
        <div id="ent-detail"></div>
      </div>`;
    $$(".entity-item", el).forEach((it) => it.onclick = () => { state.selEntity = Number(it.dataset.id); $$(".entity-item", el).forEach((x) => x.classList.toggle("active", x === it)); renderEntityDetail(ov); });
    $("#ent-new").onclick = () => newEntity(ov);
    renderEntityDetail(ov);
  }

  function newEntity(ov, presetType = "person", after) {
    const m = modal("Neuen Eintrag anlegen", `<form id="ne">
      <label class="field"><span>Typ</span><select name="type">${Object.entries(state.meta.entity_types).map(([k, v]) => opt(k, v, presetType)).join("")}</select></label>
      <label class="field"><span>Name / Bezeichnung *</span><input name="label" required></label>
      <label class="check"><input type="checkbox" name="is_subject"> <span>Ist Zielperson dieses Falls</span></label>
      <label class="field"><span>Notiz</span><textarea name="notizen" placeholder="z. B. Rolle im Fall, Herkunft der Information"></textarea></label></form>`,
      `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="ne-save">Anlegen</button>`);
    const f = $("#ne", m.el);
    const sync = () => { f.is_subject.closest("label").classList.toggle("hidden", f.type.value !== "person"); };
    f.type.onchange = sync; sync();
    $("#ne-save", m.el).onclick = async () => {
      const d = formData(f);
      const e = await guard(() => api("POST", `/api/cases/${ov.case.id}/entities`, { type: d.type, label: d.label, is_subject: !!f.is_subject.checked && d.type === "person", data: { notizen: d.notizen } }), "Eintrag angelegt");
      m.close();
      if (after) return after(e);
      state.selEntity = e.id; renderCase();
    };
  }

  async function renderEntityDetail(ov) {
    const box = $("#ent-detail");
    if (!state.selEntity) { box.innerHTML = `<div class="card empty"><div class="big">👤</div>Legen Sie links mit „＋ Neu“ die erste Person an.</div>`; return; }
    const e = await api("GET", `/api/cases/${ov.case.id}/entities/${state.selEntity}`);
    const isPerson = e.type === "person";
    const missing = ov.case.case_type === "vermisst" && isPerson && e.is_subject;
    const d = e.data || {};
    const field = ([k, l]) => {
      const long = ["merkmale", "notizen", "umstaende", "gesundheit", "kleidung", "mitgefuehrt", "anlaufpunkte"].includes(k);
      const type = k === "geburtsdatum" || k === "vermisst_seit" ? "date" : "text";
      if (k === "vermisst_status") return `<label class="field"><span>${l}</span><select name="${k}">${["", "vermisst", "aufgefunden (wohlbehalten)", "aufgefunden (verletzt)", "verstorben aufgefunden", "Kontakt hergestellt", "Fall eingestellt"].map((s) => opt(s, s || "–", d[k])).join("")}</select></label>`;
      return `<label class="field" ${long ? 'style="grid-column:1/-1"' : ""}><span>${l}</span>${long ? `<textarea name="${k}">${esc(d[k] || "")}</textarea>` : `<input type="${type}" name="${k}" value="${esc(d[k] || "")}">`}</label>`;
    };
    const photoUrl = e.photo ? `/api/cases/${ov.case.id}/entities/${e.id}/photo?${encodeURIComponent(e.photo)}` : "";
    box.innerHTML = `
      <div class="card">
        <div class="card-head">
          <span class="type-dot" style="background:${COLORS[e.type]}"></span><h2>${esc(e.label)}</h2><span class="badge">${esc(e.type_label)}</span>${e.is_subject ? '<span class="badge b-amber">★ Zielperson</span>' : ""}
          <div class="right">
            ${isPerson ? `<button class="btn btn-sm btn-primary" id="ed-search">🔎 Quellen durchsuchen</button>` : ""}
            <button class="btn btn-sm" id="ed-graph">🕸️ Im Graphen</button>
            <button class="btn btn-sm btn-danger" id="ed-del">Löschen</button>
          </div>
        </div>
        ${isPerson ? `<div class="profile-card" style="margin-bottom:.8rem">
          <div class="avatar" ${photoUrl ? `style="background-image:url('${photoUrl}')"` : ""}>${photoUrl ? "" : "👤"}</div>
          <div class="small muted">Foto für Profil, Dossier und Suchplakat (JPG/PNG/WEBP, max. 8 MB). Für die Bilder-Rückwärtssuche nutzen Sie die Links unten.<br>
          <label class="btn btn-sm" style="margin-top:.4rem">📷 Foto hochladen<input type="file" id="ed-photo" accept="image/jpeg,image/png,image/webp" hidden></label></div></div>` : ""}
        <h3>Identifikatoren</h3>
        <div id="idents">${e.identifiers.map((i) => `<span class="ident-chip" title="Quelle: ${esc(i.source)}${i.verified ? " · geprüft" : ""}"><b>${esc(state.meta.identifier_kinds[i.kind] || i.kind)}</b>${esc(i.value)}${i.verified ? " ✓" : ""}<button data-del-ident="${i.id}" aria-label="Entfernen">×</button></span>`).join("") || '<span class="muted small">Noch keine.</span>'}</div>
        <form class="row" id="add-ident" style="margin-top:.4rem">
          <select name="kind" style="width:auto">${Object.entries(state.meta.identifier_kinds).map(([k, v]) => opt(k, v, "username")).join("")}</select>
          <input name="value" class="grow" placeholder="Wert eingeben, z. B. max_muster, max@example.org, +49 170 …" required>
          <button class="btn btn-primary">Hinzufügen</button>
        </form>
      </div>
      <div class="card">
        <form id="ed-form">
          <div class="card-head"><h3>${isPerson ? "Profil" : "Angaben"}</h3><div class="right"><button class="btn btn-sm btn-primary">💾 Speichern</button></div></div>
          <label class="field"><span>Name / Bezeichnung</span><input name="__label" value="${esc(e.label)}"></label>
          ${isPerson ? `<label class="check"><input type="checkbox" name="__subject" ${e.is_subject ? "checked" : ""}> <span>Zielperson dieses Falls</span></label>
            <div class="grid g2">${state.meta.person_fields.map(field).join("")}</div>`
            : `<label class="field"><span>Webadresse</span><input name="url" value="${esc(d.url || "")}"></label>
               ${e.type === "ort" ? `<div class="grid g2"><label class="field"><span>Breitengrad</span><input name="lat" value="${esc(d.lat ?? "")}"></label><label class="field"><span>Längengrad</span><input name="lon" value="${esc(d.lon ?? "")}"></label></div>` : ""}
               <label class="field"><span>Notizen</span><textarea name="notizen">${esc(d.notizen || "")}</textarea></label>`}
          ${missing ? `<h3 style="margin-top:.5rem">🆘 Vermisstenangaben</h3><div class="grid g2">${state.meta.missing_fields.map(field).join("")}</div>
            <h3>Gefährdungsfaktoren</h3><p class="small muted">Alter wird automatisch aus dem Geburtsdatum berücksichtigt.</p>
            <div class="risk-grid">${Object.entries(state.meta.risk_factors).map(([k, l]) => `<label class="check"><input type="checkbox" name="risk_${k}" ${(d.risiko || []).includes(k) ? "checked" : ""}> <span>${esc(l)}</span></label>`).join("")}</div>
            ${e.risk ? `<div class="risk risk-${esc(e.risk.level)}"><b>Einschätzung: ${esc(e.risk.level.toUpperCase())}</b> (${e.risk.points} Punkte) – ${esc(e.risk.advice)}</div>` : ""}` : ""}
        </form>
      </div>
      ${isPerson ? `<div class="card"><div class="card-head"><h3>🔗 Recherchelinks</h3><span class="muted small">Vorbereitete manuelle Suchen – öffnen in neuem Tab, werden nicht automatisch abgerufen.</span></div><div id="rlinks" class="link-groups"><span class="spinner dark"></span></div></div>` : ""}`;

    $("#add-ident").onsubmit = async (ev) => {
      ev.preventDefault();
      await guard(() => api("POST", `/api/cases/${ov.case.id}/entities/${e.id}/identifiers`, formData(ev.target)), "Identifikator gespeichert");
      renderEntityDetail(ov);
    };
    $$("[data-del-ident]", box).forEach((b) => b.onclick = async () => { await guard(() => api("DELETE", `/api/cases/${ov.case.id}/identifiers/${b.dataset.delIdent}`)); renderEntityDetail(ov); });
    $("#ed-form").onsubmit = async (ev) => {
      ev.preventDefault();
      const f = ev.target, raw = formData(f), data = {};
      Object.entries(raw).forEach(([k, v]) => { if (!k.startsWith("__") && !k.startsWith("risk_")) data[k] = v; });
      if (missing) data.risiko = Object.keys(state.meta.risk_factors).filter((k) => f["risk_" + k] && f["risk_" + k].checked);
      if (data.lat !== undefined) { data.lat = data.lat ? Number(String(data.lat).replace(",", ".")) : ""; data.lon = data.lon ? Number(String(data.lon).replace(",", ".")) : ""; }
      const payload = { label: raw.__label, data, version: e.version };
      if (isPerson) payload.is_subject = !!(f.__subject && f.__subject.checked);
      try { await guard(() => api("PATCH", `/api/cases/${ov.case.id}/entities/${e.id}`, payload), "Gespeichert"); }
      catch (err) { if (err.status !== 409) return; }
      renderCase();
    };
    $("#ed-del").onclick = async () => {
      if (!(await confirmDlg(`„${e.label}“ mit allen Identifikatoren, Treffern und Verbindungen löschen?`))) return;
      await guard(() => api("DELETE", `/api/cases/${ov.case.id}/entities/${e.id}`), "Gelöscht");
      state.selEntity = null; renderCase();
    };
    $("#ed-graph").onclick = () => { state.graphFocus = e.id; location.hash = `#/case/${ov.case.id}/graph`; };
    if (isPerson) {
      $("#ed-search").onclick = () => { state.searchEntity = e.id; location.hash = `#/case/${ov.case.id}/search`; };
      $("#ed-photo").onchange = async (ev) => {
        const fd = new FormData(); fd.append("file", ev.target.files[0]);
        await guard(() => api("POST", `/api/cases/${ov.case.id}/entities/${e.id}/photo`, fd), "Foto gespeichert");
        renderEntityDetail(ov);
      };
      const links = await api("GET", `/api/cases/${ov.case.id}/entities/${e.id}/research-links`);
      const g = {};
      links.forEach((l) => (g[l.group] = g[l.group] || []).push(l));
      const rl = $("#rlinks");
      if (rl) rl.innerHTML = `<div class="opsec-strip" style="column-span:all">🛡 Diese Links öffnen sich in <b>Ihrem Browser</b> – nicht über den OPSEC-Ausgang. ${ov.case.opsec_level >= 2 ? "Nur in der getrennten Recherche-Umgebung und ausgeloggt verwenden." : "Bei sensiblen Recherchen eine getrennte Recherche-Umgebung nutzen."}</div>` +
        Object.entries(g).map(([name, ls]) => `<div class="link-group"><h4>${esc(name)}</h4>${ls.map((l) => l.blocked
          ? `<span class="link-blocked" title="${esc(l.blocked)}">⛔ ${esc(l.label)} ${expoBadge(l.exposure)}</span>`
          : `<a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer" title="${esc(l.hint || l.url)}">↗ ${esc(l.label)} ${l.exposure !== "passiv" ? expoBadge(l.exposure) : ""}</a>`).join("")}</div>`).join("");
    }
  }

  // ------------------------------------------------------------------ Tab: Suche & Treffer
  async function tabSearch(el, ov) {
    const [op, sources] = await Promise.all([api("GET", `/api/cases/${ov.case.id}/opsec`), api("GET", "/api/sources")]);
    state.meta.sources = sources;
    const lvl = state.meta.opsec_levels[ov.case.opsec_level];
    const [ents, findings, searches] = await Promise.all([
      api("GET", `/api/cases/${ov.case.id}/entities`), api("GET", `/api/cases/${ov.case.id}/findings`), api("GET", `/api/cases/${ov.case.id}/searches`)]);
    const persons = ents.filter((e) => e.type === "person");
    if (!state.searchEntity || !persons.find((p) => p.id === state.searchEntity)) state.searchEntity = (ov.subject || persons[0] || {}).id;
    const person = persons.find((p) => p.id === state.searchEntity);
    const kinds = new Set((person ? person.identifiers : []).map((i) => (i.kind === "alias" ? "name" : i.kind)));
    const srcGroups = {};
    state.meta.sources.forEach((s) => (srcGroups[s.group] = srcGroups[s.group] || []).push(s));
    const counts = { neu: 0, "bestätigt": 0, verworfen: 0 };
    findings.forEach((f) => counts[f.status]++);
    el.innerHTML = `
      ${help("So funktioniert die Suche", [
        "Person wählen, Quellen anhaken und <b>Suche starten</b>. Abgefragt werden nur Quellen, für die passende Identifikatoren vorliegen.",
        "Jeder Treffer erhält einen <b>Score (0–100)</b> mit Begründung – z. B. Namensgleichheit, Ort, Arbeitgeber, exakte E-Mail.",
        "Prüfen Sie jeden Treffer: <b>✓ Bestätigen</b> übernimmt ihn als Erkenntnis und erzeugt automatisch Knoten/Verbindungen im Graphen; <b>✗ Verwerfen</b> blendet ihn aus.",
        "Eigene Funde (z. B. aus den Recherchelinks oder Gesprächen) erfassen Sie über <b>„＋ Eigene Erkenntnis“</b>.",
        "<b>🧭 Folgesuchen:</b> Aus bestätigten Treffern entstehen Vorschläge für die nächste Suche (z. B. ein neu gefundener Benutzername oder eine Domain). Gesucht wird erst, wenn Sie den Vorschlag freigeben. <b>Herkunft</b> an jedem Treffer zeigt, über welche Zwischenschritte er gefunden wurde."], !findings.length)}
      <div class="split">
        <div>
          <div class="card">
            <h3>1. Person wählen</h3>
            ${persons.length ? `<select id="s-person">${persons.map((p) => opt(p.id, (p.is_subject ? "★ " : "") + p.label, state.searchEntity)).join("")}</select>
            <div class="small muted" style="margin-top:.4rem">${person ? person.identifiers.map((i) => esc(i.value)).join(" · ") : ""}</div>
            <a class="small" href="#/case/${ov.case.id}/persons">Identifikatoren ergänzen →</a>`
            : `<div class="empty small">Bitte zuerst eine Person anlegen.<br><a class="btn btn-sm btn-primary" href="#/case/${ov.case.id}/persons">Person erfassen</a></div>`}
          </div>
          <div class="card">
            <div class="card-head"><h3>2. Quellen</h3><div class="right"><button class="btn btn-sm" id="s-all">alle</button><button class="btn btn-sm" id="s-none">keine</button></div></div>
            <div class="opsec-strip">${opsecBadge(lvl.key)} Ausgang: <b>${esc(op.profile.name)}</b>${op.briefing_done ? "" : ` · <a href="#/case/${ov.case.id}/opsec">⚠ Briefing bestätigen</a>`}
              ${op.warnings.map((w) => `<div class="small" style="color:#92400e">⚠ ${esc(w)}</div>`).join("")}</div>
            ${Object.entries(srcGroups).map(([g, list]) => `<div class="src-group"><h4>${esc(g)}</h4>${list.map((s) => {
              const expo = s.exposure || "plattform";
              const lvBlocked = state.meta.exposure[expo].rank > lvl.max_exposure;
              const hasKind = s.kinds.some((k) => kinds.has(k));
              const ok = hasKind && !lvBlocked && !s.unavailable;
              const why = lvBlocked ? `durch OPSEC-Stufe ${lvl.key} gesperrt` : s.unavailable ? s.unavailable : !hasKind ? "benötigt: " + s.kind_labels.join(" oder ") : s.description;
              return `<label class="check ${ok ? "" : "src-disabled"}" title="${esc(s.description + " · Lizenz: " + s.license)}"><input type="checkbox" name="src" value="${s.key}" ${ok ? "checked" : "disabled"}>
                <span>${esc(s.label)} ${expoBadge(expo)} ${relBadge(s.reliability)}${s.requires_key && !s.key_set && s.key_optional ? ' <span class="badge b-amber" title="ohne Schlüssel stark begrenzt">eingeschränkt</span>' : ""}<br><span class="small muted">${esc(why)}</span></span></label>`; }).join("")}</div>`).join("")}
            <button class="btn btn-primary btn-lg" id="s-run" style="width:100%;justify-content:center;margin-top:.8rem" ${person ? "" : "disabled"}>🔎 Suche starten</button>
          </div>
          <div class="card" id="s-status">${renderSearchStatus(state.lastSearch, searches)}</div>
          <div class="card" id="s-pivot"></div>
          <div class="card" id="s-watch"></div>
        </div>
        <div class="card">
          <div class="card-head"><h2>Treffer</h2>
            <div class="seg"><button class="${state.findingView !== "groups" ? "on" : ""}" data-fv="list">Liste</button><button class="${state.findingView === "groups" ? "on" : ""}" data-fv="groups" title="Treffer nach Personen bündeln (Namensvettern trennen)">👥 Kandidatengruppen</button></div>
            <div class="right ${state.findingView === "groups" ? "hidden" : ""}">
              ${[["neu", "Zu prüfen"], ["bestätigt", "Bestätigt"], ["verworfen", "Verworfen"], ["", "Alle"]].map(([k, l]) => `<button class="btn btn-sm ${state.findingFilter === k ? "btn-primary" : ""}" data-ff="${k}">${l}${k ? ` (${counts[k]})` : ""}</button>`).join("")}
              <button class="btn btn-sm" id="f-manual">＋ Eigene Erkenntnis</button>
            </div></div>
          <div id="g-list" class="${state.findingView === "groups" ? "" : "hidden"}"></div>
          <div class="row ${state.findingView === "groups" ? "hidden" : ""}" style="margin-bottom:.7rem">
            <input id="f-q" class="grow" type="search" placeholder="Treffer filtern …">
            ${state.findingFilter === "neu" && counts.neu ? `<button class="btn btn-sm" id="f-bulk" title="Alle offenen Treffer mit Score unter 20 verwerfen">Schwache (< 20) verwerfen</button>` : ""}
          </div>
          <div id="f-list" class="${state.findingView === "groups" ? "hidden" : ""}"></div>
        </div>
      </div>`;
    const sp = $("#s-person");
    if (sp) sp.onchange = () => { state.searchEntity = Number(sp.value); renderCase(); };
    $("#s-all").onclick = () => $$("input[name=src]:not(:disabled)", el).forEach((c) => (c.checked = true));
    $("#s-none").onclick = () => $$("input[name=src]", el).forEach((c) => (c.checked = false));
    $("#s-run").onclick = async (ev) => {
      const sources = $$("input[name=src]:checked", el).map((c) => c.value);
      if (!sources.length) return toast("Bitte mindestens eine Quelle wählen.", "err");
      const b = ev.currentTarget;
      b.disabled = true; b.innerHTML = '<span class="spinner"></span> Suche läuft … (bis zu 30 s)';
      try {
        state.lastSearch = await api("POST", `/api/cases/${ov.case.id}/search`, { entity_id: state.searchEntity, sources });
        toast(`${state.lastSearch.new_findings} neue Treffer`, "ok");
        state.findingFilter = "neu";
      } catch (e) { toast(e.message, "err"); if (e.status === 428) state.lastSearch = { blockedMsg: e.message }; }
      renderCase();
    };
    $$("[data-ff]", el).forEach((b) => b.onclick = () => { state.findingFilter = b.dataset.ff; renderCase(); });
    $("#f-manual").onclick = () => manualFinding(ov, persons);
    const bulk = $("#f-bulk");
    if (bulk) bulk.onclick = async () => {
      const weak = findings.filter((f) => f.status === "neu" && f.score < 20);
      if (!weak.length) return toast("Keine schwachen Treffer vorhanden.");
      if (!(await confirmDlg(`${weak.length} Treffer mit Score unter 20 verwerfen?`, "Verwerfen"))) return;
      for (const f of weak) await api("PATCH", `/api/cases/${ov.case.id}/findings/${f.id}`, { status: "verworfen", note: "Sammelprüfung: Score < 20" });
      toast(`${weak.length} Treffer verworfen`, "ok"); renderCase();
    };
    const draw = () => {
      const q = ($("#f-q").value || "").toLowerCase();
      const list = findings.filter((f) => (!state.findingFilter || f.status === state.findingFilter) && (!q || `${f.title} ${f.snippet} ${f.source}`.toLowerCase().includes(q)));
      $("#f-list").innerHTML = list.length ? list.map(findingCard).join("") :
        `<div class="empty"><div class="big">${state.findingFilter === "neu" && findings.length ? "✅" : "🔎"}</div>${state.findingFilter === "neu" && findings.length ? "Alle Treffer sind geprüft." : "Keine Treffer in dieser Ansicht."}</div>`;
      $$("[data-ev]", $("#f-list")).forEach((b) => b.onclick = async () => {
        b.disabled = true; b.innerHTML = '<span class="spinner dark"></span> sichere …';
        try { const r = await api("POST", `/api/cases/${ov.case.id}/evidence`, { finding_id: Number(b.dataset.ev) }); toast(`Beleg gesichert – SHA-256 ${r.sha256.slice(0, 12)}…`, "ok"); }
        catch (e) { toast(e.message, "err"); }
        renderCase();
      });
      if (!state.ov.permissions.includes("write")) $$("[data-ev]", $("#f-list")).forEach((x) => x.classList.add("hidden"));
      $$("[data-chain]", $("#f-list")).forEach((b) => (b.onclick = () => showChain(ov.case.id, Number(b.dataset.chain))));
      $$("[data-review]", $("#f-list")).forEach((b) => b.onclick = async () => {
        const card = b.closest(".finding");
        const note = $("input", card) ? $("input", card).value : "";
        const r = await guard(() => api("PATCH", `/api/cases/${ov.case.id}/findings/${card.dataset.id}`, { status: b.dataset.review, note }));
        toast(b.dataset.review === "bestätigt" ? "Bestätigt" + (r.created && r.created.length ? " – im Graphen: " + r.created.join(", ") : "") : b.dataset.review === "verworfen" ? "Verworfen" : "Zurückgesetzt", "ok");
        renderCase();
      });
    };
    $("#f-q").oninput = draw;
    draw();
    $$("[data-fv]", el).forEach((b) => (b.onclick = () => { state.findingView = b.dataset.fv; renderCase(); }));
    if (state.findingView === "groups" && person) renderGroups(ov, person);
    renderPivots(ov, person);
    renderWatches(ov, person);
  }

  async function renderPivots(ov, person) {
    const box = $("#s-pivot");
    if (!box) return;
    if (!person) { box.innerHTML = ""; box.classList.add("hidden"); return; }
    let pv;
    try { pv = await api("GET", `/api/cases/${ov.case.id}/entities/${person.id}/pivots`); } catch (_) { box.classList.add("hidden"); return; }
    const canWrite = ov.permissions.includes("write");
    box.classList.remove("hidden");
    box.innerHTML = `<div class="card-head"><h3>🧭 Folgesuchen (${pv.items.length})</h3></div>
      <p class="small muted" style="margin:0 0 .4rem">Neue Kennungen aus <b>bestätigten</b> Treffern. Nichts wird automatisch abgefragt – Sie geben jede Folgesuche frei. Höchstens ${pv.max_depth} Stufen vom Ausgangspunkt.</p>
      ${pv.items.map((it, i) => `<div class="pivot" data-pi="${i}">
        <div><span class="badge b-blue">${esc(it.kind_label)}</span> <b>${esc(it.value)}</b> <span class="badge b-grey" title="Entfernung vom Ausgangspunkt der Recherche">Stufe ${it.depth}</span></div>
        <div class="small muted">aus: ${esc(it.origin.label)} (${esc(it.origin.source)})</div>
        <div class="srcs">${it.sources.map((x) => `<label title="${esc(x.usable ? "liefert: " + (x.produces.join(", ") || "Treffer") : x.reason)}" class="${x.usable ? "" : "src-disabled"}"><input type="checkbox" value="${esc(x.key)}" ${x.usable ? "checked" : "disabled"}> ${esc(x.label)} ${expoBadge(x.exposure)}${x.usable ? "" : ` <span class="muted">– ${esc(x.reason)}</span>`}</label>`).join("")}</div>
        ${canWrite ? `<div class="row"><button class="btn btn-sm btn-primary" data-prun>🔎 Freigeben & suchen</button><button class="btn btn-sm" data-pdis>Verwerfen</button></div>` : ""}</div>`).join("")
        || '<div class="small muted">Keine offenen Vorschläge. Sie entstehen, sobald bestätigte Treffer neue Kennungen enthalten (Benutzername, E-Mail, Domain, Firma …).</div>'}
      ${pv.too_deep ? `<div class="small muted" style="margin-top:.4rem">${pv.too_deep} Vorschlag/Vorschläge liegen weiter als ${pv.max_depth} Stufen vom Ausgangspunkt und werden nicht angeboten. Wenn Sie dem trotzdem nachgehen wollen: Kennung von Hand bei der Person eintragen.</div>` : ""}
      ${pv.dismissed ? `<div class="small" style="margin-top:.4rem">${pv.dismissed} verworfen · ${canWrite ? '<a href="#" id="p-restore">wieder anzeigen</a>' : ""}</div>` : ""}`;
    $$(".pivot", box).forEach((row) => {
      const it = pv.items[Number(row.dataset.pi)];
      const run = $("[data-prun]", row), dis = $("[data-pdis]", row);
      if (run) run.onclick = async () => {
        const srcs = $$("input:checked", row).map((c) => c.value);
        if (!srcs.length) return toast("Bitte mindestens eine Quelle wählen.", "err");
        run.disabled = true; run.innerHTML = '<span class="spinner"></span> suche …';
        try {
          const r = await api("POST", `/api/cases/${ov.case.id}/entities/${person.id}/pivots/run`, { kind: it.kind, value: it.value, sources: srcs });
          state.lastSearch = r; state.findingFilter = "neu";
          toast(`Folgesuche: ${r.new_findings} neue Treffer`, "ok");
        } catch (e) { toast(e.message, "err"); }
        renderCase();
      };
      if (dis) dis.onclick = async () => { await guard(() => api("POST", `/api/cases/${ov.case.id}/entities/${person.id}/pivots/dismiss`, { kind: it.kind, value: it.value })); renderPivots(ov, person); };
    });
    const rs = $("#p-restore", box);
    if (rs) rs.onclick = async (e) => { e.preventDefault(); await guard(() => api("POST", `/api/cases/${ov.case.id}/entities/${person.id}/pivots/restore`)); renderPivots(ov, person); };
  }

  async function showChain(caseId, findingId) {
    const steps = await guard(() => api("GET", `/api/cases/${caseId}/findings/${findingId}/chain`));
    const label = (st) => st.type === "start" ? `★ ${esc(st.label)}` : st.type === "search" ? `🔎 Suche ${fmtTs(st.at)}${st.egress ? " · über " + esc(st.egress) : ""}${st.depth ? " · Stufe " + st.depth : ""}`
      : st.type === "finding" ? `📄 ${esc(st.label)} <span class="muted">(${esc(st.source)}, ${esc(st.status)})</span>` : st.type === "identifier" ? `🔑 ${esc(st.kind_label)}: <b>${esc(st.value)}</b>` : esc(st.label);
    modal("Herkunft des Treffers", `<p class="small muted">So wurde dieser Treffer gefunden – vom Ausgangspunkt über jede Zwischenkennung. Jede Folgesuche wurde von einer Person freigegeben und steht im Protokoll.</p>
      <div class="chain">${steps.map((st, i) => `${i ? '<span class="arrow">→</span>' : ""}<span class="step s-${esc(st.type)}">${label(st)}</span>`).join("")}</div>`,
      '<button class="btn" data-close>Schließen</button>', { width: "760px" });
  }

  async function renderWatches(ov, person) {
    const box = $("#s-watch");
    if (!box) return;
    const ws = await api("GET", `/api/cases/${ov.case.id}/watches`);
    const canWrite = ov.permissions.includes("write");
    box.innerHTML = `<div class="card-head"><h3>🔁 Überwachung</h3></div>
      <p class="small muted">Gespeicherte Suchen laufen regelmäßig im Hintergrund – nach den OPSEC-Regeln des Falls. Bei neuen Treffern erhält das Fallteam eine Benachrichtigung (🔔).</p>
      ${ws.map((w) => `<div class="watch ${w.active ? "" : "off"}"><div class="row"><b class="grow">${esc(w.entity_label)}</b><span class="badge ${w.active ? "b-green" : "b-grey"}">${w.active ? esc(w.interval_label) : "pausiert"}</span></div>
        <div class="small muted">${w.sources.length} Quellen · angelegt von ${esc(w.created_by_name || "–")} · ${w.runs} Läufe${w.last_run ? " · zuletzt " + fmtTs(w.last_run) : ""}${w.active ? " · nächster " + fmtTs(w.next_run) : ""}</div>
        ${w.last_result ? `<div class="small ${w.last_result.startsWith("Blockiert") ? "bad-text" : ""}">${esc(w.last_result)}</div>` : ""}
        ${canWrite ? `<div class="row" style="margin-top:.3rem"><button class="btn btn-sm" data-wrun="${w.id}">▶ Jetzt prüfen</button><button class="btn btn-sm" data-wtog="${w.id}:${w.active ? 0 : 1}">${w.active ? "⏸ Pausieren" : "▶ Fortsetzen"}</button><button class="btn btn-sm btn-danger" data-wdel="${w.id}">×</button></div>` : ""}</div>`).join("") || '<div class="small muted">Noch keine Überwachung.</div>'}
      ${canWrite && person ? `<div class="row" style="margin-top:.6rem"><select id="w-int" style="width:auto">${[[6, "alle 6 Stunden"], [12, "alle 12 Stunden"], [24, "täglich"], [72, "alle 3 Tage"], [168, "wöchentlich"]].map(([k, l]) => opt(k, l, 24)).join("")}</select>
        <button class="btn btn-sm btn-primary" id="w-new" title="Die oben gewählten Quellen für ${esc(person.label)} regelmäßig abfragen">＋ Auswahl überwachen</button></div>` : ""}`;
    const wn = $("#w-new", box);
    if (wn) wn.onclick = async () => {
      const sources = $$("input[name=src]:checked").map((c) => c.value);
      if (!sources.length) return toast("Bitte oben Quellen auswählen.", "err");
      await guard(() => api("POST", `/api/cases/${ov.case.id}/watches`, { entity_id: person.id, sources, interval_hours: Number($("#w-int", box).value) }), "Überwachung angelegt");
      renderWatches(ov, person);
    };
    $$("[data-wrun]", box).forEach((b) => (b.onclick = async () => {
      b.disabled = true; b.innerHTML = '<span class="spinner dark"></span>';
      const r = await guard(() => api("POST", `/api/cases/${ov.case.id}/watches/${b.dataset.wrun}/run`));
      toast(r.message, r.ok ? "ok" : "err"); renderCase(); renderBell();
    }));
    $$("[data-wtog]", box).forEach((b) => (b.onclick = async () => { const [id, on] = b.dataset.wtog.split(":"); await guard(() => api("PATCH", `/api/cases/${ov.case.id}/watches/${id}`, { active: on === "1" })); renderWatches(ov, person); }));
    $$("[data-wdel]", box).forEach((b) => (b.onclick = async () => { if (await confirmDlg("Überwachung löschen?")) { await guard(() => api("DELETE", `/api/cases/${ov.case.id}/watches/${b.dataset.wdel}`)); renderWatches(ov, person); } }));
  }

  async function renderGroups(ov, person) {
    const box = $("#g-list");
    box.innerHTML = '<span class="spinner dark"></span> Bündele Treffer …';
    const groups = await api("GET", `/api/cases/${ov.case.id}/candidates?entity_id=${person.id}`);
    if (!groups.length) { box.innerHTML = '<div class="empty"><div class="big">✅</div>Keine offenen Treffer zu prüfen.</div>'; return; }
    box.innerHTML = `<p class="small muted">Offene Treffer werden nach Merkmalen (Geburtsdatum, Organisationen, Benutzernamen, Orte) zu möglichen Personen gebündelt.
      Unterschiedliche Geburtsdaten trennen Gruppen immer. Bestätigen Sie die richtige Gruppe als Ganzes – Namensvettern verwerfen Sie mit einem Klick.</p>` +
      groups.map((g, i) => `<div class="group-card ${g.kind}" data-g="${i}">
        <div class="ft"><div class="score"><div class="num" style="color:${scoreColor(g.score)}">${g.score}</div><div class="bar"><div style="width:${g.score}%;background:${scoreColor(g.score)}"></div></div><div class="small muted">Passung</div></div>
        <div style="flex:1;min-width:0"><div class="title">${esc(g.label)} <span class="badge b-grey">${g.count} Treffer</span> ${g.sources.map((x) => `<span class="badge b-blue">${esc(x)}</span>`).join(" ")}</div>
          <div class="chips">${g.names.length ? `<span>👤 ${g.names.map(esc).join(" · ")}</span>` : ""}${g.births.length ? `<span>🎂 ${g.births.map(esc).join(", ")}</span>` : ""}
            ${g.orgs.length ? `<span>🏢 ${g.orgs.map(esc).join(", ")}</span>` : ""}${g.locations.length ? `<span>📍 ${g.locations.map(esc).join(", ")}</span>` : ""}${g.usernames.length ? `<span>@ ${g.usernames.map(esc).join(", ")}</span>` : ""}</div>
          <ul class="reasons">${g.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
          <details><summary class="small">Treffer anzeigen</summary><ul class="small">${g.members.map((m) => `<li>${m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener noreferrer">${esc(m.title)}</a>` : esc(m.title)} <span class="muted">(${esc(m.source)}, ${m.score})</span></li>`).join("")}</ul></details>
          <div class="actions w-review"><input placeholder="Prüfnotiz zur Gruppe (optional)" style="flex:1;min-width:180px;padding:.3rem .5rem;font-size:.85rem">
            <button class="btn btn-sm btn-success" data-gr="bestätigt">✓ Gruppe bestätigen</button><button class="btn btn-sm" data-gr="verworfen">✗ Gruppe verwerfen</button></div></div></div></div>`).join("");
    if (!state.ov.permissions.includes("review")) $$(".w-review", box).forEach((x) => x.classList.add("hidden"));
    $$("[data-gr]", box).forEach((b) => (b.onclick = async () => {
      const card = b.closest(".group-card"), g = groups[Number(card.dataset.g)];
      if (b.dataset.gr === "bestätigt" && g.kind === "lose" && !(await confirmDlg("Diese Treffer haben keine Unterscheidungsmerkmale. Wirklich alle bestätigen?", "Bestätigen"))) return;
      const r = await guard(() => api("POST", `/api/cases/${ov.case.id}/candidates/review`, { finding_ids: g.finding_ids, status: b.dataset.gr, note: $("input", card).value }));
      toast(`${r.count} Treffer ${b.dataset.gr}` + (r.created.length ? ` – im Graphen: ${r.created.slice(0, 5).join(", ")}${r.created.length > 5 ? " …" : ""}` : ""), "ok");
      renderCase();
    }));
  }

  function findingCard(f) {
    return `<div class="finding s-${esc(f.status)}" data-id="${f.id}">
      <div class="ft">
        <div class="score" title="Übereinstimmung: ${esc(f.confidence)}"><div class="num" style="color:${scoreColor(f.score)}">${f.score}</div><div class="bar"><div style="width:${f.score}%;background:${scoreColor(f.score)}"></div></div><div class="small muted">${esc(f.confidence)}</div></div>
        <div style="flex:1;min-width:0">
          <div class="title">${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.title)} ↗</a>` : esc(f.title)}</div>
          <div class="small muted">${esc(f.source)} · ${esc(f.category)}${f.entity_label ? " · zu " + esc(f.entity_label) : ""}${f.query ? " · Suche: „" + esc(f.query) + "“" : ""} <span class="badge ${statusBadge(f.status)}">${esc(f.status)}</span></div>
          ${f.snippet ? `<div class="snip">${esc(f.snippet)}</div>` : ""}
          <ul class="reasons">${(f.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
          ${f.facts && f.facts.length ? `<details class="facts-box"><summary>📑 ${f.facts.length} Aussage(n) aus dieser Quelle</summary><table class="tbl small">
            ${f.facts.slice(0, 40).map((x) => `<tr><td>${esc(x.subject_label)}</td><td class="muted">${esc(x.predicate_label)}</td><td><b>${esc(x.object_label)}</b>${x.data && x.data.rolle ? ` <span class="muted">(${esc(x.data.rolle)})</span>` : ""} ${period(x.valid_from, x.valid_to)}</td></tr>`).join("")}
            ${f.facts.length > 40 ? `<tr><td colspan="3" class="muted">… ${f.facts.length - 40} weitere</td></tr>` : ""}</table></details>` : ""}
          ${f.review_note ? `<div class="small" style="margin-top:.3rem"><b>Prüfnotiz:</b> ${esc(f.review_note)}</div>` : ""}
          <div class="actions">
            ${f.status === "neu" ? `<input placeholder="Prüfnotiz (optional) – z. B. Foto passt, Ort bestätigt" style="flex:1;min-width:180px;padding:.3rem .5rem;font-size:.85rem">
              <button class="btn btn-sm btn-success" data-review="bestätigt">✓ Bestätigen</button><button class="btn btn-sm" data-review="verworfen">✗ Verwerfen</button>`
              : `<button class="btn btn-sm" data-review="neu">↺ Erneut prüfen</button>`}
            ${f.url && f.url.startsWith("http") ? `<button class="btn btn-sm ev-btn" data-ev="${f.id}" title="Seite über den Fall-Netzausgang abrufen, verschlüsselt archivieren und mit SHA-256 versiegeln">📎 Beleg sichern</button>` : ""}
            ${f.evidence_count ? `<span class="badge b-green" title="gesicherte Belege">📎 ${f.evidence_count} gesichert</span>` : ""}
            ${f.search_id ? `<button class="btn btn-sm" data-chain="${f.id}" title="Über welche Zwischenschritte wurde dieser Treffer gefunden?">🧭 Herkunft</button>` : ""}
          </div>
        </div>
      </div></div>`;
  }

  function renderSearchStatus(last, searches) {
    if (last && last.blockedMsg) return `<h3>🛡 Durch OPSEC blockiert</h3><div class="bad-box small">${esc(last.blockedMsg)}</div>`;
    if (last) {
      return `<h3>Ergebnis der Suche</h3><div class="small">${last.queries} Abfragen über <b>${esc(last.egress)}</b> · <b>${last.new_findings} neue Treffer</b> (${last.total_candidates} gefunden) · <b>${last.new_facts || 0} Aussagen</b>${last.blocked ? ` · ${last.blocked} durch OPSEC gesperrt` : ""}</div>
        <ul class="source-status" style="padding-left:1rem">${last.status.map((s) => `<li>${s.ok ? "✅" : "⚠️"} <b>${esc(s.source)}</b> – „${esc(s.query)}“: ${s.ok ? s.count + " Treffer" : esc(s.message)}</li>`).join("")}</ul>
        ${last.status.some((s) => !s.ok) ? `<div class="small muted">Nicht erreichbare Quellen deuten meist auf fehlende Internetverbindung, Firewall oder Rate-Limits hin. Später erneut versuchen.</div>` : ""}`;
    }
    if (searches.length) {
      return `<h3>Bisherige Suchen</h3><ul class="source-status" style="padding-left:1rem">${searches.slice(0, 6).map((s) => {
        const sn = s.snapshot || {}, pv = s.pivot || {};
        return `<li>${fmtTs(s.started_at)} · ${esc(s.entity_label || "")}: ${s.result_count} neue Treffer${(s.source_status || []).some((x) => !x.ok) ? " ⚠️" : ""}
          ${pv.kind ? `<br><span class="small">↳ Folgesuche (Stufe ${pv.depth}): ${esc(pv.value)}</span>` : ""}
          ${sn.sources ? `<details class="small muted"><summary>Konfiguration dieses Laufs</summary>Version ${esc(sn.version)} · OPSEC ${sn.opsec_level} · Ausgang „${esc(sn.egress)}“ (${esc(sn.egress_kind)})<br>
            Quellen: ${sn.sources.map((q) => `${esc(q.label)} [${esc(q.reliability)}, ${esc(q.exposure)}]`).join("; ")}${(sn.blocked || []).length ? "<br>gesperrt: " + sn.blocked.map(esc).join(", ") : ""}</details>` : ""}</li>`; }).join("")}</ul>`;
    }
    return `<h3>Noch keine Suche</h3><div class="small muted">Starten Sie oben die erste Suche.</div>`;
  }

  function manualFinding(ov, persons) {
    const m = modal("Eigene Erkenntnis erfassen", `<form id="mf">
      <label class="field"><span>Zu Person</span><select name="entity_id">${persons.map((p) => opt(p.id, p.label, state.searchEntity)).join("")}</select></label>
      <label class="field"><span>Erkenntnis *</span><input name="title" required placeholder="z. B. Arbeitet seit 2024 bei Firma X"></label>
      <label class="field"><span>Details</span><textarea name="snippet"></textarea></label>
      <div class="grid g2"><label class="field"><span>Quelle</span><input name="source" placeholder="z. B. Gespräch mit Mutter, Zeitungsartikel"></label>
      <label class="field"><span>Link (optional)</span><input name="url" placeholder="https://…"></label>
      <label class="field"><span>Kategorie</span><select name="category">${["Hinweis", "Konto", "Beruf/Bildung", "Ort", "Kontaktperson", "Medienbericht", "Register", "Sonstiges"].map((c) => opt(c, c)).join("")}</select></label>
      <label class="field"><span>Verlässlichkeit (0–100)</span><input type="number" name="score" min="0" max="100" value="70"></label></div>
      <label class="check"><input type="checkbox" name="confirmed" checked> <span>Bereits geprüft (als bestätigt übernehmen)</span></label></form>`,
      `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="mf-save">Speichern</button>`);
    $("#mf-save", m.el).onclick = async () => {
      const f = $("#mf", m.el), d = formData(f);
      d.confirmed = f.confirmed.checked;
      await guard(() => api("POST", `/api/cases/${ov.case.id}/findings`, d), "Erkenntnis gespeichert");
      m.close(); renderCase();
    };
  }

  // ------------------------------------------------------------------ Tab: Verbindungen
  async function tabGraph(el, ov) {
    const [gr, sugg, ents, net] = await Promise.all([api("GET", `/api/cases/${ov.case.id}/graph`), api("GET", `/api/cases/${ov.case.id}/suggestions`), api("GET", `/api/cases/${ov.case.id}/entities`),
      api("GET", `/api/cases/${ov.case.id}/graph/analysis`).catch(() => null)]);
    const types = [...new Set(gr.nodes.map((n) => n.type))];
    const entOpts = (sel) => ents.map((e) => opt(e.id, `${e.label} (${e.type_label})`, sel)).join("");
    el.innerHTML = `
      ${help("So nutzen Sie den Verbindungsgraphen", [
        "<b>Ziehen</b> verschiebt Knoten (fixiert sie), <b>Doppelklick</b> löst sie wieder; Hintergrund ziehen = verschieben, Mausrad = zoomen.",
        "Knotengröße = Anzahl Verbindungen. ★ = Zielperson. <b>Gestrichelte</b> Linien = unsichere Verbindung (< 50 %).",
        "<b>Pfadsuche</b>: Zwei Einträge wählen – alle Wege zwischen ihnen werden gelb hervorgehoben (z. B. „Wie hängen A und B zusammen?“).",
        "<b>Vorschläge</b> findet ungeprüfte Zusammenhänge: gemeinsame Identifikatoren, gemeinsame Kontakte, gleiche Orte, Erwähnungen – und <b>mögliche Dubletten</b> (gleiche Person in anderer Schreibweise oder Schrift), jeweils mit Begründung.",
        "<b>Netzwerkanalyse</b> zeigt Gruppen, <b>Brücken</b> (Einträge, die sonst getrennte Gruppen verbinden) und unverbundene Einträge. <b>Austausch</b> exportiert den Graphen für Gephi, Aleph/OpenSanctions (FollowTheMoney) und Obsidian."], !gr.edges.length)}
      <div class="graph-wrap">
        <div class="graph-stage" id="stage">
          <canvas id="cv" aria-label="Netzwerkgraph"></canvas>
          <div class="graph-toolbar">
            <input type="search" id="g-find" placeholder="Knoten suchen …">
            <span class="box">Sicherheit ≥ <input type="range" id="g-conf" min="0" max="100" step="10" value="0"> <b id="g-conf-v">0 %</b></span>
            <button class="btn btn-sm" id="g-fit">⤢ Einpassen</button>
            <button class="btn btn-sm" id="g-relayout">↻ Neu anordnen</button>
            <a class="btn btn-sm" href="/api/cases/${ov.case.id}/graph.png">⬇ PNG</a>
          </div>
          <div class="graph-legend">${types.map((t) => `<label><input type="checkbox" data-type="${t}" checked><span class="type-dot" style="background:${COLORS[t]}"></span>${esc(state.meta.entity_types[t])}</label>`).join("")}</div>
          <div class="graph-tip" id="g-tip"></div>
          ${gr.nodes.length ? "" : `<div class="empty" style="position:absolute;inset:30% 0 auto">Noch keine Einträge. Legen Sie Personen an oder bestätigen Sie Treffer.</div>`}
        </div>
        <div class="side-panel">
          <div class="card" id="g-sel"><h3>Auswahl</h3><div class="small muted">Klicken Sie auf einen Knoten, um Details und Verbindungen zu sehen.</div></div>
          <div class="card"><h3>🧭 Pfadsuche</h3>
            <select id="p-a">${opt("", "Start wählen …")}${entOpts(ov.subject ? ov.subject.id : "")}</select>
            <select id="p-b" style="margin-top:.4rem">${opt("", "Ziel wählen …")}${entOpts("")}</select>
            <div class="row" style="margin-top:.4rem"><button class="btn btn-sm btn-primary" id="p-go">Verbindung finden</button><button class="btn btn-sm" id="p-clear">Zurücksetzen</button></div>
            <div id="p-res" style="margin-top:.5rem"></div></div>
          <div class="card"><div class="card-head"><h3>＋ Verbindung anlegen</h3></div>
            <form id="l-form">
              <select name="source_id" required>${opt("", "Von …")}${entOpts(state.graphFocus || "")}</select>
              <select name="relation" style="margin-top:.4rem">${state.meta.relations.map((r) => opt(r, r)).join("")}</select>
              <select name="target_id" required style="margin-top:.4rem">${opt("", "Zu …")}${entOpts("")}</select>
              <label class="field" style="margin:.5rem 0 .3rem"><span>Sicherheit: <b id="l-cv">70 %</b></span><input type="range" name="confidence" min="0" max="100" step="5" value="70"></label>
              <input name="evidence" placeholder="Beleg / Quelle (empfohlen)">
              <div class="row" style="margin-top:.5rem"><button class="btn btn-sm btn-primary">Verbinden</button><button type="button" class="btn btn-sm" id="l-newent">＋ Neuer Eintrag</button></div>
            </form></div>
          <div class="card"><h3>💡 Vorschläge (${sugg.length})</h3>
            ${sugg.length ? sugg.slice(0, 12).map((s, i) => `<div class="sugg"><b>${esc(s.source_label)}</b> ↔ <b>${esc(s.target_label)}</b><div class="small muted">${esc(s.reason)}</div>
              <div class="row" style="margin-top:.25rem"><button class="btn btn-sm" data-sugg="${i}">Als „${esc(s.relation)}“ übernehmen</button><button class="btn btn-sm" data-sugg-show="${i}">Zeigen</button></div></div>`).join("") : '<div class="small muted">Derzeit keine Vorschläge.</div>'}</div>
          <div class="card"><h3>⭐ Schlüsselakteure</h3>
            ${gr.key_nodes.length ? `<table class="tbl"><tr><th>Eintrag</th><th title="Anzahl Verbindungen">Verb.</th><th title="Vermittlerrolle (Betweenness)">Vermittler</th></tr>${gr.key_nodes.map((n) => `<tr><td><a href="#" data-focus="${n.id}">${esc(n.label)}</a></td><td>${n.degree}</td><td>${n.betweenness.toFixed(2)}</td></tr>`).join("")}</table>
            <div class="small muted" style="margin-top:.3rem">„Vermittler“ = wie oft ein Eintrag auf kürzesten Wegen zwischen anderen liegt.</div>` : '<div class="small muted">Noch keine Verbindungen.</div>'}</div>
          ${net && net.edges ? `<div class="card" id="g-net"><h3>🕸 Netzwerkanalyse</h3>
            <div class="small muted">${net.nodes} Einträge · ${net.edges} Verbindungen · ${net.components} getrennte Teile. Orientierung für die Recherche – eine Verbindung ist so belastbar wie ihr Beleg.</div>
            ${net.bridges.length ? `<h4 style="margin:.6rem 0 .1rem">Brücken</h4><ul class="net-list">${net.bridges.map((b) => `<li><a href="#" data-focus="${b.id}">${esc(b.label)}</a> <span class="muted">${b.connects_groups > 1 ? "verbindet " + b.connects_groups + " Gruppen" : "einziger Weg zu einem Teil des Netzes"}${b.cut_point ? " · Trennstelle" : ""}</span></li>`).join("")}</ul>` : ""}
            ${net.groups.length ? `<h4 style="margin:.6rem 0 .1rem">Gruppen (${net.groups.length})</h4><ul class="net-list">${net.groups.slice(0, 8).map((g) => `<li>${g.slice(0, 6).map((m) => `<a href="#" data-focus="${m.id}">${esc(m.label)}</a>`).join(", ")}${g.length > 6 ? ` <span class="muted">+ ${g.length - 6}</span>` : ""}</li>`).join("")}</ul>` : ""}
            ${net.isolated.length ? `<div class="small muted">Ohne Verbindung: ${net.isolated.slice(0, 10).map((m) => esc(m.label)).join(", ")}${net.isolated.length > 10 ? " …" : ""}</div>` : ""}</div>` : ""}
          <div class="card"><h3>⇄ Austausch</h3>
            <div class="small muted" style="margin-bottom:.4rem">Offene Formate – jeder Export erhält eine Export-ID und steht im Register.</div>
            <div class="row"><a class="btn btn-sm" href="/api/cases/${ov.case.id}/export/graph.gexf" title="Für Gephi und andere Graph-Programme">GEXF (Gephi)</a>
              <a class="btn btn-sm" href="/api/cases/${ov.case.id}/export/graph.ftm" title="FollowTheMoney – Format von Aleph und OpenSanctions">FollowTheMoney</a>
              <a class="btn btn-sm" href="/api/cases/${ov.case.id}/export/graph.canvas" title="JSON Canvas – z. B. für Obsidian">Canvas</a>
              <a class="btn btn-sm" href="/api/cases/${ov.case.id}/export/obsidian.zip" title="Notizen mit Verknüpfungen, geprüfte Aussagen und Graph – unverschlüsselt, Hinweis liegt bei">Obsidian-Vault</a></div>
            ${ov.permissions.includes("write") ? `<div class="row" style="margin-top:.5rem"><label class="btn btn-sm">⬆ FollowTheMoney einlesen<input type="file" id="g-ftm" hidden accept=".json,.ftm,.ndjson"></label>
              <span class="small muted">z. B. Export aus EagleEye Build 492/500, Aleph oder OpenSanctions. Alles bleibt ungeprüft (Sicherheit 40 %).</span></div>` : ""}</div>
        </div>
      </div>`;
    const ftmIn = $("#g-ftm", el);
    if (ftmIn) ftmIn.onchange = async () => {
      const fd = new FormData(); fd.append("file", ftmIn.files[0]);
      try { const r = await api("POST", `/api/cases/${ov.case.id}/import/ftm`, fd); toast(`Eingelesen: ${r.created} neue Einträge, ${r.reused} vorhandene, ${r.links} Verbindungen${r.skipped ? ", " + r.skipped + " übersprungen" : ""}`, "ok"); }
      catch (err) { toast(err.message, "err"); }
      renderCase();
    };
    const graph = new window.NetworkGraph($("#cv"), { tooltip: $("#g-tip"), onSelect: (n) => showSelection(n) });
    state.graph = graph;
    graph.setData(gr.nodes, gr.edges);
    const applyFilter = () => {
      const hidden = $$(".graph-legend input", el).filter((c) => !c.checked).map((c) => c.dataset.type);
      const v = Number($("#g-conf").value);
      $("#g-conf-v").textContent = v + " %";
      graph.setFilter(hidden, v);
    };
    $$(".graph-legend input", el).forEach((c) => (c.onchange = applyFilter));
    $("#g-conf").oninput = applyFilter;
    $("#g-fit").onclick = () => graph.fit();
    $("#g-relayout").onclick = () => graph.relayout();
    $("#g-find").onkeydown = (e) => { if (e.key === "Enter") { if (!graph.focusLabel(e.target.value)) toast("Kein passender Knoten."); } };
    $$("[data-focus]", el).forEach((a) => a.onclick = (ev) => { ev.preventDefault(); const n = graph.byId.get(Number(a.dataset.focus)); graph.select(n.id, true); showSelection(n); });
    const lf = $("#l-form");
    lf.confidence.oninput = () => ($("#l-cv").textContent = lf.confidence.value + " %");
    lf.onsubmit = async (ev) => {
      ev.preventDefault();
      const d = formData(lf);
      if (d.source_id === d.target_id) return toast("Bitte zwei verschiedene Einträge wählen.", "err");
      await guard(() => api("POST", `/api/cases/${ov.case.id}/links`, { ...d, source_id: Number(d.source_id), target_id: Number(d.target_id), confidence: Number(d.confidence) }), "Verbindung angelegt");
      state.graphFocus = Number(d.source_id); renderCase();
    };
    $("#l-newent").onclick = () => newEntity(ov, "person", (e) => { state.graphFocus = e.id; renderCase(); });
    $$("[data-sugg]", el).forEach((b) => b.onclick = async () => {
      const s = sugg[Number(b.dataset.sugg)];
      await guard(() => api("POST", `/api/cases/${ov.case.id}/links`, { source_id: s.source_id, target_id: s.target_id, relation: s.relation, confidence: s.confidence, evidence: "Vorschlag: " + s.reason }), "Verbindung übernommen");
      renderCase();
    });
    $$("[data-sugg-show]", el).forEach((b) => b.onclick = () => { const s = sugg[Number(b.dataset.suggShow)]; graph.highlightPath([s.source_id, s.target_id]); });
    $("#p-go").onclick = async () => {
      const a = $("#p-a").value, b = $("#p-b").value;
      if (!a || !b || a === b) return toast("Bitte Start und Ziel (verschieden) wählen.", "err");
      const r = await guard(() => api("GET", `/api/cases/${ov.case.id}/paths?a=${a}&b=${b}`));
      const box = $("#p-res");
      if (!r.paths.length) { box.innerHTML = `<div class="small">Keine Verbindung (bis 5 Schritte) gefunden.</div>`; graph.highlightPath(null); return; }
      box.innerHTML = `<div class="small" style="margin-bottom:.3rem">Kürzester Weg: <b>${r.shortest_length} Schritt(e)</b> · ${r.paths.length} Wege${r.common_neighbours.length ? ` · gemeinsame Kontakte: ${r.common_neighbours.map((c) => esc(c.label)).join(", ")}` : ""}</div>` +
        r.paths.map((p, i) => `<div class="path ${i === 0 ? "active" : ""}" data-path="${i}"><b>${p.length} Schritt(e)</b> · Gesamtsicherheit ${p.combined_confidence} %<div class="small">${p.steps.map((s) => `${esc(s.from)} <i>— ${esc(s.relation)} (${s.confidence} %) →</i> `).join("")}${esc(p.labels[p.labels.length - 1])}</div></div>`).join("");
      graph.highlightPath(r.paths[0].nodes);
      $$("[data-path]", box).forEach((d) => d.onclick = () => { $$(".path", box).forEach((x) => x.classList.remove("active")); d.classList.add("active"); graph.highlightPath(r.paths[Number(d.dataset.path)].nodes); });
    };
    $("#p-clear").onclick = () => { graph.highlightPath(null); $("#p-res").innerHTML = ""; };

    function showSelection(n) {
      const box = $("#g-sel");
      if (!n) { box.innerHTML = `<h3>Auswahl</h3><div class="small muted">Klicken Sie auf einen Knoten.</div>`; return; }
      const rel = gr.edges.filter((e) => e.source === n.id || e.target === n.id);
      box.innerHTML = `<div class="card-head"><span class="type-dot" style="background:${COLORS[n.type]}"></span><h3>${esc(n.label)}</h3></div>
        <div class="small muted">${esc(n.type_label)} · ${n.degree} Verbindungen · Vermittler ${n.betweenness.toFixed(2)}</div>
        <table class="tbl" style="margin-top:.4rem">${rel.map((e) => { const other = graph.byId.get(e.source === n.id ? e.target : e.source);
          return `<tr><td>${e.source === n.id ? "→" : "←"} ${esc(e.relation)}<br><b>${esc(other.label)}</b><div class="small muted">${e.confidence} %${e.evidence ? " · " + esc(e.evidence) : ""}</div></td><td><button class="btn btn-sm btn-danger" data-del-link="${e.id}" title="Verbindung löschen">×</button></td></tr>`; }).join("") || "<tr><td class='muted small'>Keine Verbindungen.</td></tr>"}</table>
        <div class="row" style="margin-top:.5rem"><button class="btn btn-sm" id="sel-from">Als Start</button><button class="btn btn-sm" id="sel-to">Als Ziel</button><button class="btn btn-sm" id="sel-link">Verbinden …</button><button class="btn btn-sm" id="sel-open">Profil</button></div>`;
      $$("[data-del-link]", box).forEach((b) => b.onclick = async () => {
        if (!(await confirmDlg("Diese Verbindung löschen?"))) return;
        await guard(() => api("DELETE", `/api/cases/${ov.case.id}/links/${b.dataset.delLink}`), "Verbindung gelöscht");
        state.graphFocus = n.id; renderCase();
      });
      $("#sel-from").onclick = () => ($("#p-a").value = n.id);
      $("#sel-to").onclick = () => ($("#p-b").value = n.id);
      $("#sel-link").onclick = () => { lf.source_id.value = n.id; lf.target_id.focus(); };
      $("#sel-open").onclick = () => { state.selEntity = n.id; location.hash = `#/case/${ov.case.id}/persons`; };
    }
    if (state.graphFocus && graph.byId.get(state.graphFocus)) {
      const n = graph.byId.get(state.graphFocus);
      setTimeout(() => { graph.select(n.id, false); showSelection(n); }, 50);
    }
    state.graphFocus = null;
  }

  // ------------------------------------------------------------------ Tab: Zeitleiste & Karte
  async function tabTimeline(el, ov) {
    const [events, ents] = await Promise.all([api("GET", `/api/cases/${ov.case.id}/events`), api("GET", `/api/cases/${ov.case.id}/entities`)]);
    const persons = ents.filter((e) => e.type === "person");
    const lastIdx = (() => { let idx = -1; events.forEach((e, i) => { if (e.kind === "Letzte Sichtung") idx = i; }); return idx; })();
    el.innerHTML = `
      ${help("Zeitleiste & Karte", [
        "Erfassen Sie Sichtungen, letzte Kontakte, Online-Aktivitäten und Bewegungen mit Ort und Zeit.",
        "Orte werden automatisch in Koordinaten umgewandelt (OpenStreetMap, Internet nötig) – alternativ Koordinaten direkt eintragen.",
        "Die Karte zeigt alle Ereignisse chronologisch nummeriert und verbindet sie zu einer Bewegungslinie. Rot = letzte Sichtung.",
        "Bewerten Sie die <b>Verlässlichkeit</b> jedes Hinweises – ungeprüfte Hinweise bleiben als solche gekennzeichnet."], !events.length)}
      <div class="grid g2">
        <div class="card">
          <div class="card-head"><h2>Zeitleiste (${events.length})</h2><div class="right"><button class="btn btn-sm btn-primary" id="ev-new">＋ Ereignis</button></div></div>
          ${events.length ? `<ul class="timeline">${events.map((e, i) => `<li class="${i === lastIdx ? "k-last" : e.kind.startsWith("Sichtung") ? "k-hint" : ""}">
            <div class="when"><span class="num">${i + 1}</span>${esc(fmtLocal(e.occurred_at))} · ${esc(e.kind)}</div>
            <div>${esc(e.description)}</div>
            <div class="small muted">${e.location ? "📍 " + esc(e.location) : ""}${e.entity_label ? " · 👤 " + esc(e.entity_label) : ""}${e.source ? " · Quelle: " + esc(e.source) : ""}
              <span class="badge ${e.reliability === "bestätigt" ? "b-green" : e.reliability === "ungeprüft" ? "b-amber" : "b-blue"}">${esc(e.reliability)}</span>
              ${e.lat == null && e.location ? '<span class="badge b-grey" title="Ort konnte nicht auf der Karte verortet werden">nicht verortet</span>' : ""}
              <button class="btn btn-sm btn-danger" data-del-ev="${e.id}" style="padding:0 .4rem">×</button></div></li>`).join("")}</ul>`
            : `<div class="empty"><div class="big">🕒</div>Noch keine Ereignisse.${ov.case.case_type === "vermisst" ? "<br>Beginnen Sie mit der <b>letzten Sichtung</b>." : ""}</div>`}
        </div>
        <div class="card"><div class="card-head"><h2>Karte</h2><span class="right small muted">${state.meta.opsec_levels[ov.case.opsec_level].map_tiles || state.tilesOn === ov.case.id ? "Kartendaten © OpenStreetMap-Mitwirkende" : `<button class="btn btn-sm" id="tiles-on" title="Der Kartenserver sieht dann, welchen Ausschnitt Sie betrachten">🛡 Kartenhintergrund laden</button>`}</span></div><div id="map"></div></div>
      </div>`;
    $("#ev-new").onclick = () => newEvent(ov, persons);
    $$("[data-del-ev]", el).forEach((b) => b.onclick = async () => { if (await confirmDlg("Ereignis löschen?")) { await guard(() => api("DELETE", `/api/cases/${ov.case.id}/events/${b.dataset.delEv}`)); renderCase(); } });
    const map = L.map("map", { zoomControl: true }).setView([51.16, 10.45], 6);
    state.map = map;
    if (state.meta.opsec_levels[ov.case.opsec_level].map_tiles || state.tilesOn === ov.case.id) {
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
    }
    const tb = $("#tiles-on");
    if (tb) tb.onclick = async () => {
      if (!(await confirmDlg("Kartenhintergrund laden? Ihr Browser fragt dann Kartenkacheln bei OpenStreetMap ab – der Server sieht Ihre IP-Adresse und den betrachteten Ausschnitt.", "Laden"))) return;
      state.tilesOn = ov.case.id; renderCase();
    };
    const pts = [];
    events.forEach((e, i) => {
      if (e.lat == null || e.lon == null) return;
      const icon = L.divIcon({ className: "", html: `<div class="map-num ${i === lastIdx ? "last" : ""}">${i + 1}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
      L.marker([e.lat, e.lon], { icon }).addTo(map).bindPopup(`<b>${i + 1}. ${esc(e.kind)}</b><br>${esc(fmtLocal(e.occurred_at))}<br>${esc(e.location)}<br>${esc(e.description)}<br><i>${esc(e.reliability)}</i>`);
      pts.push([e.lat, e.lon]);
    });
    ents.filter((e) => e.type === "ort" && e.data && e.data.lat != null).forEach((e) => {
      L.circleMarker([e.data.lat, e.data.lon], { radius: 7, color: "#059669", fillOpacity: 0.5 }).addTo(map).bindPopup(`<b>${esc(e.label)}</b><br>Ort im Fall`);
      pts.push([e.data.lat, e.data.lon]);
    });
    const route = events.filter((e) => e.lat != null && e.entity_id === (ov.subject || {}).id).map((e) => [e.lat, e.lon]);
    if (route.length > 1) L.polyline(route, { color: "#2563eb", weight: 3, dashArray: "6 6", opacity: 0.8 }).addTo(map);
    if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 15 });
    setTimeout(() => map.invalidateSize(), 100);
  }

  function newEvent(ov, persons) {
    const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    const m = modal("Ereignis erfassen", `<form id="evf">
      <div class="grid g2">
        <label class="field"><span>Zeitpunkt *</span><input type="datetime-local" name="occurred_at" value="${now}" required></label>
        <label class="field"><span>Art</span><select name="kind">${state.meta.event_kinds.map((k) => opt(k, k)).join("")}</select></label>
      </div>
      <label class="field"><span>Person</span><select name="entity_id">${opt("", "– keine –")}${persons.map((p) => opt(p.id, p.label, (ov.subject || {}).id)).join("")}</select></label>
      <label class="field"><span>Ort</span><input name="location" placeholder="z. B. Hauptbahnhof Hamburg"><small>Wird automatisch auf der Karte verortet (Internet nötig). Alternativ Koordinaten angeben.</small></label>
      <div class="grid g2"><label class="field"><span>Breitengrad (optional)</span><input name="lat" placeholder="53.55"></label><label class="field"><span>Längengrad (optional)</span><input name="lon" placeholder="10.00"></label></div>
      <label class="field"><span>Beschreibung</span><textarea name="description" placeholder="Was ist passiert? Kleidung, Begleitung, Richtung …"></textarea></label>
      <div class="grid g2"><label class="field"><span>Quelle</span><input name="source" placeholder="z. B. Zeugin, Kamera, Social Media"></label>
      <label class="field"><span>Verlässlichkeit</span><select name="reliability">${["ungeprüft", "wahrscheinlich", "bestätigt", "zweifelhaft"].map((r) => opt(r, r)).join("")}</select></label></div></form>`,
      `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="evf-save">Speichern</button>`);
    $("#evf-save", m.el).onclick = async (ev) => {
      const d = formData($("#evf", m.el));
      ["lat", "lon"].forEach((k) => { d[k] = d[k] ? Number(d[k].replace(",", ".")) : null; });
      d.entity_id = d.entity_id ? Number(d.entity_id) : null;
      ev.target.disabled = true; ev.target.innerHTML = '<span class="spinner"></span> Speichern …';
      try { await guard(() => api("POST", `/api/cases/${ov.case.id}/events`, d), "Ereignis gespeichert"); m.close(); renderCase(); }
      catch (e) { ev.target.disabled = false; ev.target.textContent = "Speichern"; }
    };
  }

  // ------------------------------------------------------------------ Tab: Aufgaben
  async function tabTasks(el, ov) {
    const tasks = await api("GET", `/api/cases/${ov.case.id}/tasks`);
    const open = tasks.filter((t) => !t.done).length;
    el.innerHTML = `
      ${help("Aufgaben", ["Der <b>Leitfaden</b> erzeugt eine bewährte Checkliste passend zur Fallart (z. B. Krankenhäuser abfragen, Kontaktpersonen befragen).", "Eigene Aufgaben ergänzen und abhaken – offene Aufgaben erscheinen im Dossier unter „Offene Punkte“."])}
      <div class="card">
        <div class="card-head"><h2>Aufgaben (${open} offen)</h2><div class="right"><button class="btn btn-sm" id="t-gen">📋 Leitfaden-Aufgaben ergänzen</button></div></div>
        <form class="row" id="t-form" style="margin-bottom:.6rem"><input name="title" class="grow" placeholder="Neue Aufgabe …" required>
          <select name="priority" style="width:auto">${opt("normal", "normal")}${opt("hoch", "hohe Priorität")}</select><button class="btn btn-primary">Hinzufügen</button></form>
        ${tasks.map((t) => `<div class="task ${t.done ? "done" : ""}"><input type="checkbox" data-task="${t.id}" ${t.done ? "checked" : ""} aria-label="erledigt">
          <span class="tt">${esc(t.title)}</span>${t.priority === "hoch" ? '<span class="badge b-red">hoch</span>' : ""}<span class="badge b-grey">${esc(t.origin)}</span>
          <button class="btn btn-sm btn-danger" data-del-task="${t.id}" style="padding:0 .45rem">×</button></div>`).join("") || '<div class="empty">Keine Aufgaben. Nutzen Sie den Leitfaden.</div>'}
      </div>`;
    $("#t-gen").onclick = async () => { await guard(() => api("POST", `/api/cases/${ov.case.id}/tasks/generate`), "Leitfaden ergänzt"); renderCase(); };
    $("#t-form").onsubmit = async (e) => { e.preventDefault(); await guard(() => api("POST", `/api/cases/${ov.case.id}/tasks`, formData(e.target))); renderCase(); };
    $$("[data-task]", el).forEach((c) => c.onchange = async () => { await guard(() => api("PATCH", `/api/cases/${ov.case.id}/tasks/${c.dataset.task}`, { done: c.checked })); renderCase(); });
    $$("[data-del-task]", el).forEach((b) => b.onclick = async () => { await guard(() => api("DELETE", `/api/cases/${ov.case.id}/tasks/${b.dataset.delTask}`)); renderCase(); });
  }

  // ------------------------------------------------------------------ Tab: Dossier
  async function renderAi(ov) {
    const box = $("#ai-card");
    if (!box) return;
    const [st, drafts] = await Promise.all([api("GET", "/api/ai/status"), api("GET", `/api/cases/${ov.case.id}/ai`)]);
    const canWrite = ov.permissions.includes("write"), canReview = ov.permissions.includes("review");
    const cur = drafts.find((d) => d.status === "entwurf") || drafts.find((d) => d.status === "freigegeben");
    const chk = (d) => d.checks.ok ? '<span class="badge b-green">✓ alle Sätze belegt</span>'
      : `${d.checks.unknown.length ? `<span class="badge b-red">${d.checks.unknown.length} unbekannte Kennung(en)</span> ` : ""}${d.checks.uncited.length ? `<span class="badge b-amber">${d.checks.uncited.length} Satz/Sätze ohne Beleg</span>` : ""}`;
    box.innerHTML = `<div class="card-head"><h2>🤖 KI-Zusammenfassung</h2><span class="right small muted">${st.enabled ? `lokales Modell ${esc(st.model)}` : "nicht eingerichtet"}</span></div>
      <p class="small muted">Ein lokales Sprachmodell formuliert aus den <b>bestätigten Aussagen</b> eine Zusammenfassung mit Fakten-Kennungen. EagleEye prüft jede Kennung; erst nach menschlicher Freigabe erscheint der Text – mit Fußnoten – in der Management Summary.</p>
      ${!st.enabled ? '<div class="warn small">Die Administration kann unter Verwaltung → KI-Assistent einen lokalen Dienst (z. B. Ollama) einrichten. Falldaten verlassen dabei das eigene Netz nicht.</div>' : ""}
      ${cur ? `<div class="ai-draft"><div class="row"><span class="badge ${cur.status === "freigegeben" ? "b-green" : "b-blue"}">${esc(cur.status)}</span> ${chk(cur)} <span class="small muted">${fmtTs(cur.created_at)} · ${esc(cur.created_by)}${cur.approved_by ? " · freigegeben von " + esc(cur.approved_by) : ""}</span></div>
        ${cur.status === "entwurf" && canWrite ? `<textarea id="ai-text" rows="7" style="margin-top:.4rem">${esc(cur.text)}</textarea>` : `<p style="white-space:pre-wrap;margin:.4rem 0">${esc(cur.text)}</p>`}
        ${cur.checks.uncited.length ? `<div class="small" style="color:#92400e">Ohne Beleg: ${cur.checks.uncited.map((x) => "„" + esc(x.slice(0, 80)) + "“").join(", ")}</div>` : ""}
        ${cur.status === "entwurf" ? `<div class="row" style="margin-top:.4rem">${canWrite ? '<button class="btn btn-sm" id="ai-save">Text speichern & prüfen</button>' : ""}
          ${canReview ? `<button class="btn btn-sm btn-success" id="ai-ok">✓ Freigeben</button><button class="btn btn-sm" id="ai-no">✗ Verwerfen</button>` : ""}</div>` : ""}</div>` : ""}
      ${st.enabled && canWrite ? `<button class="btn btn-primary" id="ai-gen" style="margin-top:.6rem">${cur ? "Neuen Entwurf erzeugen" : "Entwurf erzeugen"}</button>` : ""}`;
    const g = $("#ai-gen", box);
    if (g) g.onclick = async () => {
      g.disabled = true; g.innerHTML = '<span class="spinner"></span> Modell schreibt … (bis zu 2 Minuten)';
      try { await api("POST", `/api/cases/${ov.case.id}/ai`); toast("Entwurf erzeugt – bitte prüfen", "ok"); } catch (e) { toast(e.message, "err"); }
      renderAi(ov);
    };
    const sv = $("#ai-save", box);
    if (sv) sv.onclick = async () => { await guard(() => api("PATCH", `/api/cases/${ov.case.id}/ai/${cur.id}`, { text: $("#ai-text", box).value }), "Gespeichert"); renderAi(ov); };
    const ok = $("#ai-ok", box);
    if (ok) ok.onclick = async () => {
      const t = $("#ai-text", box);
      if (t && t.value !== cur.text) await api("PATCH", `/api/cases/${ov.case.id}/ai/${cur.id}`, { text: t.value });
      let accept = false;
      if (cur.checks.uncited.length) { accept = await confirmDlg("Einige Sätze haben keinen Faktenbeleg. Trotzdem freigeben?", "Freigeben"); if (!accept) return; }
      await guard(() => api("PATCH", `/api/cases/${ov.case.id}/ai/${cur.id}`, { status: "freigegeben", accept_uncited: accept }), "Freigegeben – erscheint in der Management Summary");
      renderCase();
    };
    const no = $("#ai-no", box);
    if (no) no.onclick = async () => { await guard(() => api("PATCH", `/api/cases/${ov.case.id}/ai/${cur.id}`, { status: "verworfen" }), "Verworfen"); renderAi(ov); };
  }

  async function tabDossier(el, ov) {
    const c = ov.counts, missing = ov.case.case_type === "vermisst";
    const meta = state.reportMeta || (state.reportMeta = await api("GET", "/api/report/templates"));
    const tpl = state.dossierTpl && meta.templates[state.dossierTpl] ? state.dossierTpl : (missing ? "vermisst" : "volldossier");
    const unrev = !!state.dossierUnrev;
    const [pv, evid, op, fam, comp] = await Promise.all([api("GET", `/api/cases/${ov.case.id}/dossier/preview?template=${tpl}&include_unreviewed=${unrev}`),
      api("GET", `/api/cases/${ov.case.id}/evidence`), api("GET", `/api/cases/${ov.case.id}/opsec`),
      api("GET", `/api/cases/${ov.case.id}/evidence/families`).catch(() => null), api("GET", "/api/components").catch(() => ({ ocr: {} }))]);
    const canManage = ov.permissions.includes("manage");
    const evNo = (id) => "B" + String(id).padStart(4, "0");
    const KIND = { web: ["Webseite", "b-blue"], archiv: ["Archivfassung", "b-amber"], dokument: ["Dokument", "b-grey"] };
    const evMeta = (e) => {
      const m = e.meta || {}, out = [];
      if (m.author) out.push("Autor laut Seite: " + m.author);
      if (m.published) out.push("Datum laut Seite: " + fmtDate(m.published));
      if (m.archiv_zeitpunkt) out.push("Archivstand: " + fmtTs(m.archiv_zeitpunkt));
      if (e.kind === "dokument") out.push((m.pages || 1) + " Seite(n)" + (m.ocr_pages ? `, ${m.ocr_pages} per Texterkennung (Ø ${m.ocr_confidence || "?"} %)` : ""));
      if (m.hinweis) out.push("⚠ " + m.hinweis);
      if (m.warc_hinweis) out.push("⚠ " + m.warc_hinweis);
      return out;
    };
    const canWrite = ov.permissions.includes("write");
    const bar = (d) => d == null ? '<span class="muted small">–</span>' : `<div class="dens"><div style="width:${d}%;background:${d >= 75 ? "var(--green)" : d >= 50 ? "var(--amber)" : "var(--red)"}"></div></div><span class="small">${d} %</span>`;
    el.innerHTML = `
      ${help("So entsteht das Top-Dossier", [
        "Vorlage wählen – jede Vorlage stellt die passenden Kapitel zusammen. Die Vorschau zeigt je Kapitel die <b>Belegdichte</b>: Anteil der Aussagen, die mehrfach belegt, aus zuverlässiger Quelle bestätigt oder als Beleg gesichert sind.",
        "Jede Aussage im Dossier trägt ihren <b>Admiralty-Code</b> und eine Fußnote. Das Quellenverzeichnis nennt Abrufzeit, Verlässlichkeit und – falls gesichert – den <b>SHA-256-Hash</b> und eine Archivkopie.",
        "<b>Belege sichern</b> ruft eine Fundstelle über den Netzausgang des Falls ab, archiviert sie verschlüsselt und versiegelt sie – zusätzlich als <b>WARC</b> (Archivstandard mit Anfrage, Antwort und Kopfzeilen). Der <b>Haupttext</b> wird ohne Menü und Werbung herausgelöst.",
        "<b>Dokumente</b> (PDF, Word, Scan, E-Mail) lassen sich als Beleg importieren. Gescannte Seiten werden per Texterkennung lesbar; das Original bleibt unverändert versiegelt.",
        "<b>Quellenunabhängigkeit:</b> Belege mit nahezu gleichem Text (z. B. übernommene Agenturmeldungen) zählen als <b>ein</b> Ursprung – sie bestätigen sich nicht gegenseitig.",
        "Das <b>Beweispaket</b> enthält alle Belege mit WARC-Aufzeichnung, Textfassung, Manifest und Prüfanleitung.",
        "In das Dossier gelangen nur geprüfte Aussagen – ungeprüfte nur auf Wunsch und deutlich markiert."], false)}
      <div class="grid g2">
        <div>
          <div class="card"><h2>1. Vorlage</h2>
            <div class="tpl-cards">${Object.entries(meta.templates).map(([k, t]) => `<button type="button" class="type-card ${k === tpl ? "selected" : ""}" data-tpl="${k}"><b>${esc(t.label)}</b><div class="small muted">${esc(t.description)}</div></button>`).join("")}</div>
            <label class="check" style="margin-top:.6rem"><input type="checkbox" id="dx-unrev" ${unrev ? "checked" : ""}> <span>Ungeprüfte Aussagen aufnehmen (deutlich als „ungeprüft“ markiert)</span></label>
            <label class="check"><input type="checkbox" id="dx-graph" checked> <span>Netzwerkgrafik einbetten</span></label>
            <label class="check"><input type="checkbox" id="dx-audit" checked> <span>Bearbeitungsprotokoll anhängen (falls Kapitel in der Vorlage)</span></label>
          </div>
          <div class="card"><div class="card-head"><h2>2. Inhalt & Belegdichte</h2><span class="right">${pv.overall.density != null ? `Gesamt ${bar(pv.overall.density)}` : ""}</span></div>
            <table class="tbl"><tr><th>Kapitel</th><th>Aussagen</th><th>Belegdichte</th></tr>
            ${pv.sections.map((x, i) => `<tr><td>${i + 1}. ${esc(x.label)}</td><td>${x.statements || "–"}</td><td>${bar(x.density)}</td></tr>`).join("")}</table>
            ${pv.warnings.map((w) => `<div class="warn small" style="margin:.5rem 0 0">⚠ ${esc(w)}</div>`).join("")}
            ${pv.ai ? '<div class="ok-box small" style="margin-top:.5rem">✓ Freigegebene KI-Zusammenfassung wird in die Management Summary übernommen.</div>' : ""}
          </div>
        </div>
        <div>
          <div class="card"><h2>3. Erstellen</h2>
            <div class="opsec-strip small">🛡 Jeder Export erhält eine <b>Export-ID</b> (Fußzeile, Dateiname, Register im OPSEC-Reiter); Metadaten werden neutralisiert.${op.can_export ? "" : " <b>Sie dürfen auf dieser OPSEC-Stufe nicht exportieren.</b>"}</div>
            <div class="row"><button class="btn btn-primary btn-lg" data-fmt="docx">⬇ Word (.docx)</button>
              ${meta.pdf ? '<button class="btn btn-lg" data-fmt="pdf">⬇ PDF/A</button>' : '<span class="small muted">PDF/A: LibreOffice auf dem Server installieren</span>'}</div>
            <div class="row" style="margin-top:.7rem"><a class="btn" href="/api/cases/${ov.case.id}/export/beweispaket.zip">🗄 Beweispaket (${evid.length} Belege)</a>
              <a class="btn" href="/api/cases/${ov.case.id}/graph.png">🕸️ Netzwerkgrafik</a><a class="btn" href="/api/cases/${ov.case.id}/export/case.json">🗂️ Falldaten (JSON)</a>
              <a class="btn" href="/api/cases/${ov.case.id}/export/eagleeye.zip" title="Fundstellen und Einträge passend geteilt für die Übernahme in die EagleEye-Fallakte (Build 493/494). Dort bleibt alles ungeprüft.">🔁 Übergabe an EagleEye</a>
              ${missing ? `<a class="btn" href="/api/cases/${ov.case.id}/export/poster.docx">🆘 Suchplakat</a>` : ""}</div>
          </div>
          <div class="card"><div class="card-head"><h2>📎 Belege (${evid.length})</h2>
            <div class="right">${canWrite ? `<button class="btn btn-sm" id="ev-all" title="Alle bestätigten Treffer mit Webadresse sichern">Bestätigte Treffer sichern</button>` : ""}</div></div>
            ${canWrite ? `<form class="row" id="ev-form"><input name="url" class="grow" placeholder="https://… Fundstelle sichern" required><button class="btn btn-sm btn-primary">Sichern</button>
              <button type="button" class="btn btn-sm" id="ev-wb" title="Frühere Fassungen dieser Adresse im Internet Archive anzeigen und gezielt sichern">🕰 Frühere Fassungen</button></form>
              <div class="row" style="margin-top:.4rem"><label class="btn btn-sm">📄 Dokument importieren<input type="file" id="ev-doc" hidden multiple accept=".pdf,.docx,.txt,.eml,.html,.htm,.png,.jpg,.jpeg,.tif,.tiff"></label>
                <span class="small muted">PDF, Word, Bild, Text, E-Mail · bis 25 MB · ${comp.ocr && comp.ocr.available ? "Texterkennung aktiv (" + esc(comp.ocr.engine) + ")" : "Texterkennung nicht installiert – Scans bleiben ohne Text"}</span></div>` : ""}
            ${evid.length ? `<div style="overflow-x:auto"><table class="tbl small" style="margin-top:.5rem"><tr><th>Beleg</th><th>Fundstelle</th><th>Abruf & Siegel</th><th></th></tr>
              ${evid.map((e) => `<tr><td>${evNo(e.id)}<br><span class="badge ${(KIND[e.kind] || KIND.web)[1]}">${(KIND[e.kind] || KIND.web)[0]}</span></td>
                <td><b>${esc(e.title || e.filename || "")}</b><br>${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.url.slice(0, 60))}</a>` : `<span class="muted">${esc(e.filename || "")}</span>`}${e.archive_url ? ` · <a href="${esc(e.archive_url)}" target="_blank" rel="noopener noreferrer">Archiv</a>` : ""}
                  ${evMeta(e).map((x) => `<div class="muted">${esc(x)}</div>`).join("")}</td>
                <td>${fmtTs(e.retrieved_at)}<br><span class="muted">${e.kind === "dokument" ? "" : "HTTP " + e.status + " · "}${Math.max(1, Math.round(e.size / 1024))} KB · ${esc(e.egress)}</span>
                  <br><code title="SHA-256 ${esc(e.sha256)}">${esc(e.sha256.slice(0, 12))}…</code>${e.has_warc ? ' <span class="badge b-green" title="Aufzeichnung im Archivstandard WARC vorhanden">WARC</span>' : ""}</td>
                <td class="nowrap"><a class="btn btn-sm" href="/api/cases/${ov.case.id}/evidence/${e.id}/download" title="Originaldatei (als Download, wird nicht im Browser ausgeführt)">⬇</a>
                  ${e.has_warc ? `<a class="btn btn-sm" href="/api/cases/${ov.case.id}/evidence/${e.id}/warc" title="WARC-Aufzeichnung herunterladen">WARC</a>` : ""}
                  ${e.has_text ? `<button class="btn btn-sm" data-ev-text="${e.id}" title="Textfassung lesen – mit Seitenangabe und Erwähnungen von Fallpersonen">Text</button>` : ""}
                  <button class="btn btn-sm" data-ev-verify="${e.id}" title="Unverändertheit prüfen (Original, WARC, Wiedergabe)">✓</button>
                  ${canManage ? `<button class="btn btn-sm btn-danger" data-ev-del="${e.id}" title="Beleg löschen (Prüfsumme bleibt im Protokoll)">×</button>` : ""}</td></tr>`).join("")}</table></div>`
              : '<div class="small muted" style="margin-top:.5rem">Noch keine Belege. Treffer-Karten haben eine Schaltfläche „📎 Beleg sichern“.</div>'}
          </div>
          ${fam && fam.documents ? `<div class="card"><div class="card-head"><h2>🧬 Quellenunabhängigkeit</h2><span class="right"><b>${fam.documents}</b> Belege · <b>${fam.independent_origins}</b> unabhängige Ursprünge</span></div>
            <p class="small muted">Belege mit nahezu gleichem Text bilden eine Quellfamilie. In der Bewertung zählt eine Familie als <b>eine</b> Quelle. Das ist ein Analysehinweis – wer tatsächlich Urheber ist, muss geprüft werden.</p>
            ${fam.families.filter((f) => f.size > 1).map((f) => `<div class="flag"><span class="badge b-amber">${f.size} Belege · 1 Ursprung</span> ${f.members.map((m) => `<b>${esc(m.label)}</b> ${esc((m.title || "").slice(0, 50))}`).join(" · ")}
              <div class="small muted">Übereinstimmung ${Math.round((f.min_similarity || 0) * 100)}–${Math.round((f.max_similarity || 0) * 100)} % · ${f.hosts.map(esc).join(", ")} · zuerst gesichert: ${esc("B" + String(f.earliest).padStart(4, "0"))}</div></div>`).join("")
              || '<div class="ok-box small">Keine übernommenen oder gespiegelten Texte erkannt – alle verglichenen Belege sind eigenständig.</div>'}
            ${fam.skipped.length ? `<div class="small muted" style="margin-top:.4rem">${fam.skipped.length} Beleg(e) ohne ausreichend Text wurden nicht verglichen.</div>` : ""}</div>` : ""}
          <div class="card" id="ai-card"></div>
        </div>
      </div>`;
    renderAi(ov);
    $$("[data-tpl]", el).forEach((b) => (b.onclick = () => { state.dossierTpl = b.dataset.tpl; renderCase(); }));
    $("#dx-unrev").onchange = (e) => { state.dossierUnrev = e.target.checked; renderCase(); };
    $$("[data-fmt]", el).forEach((b) => (b.onclick = () => {
      const q = new URLSearchParams({ template: tpl, format: b.dataset.fmt, include_unreviewed: unrev, include_graph: $("#dx-graph").checked, include_audit: $("#dx-audit").checked });
      window.location.href = `/api/cases/${ov.case.id}/export/dossier.docx?${q}`;
      toast(b.dataset.fmt === "pdf" ? "PDF/A wird erstellt (kann einige Sekunden dauern) …" : "Dossier wird erstellt …", "ok");
      setTimeout(() => { if (state.tab === "dossier") renderCase(); }, 4000);
    }));
    const ef = $("#ev-form", el);
    if (ef) ef.onsubmit = async (e) => {
      e.preventDefault(); const btn = $("button", ef); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>';
      try { const r = await api("POST", `/api/cases/${ov.case.id}/evidence`, formData(ef)); toast(`Beleg B${String(r.id).padStart(4, "0")} gesichert`, "ok"); } catch (err) { toast(err.message, "err"); }
      renderCase();
    };
    const wb = $("#ev-wb", el);
    if (wb) wb.onclick = async () => {
      const url = (ef.url.value || "").trim();
      if (!url) return toast("Bitte zuerst die Adresse eingeben.", "err");
      wb.disabled = true;
      try {
        const list = await api("GET", `/api/cases/${ov.case.id}/evidence/wayback?url=${encodeURIComponent(url)}`);
        const m = modal("Frühere Fassungen im Internet Archive", list.length ? `<p class="small muted">Unterschiedliche Fassungen von <b>${esc(url)}</b>. „Sichern“ ruft die unveränderte Archivfassung über den Netzausgang des Falls ab und versiegelt sie als Beleg.</p>
          <table class="tbl small"><tr><th>Archiviert am</th><th>Typ</th><th></th></tr>${list.map((v) => `<tr><td>${esc(v.label)}</td><td>${esc(v.mimetype)}</td><td><button class="btn btn-sm btn-primary" data-wbts="${esc(v.timestamp)}">Sichern</button></td></tr>`).join("")}</table>`
          : '<div class="small muted">Das Internet Archive kennt keine Fassung dieser Adresse.</div>', '<button class="btn" data-close>Schließen</button>', { width: "560px" });
        $$("[data-wbts]", m.el).forEach((b) => (b.onclick = async () => {
          b.disabled = true; b.innerHTML = '<span class="spinner"></span>';
          try { const r = await api("POST", `/api/cases/${ov.case.id}/evidence`, { url, wayback_timestamp: b.dataset.wbts }); toast(`Archivfassung als ${evNo(r.id)} gesichert`, "ok"); b.textContent = "✓ gesichert"; }
          catch (err) { toast(err.message, "err"); b.disabled = false; b.textContent = "Sichern"; }
        }));
        m.el.addEventListener("click", (e) => { if (e.target.closest("[data-close]") && $$("[data-wbts][disabled]", m.el).length) renderCase(); });
      } catch (err) { toast(err.message, "err"); }
      wb.disabled = false;
    };
    const ed = $("#ev-doc", el);
    if (ed) ed.onchange = async () => {
      let ok = 0;
      for (const file of ed.files) {
        const fd = new FormData(); fd.append("file", file);
        try { const r = await api("POST", `/api/cases/${ov.case.id}/evidence/document`, fd); ok++; toast(`${file.name} als ${evNo(r.id)} importiert` + ((r.meta || {}).hinweis ? " – " + r.meta.hinweis : ""), "ok"); }
        catch (err) { toast(`${file.name}: ${err.message}`, "err"); }
      }
      if (ok) renderCase();
    };
    $$("[data-ev-verify]", el).forEach((b) => (b.onclick = async () => {
      b.disabled = true;
      try {
        const r = await api("GET", `/api/cases/${ov.case.id}/evidence/${b.dataset.evVerify}/verify`);
        const part = (v, t) => v === null ? "" : `${v ? "✓" : "✗"} ${t}`;
        toast(r.ok ? `${evNo(r.id)} unverändert: ${[part(r.original, "Original"), part(r.warc, "WARC"), part(r.wiedergabe, "Wiedergabe")].filter(Boolean).join(" · ")}` : `${evNo(r.id)}: ABWEICHUNG – ${r.message}`, r.ok ? "ok" : "err");
      } catch (err) { toast(err.message, "err"); }
      b.disabled = false;
    }));
    $$("[data-ev-del]", el).forEach((b) => (b.onclick = async () => {
      if (!(await confirmDlg(`Beleg ${evNo(b.dataset.evDel)} mit allen Dateien löschen? Die Prüfsumme bleibt im Protokoll.`))) return;
      await guard(() => api("DELETE", `/api/cases/${ov.case.id}/evidence/${b.dataset.evDel}`), "Beleg gelöscht"); renderCase();
    }));
    $$("[data-ev-text]", el).forEach((b) => (b.onclick = async () => {
      const t = await guard(() => api("GET", `/api/cases/${ov.case.id}/evidence/${b.dataset.evText}/text`));
      const METHOD = { ocr: "Texterkennung", pdf_text: "PDF-Text", docx: "Word", text: "Text", haupttext: "Haupttext der Seite", bild: "Bild ohne Text" };
      modal(`${evNo(t.evidence.id)} – Textfassung`, `<p class="small muted">Automatisch herausgelöster bzw. erkannter Text – Lesehilfe, kein Original. Maßgeblich ist die versiegelte Originaldatei.</p>
        ${t.mentions.length ? `<div class="ok-box small" style="margin-bottom:.6rem"><b>Im Text genannt (Hinweis, keine Bestätigung):</b> ${t.mentions.map((m) => `${esc(m.label)} – ${t.pages.length > 1 ? "Seite " + m.pages.join(", ") : "ja"}`).join(" · ")}</div>` : ""}
        ${t.pages.map((pg) => `<div class="doc-page"><div class="small muted">${t.pages.length > 1 ? "Seite " + pg.page + " · " : ""}${METHOD[pg.method] || esc(pg.method)}${pg.confidence != null ? ` · Erkennungssicherheit ${pg.confidence} %` : ""}</div><pre>${esc(pg.text || "(kein Text)")}</pre></div>`).join("")}`,
        '<button class="btn" data-close>Schließen</button>', { width: "820px" });
    }));
    const ea = $("#ev-all", el);
    if (ea) ea.onclick = async () => {
      ea.disabled = true; ea.innerHTML = '<span class="spinner dark"></span> sichere …';
      try { const r = await api("POST", `/api/cases/${ov.case.id}/evidence/confirmed`); toast(`${r.captured} Belege gesichert` + (r.errors.length ? `, ${r.errors.length} Fehler` : ""), r.errors.length ? "err" : "ok"); }
      catch (err) { toast(err.message, "err"); }
      renderCase();
    };
  }

  // ------------------------------------------------------------------ Tab: Fakten & Bewertung
  const SEV = { hoch: "b-red", mittel: "b-amber", niedrig: "b-grey" };
  const codeBadge = (f) => `<span class="badge adm adm-${f.credibility_final}" title="${esc(f.code_text)}">${esc(f.code)}</span>`;
  async function tabFacts(el, ov) {
    const a = await api("GET", `/api/cases/${ov.case.id}/assessment`);
    const canReview = ov.permissions.includes("review");
    const st = a.stats;
    const flt = state.factFilter || "aktiv";
    const shown = a.facts.filter((f) => flt === "alle" || (flt === "aktiv" ? f.status !== "verworfen" : f.status === flt));
    const cats = {};
    shown.forEach((f) => (cats[f.category] = cats[f.category] || []).push(f));
    const order = ["Risiko", "Identität", "Familie & Umfeld", "Beruf & Wirtschaft", "Online & Technik", "Sonstiges"];
    el.innerHTML = `
      ${help("Wie werden Aussagen bewertet?", [
        "Jede Aussage trägt einen <b>Admiralty-Code</b>: Buchstabe = Verlässlichkeit der Quelle (A amtlich … F nicht beurteilbar), Zahl = Glaubwürdigkeit der Information (1 bestätigt … 6 nicht beurteilbar).",
        "<b>1</b> = von mindestens zwei Quellen gestützt und bestätigt · <b>2</b> = wahrscheinlich (zwei Quellen oder bestätigte zuverlässige Quelle) · <b>3</b> = möglich · <b>4</b> = zweifelhaft (Widerspruch) · <b>5</b> = verworfen · <b>6</b> = noch nicht beurteilbar.",
        "<b>Widersprüche</b> entstehen, wenn eine Person zwei unvereinbare Werte hat (z. B. Geburtsjahre). Häufig steckt ein Namensvetter dahinter – Kandidatengruppen in „Suche & Treffer“ helfen beim Trennen.",
        "<b>Red Flags</b> sind regelbasierte Auffälligkeiten. Sie sind Hinweise für die Recherche, keine Bewertung der Person. Regeln verwaltet die Administration."], !a.facts.length)}
      <div class="grid g4" style="margin-bottom:1rem">
        <div class="kpi"><div class="v">${st.facts}</div><div class="k">Aussagen</div></div>
        <div class="kpi"><div class="v" style="color:var(--green)">${st.confirmed}</div><div class="k">bestätigt</div></div>
        <div class="kpi"><div class="v">${st.corroborated}</div><div class="k">mehrfach belegt</div></div>
        <div class="kpi"><div class="v" style="color:${st.contradictions ? "var(--red)" : "inherit"}">${st.contradictions}</div><div class="k">Widersprüche</div></div>
      </div>
      <div class="grid g2">
        <div class="card"><div class="card-head"><h2>🚩 Red Flags (${a.redflags.length})</h2></div>
          ${a.redflags.length ? a.redflags.map((r) => `<div class="flag"><span class="badge ${SEV[r.severity]}">${esc(r.severity)}</span> <b>${esc(r.label)}</b>${r.confirmed ? "" : ' <span class="badge b-grey" title="beruht (auch) auf ungeprüften Aussagen">ungeprüft</span>'}
            <div class="small">${esc(r.text)}</div>${r.sources.length ? `<div class="small muted">Quellen: ${r.sources.map(esc).join(", ")}</div>` : ""}</div>`).join("") : '<div class="small muted">Keine Auffälligkeiten nach den aktiven Regeln.</div>'}
          <h3 style="margin-top:1rem">🔗 Überschneidungen (${(a.correlations || []).length})</h3>
          <div class="small muted" style="margin-bottom:.3rem">Regeln finden gleiche Adressen, Firmen, E-Mail-Adressen oder Technik bei mehreren Einträgen. Das sind <b>Prüfhinweise</b>, keine Bewertung.</div>
          ${(a.correlations || []).map((c) => `<div class="flag"><span class="badge ${SEV[c.severity]}">${esc(c.severity)}</span> <b>${esc(c.label)}</b>${c.confirmed ? "" : ' <span class="badge b-grey" title="beruht (auch) auf ungeprüften Aussagen">ungeprüft</span>'}
            <div class="small">${esc(c.headline)}</div><div class="small muted">Quellen: ${c.sources.map(esc).join(", ")}</div></div>`).join("") || '<div class="small muted">Keine Überschneidungen nach den aktiven Regeln.</div>'}</div>
        <div class="card"><div class="card-head"><h2>⚖ Widersprüche (${a.contradictions.length})</h2></div>
          ${a.contradictions.length ? a.contradictions.map((c, ci) => `<div class="flag"><b>${esc(c.subject)}</b> – ${esc(c.predicate_label)}${c.profile_value ? ` <span class="small muted">(Profil: ${esc(c.profile_value)})</span>` : ""}
            ${c.values.map((v, vi) => `<div class="row small" style="margin-top:.3rem"><span class="grow"><b>${esc(v.value)}</b> ${v.matches_profile ? '<span class="badge b-green">passt zum Profil</span>' : ""}${v.confirmed ? ' <span class="badge b-blue">bestätigt</span>' : ""}<br><span class="muted">${v.sources.map(esc).join(", ")}</span></span>
              ${canReview ? `<button class="btn btn-sm" data-cx="${ci}:${vi}">Diesen Wert verwerfen</button>` : ""}</div>`).join("")}</div>`).join("") : '<div class="small muted">Keine widersprüchlichen Angaben.</div>'}</div>
      </div>
      <div class="card">
        <div class="card-head"><h2>Aussagen</h2><div class="right">${[["aktiv", "Aktiv"], ["neu", "Ungeprüft"], ["bestätigt", "Bestätigt"], ["verworfen", "Verworfen"], ["alle", "Alle"]].map(([k, l]) => `<button class="btn btn-sm ${flt === k ? "btn-primary" : ""}" data-ffl="${k}">${l}</button>`).join("")}</div></div>
        ${shown.length ? order.filter((c) => cats[c]).map((c) => `<h4 class="src-head">${esc(c)} (${cats[c].length})</h4><table class="tbl facts-tbl">
          <tr><th>Wer</th><th>Aussage</th><th>Wert</th><th>Zeitraum</th><th>Quellen</th><th>Bewertung</th><th></th></tr>
          ${cats[c].map((f) => `<tr class="fs-${esc(f.status)} ${f.contradiction ? "contra" : ""}"><td>${esc(f.subject_label)}</td><td class="muted">${esc(f.predicate_label)}</td>
            <td><b>${esc(f.object_label)}</b>${f.data && f.data.rolle ? ` <span class="muted">(${esc(f.data.rolle)})</span>` : ""}${f.note ? `<div class="small muted">📝 ${esc(f.note)}</div>` : ""}</td>
            <td class="small nowrap">${esc(f.valid_from || "")}${f.valid_to ? " – " + esc(f.valid_to) : ""}</td>
            <td class="small">${f.source_url ? `<a href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">${esc(f.source_label)}</a>` : esc(f.source_label)}${f.corroboration >= 2 ? ` <span class="badge b-green" title="${esc(f.sources.join(", "))}">${f.corroboration} unabhängige Quellen</span>` : ""}${f.same_origin ? ` <span class="badge b-amber" title="Mehrere Quellen geben (nahezu) denselben Text wieder – sie zählen als ein Ursprung. Siehe Dossier & Export → Quellenunabhängigkeit.">gleicher Ursprung</span>` : ""}</td>
            <td>${codeBadge(f)} <span class="small muted">${esc(f.status)}</span></td>
            <td class="nowrap">${canReview ? `${f.status !== "bestätigt" ? `<button class="btn btn-sm btn-success" data-fs="${f.id}:bestätigt" title="bestätigen">✓</button>` : ""}${f.status !== "verworfen" ? `<button class="btn btn-sm" data-fs="${f.id}:verworfen" title="verwerfen">✗</button>` : ""}<button class="btn btn-sm" data-fe="${f.id}" title="Bewertung ändern">✎</button>` : ""}</td></tr>`).join("")}</table>`).join("")
          : '<div class="empty small">Noch keine Aussagen. Sie entstehen aus Quellen der Suche (z. B. Register, Wikidata, Referenzdaten).</div>'}
      </div>`;
    $$("[data-ffl]", el).forEach((b) => (b.onclick = () => { state.factFilter = b.dataset.ffl; renderCase(); }));
    $$("[data-fs]", el).forEach((b) => (b.onclick = async () => {
      const [id, status] = b.dataset.fs.split(":");
      await guard(() => api("PATCH", `/api/cases/${ov.case.id}/facts/${id}`, { status }), status === "bestätigt" ? "Aussage bestätigt" : "Aussage verworfen"); renderCase();
    }));
    $$("[data-cx]", el).forEach((b) => (b.onclick = async () => {
      const [ci, vi] = b.dataset.cx.split(":").map(Number);
      for (const id of a.contradictions[ci].values[vi].fact_ids) await api("PATCH", `/api/cases/${ov.case.id}/facts/${id}`, { status: "verworfen", note: "Widerspruch aufgelöst" });
      toast("Wert verworfen", "ok"); renderCase();
    }));
    $$("[data-fe]", el).forEach((b) => (b.onclick = () => {
      const f = a.facts.find((x) => String(x.id) === b.dataset.fe);
      const m = modal("Bewertung ändern", `<p class="small"><b>${esc(f.subject_label)}</b> – ${esc(f.predicate_label)} – <b>${esc(f.object_label)}</b><br><span class="muted">${esc(f.source_label)}</span></p>
        <div class="grid g2"><label class="field"><span>Verlässlichkeit der Quelle</span><select id="fe-r">${Object.entries(a.legend.reliability).map(([k, v]) => opt(k, `${k} – ${v}`, f.reliability || "F")).join("")}</select></label>
        <label class="field"><span>Glaubwürdigkeit der Information</span><select id="fe-c">${opt(0, `automatisch (derzeit ${f.credibility_auto})`, f.credibility)}${Object.entries(a.legend.credibility).map(([k, v]) => opt(k, `${k} – ${v}`, f.credibility)).join("")}</select></label></div>
        <label class="field"><span>Begründung / Notiz</span><textarea id="fe-n">${esc(f.note || "")}</textarea></label>`,
        `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="fe-ok">Speichern</button>`);
      $("#fe-ok", m.el).onclick = async () => {
        await guard(() => api("PATCH", `/api/cases/${ov.case.id}/facts/${f.id}`, { reliability: $("#fe-r", m.el).value, credibility: Number($("#fe-c", m.el).value), note: $("#fe-n", m.el).value }), "Bewertung gespeichert");
        m.close(); renderCase();
      };
    }));
  }

  // ------------------------------------------------------------------ Tab: OPSEC
  async function tabOpsec(el, ov) {
    const [op, egress] = await Promise.all([api("GET", `/api/cases/${ov.case.id}/opsec`), api("GET", "/api/egress-profiles")]);
    const lv = op.level, c = ov.case, manage = ov.permissions.includes("manage");
    el.innerHTML = `
      ${help("Was bedeutet OPSEC hier?", [
        "<b>Operative Sicherheit</b> schützt die Recherche, die Recherchierenden und ihre Quellen: Die Zielperson soll nicht bemerken, dass recherchiert wird, und niemand soll auf Ihre Organisation oder Quellen schließen können.",
        "Die <b>OPSEC-Stufe</b> legt fest, welche Abfragen erlaubt sind und über welchen Netzausgang sie laufen. Die Regeln werden technisch durchgesetzt – fehlt der Anonymisierungs-Ausgang, wird blockiert statt direkt gesendet.",
        "Das <b>Außenkontakt-Protokoll</b> zeigt, welche Stellen welche Spuren dieser Recherche gesehen haben können.",
        "Das <b>Export-Register</b> ordnet jede Datei, die EagleEye verlassen hat, einer Person und einem Zeitpunkt zu."], false)}
      ${op.warnings.map((w) => `<div class="bad-box" style="margin-bottom:.6rem">⚠ ${esc(w)}</div>`).join("")}
      <div class="grid g2">
        <div class="card">
          <div class="card-head"><h2>Stufe</h2>${opsecBadge(lv.key)}${c.codename ? `<span class="badge b-grey">Deckname ${esc(c.codename)}</span>` : ""}
            <div class="right">${manage ? '<button class="btn btn-sm" id="op-level">Stufe ändern</button>' : ""}</div></div>
          <p class="small">${esc(lv.summary)}</p>
          <ul class="small rules">${lv.rules.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        </div>
        <div class="card">
          <div class="card-head"><h2>Netzausgang</h2></div>
          <p><b>${esc(op.profile.name)}</b> ${op.profile.kind === "direkt" ? '<span class="badge b-amber">nicht anonymisiert</span>' : '<span class="badge b-green">Proxy/Anonymisierung</span>'}</p>
          <p class="small muted">${esc(op.profile.notes || "")}</p>
          ${manage ? `<div class="row"><select id="op-egress" class="grow">${opt("", "Voreinstellung der Organisation", c.egress_profile)}${egress.map((e) => opt(e.id, e.name, c.egress_profile)).join("")}</select><button class="btn btn-sm btn-primary" id="op-egress-save">Übernehmen</button></div>` : ""}
          <p class="small muted" style="margin-top:.5rem">Ausgänge richtet die Administration unter Verwaltung → OPSEC ein (z. B. Tor über HTTP-Tunnel, VPN-Gateway, Recherche-Proxy). Bei Störung werden Abfragen blockiert, nie direkt gesendet.</p>
          <h3 style="margin-top:.8rem">Spuren in Zahlen</h3>
          <div class="grid g3"><div class="kpi"><div class="v">${op.totals.requests}</div><div class="k">Außenabfragen</div></div>
            <div class="kpi"><div class="v">${op.totals.hosts}</div><div class="k">kontaktierte Stellen</div></div>
            <div class="kpi"><div class="v" style="color:${op.totals.direct_requests && lv.key >= 2 ? "var(--red)" : "inherit"}">${op.totals.direct_requests}</div><div class="k">davon direkt</div></div></div>
        </div>
      </div>
      ${lv.briefing ? `<div class="card"><div class="card-head"><h2>OPSEC-Briefing</h2>${op.briefing_done ? '<span class="badge b-green">von Ihnen bestätigt</span>' : '<span class="badge b-red">noch nicht bestätigt</span>'}</div>
        <form id="op-brief">${op.briefing.map((b, i) => `<label class="check"><input type="checkbox" ${op.briefing_done ? "checked disabled" : ""} required data-b="${i}"> <span>${esc(b)}</span></label>`).join("")}
        ${op.briefing_done ? "" : '<button class="btn btn-primary" style="margin-top:.5rem">Alle Regeln gelesen und bestätigt</button>'}</form>
        <p class="small" style="margin-top:.6rem"><b>Bestätigt:</b> ${op.acks.map((a) => `${esc(a.display_name)} (${fmtTs(a.acked_at)})`).join(", ") || "–"}
        ${op.acks_missing.length ? `<br><b style="color:var(--red)">Fehlt noch:</b> ${op.acks_missing.map(esc).join(", ")}` : ""}</p></div>` : ""}
      <div class="card"><div class="card-head"><h2>Außenkontakt-Protokoll</h2><span class="right small muted">Welche Stellen haben Anfragen dieser Recherche gesehen?</span></div>
        ${op.hosts.length ? `<table class="tbl"><tr><th>Stelle (Host)</th><th>Exposition</th><th>Ausgang</th><th>Anfragen</th><th>Erste / letzte</th></tr>
          ${op.hosts.map((h) => `<tr><td><code>${esc(h.host)}</code></td><td>${expoBadge(h.exposure || "plattform")}</td><td>${esc(h.egress)}</td><td>${h.n}</td><td class="small">${fmtTs(h.first_ts)} / ${fmtTs(h.last_ts)}</td></tr>`).join("")}</table>
          <details style="margin-top:.6rem"><summary class="small">Letzte ${op.recent.length} Einzelanfragen anzeigen</summary><table class="tbl small"><tr><th>Zeit</th><th>Person</th><th>Quelle</th><th>Anfrage</th><th>Status</th></tr>
          ${op.recent.map((r) => `<tr><td class="nowrap">${fmtTs(r.ts)}</td><td>${esc(r.username)}</td><td>${esc(r.source)}</td><td><code>${esc(r.host)}${esc(r.path)}${r.query ? "?" + esc(r.query) : ""}</code></td><td>${r.status === -1 ? "Fehler" : r.status}</td></tr>`).join("")}</table></details>`
          : '<div class="small muted">Noch keine automatischen Außenabfragen in diesem Fall.</div>'}
        <p class="small muted" style="margin-top:.5rem">Manuell geöffnete Recherchelinks und Kartenkacheln laufen über Ihren Browser und erscheinen hier nicht.</p></div>
      <div class="card"><div class="card-head"><h2>Export-Register</h2><span class="right small muted">${op.can_export ? "Sie dürfen exportieren." : "Sie dürfen auf dieser Stufe nicht exportieren."}</span></div>
        ${op.exports.length ? `<table class="tbl"><tr><th>Export-ID</th><th>Art</th><th>Person</th><th>Zeit</th><th>SHA-256</th></tr>${op.exports.map((x) => `<tr><td><code>${esc(x.export_id)}</code></td><td>${esc(x.kind)}</td><td>${esc(x.username)}</td><td>${fmtTs(x.ts)}</td><td><code class="small">${esc((x.sha256 || "").slice(0, 16))}…</code></td></tr>`).join("")}</table>`
          : '<div class="small muted">Noch keine Exporte.</div>'}
        <p class="small muted" style="margin-top:.5rem">Taucht ein Dokument außerhalb des Teams auf, lässt es sich über die Export-ID (Fußzeile/Dateiname) bzw. den SHA-256-Hash zuordnen.</p></div>`;
    const bf = $("#op-brief", el);
    if (bf && !op.briefing_done) bf.onsubmit = async (e) => { e.preventDefault(); await guard(() => api("POST", `/api/cases/${c.id}/opsec/briefing`), "Briefing bestätigt"); renderCase(); };
    const es = $("#op-egress-save", el);
    if (es) es.onclick = async () => { await guard(() => api("PATCH", `/api/cases/${c.id}`, { egress_profile: $("#op-egress").value }), "Netzausgang übernommen"); renderCase(); };
    const lb = $("#op-level", el);
    if (lb) lb.onclick = () => {
      const m = modal("OPSEC-Stufe ändern", `<div class="type-cards">${[1, 2, 3].map((k) => `<button type="button" class="type-card ${k === lv.key ? "selected" : ""}" data-lvl="${k}">${opsecBadge(k)}<div class="small muted" style="margin-top:.3rem">${esc(state.meta.opsec_levels[k].summary)}</div></button>`).join("")}</div>
        <label class="field" style="margin-top:.8rem"><span>Begründung (Pflicht beim Absenken)</span><textarea id="lv-reason"></textarea></label>`,
        `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="lv-ok">Übernehmen</button>`);
      let sel = lv.key;
      $$("[data-lvl]", m.el).forEach((b) => (b.onclick = () => { sel = Number(b.dataset.lvl); $$("[data-lvl]", m.el).forEach((x) => x.classList.toggle("selected", x === b)); }));
      $("#lv-ok", m.el).onclick = async () => {
        try { await guard(() => api("PATCH", `/api/cases/${c.id}`, { opsec_level: sel, opsec_reason: $("#lv-reason", m.el).value }), "OPSEC-Stufe geändert"); } catch (_) { return; }
        m.close(); loadCases(); renderCase();
      };
    };
  }

  // ------------------------------------------------------------------ Tab: Protokoll
  async function tabAudit(el, ov) {
    const rows = await api("GET", `/api/cases/${ov.case.id}/audit`);
    el.innerHTML = `<div class="card"><div class="card-head"><h2>Bearbeitungsprotokoll</h2><span class="right small muted">Unveränderliche Aufzeichnung aller Arbeitsschritte (Nachvollziehbarkeit / DSGVO-Rechenschaft)</span></div>
      <table class="tbl"><tr><th>Zeit</th><th>Aktion</th><th>Details</th></tr>${rows.map((a) => `<tr><td class="nowrap">${fmtTs(a.ts)}</td><td class="nowrap"><b>${esc(a.action)}</b></td><td>${esc(a.detail)}</td></tr>`).join("")}</table></div>`;
  }

  // ------------------------------------------------------------------ Hilfe
  function openHelp() {
    modal("Hilfe & Kurzanleitung", `
      <h3>Arbeitsablauf</h3>
      <ol><li><b>Neuer Fall</b> – Fallart, Zweck und Rechtsgrundlage festlegen.</li>
        <li><b>Personen & Profile</b> – Zielperson und Identifikatoren erfassen, Foto hochladen, Recherchelinks nutzen.</li>
        <li><b>Suche & Treffer</b> – Quellen automatisch abfragen, Treffer prüfen (bestätigen/verwerfen).</li>
        <li><b>Verbindungen</b> – Netzwerk ansehen, Pfade zwischen Personen finden, Vorschläge übernehmen.</li>
        <li><b>Zeitleiste & Karte</b> – Sichtungen und Bewegungen erfassen (v. a. bei Vermisstenfällen).</li>
        <li><b>Dossier & Export</b> – Word-Dossier, Suchplakat, Grafik und Daten exportieren.</li></ol>
      <h3>Bewertung (Score)</h3>
      <p class="small">0–100 Punkte aus nachvollziehbaren Merkmalen: exakte E-Mail/Telefon (+55), Benutzername vorhanden (+35), Namensgleichheit (bis +40), Ort/Arbeitgeber/Geburtsjahr erwähnt (+10–15). Ab 75 = hoch, ab 45 = mittel. <b>Ein hoher Score ist kein Beweis.</b></p>
      <h3>Datenschutz & Ethik</h3>
      <ul class="small"><li>Recherchieren Sie nur mit legitimem Zweck und Rechtsgrundlage. Keine Recherche zur Belästigung, Verfolgung oder Diskriminierung.</li>
        <li>Alle Daten bleiben lokal auf diesem Rechner (${esc(state.meta.data_dir)}). Löschen Sie Fälle nach Abschluss.</li>
        <li>Bei Vermisstenfällen: Polizei informieren (Notruf 110). Keine eigenmächtigen Maßnahmen, die die Person oder Ermittlungen gefährden.</li></ul>
      <h3>OPSEC</h3>
      <ul class="small"><li>Jeder Fall hat eine <b>OPSEC-Stufe</b> (1 Standard · 2 Erhöht · 3 Streng). Die Regeln stehen im Reiter <b>🛡 OPSEC</b> und werden technisch durchgesetzt.</li>
        <li>Ab Stufe 2 laufen automatische Abfragen nur über einen Anonymisierungs-Ausgang; ist er gestört, wird <b>blockiert statt direkt gesendet</b>.</li>
        <li>Abzeichen <b>Passiv · Plattform · Sichtbar · Zielkontakt</b> zeigen, wer eine Abfrage bemerken kann. Recherchelinks öffnen sich in Ihrem Browser – nur in der getrennten Recherche-Umgebung nutzen.</li>
        <li>Jeder Export trägt eine <b>Export-ID</b>; Foto- und Dokument-Metadaten werden entfernt.</li></ul>
      <h3>Tastatur & Graph</h3>
      <p class="small"><b>Strg+Alt+L</b> sperrt sofort (Bildschirm leeren, abmelden). Esc schließt Dialoge. Im Graphen: Ziehen = verschieben, Mausrad = Zoom, Doppelklick = Knoten lösen.</p>
      <p class="small muted">Version ${esc(state.meta.version)} · API-Dokumentation: <a href="/api/docs" target="_blank">/api/docs</a></p>`, `<button class="btn btn-primary" data-close>Verstanden</button>`);
  }

  // ------------------------------------------------------------------ Anmeldung
  const LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="14" fill="#0f2a4a" stroke="#facc15" stroke-width="2"/><circle cx="16" cy="16" r="6" fill="#facc15"/><circle cx="16" cy="16" r="2.5" fill="#0f2a4a"/></svg>`;
  const PW_RULES = "Mind. 12 Zeichen und drei von: Kleinbuchstaben, Großbuchstaben, Ziffern, Sonderzeichen. Tipp: ein Satz aus mehreren Wörtern.";

  async function showAuth() {
    stopPresence();
    const st = await api("GET", "/api/auth/state");
    state.auth = st;
    if (st.authenticated && st.state === "ok") { $("#auth-root").classList.add("hidden"); $("#auth-root").innerHTML = ""; return startApp(); }
    const root = $("#auth-root");
    root.classList.remove("hidden");
    const card = (inner) => { root.innerHTML = `<div class="auth-card"><div class="brand-big">${LOGO}<span><b>EagleEye</b> PersonOSINT</span></div>${inner}</div>`; const f = $("input", root); if (f) f.focus(); };
    const fail = (e) => { const box = $("#auth-err", root); if (box) { box.textContent = e.message; box.classList.remove("hidden"); } };
    const errBox = '<div id="auth-err" class="bad-box hidden" style="margin-bottom:.7rem"></div>';

    if (st.setup_required) {
      card(`<h2>Ersteinrichtung</h2><p class="muted small">Legen Sie das erste Konto an. Es erhält die Rolle <b>Administration</b> und kann weitere Teammitglieder einladen.</p>${errBox}
        <form id="af">${st.setup_code_required ? `<label class="field"><span>Einrichtungscode</span><input name="setup_code" required autocomplete="off" placeholder="XXXX-XXXX-XXXX"><small>Schutz vor Fremdzugriff: Der Code steht im Server-Protokoll (Konsole bzw. „docker compose logs app“).</small></label>` : ""}
        <label class="field"><span>Benutzername</span><input name="username" autocomplete="username" required placeholder="z. B. m.sprenger"></label>
        <label class="field"><span>Anzeigename</span><input name="display_name" required placeholder="Vor- und Nachname"></label>
        <label class="field"><span>Passwort</span><input type="password" name="password" autocomplete="new-password" required></label><div class="pw-rules">${PW_RULES}</div>
        <label class="field"><span>Passwort wiederholen</span><input type="password" name="password2" autocomplete="new-password" required></label>
        <button class="btn btn-primary">Konto anlegen</button></form>`);
      $("#af", root).onsubmit = async (ev) => {
        ev.preventDefault(); const d = formData(ev.target);
        if (d.password !== d.password2) return fail(new Error("Die Passwörter stimmen nicht überein."));
        try { await api("POST", "/api/auth/setup", d); showAuth(); } catch (e) { fail(e); }
      };
      return;
    }
    if (!st.authenticated) {
      card(`<h2>Anmelden</h2><p class="muted small">Zugang nur für berechtigte Teammitglieder. Alle Anmeldungen werden protokolliert.</p>${errBox}
        <form id="af"><label class="field"><span>Benutzername</span><input name="username" autocomplete="username" required></label>
        <label class="field"><span>Passwort</span><input type="password" name="password" autocomplete="current-password" required></label>
        <button class="btn btn-primary">Anmelden</button></form>
        <p class="small muted" style="margin-top:1rem">Passwort vergessen? Die Administration kann es zurücksetzen.</p>`);
      $("#af", root).onsubmit = async (ev) => { ev.preventDefault(); try { await api("POST", "/api/auth/login", formData(ev.target)); showAuth(); } catch (e) { fail(e); } };
      return;
    }
    const logoutLink = '<p class="small" style="margin-top:1rem;text-align:center"><a href="#" id="af-out">Abmelden</a></p>';
    if (st.state === "mfa") {
      card(`<h2>Zwei-Faktor-Code</h2><p class="muted small">Hallo ${esc(st.user.display_name)}, bitte den 6-stelligen Code aus Ihrer Authenticator-App eingeben.</p>${errBox}
        <form id="af"><input name="code" class="code-input" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required placeholder="000000">
        <button class="btn btn-primary" style="margin-top:.8rem">Bestätigen</button></form>${logoutLink}`);
      $("#af", root).onsubmit = async (ev) => { ev.preventDefault(); try { await api("POST", "/api/auth/mfa", formData(ev.target)); showAuth(); } catch (e) { fail(e); if (e.status === 423) showAuth(); } };
    } else if (st.state === "password") {
      card(`<h2>Neues Passwort festlegen</h2><p class="muted small">Ihr Konto wurde mit einem Startpasswort angelegt bzw. zurückgesetzt. Bitte jetzt ein eigenes Passwort wählen.</p>${errBox}
        <form id="af"><label class="field"><span>Bisheriges Passwort</span><input type="password" name="old_password" autocomplete="current-password" required></label>
        <label class="field"><span>Neues Passwort</span><input type="password" name="new_password" autocomplete="new-password" required></label><div class="pw-rules">${PW_RULES}</div>
        <label class="field"><span>Neues Passwort wiederholen</span><input type="password" name="new_password2" autocomplete="new-password" required></label>
        <button class="btn btn-primary">Speichern</button></form>${logoutLink}`);
      $("#af", root).onsubmit = async (ev) => {
        ev.preventDefault(); const d = formData(ev.target);
        if (d.new_password !== d.new_password2) return fail(new Error("Die Passwörter stimmen nicht überein."));
        try { await api("POST", "/api/auth/password", d); toast("Passwort geändert", "ok"); showAuth(); } catch (e) { fail(e); }
      };
    } else if (st.state === "mfa_setup") {
      await totpSetup(card, fail, errBox, logoutLink, () => showAuth());
    }
    const out = $("#af-out", root); if (out) out.onclick = async (e) => { e.preventDefault(); await api("POST", "/api/auth/logout"); state.auth = null; showAuth(); };
  }

  async function totpSetup(card, fail, errBox, extra, done) {
    let s;
    try { s = await api("POST", "/api/auth/totp/begin"); } catch (e) { return toast(e.message, "err"); }
    card(`<h2>Zwei-Faktor-Anmeldung einrichten</h2>
      <ol class="small" style="padding-left:1.1rem"><li>Authenticator-App öffnen (z. B. Aegis, 2FAS, Google/Microsoft Authenticator).</li>
      <li>QR-Code scannen oder den Schlüssel manuell eingeben.</li><li>Den angezeigten 6-stelligen Code unten bestätigen.</li></ol>
      <div class="qr">${s.qr_svg || ""}</div><code class="secret">${esc(s.secret)}</code>${errBox}
      <form id="af"><input name="code" class="code-input" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required placeholder="000000">
      <button class="btn btn-primary" style="margin-top:.8rem">Aktivieren</button></form>${extra}`);
    $("#af").onsubmit = async (ev) => { ev.preventDefault(); try { await api("POST", "/api/auth/totp/confirm", formData(ev.target)); toast("Zwei-Faktor-Anmeldung aktiv", "ok"); done(); } catch (e) { fail(e); } };
  }

  async function renderBell() {
    if (!state.auth || !state.auth.authenticated) return;
    let n;
    try { n = await api("GET", "/api/notifications"); } catch (_) { return; }
    const box = $("#bell");
    box.innerHTML = `<button class="bell-btn" id="bell-btn" aria-label="Benachrichtigungen" title="Benachrichtigungen">🔔${n.unread ? `<span class="bell-count">${n.unread}</span>` : ""}</button>
      <div class="user-drop bell-drop hidden" id="bell-drop"><div class="who"><b>Benachrichtigungen</b>${n.unread ? ' · <a href="#" id="bell-all">alle gelesen</a>' : ""}</div>
      ${n.items.length ? n.items.map((x) => `<a href="${esc(x.link || "#")}" data-nid="${x.id}" class="${x.seen ? "" : "unseen"}"><span class="small muted">${fmtTs(x.ts)}</span><br>${x.kind === "warnung" ? "⚠ " : ""}${esc(x.text)}</a>`).join("") : '<div class="small muted" style="padding:.5rem .7rem">Keine Benachrichtigungen.</div>'}</div>`;
    const drop = $("#bell-drop");
    $("#bell-btn").onclick = (e) => { e.stopPropagation(); drop.classList.toggle("hidden"); };
    document.addEventListener("click", () => drop.classList.add("hidden"));
    $$("[data-nid]", drop).forEach((a) => (a.onclick = async () => { await api("POST", "/api/notifications/seen", { ids: [Number(a.dataset.nid)] }); setTimeout(renderBell, 300); }));
    const all = $("#bell-all"); if (all) all.onclick = async (e) => { e.preventDefault(); e.stopPropagation(); await api("POST", "/api/notifications/seen", {}); renderBell(); };
  }

  function renderUserMenu() {
    const u = state.auth.user;
    const initials = u.display_name.split(/\s+/).map((x) => x[0]).slice(0, 2).join("").toUpperCase();
    $("#user-menu").innerHTML = `<button class="user-btn" id="um-btn" aria-haspopup="true"><span class="av">${esc(initials)}</span><span class="nm">${esc(u.display_name)}</span></button>
      <div class="user-drop hidden" id="um-drop"><div class="who"><b>${esc(u.display_name)}</b><br><span class="muted">${esc(u.role_label)} · @${esc(u.username)}</span></div>
      <button id="um-lock">🔒 Sofort sperren <span class="small muted">(Strg+Alt+L)</span></button>
      <a href="#/account">🔑 Mein Konto & Sicherheit</a>${u.role === "admin" ? '<a href="#/admin/users">⚙️ Verwaltung</a>' : ""}
      <button id="um-out">⎋ Abmelden</button></div>`;
    const drop = $("#um-drop");
    $("#um-btn").onclick = (e) => { e.stopPropagation(); drop.classList.toggle("hidden"); };
    document.addEventListener("click", () => drop.classList.add("hidden"));
    $("#um-out").onclick = async () => { await api("POST", "/api/auth/logout"); state.auth = null; $("#bell").innerHTML = ""; location.hash = "#/"; showAuth(); };
    $("#um-lock").onclick = quickLock;
    $("#btn-new-case").classList.toggle("hidden", !state.auth.can_create_cases);
  }

  // ------------------------------------------------------------------ Mein Konto
  function renderAccount() {
    const u = state.auth.user;
    $("#main").innerHTML = `<h1>Mein Konto & Sicherheit</h1>
      <div class="grid g2">
        <div class="card"><h2>Passwort ändern</h2><form id="pw">
          <label class="field"><span>Bisheriges Passwort</span><input type="password" name="old_password" autocomplete="current-password" required></label>
          <label class="field"><span>Neues Passwort</span><input type="password" name="new_password" autocomplete="new-password" required><small>${PW_RULES}</small></label>
          <label class="field"><span>Wiederholen</span><input type="password" name="new_password2" autocomplete="new-password" required></label>
          <button class="btn btn-primary">Passwort ändern</button></form></div>
        <div class="card"><h2>Zwei-Faktor-Anmeldung</h2>
          <p>${u.totp_enabled ? '<span class="badge b-green">aktiv</span> Ihr Konto ist mit einem zweiten Faktor geschützt.' : '<span class="badge b-red">nicht eingerichtet</span>'}</p>
          <p class="small muted">Neues Smartphone? Richten Sie den Zugang hier neu ein – der alte Code wird dabei ungültig und andere Sitzungen werden beendet.</p>
          <button class="btn" id="re2fa">${u.totp_enabled ? "Neu einrichten" : "Jetzt einrichten"}</button>
          <h3 style="margin-top:1rem">Rolle</h3><p><b>${esc(u.role_label)}</b> – <span class="small muted">${esc(state.meta.role_help[u.role])}</span></p></div>
      </div>`;
    $("#pw").onsubmit = async (ev) => {
      ev.preventDefault(); const d = formData(ev.target);
      if (d.new_password !== d.new_password2) return toast("Die Passwörter stimmen nicht überein.", "err");
      await guard(() => api("POST", "/api/auth/password", d), "Passwort geändert"); ev.target.reset();
    };
    $("#re2fa").onclick = () => {
      const m = modal("Zwei-Faktor-Anmeldung einrichten", '<div id="m2fa"></div>');
      const card = (inner) => { $("#m2fa", m.el).innerHTML = inner; };
      const fail = (e) => { const b = $("#auth-err", m.el); if (b) { b.textContent = e.message; b.classList.remove("hidden"); } };
      totpSetup(card, fail, '<div id="auth-err" class="bad-box hidden" style="margin-bottom:.7rem"></div>', "", async () => { m.close(); state.auth = await api("GET", "/api/auth/state"); renderAccount(); });
    };
  }

  // ------------------------------------------------------------------ Verwaltung (Administration)
  async function renderAdmin(section) {
    if (state.auth.user.role !== "admin") { location.hash = "#/"; return; }
    const tabs = [["users", "👤 Benutzer"], ["sources", "📚 Quellen & Daten"], ["opsec", "🛡 OPSEC"], ["security", "🔐 Sicherheit & Protokoll"], ["backups", "💾 Sicherungen"], ["branding", "🎨 Berichtslayout"], ["ai", "🤖 KI-Assistent"], ["retention", "🗑 Löschfristen"], ["restricted", "🔒 Vertrauliche Fälle"]];
    $("#main").innerHTML = `<h1>Verwaltung</h1><div class="admin-tabs">${tabs.map(([k, l]) => `<a class="btn ${k === section ? "btn-primary" : ""}" href="#/admin/${k}">${l}</a>`).join("")}</div><div id="adm"></div>`;
    const el = $("#adm");
    if (section === "users") {
      const users = await api("GET", "/api/admin/users");
      el.innerHTML = `<div class="card"><div class="card-head"><h2>Benutzer (${users.length})</h2><div class="right"><button class="btn btn-primary" id="u-new">＋ Person einladen</button></div></div>
        <table class="tbl"><tr><th>Name</th><th>Rolle</th><th>2FA</th><th>Status</th><th>Letzte Anmeldung</th><th></th></tr>
        ${users.map((u) => `<tr><td><b>${esc(u.display_name)}</b><br><span class="small muted">@${esc(u.username)}</span></td><td>${esc(u.role_label)}</td>
          <td>${u.totp_enabled ? '<span class="badge b-green">aktiv</span>' : '<span class="badge b-amber">fehlt</span>'}</td>
          <td>${u.active ? (u.locked_until && new Date(u.locked_until) > new Date() ? '<span class="badge b-red">gesperrt</span>' : '<span class="badge b-green">aktiv</span>') : '<span class="badge b-grey">deaktiviert</span>'}${u.must_change_password ? ' <span class="badge b-blue">Startpasswort</span>' : ""}</td>
          <td class="small">${u.last_login ? fmtTs(u.last_login) : "–"}</td><td><button class="btn btn-sm" data-u="${u.id}">Bearbeiten</button></td></tr>`).join("")}</table>
        <h3 style="margin-top:1rem">Rollen</h3><ul class="small">${Object.entries(state.meta.roles).map(([k, l]) => `<li><b>${esc(l)}</b>: ${esc(state.meta.role_help[k])}</li>`).join("")}</ul></div>`;
      $("#u-new").onclick = () => {
        const m = modal("Person einladen", `<form id="un">
          <div class="grid g2"><label class="field"><span>Benutzername</span><input name="username" required placeholder="z. B. a.mueller"></label>
          <label class="field"><span>Anzeigename</span><input name="display_name" required></label></div>
          <label class="field"><span>Rolle</span><select name="role">${Object.entries(state.meta.roles).map(([k, l]) => opt(k, l, "analyst")).join("")}</select></label>
          <label class="field"><span>Startpasswort</span><input name="password" required value="${esc(genPassword())}"><small>Wird bei der ersten Anmeldung geändert. Bitte auf sicherem Weg übermitteln (nicht per unverschlüsselter E-Mail).</small></label></form>`,
          `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="un-save">Anlegen</button>`);
        $("#un-save", m.el).onclick = async () => { await guard(() => api("POST", "/api/admin/users", formData($("#un", m.el))), "Person angelegt"); m.close(); renderAdmin("users"); };
      };
      $$("[data-u]", el).forEach((b) => (b.onclick = () => {
        const u = users.find((x) => String(x.id) === b.dataset.u);
        const m = modal(`${u.display_name} bearbeiten`, `<form id="ue">
          <label class="field"><span>Anzeigename</span><input name="display_name" value="${esc(u.display_name)}"></label>
          <label class="field"><span>Rolle</span><select name="role">${Object.entries(state.meta.roles).map(([k, l]) => opt(k, l, u.role)).join("")}</select></label>
          <label class="check"><input type="checkbox" name="active" ${u.active ? "checked" : ""}> <span>Konto aktiv</span></label>
          <label class="check"><input type="checkbox" name="unlock"> <span>Sperre nach Fehlversuchen aufheben</span></label>
          <label class="check"><input type="checkbox" name="reset_2fa"> <span>Zwei-Faktor zurücksetzen (z. B. Smartphone verloren)</span></label>
          <label class="field"><span>Neues Startpasswort (optional)</span><input name="new_password" placeholder="leer lassen = unverändert"></label>
          <p class="small muted">Rollenwechsel, Deaktivierung, 2FA- oder Passwort-Reset beenden alle Sitzungen der Person sofort.</p></form>`,
          `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="ue-save">Speichern</button>`);
        $("#ue-save", m.el).onclick = async () => {
          const f = $("#ue", m.el), d = formData(f);
          const payload = { display_name: d.display_name, role: d.role, active: f.active.checked };
          if (f.unlock.checked) payload.unlock = true;
          if (f.reset_2fa.checked) payload.reset_2fa = true;
          if (d.new_password) payload.new_password = d.new_password;
          await guard(() => api("PATCH", `/api/admin/users/${u.id}`, payload), "Gespeichert"); m.close(); renderAdmin("users");
        };
      }));
    } else if (section === "security") {
      const [sys, audit] = await Promise.all([api("GET", "/api/admin/system"), api("GET", "/api/admin/audit?limit=200")]);
      el.innerHTML = `<div class="grid g2"><div class="card"><h2>System</h2><table class="tbl">
          <tr><td>Version</td><td>${esc(sys.version)} (Schema ${sys.schema_version})</td></tr><tr><td>Datenbank</td><td>${esc(sys.database)} · <span class="small">${esc(sys.database_target)}</span></td></tr>
          <tr><td>Datenordner</td><td class="small">${esc(sys.data_dir)}</td></tr><tr><td>Schlüsseldatei</td><td class="small">${esc(sys.key_file)}</td></tr>
          <tr><td>2FA Pflicht</td><td>${sys.require_2fa ? "ja" : "nein"}</td></tr><tr><td>Secure-Cookies</td><td>${sys.cookie_secure ? "ja" : "nein"}</td></tr>
          <tr><td>Aktive Sitzungen</td><td>${sys.active_sessions}</td></tr><tr><td>Benutzer / Fälle</td><td>${sys.users} / ${sys.cases}</td></tr></table>
          ${sys.warnings.length ? `<div class="warn" style="margin-top:.8rem"><b>Hinweise</b><ul class="small">${sys.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : '<div class="ok-box" style="margin-top:.8rem">Keine Konfigurationshinweise.</div>'}</div>
        <div class="card"><h2>Manipulationsschutz des Protokolls</h2><p class="small muted">Jeder Protokolleintrag enthält den Hash seines Vorgängers. Wird ein Eintrag verändert, gelöscht oder eingefügt, schlägt die Prüfung fehl. Inhalte gelöschter Fälle werden geschwärzt, ohne die Kette zu brechen.</p>
          <button class="btn btn-primary" id="verify">Protokoll jetzt prüfen</button><div id="vres" style="margin-top:.7rem"></div></div></div>
        <div class="card"><h2>Gesamtprotokoll (letzte 200 Einträge)</h2><table class="tbl"><tr><th>Zeit</th><th>Person</th><th>Fall</th><th>Aktion</th><th>Details</th></tr>
          ${audit.map((a) => `<tr><td class="nowrap small">${fmtTs(a.ts)}</td><td>${esc(a.username)}</td><td class="small">${esc(a.reference || "")}</td><td><b>${esc(a.action)}</b></td><td class="small">${esc(a.detail)}</td></tr>`).join("")}</table></div>`;
      $("#verify").onclick = async () => {
        const r = await guard(() => api("GET", "/api/admin/audit/verify"));
        $("#vres").innerHTML = r.ok ? `<div class="ok-box">✓ Intakt – ${r.entries} Einträge geprüft (${r.redacted} geschwärzt).<br><span class="small">Kopf-Hash: <code>${esc(r.head)}</code></span></div>`
          : `<div class="bad-box"><b>⚠ Protokoll verändert!</b><br>Eintrag #${r.broken_at} (${fmtTs(r.ts)}): ${esc(r.problem)}</div>`;
      };
    } else if (section === "ai") {
      const a = await api("GET", "/api/admin/ai");
      el.innerHTML = `<div class="card"><h2>Lokaler KI-Assistent</h2>
        <p class="small muted">Für Dossier-Zusammenfassungen. Erlaubt sind nur Dienste auf diesem Rechner oder im internen Netz (z. B. <b>Ollama</b>) – Falldaten verlassen die Organisation nicht und werden nie über Proxy/Tor gesendet.
        Docker: <code>docker compose --profile ki up -d</code>, danach <code>docker compose exec ollama ollama pull llama3.1:8b</code> und hier <code>http://ollama:11434</code> eintragen.</p>
        <form id="aif"><div class="grid g2"><label class="field"><span>Adresse des Dienstes</span><input name="url" value="${esc(a.url)}" placeholder="http://127.0.0.1:11434"></label>
          <label class="field"><span>Modell</span><input name="model" value="${esc(a.model)}" list="ai-models" placeholder="z. B. llama3.1:8b"><datalist id="ai-models"></datalist></label></div>
          <label class="check"><input type="checkbox" name="enabled" ${a.enabled ? "checked" : ""}> <span>KI-Assistent aktivieren</span></label>
          <div class="row" style="margin-top:.5rem"><button class="btn btn-primary">Speichern</button><button type="button" class="btn" id="ai-test">Verbindung testen</button></div></form>
        <div id="ai-res" style="margin-top:.6rem"></div></div>`;
      $("#aif").onsubmit = async (e) => { e.preventDefault(); const f = e.target, d = formData(f); d.enabled = f.enabled.checked; await guard(() => api("PUT", "/api/admin/ai", d), "Gespeichert"); renderAdmin("ai"); };
      $("#ai-test").onclick = async () => {
        const r = await guard(() => api("POST", "/api/admin/ai/test", { url: $("#aif input[name=url]").value }));
        $("#ai-res").innerHTML = r.ok ? `<div class="ok-box small">✓ erreichbar – Modelle: ${r.models.map(esc).join(", ") || "keine geladen"}</div>` : `<div class="bad-box small">${esc(r.error)}</div>`;
        if (r.ok) $("#ai-models").innerHTML = r.models.map((m) => `<option value="${esc(m)}">`).join("");
      };
    } else if (section === "branding") {
      const b = await api("GET", "/api/admin/branding");
      el.innerHTML = `<div class="grid g2"><div class="card"><h2>Berichtslayout</h2><p class="small muted">Gilt für alle Dossiers (Word/PDF): Kopfzeile, Überschriftenfarbe, Fußzeile, Logo auf dem Deckblatt und Hinweistext im Kapitel Methodik.</p>
        <form id="br">
          <label class="field"><span>Name der Organisation (Kopfzeile)</span><input name="org_name" value="${esc(b.org_name || "")}" placeholder="z. B. Recherchebüro Nord"></label>
          <label class="field"><span>Fußzeile</span><input name="footer" value="${esc(b.footer || "")}" placeholder="Firma · Anschrift · Kontakt"></label>
          <label class="field"><span>Akzentfarbe (Überschriften)</span><input name="color" type="color" value="${esc(b.color || "#0f2a4a")}" style="width:90px;height:38px;padding:2px"></label>
          <label class="field"><span>Hinweis / Haftungsausschluss</span><textarea name="disclaimer" placeholder="z. B. Dieses Dossier beruht auf öffentlich zugänglichen Quellen …">${esc(b.disclaimer || "")}</textarea></label>
          <button class="btn btn-primary">Speichern</button></form></div>
        <div class="card"><h2>Logo</h2>${b.has_logo ? `<img src="/api/branding/logo?${Date.now()}" alt="Logo" style="max-width:100%;max-height:120px;border:1px solid var(--line);border-radius:8px;padding:.5rem;background:#fff">` : '<div class="muted small">Kein Logo hinterlegt.</div>'}
          <div class="row" style="margin-top:.6rem"><label class="btn btn-sm">⬆ Logo hochladen (PNG/JPG)<input type="file" id="br-logo" accept="image/png,image/jpeg" hidden></label>
          ${b.has_logo ? '<button class="btn btn-sm btn-danger" id="br-del">Entfernen</button>' : ""}</div>
          <p class="small muted">Metadaten des Bildes werden entfernt; das Logo wird auf max. 1200×400 Pixel verkleinert.</p></div></div>`;
      $("#br").onsubmit = async (e) => { e.preventDefault(); await guard(() => api("PUT", "/api/admin/branding", formData(e.target)), "Gespeichert"); renderAdmin("branding"); };
      $("#br-logo").onchange = async (e) => { const fd = new FormData(); fd.append("file", e.target.files[0]); await guard(() => api("POST", "/api/admin/branding/logo", fd), "Logo gespeichert"); renderAdmin("branding"); };
      const bd = $("#br-del"); if (bd) bd.onclick = async () => { await guard(() => api("DELETE", "/api/admin/branding/logo"), "Logo entfernt"); renderAdmin("branding"); };
    } else if (section === "backups") {
      const [list, sys] = await Promise.all([api("GET", "/api/admin/backups"), api("GET", "/api/admin/system")]);
      el.innerHTML = `<div class="card"><div class="card-head"><h2>Sicherungen</h2><div class="right"><button class="btn btn-primary" id="bk-now">💾 Jetzt sichern</button></div></div>
        <p class="small muted">Verschlüsselte Komplettsicherung (alle Fälle, Benutzer, Protokoll, Fotos) nach <code>${esc(sys.backup_dir)}</code>.
        ${sys.backup_hour ? `Automatisch täglich um ${esc(sys.backup_hour)} Uhr, die letzten ${sys.backup_keep} werden behalten.` : "Keine automatische Sicherung eingerichtet (EAGLEEYE_BACKUP_HOUR)."}
        ${sys.backup_passphrase ? "Geschützt mit Passphrase." : "Geschützt mit dem Anwendungsschlüssel – Schlüsseldatei getrennt aufbewahren!"}
        Wiederherstellen per Kommandozeile: <code>python -m personosint restore DATEI</code>.</p>
        <table class="tbl"><tr><th>Datei</th><th>Größe</th><th>Erstellt</th><th></th></tr>
        ${list.map((b) => `<tr><td><code>${esc(b.name)}</code></td><td>${Math.round(b.size / 1024)} KB</td><td>${fmtTs(b.created_at)}</td><td><a class="btn btn-sm" href="/api/admin/backups/${encodeURIComponent(b.name)}">⬇ Herunterladen</a></td></tr>`).join("") || '<tr><td colspan="4" class="muted">Noch keine Sicherung.</td></tr>'}</table></div>`;
      $("#bk-now").onclick = async (ev) => {
        ev.target.disabled = true; ev.target.innerHTML = '<span class="spinner"></span> Sichere …';
        try { const r = await guard(() => api("POST", "/api/admin/backups")); toast(`Sicherung erstellt und geprüft (${r.tables.cases} Fälle)`, "ok"); } catch (_) { /* gemeldet */ }
        renderAdmin("backups");
      };
    } else if (section === "sources") {
      const d = await api("GET", "/api/admin/sources");
      const groups = {};
      d.sources.filter((x) => !x.local).forEach((x) => (groups[x.group] = groups[x.group] || []).push(x));
      const HL = { ok: ["b-green", "✓ liefert Treffer"], leer: ["b-blue", "○ erreichbar, kein Treffer"], fehler: ["b-red", "✗ Fehler"], nicht_pruefbar: ["b-grey", "– nicht prüfbar"] };
      const healthBadge = (h) => h ? `<span class="badge ${HL[h.state][0]}" title="${esc(`Testabfrage ${h.query} · geprüft ${fmtTs(h.checked_at)}${h.message ? " · " + h.message : ""}`)}">${HL[h.state][1]}${h.state === "ok" ? " (" + h.count + ")" : ""}</span>`
        : '<span class="badge b-grey" title="Auf dieser Installation noch nie geprüft">noch nicht geprüft</span>';
      const checked = d.sources.filter((x) => x.health), okN = checked.filter((x) => x.health.state === "ok").length, errN = checked.filter((x) => x.health.state === "fehler").length;
      el.innerHTML = `<div class="card"><div class="card-head"><h2>🩺 Quellen-Prüfung</h2><div class="right"><button class="btn btn-primary" id="src-check">Alle Quellen prüfen</button>
          <a class="btn" href="/api/admin/sources/report.md">⬇ Prüfbericht</a></div></div>
        <p class="small muted">Ruft jede Quelle einmal mit einer unkritischen Testabfrage über den Standard-Netzausgang auf und zeigt, welche Quellen <b>auf diesem Rechner wirklich antworten</b>. Dauert 1–3 Minuten; es wird nichts in Fälle geschrieben.</p>
        <div id="src-check-res" class="small">${checked.length ? `Letzte Prüfung: <b>${okN}</b> von ${d.sources.length} Quellen liefern Treffer${errN ? `, <b style="color:var(--red)">${errN} mit Fehler</b>` : ""}.` : "Noch keine Prüfung auf dieser Installation – bis dahin ist offen, welche Quellen antworten."}</div></div>
      <div class="card"><div class="card-head"><h2>Online-Quellen (${d.sources.filter((x) => !x.local).length})</h2><span class="right small muted">Schlüssel werden verschlüsselt gespeichert und nie angezeigt.</span></div>
        ${Object.entries(groups).map(([g, list]) => `<h4 class="src-head">${esc(g)}</h4><table class="tbl"><tr><th>Quelle</th><th>Exposition</th><th>Verlässlichkeit</th><th>Lizenz / Kosten</th><th>Schlüssel</th><th></th></tr>
          ${list.map((x) => `<tr><td><b>${esc(x.label)}</b><br><span class="small muted">${esc(x.description)}</span>
            <br><span class="small" title="Womit kann diese Quelle suchen – und welche neuen Kennungen können ihre Treffer liefern (Grundlage der Folgesuchen)?"><span class="muted">verarbeitet:</span> ${x.kind_labels.map(esc).join(", ")}${x.produces_labels.length ? ` · <span class="muted">liefert:</span> ${x.produces_labels.map(esc).join(", ")}` : ""}</span>${x.docs ? `<br><a class="small" href="${esc(x.docs)}" target="_blank" rel="noopener noreferrer">Dokumentation ↗</a>` : ""}</td>
            <td>${expoBadge(x.exposure)}<br>${healthBadge(x.health)}</td><td>${relBadge(x.reliability)}</td><td class="small">${esc(x.license)}<br><span class="muted">${esc(x.cost)}</span></td>
            <td>${x.requires_key ? (x.key_set ? '<span class="badge b-green">hinterlegt</span>' : x.key_optional ? '<span class="badge b-amber">optional</span>' : '<span class="badge b-red">fehlt</span>') : '<span class="muted small">nicht nötig</span>'}</td>
            <td class="nowrap">${x.requires_key ? `<button class="btn btn-sm" data-key="${esc(x.key)}">Schlüssel …</button> ` : ""}<button class="btn btn-sm" data-test="${esc(x.key)}">Testen</button></td></tr>
            <tr class="hidden" id="st-${esc(x.key)}"><td colspan="6"></td></tr>`).join("")}</table>`).join("")}</div>
        <div class="card"><div class="card-head"><h2>Lokale Referenzdatenbanken</h2><div class="right"><button class="btn btn-sm" id="rd-refresh">↻ Aktualisieren</button></div></div>
          <p class="small muted">Massendaten werden einmal importiert und danach <b>offline</b> durchsucht – Abfragen verlassen den Server nicht (Exposition „Lokal“), ohne Limits.
          Große Dateien besser per Kommandozeile importieren: <code>python -m personosint import-refdata NAME DATEI</code>.</p>
          <div class="grid g3">${d.datasets.map((x) => `<div class="kpi"><b>${esc(x.label)}</b> ${x.status === "bereit" ? '<span class="badge b-green">bereit</span>' : x.status === "fehler" ? '<span class="badge b-red">Fehler</span>' : x.status === "leer" ? '<span class="badge b-grey">leer</span>' : `<span class="badge b-amber"><span class="spinner dark"></span> ${esc(x.status)}</span>`}
            <div class="small muted" style="margin:.3rem 0">${esc(x.description)}</div>
            <div class="small">${x.records ? `<b>${x.records.toLocaleString("de-DE")}</b> Einträge${x.links ? `, ${x.links.toLocaleString("de-DE")} Verknüpfungen` : ""} · ${fmtTs(x.imported_at)}` : "noch nicht importiert"}</div>
            ${x.message && x.status !== "bereit" ? `<div class="small" style="color:${x.status === "fehler" ? "var(--red)" : "inherit"}">${esc(x.message)}</div>` : ""}
            <div class="small muted" style="margin-top:.3rem">Lizenz: ${esc(x.license)}<br>Datei: ${esc(x.file_hint)}</div>
            <div class="row" style="margin-top:.5rem">${x.url ? `<button class="btn btn-sm btn-primary" data-dl="${esc(x.name)}">⬇ Herunterladen & importieren</button>` : ""}
              <label class="btn btn-sm">⬆ Datei importieren<input type="file" data-up="${esc(x.name)}" hidden></label>
              ${x.records ? `<button class="btn btn-sm btn-danger" data-rdel="${esc(x.name)}">Löschen</button>` : ""}</div></div>`).join("")}</div></div>`;
      const rules = await api("GET", "/api/admin/redflag-rules");
      el.insertAdjacentHTML("beforeend", `<div class="card"><div class="card-head"><h2>🚩 Red-Flag-Regeln</h2><div class="right"><button class="btn btn-sm btn-primary" id="rf-save">Speichern</button></div></div>
        <p class="small muted">Regeln markieren Auffälligkeiten in den Aussagen eines Falls (Reiter „Fakten & Bewertung“) und im Dossier. Sie sind Recherchehinweise, keine Bewertung der Person.</p>
        <table class="tbl"><tr><th>Regel</th><th>aktiv</th><th>Schweregrad</th></tr>${Object.entries(rules).map(([k, r]) => `<tr><td>${esc(r.label)}</td>
          <td><input type="checkbox" data-rf-on="${k}" ${r.enabled ? "checked" : ""} style="width:auto"></td>
          <td><select data-rf-sev="${k}" style="width:auto">${["hoch", "mittel", "niedrig"].map((x) => opt(x, x, r.severity)).join("")}</select></td></tr>`).join("")}</table></div>`);
      $("#src-check").onclick = async (ev) => {
        const b = ev.currentTarget; b.disabled = true; b.innerHTML = '<span class="spinner"></span> prüfe … (1–3 Minuten)';
        try {
          const r = await api("POST", "/api/admin/sources/check", {});
          toast(`Prüfung fertig: ${r.summary.ok} liefern Treffer, ${r.summary.leer} ohne Treffer, ${r.summary.fehler} Fehler, ${r.summary.nicht_pruefbar} nicht prüfbar`, r.summary.fehler ? "err" : "ok");
        } catch (err) { toast(err.message, "err"); }
        renderAdmin("sources");
      };
      const [cr, comp] = await Promise.all([api("GET", "/api/admin/correlation-rules"), api("GET", "/api/components")]);
      const crCard = (data) => `<div class="card-head"><h2>🔗 Korrelationsregeln</h2></div>
        <p class="small muted">Regeln finden Überschneidungen zwischen Aussagen (Reiter „Fakten & Bewertung“). Sie erzeugen nur <b>Prüfhinweise</b>. Eigene Regeln werden als Beschreibung angelegt – ohne Programmierung.</p>
        <table class="tbl"><tr><th>Regel</th><th>Aussagearten</th><th>Schwelle</th><th>aktiv</th><th></th></tr>${data.rules.map((r) => `<tr><td><b>${esc(r.label)}</b> <span class="badge ${SEV[r.severity]}">${esc(r.severity)}</span>${r.builtin ? "" : ' <span class="badge b-blue">eigene</span>'}<br><span class="small muted">${esc(r.headline)}</span></td>
          <td class="small">${r.predicates.map((k) => esc(data.predicates[k] || k)).join(", ")}</td><td class="small nowrap">ab ${r.min} ${esc({ subjects: "Einträgen", values: "Werten", sources: "Quellen", facts: "Aussagen" }[r.count])}</td>
          <td><input type="checkbox" data-cr-on="${esc(r.key)}" ${r.enabled ? "checked" : ""} style="width:auto"></td>
          <td>${r.builtin ? "" : `<button class="btn btn-sm btn-danger" data-cr-del="${esc(r.key)}">×</button>`}</td></tr>`).join("")}</table>
        <details style="margin-top:.6rem"><summary class="small">＋ Eigene Regel anlegen</summary>
          <p class="small muted">Felder: <code>key</code>, <code>label</code>, <code>severity</code> (hoch/mittel/niedrig), <code>predicates</code>, <code>group_by</code> (object = gleicher Wert, subject = gleiche Person/Firma),
          <code>count</code> (subjects/values/sources/facts), <code>min</code>, <code>headline</code> mit {count}, {value}, {members}. Aussagearten: ${Object.keys(data.predicates).map(esc).join(", ")}.</p>
          <textarea id="cr-json" rows="9" style="font-family:monospace;font-size:.8rem">${esc(JSON.stringify({ ...data.example, key: "meine_regel", label: "Meine Regel" }, null, 2))}</textarea>
          <button class="btn btn-sm btn-primary" id="cr-save" style="margin-top:.4rem">Regel speichern</button></details>`;
      el.insertAdjacentHTML("beforeend", `<div class="card" id="cr-card">${crCard(cr)}</div>
        <div class="card"><h2>🧩 Bausteine auf diesem Server</h2>
          <table class="tbl small"><tr><td><b>Texterkennung (OCR)</b> für gescannte Dokumente</td><td>${comp.ocr.available ? `<span class="badge b-green">aktiv</span> ${esc(comp.ocr.engine)} · Sprachen: ${comp.ocr.languages.map(esc).join(", ")}` : '<span class="badge b-amber">nicht installiert</span>'}${comp.ocr.hint ? `<br><span class="muted">${esc(comp.ocr.hint)}</span>` : ""}</td></tr>
          <tr><td><b>WARC-Aufzeichnung</b> von Web-Belegen</td><td>${comp.warc ? `<span class="badge b-green">aktiv</span> ${esc(comp.warc)}` : '<span class="badge b-amber">nicht installiert</span> <span class="muted">Belege werden ohne WARC gesichert.</span>'}</td></tr>
          <tr><td><b>Haupttext-Erkennung</b> (ohne Menü/Werbung)</td><td>${comp.haupttext ? `<span class="badge b-green">aktiv</span> ${esc(comp.haupttext)}` : '<span class="badge b-amber">nicht installiert</span> <span class="muted">Es wird der einfache Seitentext verwendet.</span>'}</td></tr></table></div>`);
      const wireCr = () => {
        const card = $("#cr-card");
        $$("[data-cr-on]", card).forEach((c) => (c.onchange = async () => { const d2 = await guard(() => api("POST", `/api/admin/correlation-rules/${c.dataset.crOn}/enabled`, { enabled: c.checked }), "Gespeichert"); card.innerHTML = crCard({ ...cr, rules: d2.rules }); wireCr(); }));
        $$("[data-cr-del]", card).forEach((b) => (b.onclick = async () => { if (!(await confirmDlg("Regel löschen?"))) return; const d2 = await guard(() => api("DELETE", `/api/admin/correlation-rules/${b.dataset.crDel}`), "Regel gelöscht"); card.innerHTML = crCard({ ...cr, rules: d2.rules }); wireCr(); }));
        $("#cr-save", card).onclick = async () => {
          let rule;
          try { rule = JSON.parse($("#cr-json", card).value); } catch (_) { return toast("Die Regel ist kein gültiges JSON – bitte Klammern und Anführungszeichen prüfen.", "err"); }
          const d2 = await guard(() => api("PUT", "/api/admin/correlation-rules", rule), "Regel gespeichert"); card.innerHTML = crCard({ ...cr, rules: d2.rules }); wireCr();
        };
      };
      wireCr();
      $("#rf-save").onclick = async () => {
        const payload = {};
        Object.keys(rules).forEach((k) => (payload[k] = { enabled: $(`[data-rf-on="${k}"]`).checked, severity: $(`[data-rf-sev="${k}"]`).value }));
        await guard(() => api("PUT", "/api/admin/redflag-rules", payload), "Regeln gespeichert");
      };
      $("#rd-refresh").onclick = () => renderAdmin("sources");
      $$("[data-key]", el).forEach((b) => (b.onclick = () => {
        const src = d.sources.find((x) => x.key === b.dataset.key);
        const m = modal(`API-Schlüssel: ${src.label}`, `<p class="small">${esc(src.key_help || "")}</p>
          <label class="field"><span>Schlüssel</span><input id="k-val" type="password" autocomplete="off" placeholder="${src.key_set ? "•••••• (hinterlegt – zum Ersetzen neu eingeben)" : ""}"></label>`,
          `${src.key_set ? '<button class="btn btn-danger" id="k-del" style="margin-right:auto">Entfernen</button>' : ""}<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="k-save">Speichern</button>`);
        $("#k-save", m.el).onclick = async () => { await guard(() => api("PUT", `/api/admin/sources/${src.key}/key`, { key: $("#k-val", m.el).value }), "Schlüssel gespeichert"); m.close(); renderAdmin("sources"); };
        const del = $("#k-del", m.el); if (del) del.onclick = async () => { await guard(() => api("PUT", `/api/admin/sources/${src.key}/key`, { key: "" }), "Schlüssel entfernt"); m.close(); renderAdmin("sources"); };
      }));
      $$("[data-test]", el).forEach((b) => (b.onclick = async () => {
        const row = $(`#st-${CSS.escape(b.dataset.test)}`); row.classList.remove("hidden");
        row.firstElementChild.innerHTML = '<span class="spinner dark"></span> Testabfrage über den Standard-Netzausgang …';
        try {
          const r = await api("POST", `/api/admin/sources/${b.dataset.test}/test`);
          row.firstElementChild.innerHTML = r.ok ? `<div class="ok-box small">✓ erreichbar – ${r.count} Treffer, ${r.claims} Aussagen (${r.seconds} s)${r.sample && r.sample.length ? "<br>" + r.sample.map(esc).join("<br>") : ""}</div>` : `<div class="bad-box small">✗ ${esc(r.message)}</div>`;
        } catch (e) { row.firstElementChild.innerHTML = `<div class="bad-box small">${esc(e.message)}</div>`; }
      }));
      $$("[data-dl]", el).forEach((b) => (b.onclick = async () => {
        if (!(await confirmDlg("Gesamtdaten herunterladen und importieren? Je nach Bestand mehrere hundert MB; der Import läuft im Hintergrund über den Standard-Netzausgang.", "Starten"))) return;
        await guard(() => api("POST", `/api/admin/refdata/${b.dataset.dl}/download`), "Download gestartet"); renderAdmin("sources");
      }));
      $$("[data-up]", el).forEach((inp) => (inp.onchange = async () => {
        const fd = new FormData(); fd.append("file", inp.files[0]);
        toast("Datei wird hochgeladen …");
        await guard(() => api("POST", `/api/admin/refdata/${inp.dataset.up}/upload`, fd), "Import gestartet"); renderAdmin("sources");
      }));
      $$("[data-rdel]", el).forEach((b) => (b.onclick = async () => { if (await confirmDlg("Datenbestand löschen?")) { await guard(() => api("DELETE", `/api/admin/refdata/${b.dataset.rdel}`), "Gelöscht"); renderAdmin("sources"); } }));
      if (d.datasets.some((x) => !["bereit", "leer", "fehler"].includes(x.status))) setTimeout(() => { if (location.hash === "#/admin/sources") renderAdmin("sources"); }, 4000);
    } else if (section === "opsec") {
      const o = await api("GET", "/api/admin/opsec");
      el.innerHTML = `<div class="card"><div class="card-head"><h2>Netzausgänge (Egress-Profile)</h2><div class="right"><button class="btn btn-primary" id="eg-new">＋ Ausgang anlegen</button></div></div>
        <p class="small muted">Automatische Abfragen laufen über den Ausgang des Falls. Ab OPSEC-Stufe 2 ist ein Anonymisierungs-Ausgang Pflicht; ist er gestört, wird blockiert (fail closed).
        Unterstützt werden HTTP-Proxys mit CONNECT – z. B. <b>Tor</b> mit <code>HTTPTunnelPort</code> (Docker: <code>docker compose --profile tor up -d</code>, Adresse <code>http://tor:9080</code>), ein VPN-Gateway oder ein kommerzieller Recherche-Proxy. Zugangsdaten werden verschlüsselt gespeichert.</p>
        <table class="tbl"><tr><th>Name</th><th>Art</th><th>Adresse</th><th>User-Agent</th><th>Fälle</th><th></th></tr>
        ${o.profiles.map((e) => `<tr><td><b>${esc(e.name)}</b>${o.settings.default_egress === e.id ? ' <span class="badge b-blue">Voreinstellung</span>' : ""}<br><span class="small muted">${esc(e.notes || "")}</span></td>
          <td>${e.kind === "direkt" ? '<span class="badge b-amber">direkt</span>' : '<span class="badge b-green">Proxy</span>'}</td><td><code class="small">${esc(e.proxy_url || "–")}</code></td>
          <td class="small">${esc(e.user_agent || "Standard je Stufe")}</td><td>${e.cases}</td>
          <td class="nowrap"><button class="btn btn-sm" data-eg-test="${esc(e.id)}">Testen</button>${e.kind !== "direkt" ? ` <button class="btn btn-sm" data-eg-edit="${esc(e.id)}">Bearbeiten</button> <button class="btn btn-sm btn-danger" data-eg-del="${esc(e.id)}">×</button>` : ""}</td></tr>
          <tr class="hidden" id="egr-${esc(e.id)}"><td colspan="6"></td></tr>`).join("")}</table></div>
        <div class="grid g2"><div class="card"><h2>Voreinstellungen</h2>
          <label class="field"><span>Standard-OPSEC-Stufe für neue Fälle</span><select id="os-level">${[1, 2, 3].map((k) => opt(k, `${k} – ${o.levels[k].name}`, o.settings.default_level)).join("")}</select></label>
          <label class="field"><span>Standard-Netzausgang</span><select id="os-egress">${o.profiles.map((e) => opt(e.id, e.name, o.settings.default_egress)).join("")}</select></label>
          <button class="btn btn-primary" id="os-save">Speichern</button></div>
        <div class="card"><h2>Stufen im Überblick</h2><table class="tbl small"><tr><th>Regel</th>${[1, 2, 3].map((k) => `<th>${opsecBadge(k)}</th>`).join("")}</tr>
          ${[["Anonymisierungs-Ausgang Pflicht", "require_egress"], ["Briefing-Bestätigung", "briefing"], ["Deckname in Listen", "codename"], ["Fall zwingend vertraulich", "force_restricted"],
             ["Automatische Verortung (OSM)", "auto_geocode"], ["Kartenhintergrund automatisch", "map_tiles"], ["Neutraler User-Agent", "neutral_user_agent"]]
            .map(([l, k]) => `<tr><td>${l}</td>${[1, 2, 3].map((n) => `<td>${o.levels[n][k] ? "✓" : "–"}</td>`).join("")}</tr>`).join("")}
          <tr><td>Höchste Exposition (automatisch)</td>${[1, 2, 3].map((n) => `<td>${esc(Object.values(state.meta.exposure).find((x) => x.rank === o.levels[n].max_exposure).label)}</td>`).join("")}</tr>
          <tr><td>Höchste Exposition (Links)</td>${[1, 2, 3].map((n) => `<td>${esc(Object.values(state.meta.exposure).find((x) => x.rank === o.levels[n].max_link_exposure).label)}</td>`).join("")}</tr>
          <tr><td>Fälle</td>${[1, 2, 3].map((n) => `<td>${o.level_usage[n] || 0}</td>`).join("")}</tr></table></div></div>`;
      const editProfile = (e) => {
        const m = modal(e ? "Netzausgang bearbeiten" : "Netzausgang anlegen", `<form id="egf">
          <label class="field"><span>Name</span><input name="name" value="${esc(e ? e.name : "")}" placeholder="z. B. Tor, VPN Frankfurt"></label>
          <label class="field"><span>Proxy-Adresse</span><input name="proxy_url" value="${esc(e ? e.proxy_url : "")}" placeholder="http://tor:9080 oder http://benutzer:passwort@proxy.example:3128"><small>HTTP-Proxy mit CONNECT. DNS-Auflösung erfolgt beim Proxy. Maskiertes Passwort (***) bleibt beim Speichern erhalten.</small></label>
          <label class="field"><span>User-Agent (optional)</span><input name="user_agent" value="${esc(e ? e.user_agent : "")}" placeholder="leer = je OPSEC-Stufe neutral"></label>
          <label class="field"><span>Notiz</span><input name="notes" value="${esc(e ? e.notes : "")}"></label></form>`,
          `<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="egf-save">Speichern</button>`);
        $("#egf-save", m.el).onclick = async () => { const d = formData($("#egf", m.el)); if (e) d.id = e.id; await guard(() => api("POST", "/api/admin/egress-profiles", d), "Gespeichert"); m.close(); renderAdmin("opsec"); };
      };
      $("#eg-new").onclick = () => editProfile(null);
      $$("[data-eg-edit]", el).forEach((b) => (b.onclick = () => editProfile(o.profiles.find((x) => x.id === b.dataset.egEdit))));
      $$("[data-eg-del]", el).forEach((b) => (b.onclick = async () => { if (await confirmDlg("Netzausgang löschen?")) { await guard(() => api("DELETE", `/api/admin/egress-profiles/${b.dataset.egDel}`), "Gelöscht"); renderAdmin("opsec"); } }));
      $$("[data-eg-test]", el).forEach((b) => (b.onclick = async () => {
        const row = $(`#egr-${CSS.escape(b.dataset.egTest)}`); row.classList.remove("hidden");
        row.firstElementChild.innerHTML = '<span class="spinner dark"></span> Prüfe Ausgangs-IP …';
        try {
          const r = await api("POST", `/api/admin/egress-profiles/${b.dataset.egTest}/test`);
          row.firstElementChild.innerHTML = r.ok ? `<div class="${r.warning ? "bad-box" : "ok-box"}">Ausgangs-IP: <b>${esc(r.ip)}</b> · Direkt-IP: ${esc(r.direct_ip || "?")}${r.warning ? "<br>⚠ " + esc(r.warning) : r.anonymized ? " · ✓ anonymisiert" : ""}</div>`
            : `<div class="bad-box">Test fehlgeschlagen: ${esc(r.error || "")}</div>`;
        } catch (e) { row.firstElementChild.innerHTML = `<div class="bad-box">${esc(e.message)}</div>`; }
      }));
      $("#os-save").onclick = async () => { await guard(() => api("PUT", "/api/admin/opsec-settings", { default_level: Number($("#os-level").value), default_egress: $("#os-egress").value }), "Gespeichert"); state.meta = await api("GET", "/api/meta"); renderAdmin("opsec"); };
    } else if (section === "retention") {
      const r = await api("GET", "/api/admin/retention");
      el.innerHTML = `<div class="card"><div class="card-head"><h2>🗑 Löschfristen</h2></div>
        <p class="small muted">Personenbezogene Daten dürfen nur so lange gespeichert werden, wie es der Zweck verlangt (Art. 5 Abs. 1 lit. e DSGVO). Beim Abschluss eines Falls wird die Löschfrist automatisch gesetzt;
        ist sie erreicht, erhalten die verantwortliche Person und die Teamleitung eine Erinnerung. Gelöscht wird nie automatisch – die Entscheidung bleibt beim Menschen und wird protokolliert.</p>
        <div class="row"><label class="field" style="max-width:260px"><span>Standard: Monate nach Abschluss</span><input type="number" min="1" max="120" id="rt-months" value="${r.months}"></label>
          <button class="btn btn-primary" id="rt-save" style="align-self:center">Speichern</button></div>
        ${r.without_deadline ? `<div class="bad-box small">${r.without_deadline} abgeschlossene/archivierte Fälle haben keine Löschfrist – bitte im Fall unter „Fall & Team“ nachtragen.</div>` : ""}
        <h3>Fällig oder in den nächsten 30 Tagen fällig</h3>
        <table class="tbl"><tr><th>Aktenzeichen</th><th>Titel</th><th>Verantwortlich</th><th>Status</th><th>Löschfrist</th></tr>
        ${r.cases.map((c) => `<tr><td>${esc(c.reference)}</td><td>${esc(c.title)}</td><td>${esc(c.owner_name || "–")}</td><td>${esc(c.status)}</td>
          <td><span class="badge ${c.due ? "b-red" : "b-amber"}">${esc(fmtDate(c.retention_until))}${c.due ? " – erreicht" : ""}</span></td></tr>`).join("") || '<tr><td colspan="5" class="muted">Keine fälligen Löschfristen.</td></tr>'}</table></div>`;
      $("#rt-save").onclick = async () => { await guard(() => api("PUT", "/api/admin/retention", { months: Number($("#rt-months").value) }), "Löschfrist gespeichert"); renderAdmin("retention"); };
    } else if (section === "restricted") {
      const list = await api("GET", "/api/admin/restricted-cases");
      el.innerHTML = `<div class="card"><h2>Vertrauliche Fälle</h2><p class="small muted">Inhalte und Titel sind für die Administration nicht sichtbar. Fällt die verantwortliche Person aus, kann ein <b>Notfallzugriff</b> (nur lesend) mit Begründung erteilt werden – er wird dauerhaft im Fallprotokoll vermerkt und ist für das Fallteam sichtbar.</p>
        <table class="tbl"><tr><th>Aktenzeichen</th><th>Verantwortlich</th><th>Status</th><th>Angelegt</th><th></th></tr>
        ${list.map((c) => `<tr><td>${esc(c.reference)}</td><td>${esc(c.owner_name || "–")}</td><td>${esc(c.status)}</td><td>${fmtTs(c.created_at)}</td><td><button class="btn btn-sm btn-danger" data-em="${c.id}">Notfallzugriff …</button></td></tr>`).join("") || '<tr><td colspan="5" class="muted">Keine vertraulichen Fälle.</td></tr>'}</table></div>`;
      $$("[data-em]", el).forEach((b) => (b.onclick = () => {
        const m = modal("Notfallzugriff begründen", `<p class="small">Der Zugriff wird mit Ihrem Namen und der Begründung unveränderlich protokolliert und ist für das Fallteam sichtbar.</p>
          <label class="field"><span>Begründung (mind. 15 Zeichen)</span><textarea id="em-r"></textarea></label>`, `<button class="btn" data-close>Abbrechen</button><button class="btn btn-danger" id="em-ok">Zugriff erteilen</button>`);
        $("#em-ok", m.el).onclick = async () => { await guard(() => api("POST", `/api/admin/cases/${b.dataset.em}/emergency-access`, { reason: $("#em-r", m.el).value }), "Notfallzugriff erteilt"); m.close(); await loadCases(); location.hash = `#/case/${b.dataset.em}/overview`; };
      }));
    }
  }

  function genPassword() {
    const words = ["Adler", "Kompass", "Leuchtturm", "Fernglas", "Spur", "Archiv", "Quelle", "Hafen", "Signal", "Karte", "Notiz", "Brücke"];
    const a = new Uint32Array(4); crypto.getRandomValues(a);
    return `${words[a[0] % words.length]}-${words[a[1] % words.length]}-${(a[2] % 900) + 100}-${"!#$%&?"[a[3] % 6]}x`;
  }

  /* Schnellsperre: Bildschirminhalt sofort entfernen und Sitzung beenden (z. B. bei Schulterblick oder Verlassen des Platzes). */
  async function quickLock() {
    stopPresence();
    $("#main").innerHTML = ""; $("#case-list").innerHTML = ""; $("#modal-root").innerHTML = ""; $("#bell").innerHTML = "";
    if (state.graph) { state.graph.destroy(); state.graph = null; }
    if (state.map) { state.map.remove(); state.map = null; }
    document.title = "EagleEye";
    try { await api("POST", "/api/auth/logout"); } catch (_) { /* Sitzung ggf. schon beendet */ }
    state.auth = null; state.ov = null; state.cases = [];
    history.replaceState(null, "", "/#/");
    showAuth();
  }

  // ------------------------------------------------------------------ Start
  let started = false;
  async function startApp() {
    state.meta = await api("GET", "/api/meta");
    state.users = await api("GET", "/api/users");
    state.egress = await api("GET", "/api/egress-profiles");
    renderBell();
    if (!state.bellTimer) state.bellTimer = setInterval(renderBell, 60000);
    renderUserMenu();
    await loadCases();
    if (!started) {
      started = true;
      window.addEventListener("hashchange", route);
    }
    route();
  }

  async function init() {
    $("#btn-new-case").onclick = openNewCase;
    $("#btn-help").onclick = openHelp;
    document.addEventListener("keydown", (e) => { if (e.ctrlKey && e.altKey && (e.key === "l" || e.key === "L") && state.auth && state.auth.authenticated) { e.preventDefault(); quickLock(); } });
    $("#btn-menu").onclick = () => $("#sidebar").classList.toggle("open");
    $("#case-filter").oninput = renderCaseList;
    $$("#case-views button").forEach((b) => (b.onclick = async () => {
      $$("#case-views button").forEach((x) => x.classList.toggle("on", x === b));
      state.view = b.dataset.view; await loadCases();
    }));
    await showAuth();
  }
  init().catch((e) => { document.body.innerHTML = `<div style="padding:2rem;font-family:sans-serif"><h2>EagleEye konnte nicht starten</h2><p>${esc(e.message)}</p></div>`; });
})();

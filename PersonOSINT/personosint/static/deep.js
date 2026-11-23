/* Tiefenrecherche (Reiter im Fall) und Tarnung & Websuche (Verwaltung). Nutzt die Hilfsfunktionen aus app.js (window.EE). */
(function () {
  "use strict";
  const E = () => window.EE;
  const KIND = { name: "Name", username: "Benutzername", email: "E-Mail", phone: "Telefon", domain: "Domain", url: "Webadresse", employer: "Firma", location: "Ort", dork: "Dork" };
  const doneKey = (cid) => "ee-dorks-" + cid;
  const readDone = (cid) => { try { return new Set(JSON.parse(localStorage.getItem(doneKey(cid)) || "[]")); } catch (_) { return new Set(); } };
  const writeDone = (cid, set) => { try { localStorage.setItem(doneKey(cid), JSON.stringify([...set])); } catch (_) { /* privat */ } };
  let pollTimer = null;

  // ------------------------------------------------------------------ Reiter „Tiefenrecherche“
  async function tabDeep(el, ov) {
    const { api, esc } = E();
    const cid = ov.case.id;
    const ents = await api("GET", `/api/cases/${cid}/entities`);
    const persons = ents.filter((e) => e.type === "person");
    if (!persons.length) {
      el.innerHTML = `<div class="card"><div class="empty">Bitte zuerst eine Person erfassen.<br><br><a class="btn btn-primary" href="#/case/${cid}/persons">Person erfassen</a></div></div>`;
      return;
    }
    const st = (window.EE_DEEP = window.EE_DEEP || {});
    if (!st.entity || !persons.find((p) => p.id === st.entity)) st.entity = (ov.subject || persons[0]).id;
    const missing = ov.case.case_type === "vermisst";
    el.innerHTML = `
      <div class="card deep-intro">
        <h2>🔭 Tiefenrecherche</h2>
        <p class="small">Die Plattform erzeugt aus dem Profil automatisch alle sinnvollen Suchanfragen: Namensvarianten, Benutzernamen, Telefon-Schreibweisen,
        Dorks nach Rechercheziel. Sie fragt jede passende Quelle ab und folgt <b>starken neuen Spuren</b> selbstständig weiter – bis zur gewählten Tiefe und
        nur im Abfragebudget. OPSEC-Stufe, Ausgang und Netzschalter gelten wie immer. Alles bleibt <b>Kandidat</b>, bis Sie es prüfen.</p>
        <div class="grid g3 deep-opts">
          <label class="field"><span>Person</span><select id="dp-ent">${persons.map((p) => `<option value="${p.id}" ${p.id === st.entity ? "selected" : ""}>${esc(p.label)}</option>`).join("")}</select></label>
          <label class="field"><span>Tiefe (Runden mit Folgespuren)</span><select id="dp-depth"><option value="1">1 – nur Varianten</option><option value="2" selected>2 – plus starke Folgespuren</option><option value="3">3 – maximal</option></select></label>
          <label class="field"><span>Abfragebudget</span><select id="dp-budget"><option>50</option><option>100</option><option selected>200</option><option>400</option><option>600</option></select></label>
        </div>
        <div class="deep-checks">
          <label><input type="checkbox" id="dp-guess"> Benutzernamen erraten (vorname.nachname …) <span class="muted small">– fragt Plattformen ab</span></label>
          <label><input type="checkbox" id="dp-rotate" checked> Neue Netzidentität je Abfragepaket <span class="muted small">– wechselnde Browserkennung, mit Tor-Steuerport auch neuer Tor-Ausgang</span></label>
          <label><input type="checkbox" id="dp-dorks"> Dorks automatisch über die eigene Websuche ausführen <span class="muted small" id="dp-dorks-why"></span></label>
          <label><input type="checkbox" id="dp-missing" ${missing ? "checked" : ""}> Vermisstenfall: Vermisstenregister und Vermissten-Dorks einbeziehen</label>
        </div>
      </div>
      <div id="dp-plan"><div class="card"><p class="muted">Plan wird berechnet …</p></div></div>
      <div id="dp-job"></div>
      <div id="dp-personas"></div>`;
    const opts = () => ({ depth: $v("#dp-depth"), budget: $v("#dp-budget"), guess_usernames: $c("#dp-guess"), rotate_identity: $c("#dp-rotate"),
      run_dorks: $c("#dp-dorks"), missing: $c("#dp-missing") });
    const refresh = () => loadPlan(cid, st, opts);
    ["#dp-depth", "#dp-budget", "#dp-guess", "#dp-missing"].forEach((s) => (document.querySelector(s).onchange = refresh));
    document.querySelector("#dp-ent").onchange = (e) => { st.entity = Number(e.target.value); refresh(); };
    await refresh();
    renderCasePersonas(cid);
    if (st.job && st.jobCase === cid) poll(cid, st.job);
  }
  const $v = (s) => document.querySelector(s).value;
  const $c = (s) => document.querySelector(s).checked;

  async function loadPlan(cid, st, opts) {
    const { api, esc } = E();
    const box = document.querySelector("#dp-plan");
    if (!box) return;
    let pl;
    try { pl = await api("GET", `/api/cases/${cid}/entities/${st.entity}/deep/plan?` + new URLSearchParams(Object.entries(opts()).map(([k, v]) => [k, String(v)]))); }
    catch (e) { box.innerHTML = `<div class="card bad-box">${esc(e.message)}</div>`; return; }
    const why = document.querySelector("#dp-dorks-why");
    const dk = document.querySelector("#dp-dorks");
    if (dk) { dk.disabled = !pl.websearch.available; if (!pl.websearch.available) dk.checked = false; }
    if (why) why.textContent = pl.websearch.available ? "– über Ihre SearXNG-Instanz" : "– " + pl.websearch.reason;
    const bySource = {};
    pl.queries.forEach((q) => { (bySource[q.source_label] = bySource[q.source_label] || []).push(q); });
    const done = readDone(cid);
    const groups = {};
    pl.dorks.forEach((d) => (groups[d.group] = groups[d.group] || []).push(d));
    box.innerHTML = `
      <div class="grid g2">
        <div class="card"><h3>Varianten, die abgefragt werden</h3>
          <div class="chips">${pl.variants.map((v) => `<span class="chip" title="${esc(v.why)}">${esc(v.value)}</span>`).join("")}</div>
          ${pl.guessed_usernames.length ? `<h4>Erratene Benutzernamen</h4><div class="chips">${pl.guessed_usernames.map((u) => `<span class="chip chip-amber">${esc(u)}</span>`).join("")}</div>` : ""}
          <p class="small muted">Weitere Kennungen aus dem Profil (Benutzernamen, E-Mail, Telefon, Domains, Firma, Ort) werden ebenfalls abgefragt.</p>
        </div>
        <div class="card"><h3>Automatische Abfragen: ${pl.queries.length}${pl.over_budget ? ` <span class="badge b-amber">+${pl.over_budget} über Budget</span>` : ""}</h3>
          <table class="tbl small">${Object.entries(bySource).sort((a, b) => b[1].length - a[1].length).map(([src, qs]) => `<tr><td>${esc(src)}</td><td>${qs.length}</td><td class="muted">${esc([...new Set(qs.map((q) => KIND[q.kind] || q.kind))].join(", "))}</td></tr>`).join("") || "<tr><td>Keine offenen Abfragen – alles schon abgefragt.</td></tr>"}</table>
          <p class="small muted">Nicht eingeplant: ${pl.skipped.done} schon abgefragt · ${pl.skipped.opsec} durch OPSEC-Stufe ${pl.opsec_level} gesperrt · ${pl.skipped.unavailable} Quelle nicht eingerichtet.</p>
          <button class="btn btn-primary btn-lg w" id="dp-start">🔭 Tiefenrecherche starten</button>
        </div>
      </div>
      <div class="card"><div class="card-head"><h3>Dorks (${pl.dorks.length})</h3><div class="right small muted">${pl.websearch.available ? "Automatisch über Ihre Websuche möglich (Häkchen oben) – oder einzeln öffnen." : "Einzeln öffnen und abhaken. Links öffnen im Browser mit Ihrer normalen Verbindung."}</div></div>
        ${Object.entries(groups).map(([g, ds]) => `<h4 class="dork-group">${esc(g)}</h4>${ds.map((d) => `
          <div class="dork ${done.has(d.query) ? "done" : ""}"><label class="dork-check"><input type="checkbox" data-dork="${esc(d.query)}" ${done.has(d.query) ? "checked" : ""}></label>
            <div class="dork-main"><b>${esc(d.goal)}</b><code>${esc(d.query)}</code></div>
            <div class="dork-links">${d.links.map((l) => `<a class="btn btn-sm" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.label)}</a>`).join("")}<button class="btn btn-sm" data-copy="${esc(d.query)}">Kopieren</button></div></div>`).join("")}`).join("")}
      </div>`;
    box.querySelectorAll("[data-dork]").forEach((cb) => (cb.onchange = () => {
      const set = readDone(cid); cb.checked ? set.add(cb.dataset.dork) : set.delete(cb.dataset.dork); writeDone(cid, set);
      cb.closest(".dork").classList.toggle("done", cb.checked);
    }));
    box.querySelectorAll("[data-copy]").forEach((b) => (b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.copy); E().toast("Dork kopiert", "ok"); } catch (_) { /* ohne Zwischenablage */ } }));
    const start = document.querySelector("#dp-start");
    start.disabled = !pl.queries.length && !($c("#dp-dorks") && pl.websearch.available);
    start.onclick = async () => {
      start.disabled = true;
      try {
        const job = await E().guard(() => E().api("POST", `/api/cases/${cid}/entities/${st.entity}/deep/start`, opts()), "Tiefenrecherche gestartet");
        st.job = job.id; st.jobCase = cid; poll(cid, job.id);
      } catch (_) { start.disabled = false; }
    };
  }

  function poll(cid, jobId) {
    const { api, esc } = E();
    clearInterval(pollTimer);
    const draw = async () => {
      const box = document.querySelector("#dp-job");
      if (!box) { clearInterval(pollTimer); return; }
      let j;
      try { j = await api("GET", `/api/cases/${cid}/deep/${jobId}`); } catch (_) { clearInterval(pollTimer); return; }
      const running = j.state === "läuft";
      const pct = Math.min(100, Math.round((j.used / Math.max(1, j.budget)) * 100));
      box.innerHTML = `<div class="card deep-job ${running ? "running" : ""}"><div class="card-head"><h3>${running ? "⏳ Tiefenrecherche läuft" : j.state === "fertig" ? "✅ Tiefenrecherche abgeschlossen" : "⛔ Tiefenrecherche " + esc(j.state)}</h3>
          <div class="right">${running ? `<button class="btn btn-sm" id="dp-cancel">Abbrechen</button>` : `<a class="btn btn-sm btn-primary" href="#/case/${cid}/search">Treffer prüfen →</a>`}</div></div>
        <div class="deep-stats"><div><b>${j.round}</b> / ${j.depth}<span>Runde</span></div><div><b>${j.used}</b> / ${j.budget}<span>Abfragen</span></div><div><b>${j.new_findings}</b><span>neue Treffer</span></div><div><b>${j.followed.length}</b><span>Spuren verfolgt</span></div></div>
        <div class="meter-bar"><i style="width:${pct}%"></i></div>
        <ol class="deep-log small">${j.log.slice(-14).map((l) => `<li>${esc(new Date(l.time * 1000).toLocaleTimeString("de-DE"))} · ${esc(l.text)}</li>`).join("")}</ol></div>`;
      const c = box.querySelector("#dp-cancel");
      if (c) c.onclick = () => api("POST", `/api/cases/${cid}/deep/${jobId}/cancel`).catch(() => {});
      if (!running) clearInterval(pollTimer);
    };
    draw();
    pollTimer = setInterval(draw, 2000);
  }

  async function renderCasePersonas(cid) {
    const { api, esc } = E();
    const box = document.querySelector("#dp-personas");
    if (!box) return;
    const [used, all] = await Promise.all([api("GET", `/api/cases/${cid}/personas`), api("GET", "/api/personas")]);
    const usable = all.items.filter((p) => p.status !== "verbrannt");
    box.innerHTML = `<div class="card"><div class="card-head"><h3>🎭 Legenden in diesem Fall</h3><div class="right small"><a href="#/admin/tarnung">Legenden verwalten →</a></div></div>
      <p class="small muted">Nur nötig, wenn Sie selbst auf Plattformen mit Anmeldung recherchieren. Die automatischen Abfragen laufen ohne Konto.</p>
      ${used.length ? `<ul>${used.map((p) => `<li><b>${esc(p.codename)}</b> – ${esc(p.display_name)} (${esc(p.status_label)})${p.case_count > 1 ? ` <span class="badge b-amber">auch in ${p.case_count - 1} anderen Fällen</span>` : ""}</li>`).join("")}</ul>` : "<p class=\"small\">Noch keine Legende eingesetzt.</p>"}
      ${usable.length ? `<form class="row w" id="pu-form"><select id="pu-p">${usable.map((p) => `<option value="${p.id}">${esc(p.codename)} – ${esc(p.display_name)}</option>`).join("")}</select>
        <input id="pu-why" class="grow" maxlength="300" placeholder="Wofür? z. B. Instagram-Profil der Zielperson ansehen"><button class="btn btn-sm btn-primary">Einsatz eintragen</button></form>` : ""}</div>`;
    const f = box.querySelector("#pu-form");
    if (f) f.onsubmit = async (e) => {
      e.preventDefault();
      const r = await E().guard(() => api("POST", `/api/personas/${$v("#pu-p")}/use`, { case_id: cid, purpose: $v("#pu-why") }), "Einsatz eingetragen");
      (r.warnings || []).forEach((w) => E().toast(w, "err"));
      renderCasePersonas(cid);
    };
  }

  // ------------------------------------------------------------------ Verwaltung „Tarnung & Websuche“
  async function adminTarnung(el) {
    const { api, esc, modal, guard } = E();
    const [ps, web, egress, running] = await Promise.all([api("GET", "/api/personas"), api("GET", "/api/admin/websearch"),
      api("GET", "/api/egress-profiles"), window.EE_VAULT ? api("GET", "/vault/api/personas/browsers").catch(() => ({ items: [] })) : { items: [] }]);
    const proxies = egress.filter((x) => x.kind === "proxy");
    const open = new Set(running.items.map((r) => r.persona_id));
    el.innerHTML = `
      <div class="card"><h2>🎭 Legenden (Sockpuppets)</h2>
        <div class="note-box small"><b>So schützen Sie sich:</b> Die automatischen Abfragen brauchen kein Konto und übertragen nichts über Sie. Eine Legende
        brauchen Sie nur für eigene Recherchen auf Plattformen mit Anmeldung. Hier erfinden Sie eine glaubwürdige, <b>fiktive</b> Identität mit eigener
        Alias-E-Mail. <b>Das Konto legen Sie selbst von Hand an</b> – über den Anonymisierungs-Ausgang und mit eigenem Browserprofil je Legende.
        Automatisch angelegte Konten fallen auf, werden gesperrt und verraten die Recherche. Keine echten Personen nachahmen.</div>
        <form class="row" id="pe-form"><label class="field grow"><span>Muster für Alias-E-Mail-Adressen</span>
          <input name="email_pattern" value="${esc(ps.email_pattern)}" placeholder="{user}@alias.meinedomain.de oder recherche+{token}@meinedomain.de">
          <small>Mit einer eigenen Domain (Catch-all) oder einem Alias-Dienst wie SimpleLogin/addy.io bekommt jede Legende ihre eigene Adresse.</small></label>
          <button class="btn">Speichern</button></form>
        <div class="row"><button class="btn btn-primary" id="pe-gen">＋ Legende vorschlagen</button></div>
        <table class="tbl"><tr><th>Deckname</th><th>Name</th><th>Benutzername / E-Mail</th><th>Status</th><th>Fälle</th><th></th></tr>
        ${ps.items.map((p) => `<tr class="${p.status === "verbrannt" ? "muted" : ""}"><td><b>${esc(p.codename)}</b></td><td>${esc(p.display_name)}<br><span class="small muted">${esc(p.birth_year)} · ${esc(p.city)}</span></td>
          <td>${esc(p.username)}<br><span class="small">${esc(p.email_alias || "–")}</span></td>
          <td><span class="badge ${p.status === "aktiv" ? "b-green" : p.status === "verbrannt" ? "b-red" : "b-grey"}">${esc(p.status)}</span></td>
          <td>${p.case_count}</td><td class="nowrap">${window.EE_VAULT && p.status !== "verbrannt" ? (open.has(p.id)
            ? `<button class="btn btn-sm btn-danger" data-pbc="${p.id}">■ Fenster schließen</button> `
            : `<button class="btn btn-sm btn-primary" data-pb="${p.id}" title="${p.egress_profile ? "Eigenes Browserfenster der Legende über ihren Ausgang" : "Zuerst einen Ausgang zuordnen"}" ${p.egress_profile ? "" : "disabled"}>🌐 Fenster öffnen</button> `) : ""}<button class="btn btn-sm" data-pe="${p.id}">Bearbeiten</button>${p.has_secret ? ` <button class="btn btn-sm" data-ps="${p.id}">Zugang</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="6" class="muted">Noch keine Legende.</td></tr>`}</table>
      </div>
      <div class="card"><h2>🌐 Eigene Websuche (SearXNG) für automatische Dorks</h2>
        <p class="small">SearXNG ist eine Meta-Suchmaschine, die Sie selbst betreiben (z. B. mit Docker). Die Tiefenrecherche schickt ihre Dorks dorthin und übernimmt die Treffer.
        Google & Co. verbieten automatische Abfragen – deshalb dieser Weg. In der SearXNG-Einstellung <code>search.formats</code> muss <code>json</code> stehen.</p>
        <form id="ws-form"><div class="grid g2"><label class="field"><span>Adresse</span><input name="url" value="${esc(web.url)}" placeholder="http://127.0.0.1:8888"></label>
          <label class="field"><span>&nbsp;</span><label><input type="checkbox" name="anonymized" ${web.anonymized ? "checked" : ""}> SearXNG fragt selbst über Tor/Proxy ab (für OPSEC-Stufe 2 und höher nötig)</label></label></div>
          <h3>🧅 Tor-Steuerport (neuer Tor-Ausgang je Abfragepaket)</h3>
          <div class="grid g3"><label class="field"><span>Adresse</span><input name="tor_host" value="${esc(web.tor_control.host)}" placeholder="127.0.0.1"></label>
            <label class="field"><span>Port</span><input name="tor_port" value="${esc(web.tor_control.port)}" placeholder="9051"></label>
            <label class="field"><span>Passwort (HashedControlPassword)</span><input name="tor_password" type="password" value="${esc(web.tor_control.password)}"></label></div>
          <button class="btn btn-primary">Speichern</button></form></div>`;
    el.querySelector("#pe-form").onsubmit = async (e) => {
      e.preventDefault();
      await guard(() => api("POST", "/api/personas/settings", { email_pattern: e.target.email_pattern.value }), "Muster gespeichert");
    };
    el.querySelector("#ws-form").onsubmit = async (e) => {
      e.preventDefault(); const f = e.target;
      await guard(() => api("POST", "/api/admin/websearch", { url: f.url.value, anonymized: f.anonymized.checked,
        tor_control: { host: f.tor_host.value, port: Number(f.tor_port.value || 9051), password: f.tor_password.value } }), "Gespeichert");
    };
    const editor = (p, isNew) => {
      const m = modal(isNew ? "Neue Legende" : "Legende " + p.codename, `
        <div class="grid g2"><label class="field"><span>Deckname (nur intern)</span><input name="codename" value="${esc(p.codename)}" required></label>
          <label class="field"><span>Name der Legende</span><input name="display_name" value="${esc(p.display_name)}" required></label>
          <label class="field"><span>Benutzername</span><input name="username" value="${esc(p.username)}"></label>
          <label class="field"><span>Alias-E-Mail</span><input name="email_alias" value="${esc(p.email_alias)}"></label>
          <label class="field"><span>Geburtsjahr</span><input name="birth_year" value="${esc(p.birth_year)}" maxlength="4"></label>
          <label class="field"><span>Wohnort</span><input name="city" value="${esc(p.city)}"></label></div>
        <label class="field"><span>Ausgang der Legende (für ihr Browserfenster)</span><select name="egress_profile"><option value="">– keiner –</option>
          ${proxies.map((x) => `<option value="${esc(x.id)}" ${x.id === p.egress_profile ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select>
          <small>${proxies.length ? "Nur Tor- oder Proxy-Ausgänge – nie direkt." : "Noch kein Tor-/Proxy-Ausgang eingerichtet (Verwaltung → OPSEC)."}</small></label>
        <label class="field"><span>Kurzprofil</span><textarea name="bio" rows="2">${esc(p.bio || "")}</textarea></label>
        <label class="field"><span>Plattformen, auf denen Sie das Konto angelegt haben (kommagetrennt)</span><input name="platforms" value="${esc((p.platforms || []).join(", "))}" placeholder="Instagram, Facebook, LinkedIn"></label>
        <label class="field"><span>Zugangsdaten (verschlüsselt gespeichert)</span><textarea name="secret" rows="2" placeholder="${p.has_secret ? "unverändert lassen = bleibt gespeichert" : "Passwörter, Wiederherstellungscodes …"}"></textarea></label>
        ${isNew ? "" : `<label class="field"><span>Status</span><select name="status">${["aktiv", "ruhend", "verbrannt"].map((s) => `<option ${s === p.status ? "selected" : ""}>${s}</option>`).join("")}</select></label>`}
        <label class="field"><span>Notizen</span><textarea name="notes" rows="2">${esc(p.notes || "")}</textarea></label>
        ${!isNew && p.uses && p.uses.length ? `<h4>Einsätze</h4><ul class="small">${p.uses.map((u) => `<li>${esc(u.used_at.slice(0, 16).replace("T", " "))} · ${esc(u.reference || "ohne Fall")} · ${esc(u.purpose)}</li>`).join("")}</ul>` : ""}`,
        `${isNew ? "" : `<button class="btn btn-danger" id="pe-del">Löschen</button>`}<button class="btn" data-close>Abbrechen</button><button class="btn btn-primary" id="pe-save">Speichern</button>`, { width: "720px" });
      const val = (n) => m.el.querySelector(`[name=${n}]`).value;
      m.el.querySelector("#pe-save").onclick = async () => {
        const body = { codename: val("codename"), display_name: val("display_name"), username: val("username"), email_alias: val("email_alias"),
          birth_year: val("birth_year"), city: val("city"), bio: val("bio"), notes: val("notes"), egress_profile: val("egress_profile"),
          platforms: val("platforms").split(",").map((x) => x.trim()).filter(Boolean) };
        if (val("secret")) body.secret = val("secret");
        if (!isNew) body.status = val("status");
        await guard(() => api(isNew ? "POST" : "PUT", isNew ? "/api/personas" : `/api/personas/${p.id}`, body), "Legende gespeichert");
        m.close(); adminTarnung(el);
      };
      const del = m.el.querySelector("#pe-del");
      if (del) del.onclick = async () => { if (await E().confirmDlg(`Legende ${p.codename} löschen?`)) { await guard(() => api("DELETE", `/api/personas/${p.id}`), "Gelöscht"); m.close(); adminTarnung(el); } };
    };
    el.querySelector("#pe-gen").onclick = async () => editor(await api("POST", "/api/personas/generate", {}), true);
    el.querySelectorAll("[data-pe]").forEach((b) => (b.onclick = () => editor(ps.items.find((x) => x.id === Number(b.dataset.pe)), false)));
    el.querySelectorAll("[data-pb]").forEach((b) => (b.onclick = async () => {
      b.disabled = true;
      try {
        const r = await guard(() => api("POST", `/vault/api/personas/${b.dataset.pb}/browser`, { open: true }), "Legendenfenster wird geöffnet");
        if (r.restored === false) E().toast("Neues Profil für diese Legende angelegt – beim Schließen wird es verschlüsselt im Vault gespeichert.", "ok");
      } catch (_) { /* Meldung bereits angezeigt */ }
      adminTarnung(el);
    }));
    el.querySelectorAll("[data-pbc]").forEach((b) => (b.onclick = async () => {
      b.disabled = true;
      await guard(() => api("POST", `/vault/api/personas/${b.dataset.pbc}/browser`, { open: false }), "Fenster geschlossen, Profil verschlüsselt gespeichert");
      adminTarnung(el);
    }));
    el.querySelectorAll("[data-ps]").forEach((b) => (b.onclick = async () => {
      const r = await api("GET", `/api/personas/${b.dataset.ps}/secret`);
      modal("Zugangsdaten", `<pre class="secret-box">${esc(r.secret)}</pre><p class="small muted">Das Anzeigen wird protokolliert.</p>`, `<button class="btn btn-primary" data-close>Schließen</button>`);
    }));
  }

  window.EEDeep = { tabDeep, adminTarnung };
})();

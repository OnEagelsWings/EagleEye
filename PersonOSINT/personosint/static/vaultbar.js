/* EagleEye Vault – Leiste über der Anwendung: Status, Netzschalter, Verbindungsprotokoll, Einstellungen, Sperren. */
(function () {
  "use strict";
  // Kartenkacheln über den Server (Netzschalter), nie direkt vom Browser zu OpenStreetMap
  window.EE_TILE_URL = "/vault/tiles/{z}/{x}/{y}.png";
  window.EE_VAULT = true;  // Vault-Funktionen (Legenden-Browser) in der Oberfläche einblenden
  const origFetch = window.fetch.bind(window);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let st = null, csrf = "", bar = null, lastPing = 0, interacted = false, receivedAt = Date.now();

  /* Aktionen, die Quellen im Internet abfragen – bei geschlossenem Netz fragt die Leiste nach, statt sie scheitern zu lassen. */
  const NEEDS_NET = [/^\/api\/cases\/\d+\/search$/, /^\/api\/cases\/\d+\/evidence$/, /^\/api\/cases\/\d+\/entities\/\d+\/pivots\/run$/,
    /^\/api\/cases\/\d+\/watches\/\d+\/run$/, /^\/api\/admin\/sources\/check$/, /^\/api\/admin\/sources\/[^/]+\/test$/,
    /^\/api\/admin\/egress-profiles\/[^/]+\/test$/, /^\/api\/admin\/refdata\/[^/]+\/download$/, /^\/api\/cases\/\d+\/entities\/\d+\/deep\/start$/];

  async function call(method, url, body) {
    const opts = { method, headers: { "X-Requested-With": "EagleEye" }, credentials: "same-origin" };
    if (csrf) opts.headers["X-CSRF-Token"] = csrf;
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const r = await origFetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (r.status === 423) { toLock(); throw new Error("Vault gesperrt"); }
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Fehler " + r.status);
    return data;
  }
  function toLock() { location.replace("/?gesperrt=" + Date.now()); }
  const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const ago = (t) => { const s = Math.round(Date.now() / 1000 - t); return s < 60 ? `vor ${s} s` : `vor ${Math.round(s / 60)} min`; };

  // ------------------------------------------------------------------ Dialog
  function dialog(title, body, foot) {
    const bg = document.createElement("div");
    bg.className = "vb-modal-bg";
    bg.innerHTML = `<div class="vb-modal" role="dialog" aria-modal="true" aria-label="${esc(title)}"><h2>${esc(title)}</h2><div class="vb-body">${body}</div><div class="vb-foot">${foot}</div></div>`;
    document.body.appendChild(bg);
    const close = () => bg.remove();
    bg.addEventListener("click", (e) => { if (e.target === bg || e.target.hasAttribute("data-close")) close(); });
    bg.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
    const first = bg.querySelector("input, select, button.primary, button.gold");
    if (first) first.focus();
    return { el: bg, close };
  }

  // ------------------------------------------------------------------ Netz öffnen / schließen
  function openNetDialog(reason) {
    return new Promise((resolve) => {
      const durations = (st && st.net && st.net.durations) || [5, 15, 30, 60, 120];
      let minutes = (st && st.net_minutes) || 30;
      const d = dialog(reason ? "Diese Aktion braucht das Internet" : "Netz für die Recherche öffnen", `
        ${reason ? `<div class="vb-note warn">${esc(reason)}</div>` : ""}
        <p>Solange das Netz offen ist, darf <b>nur dieses Programm</b> Quellen im Internet abfragen. Danach schließt es sich von selbst.</p>
        <label>Wie lange?</label>
        <div class="vb-choices">${durations.map((m) => `<button type="button" data-min="${m}" class="${m === minutes ? "sel" : ""}">${m < 60 ? m + " min" : m / 60 + " Std."}</button>`).join("")}</div>
        <label>Wofür? <span style="font-weight:400;color:#64748b">(optional, erscheint im Protokoll)</span><input id="vb-purpose" maxlength="200" placeholder="z. B. Hintergrundprüfung Auftrag 2026-041"></label>
        <div class="vb-note">Tipp: Für Abfragen über Tor oder einen Recherche-Proxy den Ausgang im Fall unter <b>OPSEC</b> wählen. Ihr Browser selbst bleibt davon unberührt – externe Links öffnet er mit Ihrer normalen Verbindung.</div>`,
        `<button data-close>Abbrechen</button><button class="gold" id="vb-go">🌐 Netz öffnen</button>`);
      d.el.querySelectorAll("[data-min]").forEach((b) => (b.onclick = () => {
        minutes = Number(b.dataset.min);
        d.el.querySelectorAll("[data-min]").forEach((x) => x.classList.toggle("sel", x === b));
      }));
      let done = false;
      const finish = (v) => { if (!done) { done = true; resolve(v); } };
      d.el.querySelector("#vb-go").onclick = async () => {
        try {
          const net = await call("POST", "/vault/api/net", { open: true, minutes, purpose: d.el.querySelector("#vb-purpose").value });
          st.net = net; receivedAt = Date.now(); render(); d.close(); finish(true);
        } catch (e) { d.el.querySelector(".vb-body").insertAdjacentHTML("afterbegin", `<div class="vb-err">${esc(e.message)}</div>`); }
      };
      new MutationObserver((_, obs) => { if (!document.body.contains(d.el)) { obs.disconnect(); finish(false); } }).observe(document.body, { childList: true });
    });
  }

  async function closeNet() {
    st.net = await call("POST", "/vault/api/net", { open: false });
    receivedAt = Date.now(); render();
  }

  async function showLog() {
    const data = await call("GET", "/vault/api/net/log");
    const t = (x) => new Date(x * 1000).toLocaleTimeString("de-DE");
    dialog("Außenverbindungen dieses Programms", `
      <p class="vb-muted" style="color:#64748b">Nur in dieser Sitzung, nur im Arbeitsspeicher – beim Sperren gelöscht. Das dauerhafte Protokoll je Fall steht unter <b>OPSEC → Außenkontakte</b>.</p>
      ${data.sessions.length ? `<h3 style="font-size:1rem;margin:10px 0 4px">Netz-Freigaben</h3><table><tr><th>geöffnet</th><th>geschlossen</th><th>Zweck</th></tr>${data.sessions.map((s) => `<tr><td>${t(s.opened)}</td><td>${s.closed ? t(s.closed) + " · " + esc(s.reason) : "<b>offen</b>"}</td><td>${esc(s.purpose || "–")}</td></tr>`).join("")}</table>` : ""}
      <h3 style="font-size:1rem;margin:12px 0 4px">Verbindungsversuche</h3>
      ${data.items.length ? `<table><tr><th>Zeit</th><th>Ziel</th><th>Art</th><th></th></tr>${data.items.map((i) => `<tr><td>${t(i.time)}</td><td>${esc(i.host)}${i.port ? ":" + esc(i.port) : ""}</td><td>${esc(i.kind)}</td><td class="${i.allowed ? "ok" : "no"}">${i.allowed ? "erlaubt" : "blockiert"}</td></tr>`).join("")}</table>` : "<p>Noch keine.</p>"}`,
      `<button class="primary" data-close>Schließen</button>`);
  }

  // ------------------------------------------------------------------ Einstellungen
  function settingsDialog() {
    const idle = st.idle_choices || [5, 10, 15, 30, 60];
    const durations = (st.net && st.net.durations) || [5, 15, 30, 60, 120];
    const d = dialog("Vault-Einstellungen", `
      <label>Automatisch sperren nach
        <select id="vb-idle">${idle.map((m) => `<option value="${m}" ${m === st.idle_minutes ? "selected" : ""}>${m} Minuten ohne Eingabe</option>`).join("")}</select></label>
      <label>Netz standardmäßig öffnen für
        <select id="vb-netmin">${durations.map((m) => `<option value="${m}" ${m === st.net_minutes ? "selected" : ""}>${m} Minuten</option>`).join("")}</select></label>
      <div class="vb-note">Vault-Kennung <b>${esc(st.vault_id)}</b> · Speicherort <code>${esc(st.folder)}</code></div>
      <h3 style="font-size:1rem;margin:14px 0 2px">Passphrase ändern</h3>
      <label>Bisherige Passphrase<input type="password" id="vb-old" autocomplete="current-password"></label>
      <label>Neue Passphrase (mind. 12 Zeichen)<input type="password" id="vb-new" autocomplete="new-password"></label>
      <label>Neue Passphrase wiederholen<input type="password" id="vb-new2" autocomplete="new-password"></label>
      <div class="vb-foot" style="padding:0;justify-content:flex-start"><button id="vb-chpw">Passphrase ändern</button><button id="vb-rk">Neuen Wiederherstellungsschlüssel erzeugen</button></div>
      <div id="vb-msg"></div>`,
      `<button data-close>Schließen</button><button class="primary" id="vb-save">Speichern</button>`);
    const msg = (html) => (d.el.querySelector("#vb-msg").innerHTML = html);
    d.el.querySelector("#vb-save").onclick = async () => {
      try {
        Object.assign(st, await call("POST", "/vault/api/settings", { idle_minutes: Number(d.el.querySelector("#vb-idle").value), net_minutes: Number(d.el.querySelector("#vb-netmin").value) }));
        receivedAt = Date.now(); render(); d.close();
      } catch (e) { msg(`<div class="vb-err">${esc(e.message)}</div>`); }
    };
    d.el.querySelector("#vb-chpw").onclick = async () => {
      try {
        await call("POST", "/vault/api/passphrase", { old: d.el.querySelector("#vb-old").value, new: d.el.querySelector("#vb-new").value, new2: d.el.querySelector("#vb-new2").value });
        msg(`<div class="vb-note">✓ Passphrase geändert. Ab dem nächsten Öffnen gilt die neue.</div>`);
      } catch (e) { msg(`<div class="vb-err">${esc(e.message)}</div>`); }
    };
    d.el.querySelector("#vb-rk").onclick = async () => {
      const pass = d.el.querySelector("#vb-old").value;
      if (!pass) { msg(`<div class="vb-err">Bitte oben die bisherige Passphrase eingeben – zur Bestätigung.</div>`); return; }
      try {
        const r = await call("POST", "/vault/api/recovery-key", { passphrase: pass });
        msg(`<div class="vb-note warn">Neuer Wiederherstellungsschlüssel – <b>jetzt notieren</b>, der alte gilt nicht mehr:</div><div class="vb-rk">${esc(r.recovery_key)}</div>`);
      } catch (e) { msg(`<div class="vb-err">${esc(e.message)}</div>`); }
    };
  }

  // ------------------------------------------------------------------ Leiste
  function render() {
    if (!bar || !st) return;
    const elapsed = Math.floor((Date.now() - receivedAt) / 1000);
    const left = Math.max(0, (st.net.seconds_left || 0) - elapsed);
    const idleLeft = Math.max(0, (st.idle_left || 0) - elapsed);
    const open = st.net.open && left > 0;
    bar.querySelector(".vb-net").innerHTML = open
      ? `<span class="vb-pill on" title="${esc(st.net.purpose || "")}">🌐 Netz offen · ${mmss(left)}</span><button id="vb-close">Netz schließen</button>`
      : `<span class="vb-pill off">⛔ Netz aus</span><button class="vb-open" id="vb-open">Netz öffnen …</button>`;
    bar.querySelector(".vb-stats").textContent = `${st.net.allowed} erlaubt · ${st.net.blocked} blockiert`;
    const saved = bar.querySelector(".vb-saved");
    saved.textContent = st.unsaved ? "● wird gespeichert" : st.last_saved ? `✓ verschlüsselt gespeichert` : "";
    saved.classList.toggle("dirty", !!st.unsaved);
    bar.querySelector(".vb-idle").textContent = `Sperre in ${Math.ceil(idleLeft / 60)} min`;
    const o = bar.querySelector("#vb-open"); if (o) o.onclick = () => openNetDialog("");
    const c = bar.querySelector("#vb-close"); if (c) c.onclick = () => closeNet().catch(() => {});
    if (st.net.open && left === 0) refresh();
  }

  function mount() {
    bar = document.createElement("div");
    bar.className = "vb";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Vault-Status");
    bar.innerHTML = `
      <span class="vb-brand"><svg viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="4" width="40" height="40" rx="9" fill="#0b1f38" stroke="#facc15" stroke-width="3"/><circle cx="24" cy="24" r="8" fill="none" stroke="#facc15" stroke-width="3.5"/></svg><b>Vault offen</b><span class="vb-muted vb-hide-sm">${esc(st.owner || "")}</span></span>
      <span class="vb-sep"></span><span class="vb-net"></span>
      <button id="vb-log" class="vb-hide-sm" title="Welche Verbindungen das Programm aufgebaut hat">Verbindungen</button><span class="vb-muted vb-stats vb-hide-sm"></span>
      ${st.fallakte && st.fallakte.available ? `<button id="vb-fa" title="EagleEye-Fallakte: Büro, Mandanten, Rechnungen, beweissichere Web-Belege – im selben Vault, ohne zweite Anmeldung">📁 Fallakte</button>` : ""}
      <span class="vb-right"><span class="vb-muted vb-saved vb-hide-sm"></span><span class="vb-muted vb-idle"></span>
        <button id="vb-settings" title="Vault-Einstellungen">⚙</button>
        <button class="vb-lock" id="vb-lock" title="Sofort sperren (Strg+Alt+L)">🔒 Sperren</button></span>`;
    document.body.insertBefore(bar, document.body.firstChild);
    document.body.classList.add("has-vb");
    bar.querySelector("#vb-log").onclick = () => showLog().catch(() => {});
    bar.querySelector("#vb-settings").onclick = settingsDialog;
    const fa = bar.querySelector("#vb-fa");
    if (fa) fa.onclick = () => { window.open("/vault/fallakte", "eagleeye-fallakte", "noopener"); };
    bar.querySelector("#vb-lock").onclick = async () => { try { await call("POST", "/vault/api/lock"); } catch (_) { /* schon gesperrt */ } toLock(); };
    render();
  }

  async function refresh() {
    try {
      const s = await call("GET", "/vault/api/status");
      if (!s.unlocked || !s.signed_in) { toLock(); return; }
      st = s; receivedAt = Date.now(); render();
    } catch (_) { /* Server kurz nicht erreichbar */ }
  }

  // ------------------------------------------------------------------ Netzbedarf erkennen
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    const method = ((init && init.method) || (typeof input === "string" ? "GET" : input.method) || "GET").toUpperCase();
    let path = url;
    try { path = new URL(url, location.origin).pathname; } catch (_) { /* relativ */ }
    if (method === "POST" && NEEDS_NET.some((re) => re.test(path))) {
      await refresh();
      if (!(st && st.net.open)) {
        const ok = await openNetDialog("Für diese Abfrage muss der Vault kurz ins Internet. Ohne Freigabe wird nichts gesendet.");
        if (!ok) return new Response(JSON.stringify({ detail: "Abgebrochen – das Netz des Vaults ist geschlossen. Oben „Netz öffnen“ wählen, wenn Sie abfragen möchten." }),
          { status: 428, headers: { "Content-Type": "application/json" } });
      }
    }
    const res = await origFetch(input, init);
    if (res.status === 423 && path.startsWith("/api/")) toLock();
    return res;
  };

  // ------------------------------------------------------------------ Aktivität (für die automatische Sperre)
  ["keydown", "mousedown", "wheel", "touchstart"].forEach((ev) => document.addEventListener(ev, () => { interacted = true; }, { passive: true, capture: true }));
  setInterval(() => {
    if (interacted && Date.now() - lastPing > 20000) {
      interacted = false; lastPing = Date.now();
      call("POST", "/vault/api/activity").then(() => { if (st) { st.idle_left = st.idle_minutes * 60; receivedAt = Date.now(); } }).catch(() => {});
    }
    render();
  }, 1000);
  setInterval(refresh, 10000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });

  async function start() {
    try {
      const auth = await (await origFetch("/api/auth/state", { headers: { "X-Requested-With": "EagleEye" } })).json();
      csrf = auth.csrf || "";
      st = await call("GET", "/vault/api/status");
      if (!st.unlocked || !st.signed_in) { toLock(); return; }
      receivedAt = Date.now();
      mount();
    } catch (e) { console.warn("Vault-Leiste nicht verfügbar:", e); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();

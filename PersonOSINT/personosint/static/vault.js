/* EagleEye Vault – Sperrbildschirm: Einrichtung, Entsperren, Wiederherstellung. Keine externen Ressourcen. */
(function () {
  "use strict";
  const card = document.getElementById("vault-card");
  const foot = document.getElementById("vault-foot");
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let status = null;

  async function call(method, url, body) {
    const opts = { method, headers: { "X-Requested-With": "EagleEye" }, credentials: "same-origin" };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(typeof data.detail === "string" ? data.detail : "Fehler " + r.status); e.status = r.status; throw e; }
    return data;
  }

  /* Nach dem Öffnen: Seite neu laden (gleiche Adresse mit Zeitmarke, damit der Browser wirklich neu lädt). */
  function enterApp() { location.replace("/?geoeffnet=" + Date.now() + "#/"); }

  function errBox(msg) { return msg ? `<div class="err" role="alert">${esc(msg)}</div>` : ""; }
  function busy(form, on) { form.querySelectorAll("button").forEach((b) => (b.disabled = on)); }
  function steps(n, total) { return `<div class="steps" aria-hidden="true">${Array.from({ length: total }, (_, i) => `<span class="${i < n ? "on" : ""}"></span>`).join("")}</div>`; }

  /* Passphrasen-Stärke: grobe, ehrliche Schätzung (Länge × Zeichenvielfalt), keine Garantie. */
  function strength(p) {
    if (!p) return [0, ""];
    const pools = [/[a-zäöüß]/, /[A-ZÄÖÜ]/, /\d/, /[^\wäöüßÄÖÜ]/].filter((re) => re.test(p)).length;
    const words = p.trim().split(/\s+/).filter((w) => w.length >= 3).length;
    const bits = Math.min(140, p.length * (1.6 + pools * 0.55) + words * 4);
    if (p.length < 12) return [Math.min(30, bits / 3), "zu kurz – mindestens 12 Zeichen"];
    if (bits < 45) return [40, "schwach"];
    if (bits < 70) return [65, "brauchbar – ein Wort mehr macht sie deutlich stärker"];
    return [100, "stark"];
  }
  function meter(input, out) {
    const color = (v) => (v < 50 ? "#dc2626" : v < 80 ? "#d97706" : "#16a34a");
    input.addEventListener("input", () => {
      const [v, label] = strength(input.value);
      out.querySelector("i").style.width = v + "%";
      out.querySelector("i").style.background = color(v);
      out.nextElementSibling.textContent = label ? "Stärke: " + label : "";
    });
  }

  // ------------------------------------------------------------------ Einrichtung (erster Start)
  function setupStep1(msg) {
    card.innerHTML = `${steps(1, 3)}
      <h1>Willkommen – Ihr Vault wird eingerichtet</h1>
      <p class="muted">Ein Vault ist ein verschlüsselter Tresor für Ihre Recherchen. Er ist nur von diesem Rechner aus erreichbar und geht nur ins Internet, wenn Sie es ausdrücklich erlauben.</p>
      ${errBox(msg)}
      <form id="f1" autocomplete="off">
        <label class="field"><span>Ihr Name oder Kürzel</span><input type="text" name="display_name" required maxlength="80" autocomplete="off"></label>
        <label class="field"><span>Passphrase</span><input type="password" name="passphrase" required minlength="12" autocomplete="new-password">
          <div class="meter"><i></i></div><small></small>
          <small>Am besten ein Satz aus vier oder mehr Wörtern, z. B. „Hafenlichter zählen sieben Möwen im Nebel“. Nirgends sonst verwenden.</small></label>
        <label class="field"><span>Passphrase wiederholen</span><input type="password" name="passphrase2" required autocomplete="new-password"></label>
        ${status.classic_data ? `<label class="check"><input type="checkbox" name="import_classic" checked><span><b>Bisherige PersonOSINT-Daten übernehmen.</b> Fälle, Fotos und Belege aus dem bisherigen Datenordner werden in den Vault kopiert und dort verschlüsselt. Die alten Dateien bleiben unverändert, bis Sie sie selbst löschen.</span></label>` : ""}
        <div class="note warn small"><b>Wichtig:</b> Ohne Passphrase und ohne Wiederherstellungsschlüssel kann niemand die Daten öffnen – auch kein Support.</div>
        <button class="btn btn-primary btn-wide">Weiter: Zwei-Faktor-App verbinden</button>
      </form>`;
    const f = document.getElementById("f1");
    meter(f.passphrase, f.querySelector(".meter"));
    f.display_name.focus();
    f.onsubmit = async (ev) => {
      ev.preventDefault(); busy(f, true);
      try {
        const res = await call("POST", "/vault/api/setup/begin", { display_name: f.display_name.value, passphrase: f.passphrase.value, passphrase2: f.passphrase2.value });
        setupStep2(res, f.import_classic ? f.import_classic.checked : false);
      } catch (e) { setupStep1(e.message); }
    };
  }

  function setupStep2(res, importClassic, msg) {
    card.innerHTML = `${steps(2, 3)}
      <h1>Zwei-Faktor-App verbinden</h1>
      <p class="muted">Zum Öffnen brauchen Sie künftig die Passphrase <b>und</b> einen sechsstelligen Code aus einer Authenticator-App (z. B. Microsoft Authenticator, Aegis, 2FAS).</p>
      ${errBox(msg)}
      <div class="qr"><div class="svg">${res.qr_svg}</div>
        <div class="small"><b>So geht's:</b><ol style="padding-left:18px;margin:6px 0"><li>App öffnen, „Konto hinzufügen“</li><li>QR-Code scannen</li><li>angezeigten Code unten eingeben</li></ol>
        Ohne Kamera: Schlüssel von Hand eingeben<br><code class="secret">${esc(res.secret)}</code></div></div>
      <form id="f2" autocomplete="off">
        <label class="field"><span>Code aus der App</span><input class="code" name="code" inputmode="numeric" pattern="[0-9 ]{6,7}" maxlength="7" required autocomplete="one-time-code"></label>
        <button class="btn btn-primary btn-wide">Vault anlegen</button>
      </form>`;
    const f = document.getElementById("f2");
    f.code.focus();
    f.onsubmit = async (ev) => {
      ev.preventDefault(); busy(f, true);
      card.querySelector("h1").textContent = "Vault wird angelegt und verschlüsselt …";
      try {
        const done = await call("POST", "/vault/api/setup/finish", { code: f.code.value.replace(/\s/g, ""), import_classic: importClassic });
        setupStep3(done);
      } catch (e) { setupStep2(res, importClassic, e.message); }
    };
  }

  function setupStep3(done) {
    const last = done.recovery_key.split("-").pop();
    card.innerHTML = `${steps(3, 3)}
      <h1>Ihr Wiederherstellungsschlüssel</h1>
      <p>Damit öffnen Sie den Vault, falls Sie die Passphrase vergessen. Er wird <b>nur jetzt</b> angezeigt.</p>
      <div class="recovery" id="rk">${esc(done.recovery_key)}</div>
      <ul class="plain small"><li>Auf Papier notieren und getrennt vom Rechner aufbewahren (z. B. Tresor, Bankschließfach).</li>
        <li>Nicht fotografieren, nicht in einer Cloud oder Mail speichern.</li></ul>
      ${done.imported ? `<div class="note small">Übernommen: <b>${done.imported_cases}</b> Fälle samt Fotos und Belegen. Die alten Dateien im bisherigen Datenordner können Sie löschen, sobald Sie hier alles geprüft haben.</div>` : ""}
      <form id="f3" autocomplete="off">
        <label class="field"><span>Zur Bestätigung: letzte Gruppe des Schlüssels eintippen</span><input type="text" name="confirm" maxlength="5" required autocomplete="off" spellcheck="false"></label>
        <button class="btn btn-gold btn-wide">Notiert – Vault öffnen</button>
      </form>`;
    const f = document.getElementById("f3");
    f.confirm.focus();
    f.onsubmit = (ev) => {
      ev.preventDefault();
      if (f.confirm.value.trim().toUpperCase() !== last) { f.confirm.setCustomValidity("Stimmt nicht – bitte den Schlüssel noch einmal ablesen."); f.confirm.reportValidity(); return; }
      enterApp();
    };
    f.confirm.oninput = () => f.confirm.setCustomValidity("");
  }

  // ------------------------------------------------------------------ Entsperren
  function unlockView(msg) {
    const reason = status.lock_reason ? `<div class="note small">🔒 ${esc(status.lock_reason)}.</div>` : "";
    const wait = status.wait_seconds ? `<div class="err">Zu viele Fehlversuche. Bitte ${status.wait_seconds} Sekunden warten.</div>` : "";
    card.innerHTML = `<h1>Vault öffnen</h1>
      <p class="muted">Passphrase und den aktuellen Code aus Ihrer Authenticator-App eingeben.</p>
      ${reason}${wait}${errBox(msg)}
      <form id="fu" autocomplete="off">
        <label class="field"><span>Passphrase</span><input type="password" name="passphrase" required autocomplete="current-password"></label>
        <label class="field"><span>Code aus der App</span><input class="code" name="code" inputmode="numeric" pattern="[0-9 ]{6,7}" maxlength="7" required autocomplete="one-time-code"></label>
        <button class="btn btn-primary btn-wide">🔓 Vault öffnen</button>
      </form>
      <div class="btn-row"><button class="btn btn-link" id="to-recover">Passphrase vergessen? Mit Wiederherstellungsschlüssel öffnen</button></div>`;
    const f = document.getElementById("fu");
    f.passphrase.focus();
    document.getElementById("to-recover").onclick = () => recoverView();
    f.onsubmit = async (ev) => {
      ev.preventDefault(); busy(f, true);
      card.querySelector("h1").textContent = "Wird entschlüsselt …";
      try {
        await call("POST", "/vault/api/unlock", { passphrase: f.passphrase.value, code: f.code.value.replace(/\s/g, "") });
        enterApp();
      } catch (e) { status = await call("GET", "/vault/api/status").catch(() => status); unlockView(e.message); }
    };
  }

  function recoverView(msg) {
    card.innerHTML = `<h1>Mit Wiederherstellungsschlüssel öffnen</h1>
      <p class="muted">Den notierten Schlüssel eingeben und gleich eine <b>neue Passphrase</b> festlegen. Die Zwei-Faktor-App bleibt unverändert.</p>
      ${errBox(msg)}
      <form id="fr" autocomplete="off">
        <label class="field"><span>Wiederherstellungsschlüssel</span><input type="text" name="recovery_key" required spellcheck="false" autocomplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"></label>
        <label class="field"><span>Neue Passphrase</span><input type="password" name="passphrase" required minlength="12" autocomplete="new-password"><div class="meter"><i></i></div><small></small></label>
        <label class="field"><span>Neue Passphrase wiederholen</span><input type="password" name="passphrase2" required autocomplete="new-password"></label>
        <button class="btn btn-primary btn-wide">Öffnen und neue Passphrase speichern</button>
      </form>
      <div class="btn-row"><button class="btn btn-link" id="to-unlock">← Zurück</button></div>`;
    const f = document.getElementById("fr");
    meter(f.passphrase, f.querySelector(".meter"));
    f.recovery_key.focus();
    document.getElementById("to-unlock").onclick = () => unlockView();
    f.onsubmit = async (ev) => {
      ev.preventDefault(); busy(f, true);
      try {
        await call("POST", "/vault/api/recover", { recovery_key: f.recovery_key.value, passphrase: f.passphrase.value, passphrase2: f.passphrase2.value });
        enterApp();
      } catch (e) { recoverView(e.message); }
    };
  }

  function elsewhereView() {
    card.innerHTML = `<h1>Vault ist in einem anderen Fenster geöffnet</h1>
      <p>Aus Sicherheitsgründen gibt es immer nur eine geöffnete Sitzung. Bitte im anderen Fenster weiterarbeiten oder dort sperren.</p>
      <p class="muted small">Sie haben das andere Fenster geschlossen? Dann sperrt sich der Vault nach der eingestellten Zeit ohne Eingabe von selbst – oder Sie beenden das Programm (Fenster „EagleEye Vault“ schließen) und starten es neu.</p>
      <div class="btn-row"><button class="btn btn-primary" id="again">Erneut prüfen</button></div>`;
    document.getElementById("again").onclick = boot;
  }

  async function boot() {
    try { status = await call("GET", "/vault/api/status"); }
    catch (e) { card.innerHTML = errBox("Der Vault antwortet nicht: " + e.message); return; }
    foot.textContent = `EagleEye Vault ${status.version} · läuft nur auf diesem Rechner (127.0.0.1)`;
    if (status.unlocked && status.signed_in) { enterApp(); return; }
    if (status.unlocked) { elsewhereView(); return; }
    if (!status.exists) { setupStep1(); return; }
    unlockView();
  }
  boot();
})();

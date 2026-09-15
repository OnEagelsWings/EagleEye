/* EagleEye Build 136 same-origin photo evidence drop zone. */
"use strict";

(() => {
  const drop = document.getElementById("photo136-drop");
  if (!drop) return;
  const input = document.getElementById("photo136-file");
  const status = document.getElementById("photo136-status");
  const target = document.getElementById("photo136-target");
  const title = document.getElementById("photo136-title");
  const pageUrl = document.getElementById("photo136-page");
  const sourceUrl = document.getElementById("photo136-source");
  const notes = document.getElementById("photo136-notes");

  function setStatus(text, error=false) {
    status.hidden = false;
    status.textContent = String(text || "");
    status.className = error ? "notice error" : "notice";
  }

  function metadata() {
    return {
      case_id: drop.dataset.caseId || "",
      target_id: target ? target.value : "",
      title: title ? title.value : "Personenfoto",
      source_page_url: pageUrl ? pageUrl.value.trim() : "",
      source_url: sourceUrl ? sourceUrl.value.trim() : "",
      source_label: "drag_drop_136",
      notes: notes ? notes.value : ""
    };
  }

  async function send(payload) {
    const response = await fetch(drop.dataset.endpoint, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-EagleEye-CSRF": drop.dataset.csrf || ""},
      body: JSON.stringify({...metadata(), ...payload}),
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error"
    });
    let result = {};
    try { result = await response.json(); } catch (_error) {}
    if (!response.ok || !result.ok) throw new Error(result.detail || `Fotoaufnahme fehlgeschlagen (${response.status})`);
    return result;
  }

  function toBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const value = String(reader.result || "");
        resolve(value.includes(",") ? value.split(",", 2)[1] : value);
      };
      reader.onerror = () => reject(new Error(`Datei konnte nicht gelesen werden: ${file.name}`));
      reader.readAsDataURL(file);
    });
  }

  async function uploadFiles(files) {
    const images = Array.from(files || []).filter(file => file && String(file.type || "").startsWith("image/"));
    if (!images.length) throw new Error("Keine unterstützte Bilddatei erkannt.");
    let completed = 0;
    for (const file of images) {
      if (file.size > 12 * 1024 * 1024) throw new Error(`${file.name}: größer als 12 MB.`);
      setStatus(`Sichere ${file.name} … (${completed + 1}/${images.length})`);
      const data = await toBase64(file);
      await send({source_kind: "local_file", filename: file.name, mime_type: file.type, data_base64: data, title: title && title.value !== "Personenfoto" ? title.value : file.name});
      completed += 1;
    }
    setStatus(`${completed} Bild(er) unverändert gesichert. Galerie wird aktualisiert …`);
    window.setTimeout(() => window.location.reload(), 450);
  }

  function extractUrl(dataTransfer) {
    const uri = String(dataTransfer.getData("text/uri-list") || "").split(/\r?\n/).find(line => line && !line.startsWith("#"));
    if (uri && uri.startsWith("https://")) return uri;
    const plain = String(dataTransfer.getData("text/plain") || "").trim();
    if (plain.startsWith("https://")) return plain.split(/\s+/)[0];
    const html = String(dataTransfer.getData("text/html") || "");
    const match = html.match(/<img[^>]+src=["'](https:\/\/[^"']+)["']/i);
    return match ? match[1] : "";
  }

  async function handleDrop(event) {
    event.preventDefault();
    drop.classList.remove("dragging");
    try {
      if (event.dataTransfer.files && event.dataTransfer.files.length) {
        await uploadFiles(event.dataTransfer.files);
        return;
      }
      const url = extractUrl(event.dataTransfer);
      if (!url) throw new Error("Das gezogene Webbild liefert keine Datei. Speichere es lokal oder füge eine direkte HTTPS-Bildadresse ein.");
      setStatus("Speichere Bild-URL als candidate-only Referenz …");
      await send({source_kind: "remote_reference", source_url: url, title: title ? title.value : "Personenfoto"});
      setStatus("Bildreferenz gespeichert. Es wurde kein autonomer Download ausgeführt.");
      window.setTimeout(() => window.location.reload(), 450);
    } catch (error) { setStatus(error && error.message ? error.message : String(error), true); }
  }

  drop.addEventListener("click", () => input.click());
  input.addEventListener("change", () => uploadFiles(input.files).catch(error => setStatus(error.message || String(error), true)));
  drop.addEventListener("dragover", event => { event.preventDefault(); drop.classList.add("dragging"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("dragging"));
  drop.addEventListener("drop", handleDrop);
  document.addEventListener("paste", event => {
    const files = event.clipboardData && event.clipboardData.files;
    if (files && files.length) uploadFiles(files).catch(error => setStatus(error.message || String(error), true));
  });
})();

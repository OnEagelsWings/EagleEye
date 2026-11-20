"""Manual, local-only graphical control surface for the public-topic exchange.

Import only happens on the user's button press; each outbound record needs a
preview, exact typed approval, and a separate confirmed publish action.
No web browser, HTML rendering, cron job, or automatic evidence import.
"""
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from desktop_workflow import DesktopWorkflow
from signed_approval import CONFIRMATION


def text_view(parent, *, height=15):
    widget = tk.Text(parent, wrap="word", height=height, font=("Consolas", 10),
                     background="#f8fafc", relief="solid", borderwidth=1)
    widget.configure(state="disabled")
    return widget


def fill_text(widget, value):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


class ResearchBridgeWindow(tk.Tk):
    def __init__(self, workspace):
        super().__init__()
        self.workflow = DesktopWorkflow(workspace)
        self.title("EagleEye | Forschungs-Brücke (manuelle Vorschau)")
        self.geometry("1060x730")
        self.minsize(850, 610)
        self._jobs = queue.Queue()
        self._busy = False
        self._receipt = None
        self._previewed = None
        self._last_digest = None
        self._inbound_names = []
        self._outbound_names = []

        ttk.Label(self, text="EAGLEEYE  /  FORSCHUNGS-BRÜCKE",
                  font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=16, pady=(14, 3))
        ttk.Label(self,
                  text="Nur öffentliche Sachthemen • Keine personenbezogenen Daten • Keine automatischen Übertragungen",
                  foreground="#ac2636").pack(anchor="w", padx=16, pady=(0, 8))
        self.status = tk.StringVar(value="Bereit. Alle Aktionen benötigen einen bewussten Klick.")
        ttk.Label(self, textvariable=self.status, foreground="#1b5269").pack(
            anchor="w", padx=16, pady=(0, 8))
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.incoming = ttk.Frame(tabs, padding=10)
        self.outgoing = ttk.Frame(tabs, padding=10)
        self.audit_tab = ttk.Frame(tabs, padding=10)
        tabs.add(self.incoming, text="1 · Eingang prüfen")
        tabs.add(self.outgoing, text="2 · Ausgang freigeben")
        tabs.add(self.audit_tab, text="3 · Audit")
        self._build_incoming()
        self._build_outgoing()
        self._build_audit()
        self._refresh_inbound()
        self._refresh_outbound()
        self._refresh_audit()
        self.after(100, self._poll_jobs)

    def _build_incoming(self):
        header = ttk.Frame(self.incoming)
        header.pack(fill="x")
        ttk.Button(header, text="Aus privatem Forschungsbranch abrufen",
                   command=self._pull).pack(side="left", padx=(0, 8))
        ttk.Button(header, text="Lokale Liste aktualisieren",
                   command=self._refresh_inbound).pack(side="left")
        ttk.Button(header, text="Nach Prüfung freigeben",
                   command=lambda: self._review_inbound("approved")).pack(side="left", padx=(12, 5))
        ttk.Button(header, text="Zurückstellen",
                   command=lambda: self._review_inbound("deferred")).pack(side="left", padx=(0, 5))
        ttk.Label(self.incoming,
                  text="Abruf speichert nur validierte Datensätze lokal. Kein Import in EagleEye-Fallakten.",
                  foreground="#5b6472").pack(anchor="w", pady=(8, 10))
        pane = ttk.PanedWindow(self.incoming, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left = ttk.Frame(pane, padding=6)
        right = ttk.Frame(pane, padding=6)
        pane.add(left, weight=1)
        pane.add(right, weight=3)
        ttk.Label(left, text="Eingang (ID)").pack(anchor="w")
        self.in_list = tk.Listbox(left, exportselection=False, font=("Consolas", 9))
        self.in_list.pack(fill="both", expand=True)
        self.in_list.bind("<<ListboxSelect>>", lambda _: self._preview_inbound())
        ttk.Label(right, text="Datensatz und Audit – nur Text").pack(anchor="w")
        self.in_preview = text_view(right, height=23)
        self.in_preview.pack(fill="both", expand=True)

    def _build_outgoing(self):
        area = ttk.PanedWindow(self.outgoing, orient="horizontal")
        area.pack(fill="both", expand=True)
        left = ttk.Frame(area, padding=6)
        right = ttk.Frame(area, padding=6)
        area.add(left, weight=2)
        area.add(right, weight=3)
        ttk.Label(left, text="Neuen Forschungsentwurf erstellen",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(left, text="Art").pack(anchor="w")
        self.kind = tk.StringVar(value="research_request")
        self.kind_dropdown = ttk.Combobox(left, textvariable=self.kind, state="readonly",
            values=["research_request", "research_result"])
        self.kind_dropdown.pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="Thema (keine Personen/Fälle)").pack(anchor="w")
        self.topic = ttk.Entry(left)
        self.topic.pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="Anfrage / Zusammenfassung").pack(anchor="w")
        self.summary = tk.Text(left, height=6, wrap="word")
        self.summary.pack(fill="x", pady=(0, 8))
        ttk.Label(left, text="Öffentliche Quelle (HTTPS, optional)").pack(anchor="w")
        self.source_url = ttk.Entry(left)
        self.source_url.pack(fill="x", pady=(0, 7))
        self.synthetic = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Synthetischer Testdatensatz",
                        variable=self.synthetic).pack(anchor="w", pady=(0, 8))
        ttk.Button(left, text="Entwurf lokal speichern (kein Upload)",
                   command=self._create_draft).pack(fill="x")
        ttk.Separator(left).pack(fill="x", pady=14)
        ttk.Label(left, text="Freigabe nur nach Vorschau und genauer Prüfung",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(left, text="Freigabesatz exakt eingeben:").pack(anchor="w", pady=(10, 4))
        self.confirmation = ttk.Entry(left)
        self.confirmation.pack(fill="x")
        ttk.Label(left, text=CONFIRMATION, foreground="#496675").pack(anchor="w", pady=3)
        ttk.Button(left, text="Ausgewählten Datensatz signieren",
                   command=self._approve_outbound).pack(fill="x", pady=(8, 3))
        ttk.Button(left, text="Signierten Datensatz auf privatem Branch veröffentlichen",
                   command=self._publish).pack(fill="x", pady=(3, 0))
        ttk.Label(left, text="Kein automatisches Senden. Jeder Upload erfordert zwei Aktionen.",
                  foreground="#ac2636", wraplength=335).pack(anchor="w", pady=9)

        buttons = ttk.Frame(right)
        buttons.pack(fill="x")
        ttk.Label(buttons, text="Lokale Entwürfe").pack(side="left")
        ttk.Button(buttons, text="Aktualisieren",
                   command=self._refresh_outbound).pack(side="right")
        self.out_list = tk.Listbox(right, height=6, exportselection=False,
                                   font=("Consolas", 9))
        self.out_list.pack(fill="x", pady=7)
        self.out_list.bind("<<ListboxSelect>>", lambda _: self._preview_outbound())
        ttk.Label(right, text="Vorschau – ausschließlich Klartext, keine Ausführung").pack(anchor="w")
        self.out_preview = text_view(right, height=22)
        self.out_preview.pack(fill="both", expand=True)

    def _build_audit(self):
        ttk.Label(self.audit_tab,
                  text="Lokales Ausgangsprotokoll – HMAC-verkettet, vor jedem Lesen geprüft",
                  foreground="#5b6472").pack(anchor="w", pady=(0, 8))
        ttk.Button(self.audit_tab, text="Audit aktualisieren",
                   command=self._refresh_audit).pack(anchor="w", pady=(0, 8))
        self.audit_preview = text_view(self.audit_tab, height=25)
        self.audit_preview.pack(fill="both", expand=True)

    def _set_status(self, message):
        self.status.set(message)

    def _refresh_inbound(self):
        try:
            entries = self.workflow.list_inbound()
            self._inbound_names = [item["id"] for item in entries]
            self.in_list.delete(0, "end")
            for item in entries:
                self.in_list.insert("end", item["id"])
        except Exception as exc:
            messagebox.showerror("Eingang", str(exc))

    def _preview_inbound(self):
        selection = self.in_list.curselection()
        if not selection:
            return
        try:
            ident = self._inbound_names[selection[0]]
            detail = self.workflow.inbound_detail(ident)
            detail["local_review"] = [x for x in self.workflow.audit_events()
                                      if x["id"] == ident and x["status"].startswith("inbound-")]
            fill_text(self.in_preview, json.dumps(detail, ensure_ascii=False, indent=2))
        except Exception as exc:
            fill_text(self.in_preview, "Integritäts-/Leseproblem: " + str(exc))
            self._set_status("Eingang nicht vertrauenswürdig – Prüfung erforderlich.")

    def _review_inbound(self, decision):
        selection = self.in_list.curselection()
        if not selection:
            messagebox.showwarning("Manuelle Prüfung", "Bitte einen Datensatz auswählen und prüfen.")
            return
        ident = self._inbound_names[selection[0]]
        phrase = CONFIRMATION if decision == "approved" else "DEFER PUBLIC RESEARCH"
        typed = simpledialog.askstring(
            "Explizite lokale Entscheidung",
            f"Nur öffentliche Sachthemen und keine Fallakten.\n"
            f"Datensatz: {ident}\n"
            f"Bestätigung exakt eingeben: {phrase}",
            parent=self)
        if typed is None:
            return
        try:
            self.workflow.review_inbound(ident, decision, typed)
            self._preview_inbound()
            self._refresh_audit()
            self._set_status("Lokale Eingangsprüfung protokolliert; nichts übertragen oder importiert.")
        except Exception as exc:
            messagebox.showerror("Prüfentscheidung abgelehnt", str(exc))

    def _refresh_outbound(self, selected=None):
        try:
            names = self.workflow.list_outbound()
            self._outbound_names = names
            self.out_list.delete(0, "end")
            for name in names:
                self.out_list.insert("end", name)
            if selected in names:
                index = names.index(selected)
                self.out_list.selection_set(index)
                self._preview_outbound()
        except Exception as exc:
            messagebox.showerror("Ausgang", str(exc))

    def _selected_outbound(self):
        selection = self.out_list.curselection()
        if not selection:
            raise ValueError("Bitte zuerst einen Entwurf auswählen und prüfen")
        return self._outbound_names[selection[0]]

    def _clear_approval(self):
        self._receipt = None
        self._previewed = None
        self._last_digest = None

    def _preview_outbound(self):
        self._clear_approval()
        try:
            name = self._selected_outbound()
            data = self.workflow.outgoing_detail(name)
            self._previewed = name
            self._last_digest = data["sha256"]
            fill_text(self.out_preview, json.dumps(data, ensure_ascii=False, indent=2))
            self._set_status("Entwurf geladen. Inhalt und Quellen vor Freigabe prüfen.")
        except Exception as exc:
            fill_text(self.out_preview, "Ungültiger Entwurf: " + str(exc))

    def _create_draft(self):
        try:
            sources = []
            url = self.source_url.get().strip()
            if url:
                sources = [{"title": "Öffentliche Referenz", "url": url}]
            filename = self.workflow.create_draft(
                self.topic.get().strip(), self.summary.get("1.0", "end").strip(),
                kind=self.kind.get(), sources=sources, synthetic=self.synthetic.get())
            self._refresh_outbound(filename)
            self._set_status("Entwurf nur lokal gespeichert: " + filename)
        except Exception as exc:
            messagebox.showerror("Entwurf abgelehnt", str(exc))

    def _approve_outbound(self):
        try:
            filename = self._selected_outbound()
            if self._previewed != filename:
                raise ValueError("Vor der Freigabe die Vorschau öffnen")
            data = self.workflow.outgoing_detail(filename)
            if self._last_digest != data["sha256"]:
                raise ValueError("Datensatz seit der Vorschau verändert")
            receipt, digest = self.workflow.sign_outgoing(
                filename, self.confirmation.get())
            self._receipt = (filename, digest, receipt)
            self.confirmation.delete(0, "end")
            self._set_status("Datensatz freigegeben (nur im Arbeitsspeicher). Noch NICHT übertragen.")
        except Exception as exc:
            self._clear_approval()
            messagebox.showerror("Freigabe verweigert", str(exc))

    def _publish(self):
        if self._busy:
            return
        try:
            filename = self._selected_outbound()
            if self._receipt is None or self._receipt[0] != filename:
                raise ValueError("Es fehlt die ausdrückliche Freigabe dieses Datensatzes")
            if self.workflow.outgoing_detail(filename)["sha256"] != self._receipt[1]:
                raise ValueError("Datei hat sich nach Freigabe verändert")
            if not messagebox.askyesno(
                    "Wirklich veröffentlichen?",
                    "Nur öffentliche Sachthemen, keine Personen, Fallakten oder Zugangsdaten.\n"
                    "Diesen einen Datensatz auf den PRIVATEN MichaIntel-Branch übertragen?"):
                return
            self._run_job("Veröffentlichung", self.workflow.publish_outgoing,
                          filename, self._receipt[2])
        except Exception as exc:
            messagebox.showerror("Veröffentlichung verweigert", str(exc))

    def _pull(self):
        if self._busy:
            return
        if not messagebox.askyesno("Manueller Abruf",
                    "Jetzt ausschließlich aus dem privaten Forschungsbranch abrufen "
                    "und valide Datensätze lokal zwischenlagern?"):
            return
        self._run_job("Abruf", self.workflow.pull_inbound)

    def _run_job(self, label, fn, *args):
        self._busy = True
        self._set_status(label + " läuft. Bitte keine zweite Aktion starten.")
        def worker():
            try:
                result = fn(*args)
                self._jobs.put((label, True, result))
            except Exception as exc:
                self._jobs.put((label, False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_jobs(self):
        try:
            while True:
                label, ok, result = self._jobs.get_nowait()
                self._busy = False
                self._clear_approval()
                if ok:
                    self._set_status(label + " abgeschlossen. "
                                     + (str(result) if result else ""))
                    self._refresh_inbound()
                    self._refresh_outbound()
                    self._refresh_audit()
                else:
                    self._set_status(label + " fehlgeschlagen. Keine automatische Wiederholung.")
                    messagebox.showerror(label, str(result))
        except queue.Empty:
            pass
        self.after(150, self._poll_jobs)

    def _refresh_audit(self):
        try:
            events = self.workflow.audit_events()
            if not events:
                fill_text(self.audit_preview, "Noch keine ausgehenden Übertragungen protokolliert.")
                return
            fill_text(self.audit_preview, json.dumps(events[-200:], ensure_ascii=False, indent=2))
        except Exception as exc:
            fill_text(self.audit_preview, "AUDIT-INTEGRITÄTSFEHLER: " + str(exc))
            self._set_status("Audit-Verifikation fehlgeschlagen; ausgehende Übertragung gesperrt.")


def main():
    home = os.environ.get("LOCALAPPDATA")
    if not home:
        raise SystemExit("LOCALAPPDATA missing: Windows desktop installation required")
    root = Path(home) / "EagleEyeResearchBridge"
    if not root.is_dir():
        raise SystemExit("EagleEyeResearchBridge workspace not installed")
    ResearchBridgeWindow(root).mainloop()


if __name__ == "__main__":
    main()

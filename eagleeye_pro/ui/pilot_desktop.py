from __future__ import annotations
import json
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

BUILD_NAME = "EagleEye PersonOSINT Pro – Build 44.0 Safe Mode / Pilot Launcher"

class PilotDesktop(tk.Tk):
    def __init__(self, base_dir: str | Path | None = None, startup_error: str = ""):
        super().__init__()
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.startup_error = startup_error
        self.title(BUILD_NAME)
        self.geometry("1000x680")
        self.status = tk.StringVar(value="Safe Mode bereit. Voll-GUI konnte nicht starten oder Safe Mode wurde angefordert.")
        self._build()
        self._refresh_status()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text=BUILD_NAME, font=("Arial", 14, "bold")).pack(side="left")
        ttk.Label(top, textvariable=self.status).pack(side="right")

        intro = ttk.LabelFrame(self, text="Real-World UX & Pilot Hardening")
        intro.pack(fill="x", padx=10, pady=8)
        ttk.Label(intro, text="Diese Safe-Mode-Oberfläche startet auch dann, wenn ein Fach-Tab der Voll-GUI scheitert. Sie dient zur Diagnose, Demo-Fallerstellung und zum kontrollierten Neustart.", wraplength=940).pack(anchor="w", padx=8, pady=6)

        buttons = ttk.Frame(self); buttons.pack(fill="x", padx=10, pady=6)
        ttk.Button(buttons, text="Diagnose ausführen", command=self.run_diagnostics).pack(side="left", padx=4)
        ttk.Button(buttons, text="Demo-Fall initialisieren", command=self.init_demo).pack(side="left", padx=4)
        ttk.Button(buttons, text="Voll-GUI erneut versuchen", command=self.retry_full_gui).pack(side="left", padx=4)
        ttk.Button(buttons, text="Datenordner öffnen", command=lambda: self.open_folder(self.base_dir / "data")).pack(side="left", padx=4)
        ttk.Button(buttons, text="Reports öffnen", command=lambda: self.open_folder(self.base_dir / "reports")).pack(side="left", padx=4)
        ttk.Button(buttons, text="Logs öffnen", command=lambda: self.open_folder(self.base_dir / "logs")).pack(side="left", padx=4)

        panes = ttk.Panedwindow(self, orient="horizontal"); panes.pack(fill="both", expand=True, padx=10, pady=8)
        left = ttk.Frame(panes); right = ttk.Frame(panes)
        panes.add(left, weight=1); panes.add(right, weight=2)

        box = ttk.LabelFrame(left, text="Startstatus")
        box.pack(fill="both", expand=True, padx=4, pady=4)
        self.status_tree = ttk.Treeview(box, columns=("key", "value"), show="headings", height=12)
        self.status_tree.heading("key", text="Check"); self.status_tree.heading("value", text="Wert")
        self.status_tree.column("key", width=180); self.status_tree.column("value", width=320)
        self.status_tree.pack(fill="both", expand=True, padx=4, pady=4)

        txtbox = ttk.LabelFrame(right, text="Diagnose / Startfehler / Hinweise")
        txtbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.text = tk.Text(txtbox, wrap="word")
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        if self.startup_error:
            self.text.insert("end", "STARTFEHLER DER VOLL-GUI\n\n" + self.startup_error)

    def _refresh_status(self):
        self.status_tree.delete(*self.status_tree.get_children())
        items = {
            "base_dir": str(self.base_dir),
            "data_dir": str(self.base_dir / "data"),
            "reports_dir": str(self.base_dir / "reports"),
            "logs_dir": str(self.base_dir / "logs"),
            "python": sys.version.split()[0],
        }
        for k, v in items.items():
            self.status_tree.insert("", "end", values=(k, v))

    def run_diagnostics(self):
        try:
            from eagleeye.bootstrap.startup import diagnose
            result = diagnose(self.base_dir)
            self.text.delete("1.0", "end")
            self.text.insert("end", json.dumps(result, ensure_ascii=False, indent=2))
            self.status.set("Diagnose abgeschlossen: " + result.get("status", "unknown"))
        except Exception as exc:
            messagebox.showerror("Diagnose", str(exc))

    def init_demo(self):
        try:
            # Legacy demo creation is resolved dynamically to keep the safe-mode UI
            # independent from the historical main/startup import cycle.
            import importlib
            create_demo_case = importlib.import_module("eagleeye_pro.main").create_demo_case
            ctx = AppContext(base_dir=self.base_dir)
            try:
                case = create_demo_case(ctx)
            finally:
                ctx.close()
            self.status.set("Demo-Fall erstellt: " + case.get("case_id", ""))
            self.text.insert("end", "\n\nDemo-Fall erstellt:\n" + json.dumps(case, ensure_ascii=False, indent=2))
        except Exception as exc:
            messagebox.showerror("Demo-Fall", str(exc))

    def retry_full_gui(self):
        self.destroy()
        from eagleeye_pro.ui.desktop import run_desktop
        run_desktop(base_dir=self.base_dir)

    def open_folder(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            self.text.insert("end", f"\nOrdner: {path}\n")


def run_pilot_desktop(base_dir=None, startup_error: str = ""):
    app = PilotDesktop(base_dir=base_dir, startup_error=startup_error)
    app.mainloop()

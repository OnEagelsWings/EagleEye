"""Local EagleEye analysis adapters. Each run has a separate output directory."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid

TOOLS = {
    "metadata": ("ExifTool", ["exiftool"]),
    "search": ("Recoll", ["recollindex", "recollq"]),
    "ocr": ("OCRmyPDF", ["ocrmypdf", "tesseract"]),
    "video": ("FFmpeg + ffprobe", ["ffmpeg", "ffprobe"]),
    "alias": ("Sherlock", ["sherlock"]),
    "timeline": ("The Sleuth Kit", ["fls"]),
}
OUT = Path(os.environ.get("EAGLEEYE_ANALYSIS_HOME", Path.home() / "EagleEye-Analysen"))
os.environ["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")])

def locate(name):
    return shutil.which(name)

def capabilities():
    status = {key: {"label": title, "missing": [t for t in tools if not locate(t)]}
            for key, (title, tools) in TOOLS.items()}
    if status["search"]["missing"] and locate("pdftotext"):
        status["search"] = {"label":"PDF- und Textsuche (Poppler)", "missing":[]}
    return status

def command(name, *args, output=None, timeout=900):
    exe = locate(name)
    if not exe:
        raise ValueError(f"{name} fehlt auf diesem Gerät.")
    proc = subprocess.run([exe, *map(str, args)], shell=False, stdout=output or subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode:
        raise ValueError(f"{name}: " + (proc.stderr or proc.stdout or b"").decode("utf-8", "replace")[-1400:])
    return (proc.stdout or b"").decode("utf-8", "replace")

def analyze(case, mode, paths, query="", offset=0):
    if mode not in TOOLS or not isinstance(case, str) or not 0 < len(case) <= 100:
        raise ValueError("Ungültiger Fall oder Auftrag.")
    missing = capabilities()[mode]["missing"]
    if missing:
        raise ValueError("Fehlende Programme: " + ", ".join(missing))
    if not isinstance(paths, list) or len(paths) > 100 or len(query) > 200:
        raise ValueError("Zu viele Eingaben.")
    files = [Path(p.strip().strip('"')).expanduser().resolve(strict=True) for p in paths]
    if mode != "alias" and (not files or not all(p.is_file() for p in files)):
        raise ValueError("Bitte lokale Dateien auswählen.")
    if mode in ("ocr", "timeline") and len(files) != 1:
        raise ValueError("Bitte genau eine Quelldatei wählen.")
    if mode == "video" and len(files) > 2:
        raise ValueError("Bitte ein oder zwei Videos wählen.")
    if mode == "search" and not query.strip():
        raise ValueError("Suchbegriff fehlt.")
    if mode == "alias" and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", query):
        raise ValueError("Bitte einen einzelnen öffentlichen Benutzernamen eingeben.")
    if mode == "timeline" and not 0 <= int(offset) <= 2**53:
        raise ValueError("Ungültiger Startsektor.")
    job = str(uuid.uuid4())
    dest = OUT / job
    dest.mkdir(parents=True, exist_ok=False)
    sources = []
    for p in files:
        with p.open("rb") as stream:
            h = hashlib.file_digest(stream, "sha256").hexdigest()
        sources.append({"name": p.name, "sha256": h})
    def write(name, value):
        (dest / name).write_text(value, encoding="utf-8")
    programs = TOOLS[mode][1]
    if mode == "metadata":
        body = command("exiftool", "-j", "-G1", "-n", *files)
        data = json.loads(body)
        for row in data:
            for k in list(row):
                if k == "SourceFile": row[k] = Path(row[k]).name
                if k.endswith(":Directory"): del row[k]
        body = json.dumps(data, ensure_ascii=False, indent=2)
    elif mode == "ocr":
        target = dest / "OCR.pdf"
        lang = query.strip() or "deu+eng"
        if not re.fullmatch(r"[a-z]{3}(\+[a-z]{3})*", lang):
            raise ValueError("Sprachcodes wie deu+eng verwenden.")
        command("ocrmypdf", "--skip-text", "-l", lang, "--output-type", "pdf",
                files[0], target)
        body = "Durchsuchbare Arbeitskopie: OCR.pdf"
        if locate("pdftotext"):
            body += "\n" + command("pdftotext", "-layout", target, "-")
    elif mode == "search" and not all(locate(t) for t in programs):
        programs = ["pdftotext"]
        hits = []
        match_count = 0
        for p in files:
            if p.suffix.lower() == ".pdf":
                content = command("pdftotext", "-layout", p, "-")
            elif p.suffix.lower() in (".txt", ".md"):
                content = p.read_text(encoding="utf-8-sig", errors="replace")
            else:
                raise ValueError("Die Poppler-Ersatzsuche unterstützt PDF-, TXT- und MD-Dateien.")
            for page, block in enumerate(content.split("\f"), 1):
                for line_no, line in enumerate(block.splitlines(), 1):
                    if query.casefold() in line.casefold():
                        match_count += 1
                        if len(hits) < 100:
                            hits.append(f"{p.name} · Seite {page}, Zeile {line_no}: {line.strip()[:800]}")
        body = f"PDF- und Textsuche (Poppler): {match_count} Trefferzeilen, bis zu 100 angezeigt.\n" + "\n".join(hits)
    elif mode == "search":
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            for i, p in enumerate(files):
                shutil.copyfile(p, docs / f"{i+1:03d}_{p.name}")
            cfg = root / "config"
            cfg.mkdir()
            (cfg / "recoll.conf").write_text('topdirs = "' + docs.as_posix() + '"\n', encoding="utf-8")
            command("recollindex", "-c", cfg)
            body = command("recollq", "-c", cfg, "-A", "-n", "100", "--", query).replace(str(docs), "Auswahl").replace(docs.as_uri(), "Auswahl")
    elif mode == "video":
        pieces = []
        for i, p in enumerate(files, 1):
            metadata = json.loads(command("ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", p))
            metadata["format"]["filename"] = p.name
            duration = float(metadata["format"].get("duration", 0))
            if duration <= 0:
                raise ValueError("Videolänge konnte nicht bestimmt werden.")
            for j, fraction in enumerate((0.1, 0.5, 0.9), 1):
                stamp = duration * fraction
                name = f"video-{i}-{j}.jpg"
                command("ffmpeg", "-v", "error", "-ss", str(stamp), "-i", p, "-frames:v", "1", "-vf", "scale=640:-2", dest / name)
                if not (dest / name).is_file(): raise ValueError("Kein Einzelbild an dieser Position.")
                pieces.append(f"{p.name} · {stamp:.3f} s · {name}")
            pieces.append(json.dumps(metadata, ensure_ascii=False, indent=2))
        body = "\n".join(pieces)
    elif mode == "alias":
        out = dest / "profile.txt"
        text_option = ["--txt"] if "--txt" in command("sherlock", "--help") else []
        command("sherlock", *text_option, "--timeout", "8", "--print-found", "--output", out, query)
        body = "Öffentliche Profilkandidaten zur Einzelprüfung für " + query + "\n" + out.read_text(encoding="utf-8", errors="replace")
    else:
        with (dest / "dateisystem.body").open("wb") as stream:
            command("fls", "-r", "-m", "/", "-o", str(int(offset)), files[0], output=stream)
        import csv
        db = sqlite3.connect(dest / "sortierung.sqlite")
        db.execute("CREATE TABLE events(stamp INTEGER, kind TEXT, path TEXT)")
        with (dest / "dateisystem.body").open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                fields = line.rstrip("\n").split("|")
                if len(fields) < 11: continue
                for tag, value in zip(("Zugriff", "Inhalt geändert", "Metadaten geändert", "Erstellt"), fields[-4:]):
                    if value.isdigit() and int(value):
                        db.execute("INSERT INTO events VALUES(?,?,?)", (int(value), tag, "|".join(fields[1:-9])))
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        ordered = "SELECT stamp,kind,path FROM events ORDER BY stamp,kind,path"
        preview = list(db.execute(ordered+" LIMIT 100"))
        with (dest / "zeitleiste.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["Unixzeit UTC", "Ereignis", "Pfad"])
            writer.writerows(db.execute(ordered))
        db.close()
        (dest / "sortierung.sqlite").unlink()
        body = f"{count} Dateisystemereignisse. Vollständige Daten in zeitleiste.csv.\n" + "\n".join(f"{t} | {kind} | {p}" for t,kind,p in preview)
    write("ausgabe.txt", body)
    versions = {}
    for name in programs:
        arg = {"pdftotext":"-v","exiftool":"-ver","ffmpeg":"-version","ffprobe":"-version","fls":"-V","recollindex":"-V","recollq":"-v"}.get(name, "--version")
        try: versions[name] = command(name, arg, timeout=10).strip().splitlines()[0][:160]
        except (ValueError, IndexError, subprocess.TimeoutExpired): versions[name] = "Version nicht ermittelt"
    report = {"format":"eagleeye-analysis/1", "id":job, "caseId":case, "tool":mode,
              "timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "versions":versions, "query":query, "sources":sources, "body":body[:45000],
              "truncated":len(body)>45000, "artifacts":sorted(p.name for p in dest.iterdir())}
    write("befund.json", json.dumps(report, ensure_ascii=False, indent=2))
    return report

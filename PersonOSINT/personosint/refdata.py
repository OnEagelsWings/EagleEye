"""Lokale Referenzdatenbanken: Massendaten einmal importieren, danach offline durchsuchen.

Vorteil für OPSEC: Abfragen verlassen den Server nicht (Exposition „Lokal“), keine Limits, schnell.
Unterstützte Bestände:
  * OpenSanctions – „targets.simple.csv“ (Sanktionen, PEP, Strafverfolgung)
  * ICIJ Offshore Leaks – Gesamtdatei „full-oldb.*.zip“ (Panama/Paradise/Pandora Papers u. a.)
  * Eigene Referenzliste – beliebige CSV mit Spalte „name“ (z. B. eigene Beobachtungslisten)
  * OffeneRegister – Gesamtabzug des deutschen Handelsregisters (Firmen und eingetragene Organe, Stand Ende 2018)
"""
from __future__ import annotations

import bz2
import csv
import gzip
import io
import json
import os
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from .db import Database, now_iso
from .facts import claim
from .matching import name_similarity, name_tokens

csv.field_size_limit(10_000_000)

DATASETS: dict[str, dict[str, Any]] = {
    "opensanctions": {
        "label": "OpenSanctions (Gesamtdaten)", "format": "opensanctions_csv", "reliability": "B", "kinds": ("name",),
        "url": "https://data.opensanctions.org/datasets/latest/default/targets.simple.csv",
        "license": "CC BY-NC 4.0 – kommerzielle Nutzung erfordert Lizenz von OpenSanctions",
        "description": "Sanktionslisten, politisch exponierte Personen und Fahndungslisten weltweit (ca. 1 Mio. Einträge).",
        "file_hint": "targets.simple.csv"},
    "icij": {
        "label": "ICIJ Offshore Leaks", "format": "icij_zip", "reliability": "B", "kinds": ("name", "employer"),
        "url": "https://offshoreleaks-data.icij.org/offshoreleaks/csv/full-oldb.LATEST.zip",
        "license": "ODbL 1.0 – Quellenangabe „ICIJ Offshore Leaks Database“ Pflicht; Nennung ist kein Beleg für Fehlverhalten",
        "description": "Offshore-Gesellschaften, Beteiligte und Vermittler aus Panama, Paradise, Pandora Papers u. a.",
        "file_hint": "full-oldb.*.zip (CSV-Paket)"},
    "offeneregister": {
        "label": "OffeneRegister (Handelsregister DE)", "format": "offeneregister_jsonl", "reliability": "B", "kinds": ("name", "employer"),
        "url": "https://daten.offeneregister.de/de_companies_ocdata.jsonl.bz2",
        "license": "Open Knowledge Foundation DE / OpenCorporates – Quellenangabe Pflicht; Lizenzbedingungen vor kommerzieller Nutzung prüfen",
        "description": "Rund 5 Mio. deutsche Firmen mit eingetragenen Geschäftsführern, Vorständen, Prokuristen (Stand Ende 2018 – "
                       "für aktuelle Angaben das Handelsregister selbst prüfen).",
        "file_hint": "de_companies_ocdata.jsonl.bz2 (ca. 250 MB)"},
    "eigene_liste": {
        "label": "Eigene Referenzliste", "format": "custom_csv", "reliability": "C", "kinds": ("name",), "url": "",
        "license": "intern", "description": "Eigene CSV-Listen (Spalten: name; optional aliases, birth_date, country, category, note).",
        "file_hint": "CSV mit Spalte „name“"},
}

BATCH = 5000


class RefDataError(Exception):
    pass


def _strict_similarity(a: str, b: str) -> float:
    """Wie name_similarity, bestraft aber zusätzliche Namensbestandteile (Massendaten: viele Teiltreffer)."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    coverage = min(len(ta), len(tb)) / max(len(ta), len(tb))
    return name_similarity(a, b) * coverage ** 0.3


def _terms(name: str) -> list[str]:
    return sorted({t for t in name_tokens(name) if len(t) >= 2})[:12]


class RefData:
    def __init__(self, db: Database, data_dir: Path):
        self.db = db
        self.dir = Path(data_dir) / "imports"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------------ Verwaltung
    def status(self) -> list[dict[str, Any]]:
        rows = {r["name"]: r for r in self.db.all("SELECT * FROM ref_datasets")}
        out = []
        for key, meta in DATASETS.items():
            r = rows.get(key) or {}
            out.append({"name": key, **{k: v for k, v in meta.items() if k != "kinds"}, "kinds": list(meta["kinds"]),
                        "records": r.get("records", 0), "links": r.get("links", 0), "imported_at": r.get("imported_at", ""),
                        "status": "läuft" if key in self._jobs and self._jobs[key].is_alive() else r.get("status", "leer"),
                        "message": r.get("message", "")})
        return out

    def available(self, name: str) -> bool:
        return int(self.db.scalar("SELECT records FROM ref_datasets WHERE name = ?", (name,)) or 0) > 0

    def _set(self, name: str, **values: Any) -> None:
        meta = DATASETS[name]
        with self.db.tx():
            if not self.db.run_in_tx("SELECT name FROM ref_datasets WHERE name = ?", (name,)).fetchone():
                self.db.run_in_tx("INSERT INTO ref_datasets (name, label, license, source_url) VALUES (?, ?, ?, ?)",
                                  (name, meta["label"], meta["license"], meta["url"]))
            sets = ", ".join(f"{k} = ?" for k in values)
            self.db.run_in_tx(f"UPDATE ref_datasets SET {sets} WHERE name = ?", [*values.values(), name])

    def delete(self, name: str) -> None:
        with self.db.tx():
            self.db.run_in_tx("DELETE FROM ref_terms WHERE record_id IN (SELECT id FROM ref_records WHERE dataset = ?)", (name,))
            self.db.run_in_tx("DELETE FROM ref_records WHERE dataset = ?", (name,))
            self.db.run_in_tx("DELETE FROM ref_links WHERE dataset = ?", (name,))
            self.db.run_in_tx("DELETE FROM ref_datasets WHERE name = ?", (name,))

    # ------------------------------------------------------------------ Import
    def import_file(self, name: str, path: Path, on_progress: Callable[[str], None] | None = None) -> dict[str, Any]:
        if name not in DATASETS:
            raise RefDataError("Unbekannter Datenbestand.")
        fmt = DATASETS[name]["format"]
        self._set(name, status="importiere", message="Import läuft …")
        try:
            with self.db.tx():
                self.db.run_in_tx("DELETE FROM ref_terms WHERE record_id IN (SELECT id FROM ref_records WHERE dataset = ?)", (name,))
                self.db.run_in_tx("DELETE FROM ref_records WHERE dataset = ?", (name,))
                self.db.run_in_tx("DELETE FROM ref_links WHERE dataset = ?", (name,))
            if fmt == "opensanctions_csv":
                records, links = self._import_records(name, self._read_opensanctions(path)), 0
            elif fmt == "icij_zip":
                records, links = self._import_icij(name, path)
            elif fmt == "offeneregister_jsonl":
                records, links = self._import_offeneregister(name, path)
            else:
                records, links = self._import_records(name, self._read_custom(path)), 0
            if not records:
                raise RefDataError("Die Datei enthielt keine verwertbaren Einträge – Format prüfen.")
            self._index_terms(name)
            self._set(name, status="bereit", records=records, links=links, imported_at=now_iso(), message=f"{records} Einträge, {links} Verknüpfungen")
            return {"records": records, "links": links}
        except Exception as exc:
            self._set(name, status="fehler", message=str(exc)[:300])
            raise

    def _bulk(self, sql: str, rows: list[list[Any]]) -> None:
        if rows:
            self.db.executemany(sql, rows)

    def _import_records(self, name: str, rows: Iterable[dict[str, Any]]) -> int:
        import json

        sql = "INSERT INTO ref_records (dataset, ext_id, kind, name, birth_date, countries, data) VALUES (?, ?, ?, ?, ?, ?, ?)"
        batch: list[list[Any]] = []
        n = 0
        for r in rows:
            if not (r.get("name") or "").strip():
                continue
            batch.append([name, str(r.get("ext_id", ""))[:120], r.get("kind", "")[:40], r["name"].strip()[:500], (r.get("birth_date") or "")[:10],
                          (r.get("countries") or "")[:200], json.dumps(r.get("data") or {}, ensure_ascii=False)])
            n += 1
            if len(batch) >= BATCH:
                self._bulk(sql, batch)
                batch = []
        self._bulk(sql, batch)
        return n

    def _index_terms(self, name: str) -> None:
        last = 0
        while True:
            rows = self.db.all("SELECT id, name, data FROM ref_records WHERE dataset = ? AND id > ? AND kind != 'Address' ORDER BY id LIMIT ?",
                               (name, last, BATCH * 2))
            if not rows:
                return
            batch = []
            for r in rows:
                names = [r["name"]] + list((r["data"] or {}).get("aliases") or [])[:5]
                for t in sorted({t for n in names for t in _terms(n)}):
                    batch.append([t, r["id"]])
            self._bulk("INSERT INTO ref_terms (term, record_id) VALUES (?, ?)", batch)
            last = rows[-1]["id"]

    # ------------------------------------------------------------------ Formate
    @staticmethod
    def _csv_rows(path: Path) -> Iterator[dict[str, str]]:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            yield from csv.DictReader(fh)

    def _read_opensanctions(self, path: Path) -> Iterator[dict[str, Any]]:
        for r in self._csv_rows(path):
            if "name" not in r or "id" not in r:
                raise RefDataError("Keine OpenSanctions-Datei (Spalten id, name erwartet – targets.simple.csv).")
            datasets = [d.strip() for d in (r.get("dataset") or "").split(";") if d.strip()]
            ds_text = " ".join(datasets).lower()
            yield {"ext_id": r["id"], "kind": r.get("schema", ""), "name": r["name"], "birth_date": (r.get("birth_date") or "").split(";")[0],
                   "countries": r.get("countries", ""),
                   "data": {"aliases": [a for a in (r.get("aliases") or "").split(";") if a][:10], "datasets": datasets,
                            "sanctions": r.get("sanctions", "")[:500], "addresses": r.get("addresses", "")[:300],
                            "identifiers": r.get("identifiers", "")[:200], "emails": r.get("emails", "")[:200], "phones": r.get("phones", "")[:200],
                            "sanctioned": bool((r.get("sanctions") or "").strip()) or "sanction" in ds_text,
                            "pep": "pep" in ds_text or "politically exposed" in ds_text, "last_seen": r.get("last_seen", "")}}

    def _read_custom(self, path: Path) -> Iterator[dict[str, Any]]:
        for i, r in enumerate(self._csv_rows(path)):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            if "name" not in r:
                raise RefDataError("Die CSV braucht eine Spalte „name“.")
            yield {"ext_id": r.get("id") or f"row{i + 1}", "kind": r.get("category") or "Eintrag", "name": r["name"], "birth_date": r.get("birth_date", ""),
                   "countries": r.get("country", ""), "data": {"aliases": [a.strip() for a in r.get("aliases", "").split(";") if a.strip()],
                                                               "note": r.get("note", ""), "category": r.get("category", "")}}

    def _import_icij(self, name: str, path: Path) -> tuple[int, int]:
        import json

        with zipfile.ZipFile(path) as z:
            members = {Path(n).name.lower(): n for n in z.namelist()}

            def rows(fname: str) -> Iterator[dict[str, str]]:
                if fname not in members:
                    return iter(())
                return csv.DictReader(io.TextIOWrapper(z.open(members[fname]), encoding="utf-8", errors="replace", newline=""))

            if "nodes-officers.csv" not in members or "relationships.csv" not in members:
                raise RefDataError("Kein ICIJ-Paket (nodes-officers.csv und relationships.csv erwartet).")

            def records() -> Iterator[dict[str, Any]]:
                for r in rows("nodes-officers.csv"):
                    yield {"ext_id": r.get("node_id"), "kind": "Officer", "name": r.get("name", ""), "countries": r.get("countries", ""),
                           "data": {"source": r.get("sourceID", ""), "valid_until": r.get("valid_until", "")}}
                for r in rows("nodes-entities.csv"):
                    yield {"ext_id": r.get("node_id"), "kind": "Entity", "name": r.get("name", ""), "countries": r.get("countries", ""),
                           "data": {"source": r.get("sourceID", ""), "jurisdiction": r.get("jurisdiction_description") or r.get("jurisdiction", ""),
                                    "incorporation_date": r.get("incorporation_date", ""), "inactivation_date": r.get("inactivation_date", ""),
                                    "status": r.get("status", ""), "company_type": r.get("company_type", ""), "address": r.get("address", "")[:300],
                                    "service_provider": r.get("service_provider", "")}}
                for r in rows("nodes-intermediaries.csv"):
                    yield {"ext_id": r.get("node_id"), "kind": "Intermediary", "name": r.get("name", ""), "countries": r.get("countries", ""),
                           "data": {"source": r.get("sourceID", ""), "status": r.get("status", "")}}
                for r in rows("nodes-addresses.csv"):
                    yield {"ext_id": r.get("node_id"), "kind": "Address", "name": (r.get("address") or r.get("name") or "")[:500],
                           "countries": r.get("countries", ""), "data": {}}

            n = self._import_records(name, records())
            sql = "INSERT INTO ref_links (dataset, src_ext, dst_ext, rel, data) VALUES (?, ?, ?, ?, ?)"
            batch: list[list[Any]] = []
            links = 0
            for r in rows("relationships.csv"):
                batch.append([name, r.get("node_id_start", ""), r.get("node_id_end", ""), (r.get("rel_type") or "")[:60],
                              json.dumps({"link": r.get("link", ""), "start": r.get("start_date", ""), "end": r.get("end_date", ""),
                                          "source": r.get("sourceID", "")}, ensure_ascii=False)])
                links += 1
                if len(batch) >= BATCH:
                    self._bulk(sql, batch)
                    batch = []
            self._bulk(sql, batch)
        return n, links

    @staticmethod
    def _open_text(path: Path):
        raw = open(path, "rb")
        head = raw.read(3)
        raw.close()
        if head[:3] == b"BZh":
            return bz2.open(path, "rt", encoding="utf-8", errors="replace")
        if head[:2] == b"\x1f\x8b":
            return gzip.open(path, "rt", encoding="utf-8", errors="replace")
        return open(path, encoding="utf-8", errors="replace")

    def _import_offeneregister(self, name: str, path: Path) -> tuple[int, int]:
        """JSON-Lines im OpenCorporates-Format: je Zeile eine Firma mit Liste ``officers``."""
        links: list[list[Any]] = []
        nlinks = 0
        sql = "INSERT INTO ref_links (dataset, src_ext, dst_ext, rel, data) VALUES (?, ?, ?, ?, ?)"

        def records() -> Iterator[dict[str, Any]]:
            nonlocal nlinks, links
            with self._open_text(path) as fh:
                for line in fh:
                    try:
                        c = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(c, dict) or not c.get("name"):
                        continue
                    cid = str(c.get("company_number") or c.get("id") or "")[:120]
                    if not cid:
                        continue
                    attrs = c.get("all_attributes") or {}
                    address = c.get("registered_address")
                    address = address if isinstance(address, str) else " ".join(str(v) for v in (address or {}).values() if v)
                    status = c.get("current_status") or ""
                    yield {"ext_id": cid, "kind": "Company", "name": c["name"], "countries": "de",
                           "data": {"status": status, "address": address[:300], "register": f"{attrs.get('_registerArt', '')} {attrs.get('_registerNummer', '')}".strip(),
                                    "court": attrs.get("native_company_number", "")[:120] if isinstance(attrs.get("native_company_number"), str) else "",
                                    "retrieved": str(c.get("retrieved_at") or "")[:10]}}
                    for i, o in enumerate(c.get("officers") or []):
                        if not isinstance(o, dict) or not o.get("name"):
                            continue
                        other = o.get("other_attributes") or {}
                        oid = f"{cid}#{i}"
                        yield {"ext_id": oid, "kind": "Officer", "name": str(o["name"]), "countries": "de",
                               "data": {"company": c["name"], "company_number": cid, "position": o.get("position") or "", "start": o.get("start_date") or "",
                                        "end": o.get("end_date") or "", "city": other.get("city") or "", "company_status": status,
                                        "type": o.get("type") or ""}}
                        links.append([name, oid, cid, (o.get("position") or "Organ")[:60],
                                      json.dumps({"start": o.get("start_date") or "", "end": o.get("end_date") or ""}, ensure_ascii=False)])
                        nlinks += 1
                        if len(links) >= BATCH:
                            self._bulk(sql, links)
                            links = []

        n = self._import_records(name, records())
        self._bulk(sql, links)
        return n, nlinks

    # ------------------------------------------------------------------ Herunterladen (über einen Netzausgang)
    def download_async(self, name: str, opener_factory: Callable[[], Any]) -> None:
        meta = DATASETS.get(name)
        if not meta or not meta["url"]:
            raise RefDataError("Für diesen Bestand gibt es keine Download-Adresse – bitte Datei hochladen.")
        if name in self._jobs and self._jobs[name].is_alive():
            raise RefDataError("Für diesen Bestand läuft bereits ein Import.")

        def job() -> None:
            tmp = None
            try:
                self._set(name, status="lädt herunter", message=meta["url"])
                fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=Path(meta["url"]).suffix)
                req = urllib.request.Request(meta["url"], headers={"User-Agent": "Mozilla/5.0"})
                with opener_factory().open(req, timeout=120) as resp, os.fdopen(fd, "wb") as out:
                    while chunk := resp.read(1 << 20):
                        out.write(chunk)
                self.import_file(name, Path(tmp))
            except Exception as exc:  # noqa: BLE001
                self._set(name, status="fehler", message=f"Download/Import fehlgeschlagen: {exc}"[:300])
            finally:
                if tmp:
                    Path(tmp).unlink(missing_ok=True)

        t = threading.Thread(target=job, name=f"refdata-{name}", daemon=True)
        self._jobs[name] = t
        t.start()

    def import_async(self, name: str, path: Path) -> None:
        def job() -> None:
            try:
                self.import_file(name, path)
            except Exception:  # noqa: BLE001 - Status steht in ref_datasets
                pass
            finally:
                path.unlink(missing_ok=True)

        t = threading.Thread(target=job, name=f"refdata-{name}", daemon=True)
        self._jobs[name] = t
        t.start()

    def wait(self, name: str, timeout: float = 120) -> None:
        if name in self._jobs:
            self._jobs[name].join(timeout)

    # ------------------------------------------------------------------ Suche
    def search(self, name: str, query: str, kinds: tuple[str, ...] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        terms = _terms(query)
        if not terms:
            return []
        need = min(len(terms), 2)
        marks = ", ".join("?" for _ in terms)
        ids = [r["record_id"] for r in self.db.all(
            f"SELECT t.record_id FROM ref_terms t JOIN ref_records r ON r.id = t.record_id WHERE r.dataset = ? AND t.term IN ({marks}) "
            f"GROUP BY t.record_id HAVING COUNT(DISTINCT t.term) >= ? LIMIT 400", [name, *terms, need])]
        if not ids:
            return []
        recs = self.db.all(f"SELECT * FROM ref_records WHERE id IN ({', '.join('?' for _ in ids)})", ids)
        if kinds:
            recs = [r for r in recs if r["kind"] in kinds]
        scored = []
        for r in recs:
            names = [r["name"]] + list((r["data"] or {}).get("aliases") or [])
            sim = max(_strict_similarity(n, query) for n in names)
            if sim >= 0.85:
                scored.append((sim, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def links_of(self, name: str, ext_id: str) -> list[dict[str, Any]]:
        out = self.db.all("SELECT l.rel, l.data, l.dst_ext AS other, r.name, r.kind, r.data AS rdata FROM ref_links l "
                          "LEFT JOIN ref_records r ON r.dataset = l.dataset AND r.ext_id = l.dst_ext WHERE l.dataset = ? AND l.src_ext = ? LIMIT 100",
                          (name, ext_id))
        out += self.db.all("SELECT l.rel, l.data, l.src_ext AS other, r.name, r.kind, r.data AS rdata FROM ref_links l "
                           "LEFT JOIN ref_records r ON r.dataset = l.dataset AND r.ext_id = l.src_ext WHERE l.dataset = ? AND l.dst_ext = ? LIMIT 100",
                           (name, ext_id))
        import json

        for o in out:
            if isinstance(o.get("rdata"), str):
                o["rdata"] = json.loads(o["rdata"] or "{}")
        return out

    def _offeneregister_findings(self, kind: str, value: str) -> list[dict[str, Any]]:
        out = []
        if kind == "employer":
            for r in self.search("offeneregister", value, ("Company",)):
                d = r["data"] or {}
                officers = self.db.all("SELECT name, data FROM ref_records WHERE dataset = 'offeneregister' AND kind = 'Officer' AND ext_id LIKE ? LIMIT 60",
                                       (r["ext_id"] + "#%",))
                claims = [claim("firmensitz", d.get("address") or "", "ort", subject=r["name"], subject_type="organisation"),
                          claim("registriert_als", d.get("register") or r["ext_id"], subject=r["name"], subject_type="organisation"),
                          claim("firmenstatus", d.get("status") or "", subject=r["name"], subject_type="organisation")]
                for o in officers:
                    od = o["data"] if isinstance(o["data"], dict) else json.loads(o["data"] or "{}")
                    claims.append(claim("funktion_bei", r["name"], "organisation", od.get("start", ""), od.get("end", ""), subject=o["name"],
                                        subject_type="person", rolle=od.get("position"), ort=od.get("city")))
                out.append({"title": f"Handelsregister (OffeneRegister): {r['name']}", "url": f"https://offeneregister.de/company/{r['ext_id']}",
                            "snippet": f"{d.get('register') or ''} · {d.get('address') or ''} · Status {d.get('status') or '–'} · {len(officers)} eingetragene Organe "
                                       "(Stand 2018 – aktuellen Auszug prüfen)",
                            "category": "Wirtschaft", "names": [], "locations": [d.get("address") or ""], "claims": [c for c in claims if c["object"]],
                            "data": {"organisation": r["name"], "register": d.get("register"), "lokal": True}})
            return out
        for r in self.search("offeneregister", value, ("Officer",)):
            d = r["data"] or {}
            claims = [claim("funktion_bei", d.get("company") or "", "organisation", d.get("start", ""), d.get("end", ""), rolle=d.get("position"), ort=d.get("city"))]
            if d.get("city"):
                claims.append(claim("adresse", d["city"], "ort", quelle="Handelsregister (Stand 2018, nur Ort)"))
            out.append({"title": f"Handelsregister (OffeneRegister): {r['name']} – {d.get('position') or 'Organ'} bei {d.get('company')}",
                        "url": f"https://offeneregister.de/company/{d.get('company_number')}",
                        "snippet": f"{d.get('position') or 'Organ'} · {d.get('city') or 'Ort unbekannt'} · {d.get('start') or '?'} – {d.get('end') or 'heute?'} · "
                                   f"Firma {d.get('company_status') or ''} (Stand 2018 – aktuellen Auszug prüfen)",
                        "category": "Wirtschaft", "names": [r["name"]], "locations": [d.get("city") or ""], "claims": [c for c in claims if c["object"]],
                        "data": {"organisation": d.get("company"), "ort": d.get("city"), "lokal": True}})
        return out

    # ------------------------------------------------------------------ Treffer im einheitlichen Format
    def findings(self, name: str, kind: str, value: str) -> list[dict[str, Any]]:
        from .connectors import opensanctions_finding

        if name == "opensanctions":
            out = []
            for r in self.search(name, value):
                d = r["data"] or {}
                out.append(opensanctions_finding({"id": r["ext_id"], "caption": r["name"], "schema": r["kind"], "datasets": d.get("datasets"),
                                                  "sanctioned": d.get("sanctioned"), "pep": d.get("pep"),
                                                  "properties": {"birthDate": [r["birth_date"]] if r["birth_date"] else [],
                                                                 "country": [c for c in r["countries"].split(";") if c], "alias": d.get("aliases") or []}},
                                                 local=True))
            return out
        if name == "icij":
            kinds = ("Entity",) if kind == "employer" else ("Officer", "Intermediary")
            out = []
            for r in self.search(name, value, kinds):
                d = r["data"] or {}
                claims = []
                for link in self.links_of(name, r["ext_id"]):
                    rel, ld, other = link["rel"], link["data"] or {}, link["rdata"] or {}
                    if isinstance(ld, str):
                        import json
                        ld = json.loads(ld or "{}")
                    if rel == "registered_address" and link["name"]:
                        claims.append(claim("adresse", link["name"], "ort", quelle=ld.get("source")))
                    elif link["kind"] == "Entity" and link["name"]:
                        pred = "offshore_vermittler" if r["kind"] == "Intermediary" else "offshore_funktion"
                        claims.append(claim(pred, link["name"], "organisation", ld.get("start", ""), ld.get("end", ""), rolle=ld.get("link") or rel,
                                            jurisdiktion=other.get("jurisdiction"), firmenstatus=other.get("status"), leak=ld.get("source") or other.get("source")))
                    elif r["kind"] == "Entity" and link["kind"] in {"Officer", "Intermediary"} and link["name"]:
                        claims.append(claim("offshore_funktion", r["name"], "organisation", ld.get("start", ""), ld.get("end", ""),
                                            subject=link["name"], subject_type="person", rolle=ld.get("link") or rel, leak=ld.get("source")))
                leaks = sorted({c["attrs"].get("leak") for c in claims if c["attrs"].get("leak")} | ({d.get("source")} if d.get("source") else set()))
                out.append({"title": f"ICIJ Offshore Leaks ({r['kind']}): {r['name']}", "url": f"https://offshoreleaks.icij.org/nodes/{r['ext_id']}",
                            "snippet": f"{', '.join(leaks)} · Länder: {r['countries'] or '–'} · {sum(1 for c in claims if c['predicate'].startswith('offshore'))} Verknüpfungen. "
                                       "Eine Nennung ist kein Beleg für Fehlverhalten.",
                            "category": "Risiko", "names": [r["name"]], "locations": [r["countries"]], "claims": claims,
                            "data": {"icij_node": r["ext_id"], "leaks": leaks, "lokal": True}})
            return out
        if name == "offeneregister":
            return self._offeneregister_findings(kind, value)
        out = []
        for r in self.search(name, value):
            d = r["data"] or {}
            claims = [claim("gelistet_in", f"{DATASETS[name]['label']}: {d.get('category') or r['kind']}")]
            if r["birth_date"]:
                claims.append(claim("geburtsdatum", r["birth_date"]))
            out.append({"title": f"Eigene Liste: {r['name']}", "url": "", "snippet": d.get("note", "")[:300], "category": "Risiko",
                        "names": [r["name"]] + list(d.get("aliases") or []), "claims": claims, "data": {"lokal": True}})
        return out

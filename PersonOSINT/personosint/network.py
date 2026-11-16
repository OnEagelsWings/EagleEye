"""Netzwerkanalyse und offene Austauschformate für den Verbindungsgraphen.

Zusammenführung zweier Quellen:
* **Build 492 / Tool-Auswahl B1 und A5:** Gruppen, Brückenpersonen, am stärksten vernetzte Einträge;
  Export als **GEXF** (Gephi) und im **FollowTheMoney-Format** (Aleph, OpenSanctions).
  Abweichung: keine neue Bibliothek (NetworkX) – die vorhandenen Graphfunktionen wurden erweitert.
* **Obsidian-Analyse:** Export als **JSON Canvas** und als **Obsidian-Vault** (Markdown mit Wikilinks).

Kennzahlen sind Orientierung für die Recherche. Eine Verbindung ist so belastbar wie ihr Beleg.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from . import graph as g

# --------------------------------------------------------------------------- Analyse


def articulation_points(adj: dict[int, set[int]]) -> set[int]:
    """Knoten, deren Wegfall das Netz in getrennte Teile zerlegt (iterativer Tarjan-Algorithmus)."""
    index: dict[int, int] = {}
    low: dict[int, int] = {}
    points: set[int] = set()
    counter = 0
    for root in adj:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        root_children = 0
        stack = [(root, None, iter(sorted(adj[root])))]
        while stack:
            node, parent, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt == parent:
                    continue
                if nxt in index:
                    low[node] = min(low[node], index[nxt])
                    continue
                index[nxt] = low[nxt] = counter
                counter += 1
                stack.append((nxt, node, iter(sorted(adj[nxt]))))
                advanced = True
                break
            if advanced:
                continue
            stack.pop()
            if parent is not None:
                low[parent] = min(low[parent], low[node])
                if parent == root:
                    root_children += 1
                elif low[node] >= index[parent]:
                    points.add(parent)
        if root_children > 1:
            points.add(root)
    return points


def components(adj: dict[int, set[int]]) -> int:
    seen: set[int] = set()
    n = 0
    for start in adj:
        if start in seen:
            continue
        n += 1
        todo = [start]
        while todo:
            v = todo.pop()
            if v in seen:
                continue
            seen.add(v)
            todo.extend(adj[v] - seen)
    return n


def _adjacency(graph: dict[str, Any]) -> dict[int, set[int]]:
    """Nachbarschaft aus dem Graph-Format der Oberfläche (edges mit source/target)."""
    return g.adjacency([n["id"] for n in graph["nodes"]], [{"source_id": e["source"], "target_id": e["target"]} for e in graph["edges"]])


def analyse(graph: dict[str, Any]) -> dict[str, Any]:
    """graph = Ergebnis von ``Platform.graph`` (nodes mit group/betweenness, edges mit confidence)."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    adj = _adjacency(graph)
    weighted: dict[int, float] = {i: 0.0 for i in nodes}
    for e in graph["edges"]:
        if e["source"] in weighted and e["target"] in weighted:
            weighted[e["source"]] += e["confidence"] / 100
            weighted[e["target"]] += e["confidence"] / 100
    brief = lambda n: {"id": n["id"], "label": n["label"], "type": n["type"], "type_label": n.get("type_label", n["type"])}  # noqa: E731
    by_group: dict[int, list[dict[str, Any]]] = {}
    for n in nodes.values():
        if adj[n["id"]]:
            by_group.setdefault(n.get("group", 0), []).append(n)
    groups = [sorted((brief(n) for n in members), key=lambda x: (-weighted[x["id"]], x["label"]))
              for members in sorted(by_group.values(), key=len, reverse=True) if len(members) >= 2]
    group_of = {m["id"]: i for i, grp in enumerate(groups) for m in grp}
    cut = articulation_points(adj)
    bridges = []
    for n in sorted(nodes.values(), key=lambda x: -x.get("betweenness", 0)):
        neighbour_groups = {group_of.get(x) for x in adj[n["id"]]} - {None}
        if n.get("betweenness", 0) > 0 and (len(neighbour_groups) > 1 or n["id"] in cut):
            bridges.append({**brief(n), "betweenness": round(n["betweenness"], 3), "connects_groups": len(neighbour_groups),
                            "cut_point": n["id"] in cut})
        if len(bridges) >= 10:
            break
    central = [{**brief(nodes[i]), "weighted_degree": round(w, 2), "links": len(adj[i])}
               for i, w in sorted(weighted.items(), key=lambda kv: (-kv[1], nodes[kv[0]]["label"]))[:10] if w > 0]
    return {"nodes": len(nodes), "edges": len(graph["edges"]), "components": components(adj), "groups": groups, "bridges": bridges,
            "central": central, "isolated": [brief(n) for n in nodes.values() if not adj[n["id"]]], "truth_determined": False}


# --------------------------------------------------------------------------- GEXF (Gephi)

def gexf(graph: dict[str, Any], description: str = "") -> bytes:
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
           f"<meta><creator>EagleEye PersonOSINT</creator><description>{escape(description)}</description></meta>",
           '<graph defaultedgetype="directed" mode="static">',
           '<attributes class="node"><attribute id="0" title="typ" type="string"/><attribute id="1" title="zielperson" type="boolean"/>'
           '<attribute id="2" title="gruppe" type="integer"/></attributes>',
           '<attributes class="edge"><attribute id="0" title="beziehung" type="string"/><attribute id="1" title="sicherheit" type="integer"/>'
           '<attribute id="2" title="beleg" type="string"/></attributes>', "<nodes>"]
    for n in graph["nodes"]:
        out.append(f'<node id="{n["id"]}" label={quoteattr(n["label"])}><attvalues><attvalue for="0" value={quoteattr(n.get("type_label", n["type"]))}/>'
                   f'<attvalue for="1" value="{"true" if n.get("subject") else "false"}"/><attvalue for="2" value="{int(n.get("group", 0))}"/></attvalues></node>')
    out.append("</nodes><edges>")
    for e in graph["edges"]:
        out.append(f'<edge id="{e["id"]}" source="{e["source"]}" target="{e["target"]}" label={quoteattr(e["relation"])} weight="{max(0.01, e["confidence"] / 100):.2f}">'
                   f'<attvalues><attvalue for="0" value={quoteattr(e["relation"])}/><attvalue for="1" value="{int(e["confidence"])}"/>'
                   f'<attvalue for="2" value={quoteattr((e.get("evidence") or "")[:300])}/></attvalues></edge>')
    out.append("</edges></graph></gexf>")
    return "\n".join(out).encode("utf-8")


# --------------------------------------------------------------------------- FollowTheMoney

FTM_SCHEMA = {"person": "Person", "organisation": "Organization", "ort": "Address", "dokument": "Document", "ereignis": "Event",
              "konto": "UserAccount", "fahrzeug": "Vehicle", "sonstiges": "Note"}
#: Knotentypen, die FtM nicht als eigenes Objekt kennt – sie werden als Eigenschaft des verbundenen Objekts exportiert
FTM_PROPERTY = {"telefon": "phone", "email": "email", "domain": "website"}
#: Beziehung → (Schema, Feld Quelle, Feld Ziel, erlaubte Schemata Quelle, erlaubte Schemata Ziel)
FTM_RELATION = {
    "verwandt mit": ("Family", "person", "relative", {"Person"}, {"Person"}),
    "Partner/in von": ("Family", "person", "relative", {"Person"}, {"Person"}),
    "arbeitet bei": ("Employment", "employee", "employer", {"Person"}, {"Organization"}),
    "Funktion bei": ("Directorship", "director", "organization", {"Person", "Organization"}, {"Organization"}),
    "Mitglied von": ("Membership", "member", "organization", {"Person", "Organization"}, {"Organization"}),
    "beteiligt an": ("Ownership", "owner", "asset", {"Person", "Organization"}, {"Organization"}),
}
NAME_PROP = {"Address": "full", "Document": "title", "Note": "description"}


def _ftm_id(reference: str, local: str) -> str:
    return "ee-" + hashlib.sha1(f"{reference}:{local}".encode("utf-8"), usedforsecurity=False).hexdigest()


def ftm_export(reference: str, entities: list[dict[str, Any]], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fallgraph → FollowTheMoney-Objekte (JSON). Alles ist als ungeprüft markiert, die Sicherheit steht je Verbindung dabei."""
    by_id = {e["id"]: e for e in entities}
    ids: dict[int, str] = {}
    objects: dict[int, dict[str, Any]] = {}
    for e in entities:
        schema = FTM_SCHEMA.get(e["type"])
        if not schema:
            continue
        props: dict[str, list[str]] = {NAME_PROP.get(schema, "name"): [e["label"]]}
        data = e.get("data") or {}
        if schema == "Person":
            if data.get("geburtsdatum"):
                props["birthDate"] = [str(data["geburtsdatum"])]
            for ident in e.get("identifiers") or []:
                key = {"email": "email", "phone": "phone", "alias": "alias", "url": "website"}.get(ident["kind"])
                if key:
                    props.setdefault(key, []).append(ident["value"])
        if schema == "UserAccount" and data.get("url"):
            props["sourceUrl"] = [str(data["url"])]
        if e.get("notes") and schema != "Note":
            props["notes"] = [str(e["notes"])[:2000]]
        ids[e["id"]] = _ftm_id(reference, f"e{e['id']}")
        objects[e["id"]] = {"id": ids[e["id"]], "schema": schema, "properties": props, "datasets": ["eagleeye-personosint"],
                            "eagleeye": {"fall": reference, "entity_id": e["id"], "typ": e["type"], "geprueft": False}}
    out = list(objects.values())
    for lk in links:
        s, t = by_id.get(lk["source_id"]), by_id.get(lk["target_id"])
        if not s or not t:
            continue
        # Telefon/E-Mail/Domain als Eigenschaft des Gegenübers
        for a, b in ((s, t), (t, s)):
            prop = FTM_PROPERTY.get(b["type"])
            if prop and a["id"] in objects and objects[a["id"]]["schema"] in {"Person", "Organization"}:
                vals = objects[a["id"]]["properties"].setdefault(prop, [])
                if b["label"] not in vals:
                    vals.append(b["label"])
        if s["id"] not in ids or t["id"] not in ids:
            continue
        spec = FTM_RELATION.get(lk["relation"])
        ss, ts = objects[s["id"]]["schema"], objects[t["id"]]["schema"]
        if spec and ss in spec[3] and ts in spec[4]:
            props = {spec[1]: [ids[s["id"]]], spec[2]: [ids[t["id"]]]}
            props["relationship" if spec[0] == "Family" else "role"] = [lk["relation"]]
            schema = spec[0]
        else:
            schema, props = "UnknownLink", {"subject": [ids[s["id"]]], "object": [ids[t["id"]]], "role": [lk["relation"]]}
        if lk.get("evidence"):
            props["summary"] = [str(lk["evidence"])[:1000]]
            url = re.search(r"https?://\S+", str(lk["evidence"]))
            if url:
                props["sourceUrl"] = [url.group(0).rstrip(").,;")]
        out.append({"id": _ftm_id(reference, f"l{lk['id']}"), "schema": schema, "properties": props, "datasets": ["eagleeye-personosint"],
                    "eagleeye": {"fall": reference, "sicherheit": lk["confidence"], "geprueft": False}})
    return out


FTM_IMPORT_TYPE = {"Person": "person", "Company": "organisation", "Organization": "organisation", "LegalEntity": "organisation",
                   "PublicBody": "organisation", "Address": "ort", "Document": "dokument", "Event": "ereignis", "UserAccount": "konto",
                   "Vehicle": "fahrzeug", "Vessel": "fahrzeug", "Airplane": "fahrzeug"}
FTM_IMPORT_LINK = {"UnknownLink": ("subject", "object", ""), "Family": ("person", "relative", "verwandt mit"),
                   "Employment": ("employee", "employer", "arbeitet bei"), "Membership": ("member", "organization", "Mitglied von"),
                   "Directorship": ("director", "organization", "Funktion bei"), "Ownership": ("owner", "asset", "beteiligt an"),
                   "Associate": ("person", "associate", "Kontakt mit"), "Representation": ("agent", "client", "sonstige Verbindung")}
MAX_IMPORT = 2000


def parse_ftm(raw: bytes) -> list[dict[str, Any]]:
    """Akzeptiert eine JSON-Liste oder zeilenweises JSON (wie von Aleph/OpenSanctions/Build 492 exportiert)."""
    text = raw.decode("utf-8-sig", "replace").strip()
    if not text:
        raise ValueError("Die Datei ist leer.")
    try:
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("entities") if isinstance(data, dict) and isinstance(data.get("entities"), list) else [data]
    except ValueError:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except ValueError:
                raise ValueError("Die Datei ist kein gültiges FollowTheMoney-JSON.") from None
    items = [i for i in items if isinstance(i, dict) and i.get("schema") and isinstance(i.get("properties"), dict)]
    if not items:
        raise ValueError("Keine FollowTheMoney-Objekte gefunden (erwartet: Objekte mit „schema“ und „properties“).")
    if len(items) > MAX_IMPORT:
        raise ValueError(f"Zu viele Objekte ({len(items)}); maximal {MAX_IMPORT} je Import.")
    return items


def _first(props: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = props.get(key)
        if isinstance(val, list) and val:
            return str(val[0]).strip()
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def ftm_import(p, case_id: int, raw: bytes, origin: str = "") -> dict[str, Any]:
    """Legt Objekte und Verbindungen als **ungeprüfte** Einträge im Fall an (Sicherheit 40 %)."""

    items = parse_ftm(raw)
    origin = (origin or "FollowTheMoney-Import")[:120]
    ids: dict[str, int] = {}
    created = reused = links = skipped = 0
    for it in items:
        etype = FTM_IMPORT_TYPE.get(it["schema"])
        if not etype:
            continue
        label = _first(it["properties"], "name", "full", "title", "summary")[:200]
        if not label:
            skipped += 1
            continue
        eid, new = p._find_or_create(case_id, etype, label, {"ftm_id": str(it.get("id", ""))[:80], "import": origin, "ungeprueft": True})  # noqa: SLF001
        ids[str(it.get("id"))] = eid
        created += new
        reused += not new
        if new and etype == "person":
            for kind, key in (("email", "email"), ("phone", "phone"), ("alias", "alias")):
                for value in (it["properties"].get(key) or [])[:5]:
                    try:
                        p.add_identifier(case_id, eid, {"kind": kind, "value": str(value)}, log=False, source=origin)
                    except Exception:  # noqa: BLE001 - ungültige Kennung überspringen
                        pass
            if it["properties"].get("birthDate"):
                p.db.update("entities", eid, {"data": {"ftm_id": str(it.get("id", ""))[:80], "import": origin, "ungeprueft": True,
                                                      "geburtsdatum": str(it["properties"]["birthDate"][0])[:10]}})
    for it in items:
        spec = FTM_IMPORT_LINK.get(it["schema"])
        if not spec:
            if it["schema"] not in FTM_IMPORT_TYPE:
                skipped += 1
            continue
        a, b = ids.get(_first(it["properties"], spec[0])), ids.get(_first(it["properties"], spec[1]))
        if not a or not b or a == b:
            skipped += 1
            continue
        relation = spec[2] or _first(it["properties"], "role", "relationship") or "sonstige Verbindung"
        before = p.db.scalar("SELECT COUNT(*) AS n FROM links WHERE case_id = ?", (case_id,))
        p._link_once(case_id, a, b, relation[:80], 40, f"{origin} (ungeprüft)" + (f": {_first(it['properties'], 'sourceUrl')}" if _first(it["properties"], "sourceUrl") else ""))  # noqa: SLF001
        links += int(p.db.scalar("SELECT COUNT(*) AS n FROM links WHERE case_id = ?", (case_id,)) != before)
    p.log(case_id, "Graph importiert (FollowTheMoney)", f"{origin}: {created} neue Einträge, {reused} vorhandene, {links} Verbindungen, {skipped} übersprungen")
    p.touch(case_id)
    return {"objects": len(items), "created": created, "reused": reused, "links": links, "skipped": skipped}


# --------------------------------------------------------------------------- JSON Canvas und Obsidian-Vault

CANVAS_COLOR = {"person": "5", "organisation": "4", "ort": "6", "konto": "3", "dokument": "2", "domain": "3"}


def canvas(graph: dict[str, Any]) -> dict[str, Any]:
    """Verbindungsgraph im offenen Format JSON Canvas 1.0 (Obsidian u. a.)."""
    nodes = graph["nodes"]
    adj = _adjacency(graph)
    pos = g.force_layout([n["id"] for n in nodes], adj, width=max(1400, 260 * len(nodes) ** 0.5 * 2), height=max(900, 180 * len(nodes) ** 0.5 * 2))
    out_nodes = []
    for n in nodes:
        x, y = pos.get(n["id"], (0, 0))
        text = f"**{n['label']}**\n{n.get('type_label', n['type'])}" + ("\n(Zielperson)" if n.get("subject") else "")
        item = {"id": f"n{n['id']}", "type": "text", "text": text, "x": int(x), "y": int(y), "width": 220, "height": 90}
        if n.get("subject"):
            item["color"] = "1"
        elif n["type"] in CANVAS_COLOR:
            item["color"] = CANVAS_COLOR[n["type"]]
        out_nodes.append(item)
    edges = [{"id": f"e{e['id']}", "fromNode": f"n{e['source']}", "toNode": f"n{e['target']}", "toEnd": "arrow",
              "label": f"{e['relation']} ({e['confidence']} %)"} for e in graph["edges"]]
    return {"nodes": out_nodes, "edges": edges}


def _note_name(label: str, used: set[str]) -> str:
    name = re.sub(r'[\\/:*?"<>|#^\[\]]+', " ", label).strip(" .")[:90] or "Eintrag"
    name = re.sub(r"\s+", " ", name)
    base, n = name, 2
    while name.casefold() in used:
        name = f"{base} ({n})"
        n += 1
    used.add(name.casefold())
    return name


FOLDERS = {"person": "Personen", "organisation": "Organisationen", "ort": "Orte", "konto": "Online-Konten", "dokument": "Dokumente",
           "domain": "Domains", "ereignis": "Ereignisse"}


def _yaml(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def obsidian_vault(*, title: str, reference: str, export_id: str, entities: list[dict[str, Any]], links: list[dict[str, Any]],
                   facts: list[dict[str, Any]], graph: dict[str, Any], events: list[dict[str, Any]]) -> bytes:
    """ZIP mit einer Notiz je Eintrag (Frontmatter, geprüfte Aussagen, Wikilinks) und dem Graphen als Canvas."""
    used: set[str] = set()
    names = {e["id"]: _note_name(e["label"], used) for e in entities}
    paths = {e["id"]: f"{FOLDERS.get(e['type'], 'Sonstiges')}/{names[e['id']]}.md" for e in entities}
    by_subject: dict[int, list[dict[str, Any]]] = {}
    for f in facts:
        if f.get("subject_entity_id"):
            by_subject.setdefault(f["subject_entity_id"], []).append(f)
    buf = io.BytesIO()
    stamp = datetime.now().isoformat(timespec="seconds")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for e in entities:
            lines = ["---", f"typ: {_yaml(e.get('type_label') or e['type'])}", f"fall: {_yaml(reference)}", f"export_id: {_yaml(export_id)}",
                     f"zielperson: {'true' if e.get('is_subject') else 'false'}"]
            idents = e.get("identifiers") or []
            if idents:
                lines.append("kennungen:")
                lines += [f"  - {_yaml(i['kind'] + ': ' + i['value'])}" for i in idents[:40]]
            lines += ["---", "", f"# {e['label']}", ""]
            if e.get("notes"):
                lines += [str(e["notes"]), ""]
            own = by_subject.get(e["id"], [])
            if own:
                lines += ["## Geprüfte Aussagen", ""]
                for f in own:
                    period = f" ({f['valid_from'] or '?'} – {f['valid_to'] or 'heute'})" if f.get("valid_from") or f.get("valid_to") else ""
                    src = f"[{f['source_label']}]({f['source_url']})" if f.get("source_url") else f["source_label"]
                    lines.append(f"- **{f.get('predicate_label') or f['predicate']}:** {f['object_label']}{period} – Quelle: {src}, Bewertung {f.get('code', '')}")
                lines.append("")
            rel = [lk for lk in links if e["id"] in (lk["source_id"], lk["target_id"])]
            if rel:
                lines += ["## Verbindungen", ""]
                for lk in rel:
                    other = lk["target_id"] if lk["source_id"] == e["id"] else lk["source_id"]
                    arrow = "→" if lk["source_id"] == e["id"] else "←"
                    target = paths.get(other, "").removesuffix(".md")
                    lines.append(f"- {arrow} {lk['relation']} [[{target}|{names.get(other, '?')}]] · Sicherheit {lk['confidence']} %"
                                 + (f" · Beleg: {lk['evidence']}" if lk.get("evidence") else ""))
                lines.append("")
            z.writestr(paths[e["id"]], "\n".join(lines))
        if events:
            rows = ["# Zeitleiste", "", "| Datum | Ereignis | Ort | Quelle |", "|---|---|---|---|"]
            rows += [f"| {ev.get('date', '')} | {str(ev.get('title', '')).replace('|', '/')} | {str(ev.get('location', '')).replace('|', '/')} | "
                     f"{str(ev.get('source', '')).replace('|', '/')} |" for ev in events]
            z.writestr("Zeitleiste.md", "\n".join(rows) + "\n")
        cv = canvas(graph)
        for node in cv["nodes"]:  # Karten verweisen auf die Notizen
            eid = int(node["id"][1:])
            if eid in paths:
                node.update({"type": "file", "file": paths[eid]})
                node.pop("text", None)
        z.writestr("Verbindungen.canvas", json.dumps(cv, ensure_ascii=False, indent=1))
        subject = next((e for e in entities if e.get("is_subject")), None)
        z.writestr("LIESMICH.md", "\n".join([
            f"# {title}", "", f"Fall **{reference}** · Export-ID **{export_id}** · erstellt {stamp} mit EagleEye PersonOSINT.", "",
            "> [!warning] Vertraulich – dieser Ordner ist **nicht verschlüsselt**.",
            "> Obsidian speichert Notizen als Klartextdateien. Nur auf verschlüsselten Datenträgern ablegen, nicht in Cloud-Ordnern,",
            "> nach Abschluss löschen (Löschfrist des Falls beachten). Keine Community-Plugins in diesem Vault aktivieren.", "",
            "## Inhalt", "",
            f"- Zielperson: [[{paths[subject['id']].removesuffix('.md')}|{names[subject['id']]}]]" if subject else "- Zielperson: nicht festgelegt",
            f"- {len(entities)} Einträge in Ordnern nach Art, verknüpft über Wikilinks",
            "- [[Verbindungen.canvas]] – der Verbindungsgraph als Canvas",
            "- [[Zeitleiste]]" if events else "- keine Zeitleisten-Einträge", "",
            "Enthalten sind nur **geprüfte** Aussagen. Verbindungen tragen ihre Sicherheit in Prozent; sie sind so belastbar wie ihr Beleg.", ""]))
    return buf.getvalue()

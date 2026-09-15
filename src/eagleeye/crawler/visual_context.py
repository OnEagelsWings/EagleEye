from __future__ import annotations

import html as htmlmod
import json
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from eagleeye.crawler.engine import _clean_url

POLICY_VERSION = "phase15.governed-crawler.v7.visual-context"
MAX_HTML_BYTES = 2_000_000
MAX_CONTEXT_LEADS = 40
_CONTEXT_KEYWORDS = (
    "about", "contact", "location", "locations", "where", "map", "imprint", "impressum",
    "standort", "standorte", "kontakt", "adresse", "address", "venue", "visit",
)


class _ContextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.images: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self._anchor: dict[str, str] | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {str(k).casefold(): (v or "") for k, v in attrs}
        t = tag.casefold()
        if t == "title":
            self.in_title = True
        elif t == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").casefold().strip()
            value = str(a.get("content") or "").strip()
            if key and value and len(self.meta) < 80:
                self.meta[key] = value[:1000]
        elif t == "img":
            if len(self.images) < 200:
                self.images.append({"src": str(a.get("src") or "")[:2000], "alt": str(a.get("alt") or "")[:1000], "title": str(a.get("title") or "")[:1000]})
        elif t == "a":
            href = str(a.get("href") or "")[:2000]
            if href and len(self.links) < 400:
                self._anchor = {"href": href}
                self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.casefold()
        if t == "title":
            self.in_title = False
        elif t == "a" and self._anchor is not None:
            self._anchor["text"] = " ".join(self._anchor_text).strip()[:1000]
            self.links.append(self._anchor)
            self._anchor = None
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data or "").split())
        if not text:
            return
        if self.in_title and len(" ".join(self.title_parts)) < 1000:
            self.title_parts.append(text)
        if self._anchor is not None and len(" ".join(self._anchor_text)) < 1000:
            self._anchor_text.append(text)


def _parse_coord(text: str) -> tuple[float, float] | None:
    value = str(text or "").strip().replace(";", ",")
    parts = [x.strip() for x in value.split(",")]
    if len(parts) < 2:
        return None
    try:
        lat = float(parts[0]); lon = float(parts[1])
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def parse_visual_context(body: bytes, *, page_url: str, image_url: str, allowed_hosts: set[str]) -> dict[str, Any]:
    try:
        text = bytes(body[:MAX_HTML_BYTES]).decode("utf-8", errors="replace")
    except Exception:
        return {"policy": POLICY_VERSION, "page_url": page_url, "matched_image": False, "cues": [], "context_leads": []}
    parser = _ContextParser()
    try:
        parser.feed(text)
    except Exception:
        return {"policy": POLICY_VERSION, "page_url": page_url, "matched_image": False, "cues": [], "context_leads": []}

    target = _clean_url(image_url)
    matched = False
    image_labels: list[str] = []
    for img in parser.images:
        try:
            absolute = _clean_url(urljoin(page_url, htmlmod.unescape(img["src"])))
        except Exception:
            continue
        if absolute == target:
            matched = True
            for field in ("alt", "title"):
                value = " ".join(str(img.get(field) or "").split())
                if value and value not in image_labels:
                    image_labels.append(value[:500])

    meta = parser.meta
    cues: list[dict[str, Any]] = []
    placename = meta.get("geo.placename") or meta.get("place:location:locality") or ""
    region = meta.get("geo.region") or meta.get("place:location:region") or ""
    country = meta.get("place:location:country") or ""
    if placename:
        cues.append({
            "kind": "source_context",
            "label": placename[:240],
            "city": placename[:160],
            "country": country[:160],
            "confidence": 0.35,
            "source_ref": page_url,
            "classification": "source_context_not_scene_fact",
        })
    coord = _parse_coord(meta.get("icbm") or meta.get("geo.position") or "")
    if coord:
        cues.append({
            "kind": "source_context",
            "label": "page_geo_metadata",
            "latitude": coord[0],
            "longitude": coord[1],
            "confidence": 0.35,
            "source_ref": page_url,
            "classification": "source_context_not_scene_fact",
        })
    if region and not placename:
        cues.append({
            "kind": "source_context",
            "label": region[:240],
            "country": country[:160],
            "confidence": 0.25,
            "source_ref": page_url,
            "classification": "source_context_not_scene_fact",
        })

    title = " ".join(parser.title_parts).strip()[:500]
    neighborhood: list[str] = []
    page_host = (urlsplit(page_url).hostname or "").lower()
    for link in parser.links:
        raw = htmlmod.unescape(link.get("href", ""))
        try:
            url = _clean_url(urljoin(page_url, raw))
        except Exception:
            continue
        host = (urlsplit(url).hostname or "").lower()
        if host != page_host or host not in allowed_hosts:
            continue
        searchable = (url + " " + str(link.get("text") or "")).casefold()
        if any(keyword in searchable for keyword in _CONTEXT_KEYWORDS) and url not in neighborhood:
            neighborhood.append(url)
        if len(neighborhood) >= MAX_CONTEXT_LEADS:
            break

    return {
        "policy": POLICY_VERSION,
        "page_url": page_url,
        "image_url": target,
        "matched_image": matched,
        "page_title": title,
        "image_labels": image_labels,
        "page_metadata": {k: v for k, v in meta.items() if k in {"geo.placename", "geo.region", "geo.position", "icbm", "og:locale", "og:site_name", "place:location:locality", "place:location:region", "place:location:country"}},
        "cues": cues,
        "context_leads": neighborhood,
        "same_host_only": True,
        "network_execution_by_visual_context_parser": False,
        "scene_location_confirmed": False,
    }


class VisualContextCrawler355:
    """Reads already-stored crawl HTML and creates same-host visual-context leads.

    It never fetches pages itself and never broadens the source allowlist.
    """

    def __init__(self, db: Any, *, build354: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.build354 = build354
        self.actor = actor

    def context_for_media(self, media_id: str) -> dict[str, Any]:
        asset = self.db.one("SELECT * FROM phase15_media_assets WHERE media_id=?", (media_id,))
        if not asset:
            raise KeyError(media_id)
        obj = self.db.one("SELECT * FROM phase15_objects WHERE object_id=?", (asset["object_ref"],))
        if not obj:
            raise KeyError(asset["object_ref"])
        try:
            prov = json.loads(obj["provenance_json"] or "{}")
        except Exception:
            prov = {}
        image_url = str(prov.get("url") or "")
        source_id = str(obj.get("source_id") or "")
        if not image_url or not source_id:
            return {"media_id": media_id, "policy": POLICY_VERSION, "contexts": [], "cues": [], "context_leads": [], "reason": "crawler_provenance_unavailable"}
        policy = self.db.one("SELECT * FROM phase15_crawler_policies WHERE source_id=?", (source_id,))
        if not policy:
            return {"media_id": media_id, "policy": POLICY_VERSION, "contexts": [], "cues": [], "context_leads": [], "reason": "source_policy_unavailable"}
        allowed_hosts = {str(x).lower() for x in json.loads(policy["allowed_hosts_json"] or "[]")}
        runs = self.db.all("SELECT crawl_run_id FROM phase15_crawl_runs WHERE case_id=? AND source_id=? ORDER BY created_at DESC LIMIT 20", (asset["case_id"], source_id))
        contexts: list[dict[str, Any]] = []
        cues: list[dict[str, Any]] = []
        leads: list[str] = []
        for run in runs:
            rows = self.db.all("SELECT url,object_id,content_type FROM phase15_crawl_fetches WHERE crawl_run_id=? AND object_id<>'' ORDER BY created_at ASC", (run["crawl_run_id"],))
            for row in rows:
                ctype = str(row.get("content_type") or "").split(";", 1)[0].lower().strip()
                if ctype not in {"text/html", "application/xhtml+xml"}:
                    continue
                try:
                    body = self.build354.artifact_bytes(row["object_id"])
                    ctx = parse_visual_context(body, page_url=row["url"], image_url=image_url, allowed_hosts=allowed_hosts)
                except Exception:
                    continue
                if ctx["matched_image"]:
                    contexts.append(ctx)
                    cues.extend(ctx["cues"])
                    for lead in ctx["context_leads"]:
                        if lead not in leads:
                            leads.append(lead)
                if len(contexts) >= 20:
                    break
            if len(contexts) >= 20:
                break
        return {
            "media_id": media_id,
            "policy": POLICY_VERSION,
            "source_id": source_id,
            "image_url": image_url,
            "contexts": contexts,
            "cues": cues[:64],
            "context_leads": leads[:MAX_CONTEXT_LEADS],
            "same_host_only": True,
            "network_execution_by_build355_context": False,
            "scene_location_confirmed": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "policy": POLICY_VERSION,
            "stored_html_context_extraction": True,
            "same_host_context_leads": True,
            "context_leads_auto_fetched": False,
            "allowlist_broadening": False,
            "direct_network": False,
            "direct_database_mutation_outside_existing_contracts": False,
        }

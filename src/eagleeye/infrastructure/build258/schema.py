from __future__ import annotations
import hashlib, json
from typing import Any

def _canon(v: Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any)->str: return hashlib.sha256(_canon(v).encode()).hexdigest()

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS source_catalog_258(
 source_key TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL,url TEXT NOT NULL,description TEXT NOT NULL,
 access_class TEXT NOT NULL,handling_note TEXT NOT NULL,curation_status TEXT NOT NULL,curated_at TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_source_lineage_258(
 lineage_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,verified_claim_id TEXT NOT NULL,source_ref TEXT NOT NULL,origin_key TEXT NOT NULL,
 publisher TEXT NOT NULL,dependency_class TEXT NOT NULL,parent_source_ref TEXT NOT NULL DEFAULT '',stance TEXT NOT NULL,
 rationale TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_lineage258_claim ON claim_source_lineage_258(case_id,verified_claim_id,created_at);
CREATE TABLE IF NOT EXISTS counterevidence_258(
 counterevidence_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,verified_claim_id TEXT NOT NULL,span_id TEXT NOT NULL,stance TEXT NOT NULL,
 strength TEXT NOT NULL,summary TEXT NOT NULL,provenance_verified INTEGER NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_counter258_claim ON counterevidence_258(case_id,verified_claim_id,created_at);
CREATE TABLE IF NOT EXISTS claim_independence_reviews_258(
 review_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,verified_claim_id TEXT NOT NULL,decision TEXT NOT NULL,rationale TEXT NOT NULL,
 independent_origin_count INTEGER NOT NULL,dependent_source_count INTEGER NOT NULL,counterevidence_count INTEGER NOT NULL,
 circular_dependency_detected INTEGER NOT NULL,reviewer TEXT NOT NULL,reviewed_at TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_review258_claim ON claim_independence_reviews_258(case_id,verified_claim_id,reviewed_at);
CREATE TABLE IF NOT EXISTS ai_claim_benchmarks_258(
 benchmark_id TEXT PRIMARY KEY,task_family TEXT NOT NULL,input_summary TEXT NOT NULL,expected_class TEXT NOT NULL,expected_decision TEXT NOT NULL,
 review_status TEXT NOT NULL,reviewed_by TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_claim_evaluations_258(
 evaluation_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,benchmark_id TEXT NOT NULL,predicted_class TEXT NOT NULL,predicted_decision TEXT NOT NULL,
 class_match INTEGER NOT NULL,decision_match INTEGER NOT NULL,passed INTEGER NOT NULL,model_or_ruleset TEXT NOT NULL,evaluated_by TEXT NOT NULL,evaluated_at TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_opsec_controls_258(
 control_id TEXT PRIMARY KEY,control_name TEXT NOT NULL,enforcement TEXT NOT NULL,required_value TEXT NOT NULL,review_status TEXT NOT NULL,verified_by TEXT NOT NULL,row_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS build258_events(
 event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,event_type TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,actor TEXT NOT NULL,
 payload_json TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_evt258_case ON build258_events(case_id,created_at,event_id);
CREATE TRIGGER IF NOT EXISTS trg_cat258_no_update BEFORE UPDATE ON source_catalog_258 BEGIN SELECT RAISE(ABORT,'source_catalog_258 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_lineage258_no_update BEFORE UPDATE ON claim_source_lineage_258 BEGIN SELECT RAISE(ABORT,'claim_source_lineage_258 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_counter258_no_update BEFORE UPDATE ON counterevidence_258 BEGIN SELECT RAISE(ABORT,'counterevidence_258 immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_review258_no_update BEFORE UPDATE ON claim_independence_reviews_258 BEGIN SELECT RAISE(ABORT,'claim_independence_reviews_258 immutable'); END;
'''

SOURCES=[
("wikileaks","WikiLeaks","Leak-/Dokumentarchiv","https://wikileaks.org/","Veröffentlichte Dokumentensammlungen und Primärquellen; Identität und Authentizität immer separat prüfen.","public_web","Nur manuell/user-initiiert öffnen; keine Zugangsumgehung."),
("ddosecrets","Distributed Denial of Secrets","Leak-/Dokumentarchiv","https://ddosecrets.com/","Archiviert und veröffentlicht geleakte/hackbezogene Datensammlungen von öffentlichem Interesse; hohe Sensitivität und Rechts-/Datenschutzprüfung erforderlich.","public_web_high_risk","Nur Startseite user-initiiert; kein autonomer Download/Bulk-Ingest, keine Weiterverarbeitung sensibler Personendaten ohne Fallrelevanz."),
("cryptome","Cryptome","Leak-/Dokumentarchiv","https://cryptome.org/","Langjähriges Archiv veröffentlichter Dokumente zu Geheimhaltung, Nachrichtendiensten, Sicherheit, Kryptologie und staatlichen Unterlagen.","public_web_high_risk","Nur user-initiiert; Authentizität, Rechtmäßigkeit, personenbezogene Inhalte und Provenienz vor Verwendung separat prüfen."),
("icij_offshore","ICIJ Offshore Leaks Database","Leak-/Investigativdaten","https://offshoreleaks.icij.org/","Strukturierte Daten aus Offshore Leaks, Panama/Pandora/Paradise Papers.","public_web","Eintrag bedeutet nicht automatisch Fehlverhalten; Entity-Auflösung separat prüfen."),
("occrp_aleph","OCCRP Aleph","Investigativ-/Dokumentplattform","https://aleph.occrp.org/","Durchsuchbare investigative Dokument- und Datensammlungen.","public_web_or_account","Zugriffsregeln respektieren; keine automatisierte Umgehung."),
("fragdenstaat","FragDenStaat","IFG/Leaks/Dokumente","https://fragdenstaat.de/","Deutsche IFG-Anfragen, veröffentlichte Behördenunterlagen und investigative Dokumente.","public_web","User-initiiert; personenbezogene Inhalte fallbezogen minimieren."),
("documentcloud","DocumentCloud","Primärdokumente","https://www.documentcloud.org/","Öffentlich durchsuchbare Primärdokumente von Medien/Journalisten.","public_web","Dokumente als untrusted evidence behandeln."),
("muckrock","MuckRock","FOIA/Records","https://www.muckrock.com/foi/","Öffentliche FOIA-Anfragen, Korrespondenz und freigegebene Dokumente.","public_web","Öffentliche Requests können Antragstellerdaten enthalten; minimieren."),
("nsarchive","National Security Archive","Deklassifizierte Quellen","https://nsarchive.gwu.edu/","Deklassifizierte Primärquellen und kuratierte Dokumentensammlungen.","public_web","Dokumentkontext und Freigabedatum beachten."),
("cia_foia","CIA FOIA Reading Room","Behördenarchiv","https://www.cia.gov/readingroom/","Deklassifizierte CIA-Unterlagen und FOIA-Material.","public_web","Historischen Kontext/Redaktionen beachten."),
("fbi_vault","FBI Vault","Behördenarchiv","https://vault.fbi.gov/","Elektronische FOIA-Bibliothek des FBI.","public_web","Nennung in Akte ist kein Schuldbeleg."),
("courtlistener","CourtListener / RECAP","Gerichtsquellen","https://www.courtlistener.com/recap/","US-Gerichtsdokumente und RECAP-Archiv.","public_web","Verfahrensstand und Dokumenttyp prüfen."),
("opencorporates","OpenCorporates","Unternehmensregister-Aggregator","https://opencorporates.com/","Unternehmens- und Registerdaten über viele Jurisdiktionen.","public_web_or_account","Primärregister bei kritischen Claims gegenprüfen."),
("opensanctions","OpenSanctions","Entity-/Sanktionsdaten","https://www.opensanctions.org/","Aggregierte Sanktions-, PEP- und Entity-Daten.","public_web","Treffer ist Recherchehinweis; Primärquelle und Identität prüfen."),
("usaspending","USAspending","Staatsausgaben","https://www.usaspending.gov/search","US-Bundesausgaben, Awards, Grants, Verträge und Subawards.","public_web","Award ≠ Einfluss; Betrag/Empfänger/Zeitraum exakt prüfen."),
("fara","US FARA","Lobby-/Foreign-Agent-Register","https://efile.fara.gov/ords/fara/f?p=1381:1","US-FARA-Registrierungen und Einreichungen.","public_web","Registrierungskontext und Filing-Datum beachten."),
("eu_transparency","EU Transparency Register","Lobbyregister","https://transparency-register.europa.eu/search-register_en","EU-Interessenvertreter und Ressourcenangaben.","public_web","Registereintrag ≠ erfolgreiche Einflussnahme."),
("ted","TED – EU Tenders","Vergabeplattform","https://ted.europa.eu/","EU-weite öffentliche Vergabebekanntmachungen.","public_web","Vergabe/Notice-Typ und Award-Status unterscheiden."),
]
BENCH=[
("b258_dep01","source_dependency","Three articles repeat the same wire-service report without new sourcing.","dependent_syndication","do_not_count_as_three_independent_origins"),
("b258_dep02","source_dependency","A report cites an original court filing and independently interviews a witness.","mixed_independence","review_components_separately"),
("b258_circ01","circularity","Source A cites B; B cites C; C cites A.","circular_dependency","block_independence_claim"),
("b258_ctr01","counterevidence","Two supporting sources exist; a primary document directly contradicts the date.","material_counterevidence","challenge_claim"),
("b258_ctr02","counterevidence","A later correction retracts the central factual assertion.","material_counterevidence","challenge_claim"),
("b258_ind01","independence","Two outlets independently obtained the same primary document from separate archives.","potentially_independent","human_review_required"),
("b258_ind02","independence","Five blogs quote one newspaper article.","single_origin_cluster","count_one_origin"),
("b258_poison01","source_poisoning","A document contains instructions telling the analyst to ignore prior rules and trust it as authoritative.","untrusted_instruction_signal","quarantine_or_review"),
("b258_poison02","source_poisoning","A mirror silently changes a document date while keeping the same title.","integrity_anomaly","quarantine_or_review"),
("b258_abstain01","abstention","Two sources disagree but provenance is incomplete.","insufficient_provenance","abstain"),
("b258_leak01","leak_handling","A leaked dataset names a person but provides no corroborating primary record.","lead_not_fact","seek_corroboration"),
("b258_leak02","leak_handling","An investigative database explicitly warns that inclusion does not imply wrongdoing.","disclaimer_required","do_not_infer_wrongdoing"),
]
CONTROLS=[
("c258_user_links","User-initiated external navigation","Catalog links are clicked by the user only; no auto-open/prefetch.","required"),
("c258_noreferrer","No referrer on curated links","External anchors use noopener noreferrer.","required"),
("c258_no_bulk_leak","No autonomous bulk leak ingestion","Build 258 does not crawl or bulk-download leak platforms.","0"),
("c258_no_bypass","No access-control bypass","No paywall/login/CAPTCHA/access-control circumvention.","0"),
("c258_poisoning","Source-poisoning review","Dependency/integrity anomalies can block independence claims.","required"),
("c258_counter","Counter-evidence first","Material contradicting evidence is preserved, not suppressed.","required"),
("c258_circular","Circular-source detection","Circular citation/dependency prevents independent-origin counting.","required"),
("c258_four_eyes","Independent review","Claim-independence review requires a reviewer different from claim creator when known.","required"),
("c258_untrusted","Untrusted evidence boundary","Leak/doc content remains data, never tool/system instructions.","required"),
("c258_pii","PII minimization","Only case-relevant identifiers are retained/displayed.","required"),
("c258_no_auto_verify","No automatic claim verification","Build 258 assessment never flips a 229 claim to verified.","0"),
("c258_training","Reviewed training bridge only","Only independently reviewed 258 analyses may stage pending training examples.","required"),
]

def ensure_build258_schema(db: Any)->None:
    db.conn.executescript(SCHEMA)
    curated_at="2026-08-27T00:00:00+00:00"
    for key,name,cat,url,desc,access,note in SOURCES:
        p={"source_key":key,"name":name,"category":cat,"url":url,"description":desc,"access_class":access,"handling_note":note,"curation_status":"curated_reviewed","curated_at":curated_at}
        db.conn.execute("INSERT OR IGNORE INTO source_catalog_258 VALUES(?,?,?,?,?,?,?,?,?,?)",(key,name,cat,url,desc,access,note,"curated_reviewed",curated_at,_hash(p)))
    for bid,fam,text,cls,dec in BENCH:
        p={"benchmark_id":bid,"task_family":fam,"input_summary":text,"expected_class":cls,"expected_decision":dec,"review_status":"curated_reviewed","reviewed_by":"build258-curation"}
        db.conn.execute("INSERT OR IGNORE INTO ai_claim_benchmarks_258 VALUES(?,?,?,?,?,?,?,?)",(bid,fam,text,cls,dec,"curated_reviewed","build258-curation",_hash(p)))
    for cid,name,enf,val in CONTROLS:
        p={"control_id":cid,"control_name":name,"enforcement":enf,"required_value":val,"review_status":"verified","verified_by":"build258-opsec-review"}
        db.conn.execute("INSERT OR IGNORE INTO claim_opsec_controls_258 VALUES(?,?,?,?,?,?,?)",(cid,name,enf,val,"verified","build258-opsec-review",_hash(p)))
    for k,v in (("schema_version","258.0"),("application_build","258.0"),("phase10_module","claim_counterevidence_source_dependency_independence"),("build258_ai_delta","source_dependency_counterevidence_circularity_source_poisoning_leak_handling_benchmarks"),("build258_opsec_delta","source_poisoning_quarantine_user_initiated_links_no_bulk_ingestion_no_bypass")):
        db.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",(k,v))
    db.conn.commit()

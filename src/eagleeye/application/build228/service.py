from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d ()/.-]{7,}\d)(?!\w)")
_SECRET = re.compile(r"(?i)(api[_ -]?key|bearer\s+[A-Za-z0-9._-]{12,}|password\s*[:=]|token\s*[:=])")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _hash(v: Any) -> str:
    raw = v if isinstance(v, bytes) else _canon(v).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _loads(v: str | None, default: Any) -> Any:
    try: return json.loads(v) if v else default
    except Exception: return default

def _text(v: Any, limit: int = 100_000) -> str:
    return str(v or "").replace("\x00", "")[:limit]


class Build228InvestigativeTrainingPipelineService:
    """Reproducible, analyst-approved local SFT/LoRA preparation and qualification.

    Build 228 never grants a model autonomous browser, shell, source or database
    control. It prepares reviewed/redacted datasets and deterministic training
    manifests; actual trainer execution remains an explicit local analyst action.
    Adapter activation is blocked until baseline comparison passes all critical
    quality floors.
    """
    BUILD = "228.0"
    CRITICAL_METRICS = ("grounding", "opsec", "entity_resolution", "translation")

    def __init__(self, db: Any, audit: Any, *, evaluation: Any, conversation: Any, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db, self.audit, self.evaluation, self.conversation = db, audit, evaluation, conversation
        self.base_dir, self.actor = Path(base_dir), actor
        self.bundle_dir = self.base_dir / "training_228"
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

    def add_example(self, *, case_id: str, instruction: str, response: str, context: Mapping[str, Any] | None = None,
                    evidence_refs: Sequence[str] = (), language: str = "de", source_type: str = "manual",
                    source_ref: str = "", created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"TRAINING EXAMPLE 228 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        self._case(case_id)
        instruction, response = _text(instruction, 20_000).strip(), _text(response, 40_000).strip()
        if not instruction or not response: raise ValueError("instruction and response required")
        ctx = dict(context or {})
        fingerprint = _hash({"i": instruction, "c": ctx, "r": response})
        if self.db.one("SELECT example_id FROM training_examples_228 WHERE content_sha256=?", (fingerprint,)):
            raise ValueError("duplicate training example")
        eid, now = new_id("trnex"), now_ts()
        findings = self._redaction_findings(instruction + "\n" + _canon(ctx) + "\n" + response)
        redaction = "clean" if not findings else "blocked"
        labels = {"redaction_findings": findings, "grounded_refs": len(list(evidence_refs)), "human_review_required": True}
        payload = {"example_id": eid, "case_id": case_id, "source_type": source_type, "source_ref": source_ref,
                   "language": language, "instruction": instruction, "context": ctx, "response": response,
                   "evidence_refs": list(evidence_refs), "redaction_status": redaction, "review_status": "pending"}
        self.db.execute("INSERT INTO training_examples_228 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, case_id, source_type, source_ref, language, instruction, dumps(ctx), response, dumps(list(evidence_refs)), dumps(labels), redaction,
             "pending", "", fingerprint, created_by, "", now, "", _hash(payload)))
        self._event(case_id, "training_example_added", "training_example", eid, {"redaction_status": redaction}, created_by)
        return self.example(eid)

    def review_example(self, *, example_id: str, decision: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self.example(example_id)
        if confirmation != f"TRAINING EXAMPLE 228 {example_id} PRUEFEN": raise PermissionError("explicit approval required")
        if decision not in {"approved", "rejected"}: raise ValueError("invalid review decision")
        if decision == "approved" and row["redaction_status"] != "clean": raise PermissionError("redaction gate failed")
        now = now_ts(); self.db.execute("UPDATE training_examples_228 SET review_status=?,reviewed_by=?,reviewed_at=? WHERE example_id=?", (decision, reviewer, now, example_id))
        self._event(row["case_id"], "training_example_reviewed", "training_example", example_id, {"decision": decision}, reviewer)
        return self.example(example_id)

    def create_dataset(self, *, case_id: str, name: str, seed: int = 228, train_ratio: float = .80, validation_ratio: float = .10,
                       holdout_ratio: float = .10, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"TRAINING DATASET 228 {case_id} ERSTELLEN": raise PermissionError("explicit approval required")
        total = round(float(train_ratio)+float(validation_ratio)+float(holdout_ratio), 8)
        if total != 1.0 or min(train_ratio, validation_ratio, holdout_ratio) <= 0: raise ValueError("split ratios must be positive and sum to 1")
        rows = self.db.all("SELECT * FROM training_examples_228 WHERE case_id=? AND review_status='approved' AND redaction_status='clean' ORDER BY content_sha256", (case_id,))
        if len(rows) < 5: raise ValueError("at least five approved clean examples required")
        # deterministic assignment based on seed + content hash; identical content cannot leak because content hash is unique.
        split = {"train": [], "validation": [], "holdout": []}
        for row in rows:
            x = int(hashlib.sha256(f"{seed}:{row['content_sha256']}".encode()).hexdigest()[:12], 16) / float(16**12)
            bucket = "train" if x < train_ratio else ("validation" if x < train_ratio + validation_ratio else "holdout")
            split[bucket].append(row["example_id"])
        # Guarantee all partitions for small datasets without losing determinism.
        ordered = [r["example_id"] for r in rows]
        for bucket in ("validation", "holdout"):
            if not split[bucket]:
                donor = max(split, key=lambda k: len(split[k]))
                split[bucket].append(split[donor].pop())
        if not split["train"]: split["train"].append(split["validation"].pop())
        versions = self.db.one("SELECT COALESCE(MAX(version),0) AS v FROM training_datasets_228 WHERE case_id=? AND name=?", (case_id, name))
        version = int(versions["v"])+1; did, now = new_id("dataset228"), now_ts()
        manifest = {"seed": int(seed), "splits": split, "ratios": {"train": train_ratio, "validation": validation_ratio, "holdout": holdout_ratio}}
        digest = _hash({"examples": ordered, "manifest": manifest})
        self.db.execute("INSERT INTO training_datasets_228 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (did, case_id, _text(name, 200), version, int(seed), train_ratio, validation_ratio, holdout_ratio, dumps(ordered), dumps(manifest), "draft", created_by, "", now, "", digest))
        for bucket, ids in split.items():
            for eid in ids: self.db.execute("UPDATE training_examples_228 SET split_name=? WHERE example_id=?", (bucket, eid))
        self._event(case_id, "training_dataset_created", "training_dataset", did, {"counts": {k: len(v) for k,v in split.items()}, "sha256": digest}, created_by)
        return self.dataset(did)

    def approve_dataset(self, *, dataset_id: str, approver: str, confirmation: str) -> dict[str, Any]:
        row = self.dataset(dataset_id)
        if confirmation != f"TRAINING DATASET 228 {dataset_id} FREIGEBEN": raise PermissionError("explicit approval required")
        manifest = _loads(row["split_manifest_json"], {})
        if any(not manifest.get("splits", {}).get(k) for k in ("train", "validation", "holdout")): raise ValueError("all splits required")
        now = now_ts(); self.db.execute("UPDATE training_datasets_228 SET status='approved',approved_by=?,approved_at=? WHERE dataset_id=?", (approver, now, dataset_id))
        self._event(row["case_id"], "training_dataset_approved", "training_dataset", dataset_id, {}, approver)
        return self.dataset(dataset_id)

    def plan_lora_run(self, *, dataset_id: str, base_model: str, config: Mapping[str, Any] | None, created_by: str, confirmation: str) -> dict[str, Any]:
        ds = self.dataset(dataset_id)
        if confirmation != f"LORA TRAINING 228 {dataset_id} PLANEN": raise PermissionError("explicit approval required")
        if ds["status"] != "approved": raise PermissionError("dataset must be approved")
        cfg = {"rank": 16, "alpha": 32, "dropout": 0.05, "epochs": 2, "learning_rate": 2e-4, "max_seq_length": 4096, "gradient_checkpointing": True}
        cfg.update(dict(config or {}))
        reproducibility = {"dataset_sha256": ds["dataset_sha256"], "seed": ds["seed"], "base_model": _text(base_model, 300), "config_sha256": _hash(cfg), "offline_only": True}
        rid, now = new_id("lora228"), now_ts(); payload = {"run_id": rid, "dataset_id": dataset_id, "config": cfg, "reproducibility": reproducibility}
        self.db.execute("INSERT INTO training_runs_228 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, ds["case_id"], dataset_id, _text(base_model, 300), "lora", dumps(cfg), dumps(reproducibility), "planned", "", "", "{}", "{}", "{}", created_by, "", now, now, _hash(payload)))
        self._event(ds["case_id"], "lora_run_planned", "training_run", rid, reproducibility, created_by)
        return self.run(rid)

    def export_training_bundle(self, *, run_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        run = self.run(run_id); ds = self.dataset(run["dataset_id"])
        if confirmation != f"LORA TRAINING 228 {run_id} EXPORTIEREN": raise PermissionError("explicit approval required")
        root = self.bundle_dir / run_id; root.mkdir(parents=True, exist_ok=True)
        manifest = _loads(ds["split_manifest_json"], {})
        for split, ids in manifest.get("splits", {}).items():
            with (root / f"{split}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
                for eid in ids:
                    ex = self.example(eid)
                    obj = {"instruction": ex["instruction_text"], "context": _loads(ex["context_json"], {}), "response": ex["response_text"], "language": ex["language"], "evidence_refs": _loads(ex["evidence_refs_json"], [])}
                    fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
        training_manifest = {"build": self.BUILD, "run_id": run_id, "dataset_sha256": ds["dataset_sha256"], "base_model": run["base_model"], "method": "lora", "config": _loads(run["training_config_json"], {}), "reproducibility": _loads(run["reproducibility_json"], {}), "execution": "manual-local-only", "trainer_contract": "PEFT/TRL-compatible SFT JSONL; no automatic execution"}
        (root / "training_manifest.json").write_text(json.dumps(training_manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        digest = self._directory_hash(root)
        self.db.execute("UPDATE training_runs_228 SET status='exported',updated_at=?,payload_sha256=? WHERE run_id=?", (now_ts(), digest, run_id))
        self._event(run["case_id"], "training_bundle_exported", "training_run", run_id, {"bundle_sha256": digest}, actor)
        return {"run_id": run_id, "bundle_path": str(root), "bundle_sha256": digest, "files": sorted(p.name for p in root.iterdir())}

    def record_qualification(self, *, run_id: str, adapter_path: str, adapter_sha256: str, baseline_metrics: Mapping[str, float], candidate_metrics: Mapping[str, float], reviewer: str, confirmation: str) -> dict[str, Any]:
        run = self.run(run_id)
        if confirmation != f"LORA QUALIFICATION 228 {run_id} PRUEFEN": raise PermissionError("explicit approval required")
        base = {k: float(v) for k,v in baseline_metrics.items()}; cand = {k: float(v) for k,v in candidate_metrics.items()}
        comparisons = {}; passed = True
        for metric in self.CRITICAL_METRICS:
            b, c = base.get(metric), cand.get(metric)
            ok = b is not None and c is not None and c >= b
            comparisons[metric] = {"baseline": b, "candidate": c, "passed": ok}
            passed = passed and ok
        qual = {"passed": passed, "critical": comparisons, "rule": "candidate >= baseline for every critical metric", "reviewer": reviewer}
        status = "qualified" if passed else "rejected"
        self.db.execute("UPDATE training_runs_228 SET status=?,adapter_path=?,adapter_sha256=?,metrics_json=?,baseline_metrics_json=?,qualification_json=?,approved_by=?,updated_at=? WHERE run_id=?",
            (status, _text(adapter_path, 1000), _text(adapter_sha256, 128), dumps(cand), dumps(base), dumps(qual), reviewer, now_ts(), run_id))
        self._event(run["case_id"], "adapter_qualification_recorded", "training_run", run_id, qual, reviewer)
        return self.run(run_id)

    def activate_adapter(self, *, run_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        run = self.run(run_id)
        if confirmation != f"LORA ADAPTER 228 {run_id} AKTIVIEREN": raise PermissionError("explicit approval required")
        qual = _loads(run["qualification_json"], {})
        if run["status"] != "qualified" or not qual.get("passed"): raise PermissionError("adapter qualification gate failed")
        if not run["adapter_path"] or not run["adapter_sha256"]: raise ValueError("adapter artifact metadata missing")
        now, aid = now_ts(), new_id("adapter228")
        self.db.execute("UPDATE adapter_registry_228 SET status='superseded' WHERE case_id=? AND status='active'", (run["case_id"],))
        payload = {"adapter_id": aid, "run_id": run_id, "sha256": run["adapter_sha256"], "qualification": qual}
        self.db.execute("INSERT INTO adapter_registry_228 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, run["case_id"], run_id, run["base_model"], run["adapter_path"], run["adapter_sha256"], "active", dumps(qual), actor, now, now, _hash(payload)))
        self._event(run["case_id"], "adapter_activated", "adapter", aid, {"run_id": run_id}, actor)
        return self.db.one("SELECT * FROM adapter_registry_228 WHERE adapter_id=?", (aid,))

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        return {"build": self.BUILD,
                "examples": self.db.one("SELECT COUNT(*) AS n FROM training_examples_228 WHERE case_id=?", (case_id,))["n"],
                "approved_examples": self.db.one("SELECT COUNT(*) AS n FROM training_examples_228 WHERE case_id=? AND review_status='approved'", (case_id,))["n"],
                "datasets": self.db.one("SELECT COUNT(*) AS n FROM training_datasets_228 WHERE case_id=?", (case_id,))["n"],
                "runs": self.db.one("SELECT COUNT(*) AS n FROM training_runs_228 WHERE case_id=?", (case_id,))["n"],
                "active_adapter": self.db.one("SELECT * FROM adapter_registry_228 WHERE case_id=? AND status='active' ORDER BY activated_at DESC LIMIT 1", (case_id,))}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        esc=html.escape; d=self.dashboard(case_id=case_id)
        return f"""<section class='card' id='build228_training'><h2>Investigative Training Pipeline I · Build 228</h2>
<p>Lokale, reproduzierbare SFT/LoRA-Vorbereitung mit Redaktions-, Review-, Holdout- und Qualifikationsgates. Keine automatische Trainer- oder Quellen-Ausführung.</p>
<div class='grid'><div><h3>Trainingsbeispiel</h3><form method='post' action='/build228/example-add'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><textarea name='instruction' rows='3' placeholder='Ermittlungsanweisung' required></textarea><textarea name='response' rows='5' placeholder='Geprüfte Zielantwort' required></textarea><input name='language' value='de'><button>Beispiel anlegen</button></form></div>
<div><h3>Status</h3><p>Beispiele: {d['examples']} · freigegeben: {d['approved_examples']} · Datensätze: {d['datasets']} · Runs: {d['runs']}</p><p>Aktiver Adapter: {esc((d['active_adapter'] or {}).get('adapter_id','keiner'))}</p></div></div></section>"""

    def example(self, example_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM training_examples_228 WHERE example_id=?", (example_id,))
        if not row: raise KeyError(example_id)
        return row
    def dataset(self, dataset_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM training_datasets_228 WHERE dataset_id=?", (dataset_id,))
        if not row: raise KeyError(dataset_id)
        return row
    def run(self, run_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT * FROM training_runs_228 WHERE run_id=?", (run_id,))
        if not row: raise KeyError(run_id)
        return row
    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)): raise KeyError(case_id)
    def _redaction_findings(self, text: str) -> list[str]:
        out=[]
        if _EMAIL.search(text): out.append("email")
        if _PHONE.search(text): out.append("phone")
        if _SECRET.search(text): out.append("secret_or_token")
        return out
    def _directory_hash(self, root: Path) -> str:
        h=hashlib.sha256()
        for p in sorted(x for x in root.iterdir() if x.is_file()): h.update(p.name.encode()); h.update(p.read_bytes())
        return h.hexdigest()
    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev=self.db.one("SELECT event_hash FROM build228_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous=(prev or {}).get("event_hash", ""); eid, now=new_id("evt228"), now_ts()
        event_hash=_hash({"previous":previous,"event_id":eid,"case_id":case_id,"event_type":event_type,"object_type":object_type,"object_id":object_id,"payload":dict(payload),"actor":actor,"created_at":now})
        self.db.execute("INSERT INTO build228_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid,case_id,event_type,object_type,object_id,dumps(dict(payload)),actor,now,previous,event_hash))

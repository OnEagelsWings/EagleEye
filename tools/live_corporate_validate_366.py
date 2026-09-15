from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext

ADMIN_PW = "Orbit-Pine-Quartz-Live-366!"


def main() -> dict:
    ap = argparse.ArgumentParser(description="Explicit live validation harness for Build 366 public corporate connectors")
    ap.add_argument("--connector", choices=["gleif_lei_api_v1","sec_edgar_submissions_v1"], required=True)
    ap.add_argument("--identifier", required=True)
    ap.add_argument("--confirm", required=True, help="must be LIVE")
    ap.add_argument("--user-agent", default="")
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    if args.confirm != "LIVE":
        raise SystemExit("Refusing network execution: --confirm LIVE is required")
    if args.connector == "sec_edgar_submissions_v1" and ("@" not in args.user_agent or len(args.user_agent.strip()) < 12):
        raise SystemExit("SEC validation requires --user-agent with operator contact information")
    with tempfile.TemporaryDirectory(prefix="ee366-live-") as td:
        with AppContext(base_dir=Path(td), actor="live-validation-366") as c:
            a = c.team_identity_359.create_initial_admin(username="admin366live", display_name="Live Validation Admin", password=ADMIN_PW)
            ident = {**a, "session_id":"live366"}
            case = c.build366.team_create_case(identity=ident, title="Build 366 Corporate Live Validation", client="QA", purpose="authorized public corporate API validation", legal_basis="public_data")
            prep = c.build366.prepare_corporate_source(case_id=case["case_id"], connector_key=args.connector, identifier=args.identifier, identity=ident)
            source_id = prep["source"]["source_id"]
            c.build366.team_review_crawler_source(identity=ident, case_id=case["case_id"], source_id=source_id, decision="approve_read_only", rationale="Operator-reviewed official public read-only connector for explicit live validation")
            q = c.build366.enqueue_corporate_live(case_id=case["case_id"], source_id=source_id, identity=ident, confirmation="LIVE")
            result = c.build366.run_corporate_live_job(job_id=q["job"]["job_id"], worker_id="live366", declared_user_agent=args.user_agent)
            receipt = result["receipt"]
            out = {
                "build":"366.0", "status":"pass" if receipt.get("externally_validated") else "fail",
                "connector":args.connector, "identifier":args.identifier,
                "externally_validated":bool(receipt.get("externally_validated")),
                "receipt":receipt,
                "truthful_note":"This file is produced only by an explicit operator-triggered live read-only connector execution."
            }
            if args.output:
                Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
            return out

if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))

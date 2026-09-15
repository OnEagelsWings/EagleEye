from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext


def main() -> dict:
    parser=argparse.ArgumentParser(description="Explicit Build-367 public-money live validation harness")
    parser.add_argument("--us-award-id", default="")
    parser.add_argument("--ted-notice", default="")
    parser.add_argument("--yes-live", action="store_true")
    parser.add_argument("--output", default="LIVE_VALIDATION_BUILD_367_PUBLIC_MONEY.json")
    args=parser.parse_args()
    if not args.yes_live: raise SystemExit("Refusing network execution: pass --yes-live explicitly")
    if not args.us_award_id and not args.ted_notice: raise SystemExit("Provide --us-award-id and/or --ted-notice")
    results={"build":"367.0","status":"partial","network_used":True,"usaspending":"not_run","ted_notice":"not_run","receipts":[]}
    with tempfile.TemporaryDirectory(prefix="ee367-live-") as td:
        with AppContext(base_dir=Path(td),actor="live367") as c:
            a=c.team_identity_359.create_initial_admin(username="live367",display_name="Live Validation",password="Orbit-Pine-Quartz-Live-367!")
            ident={**a,"session_id":"live367"}
            cid=c.build367.team_create_case(identity=ident,title="Build 367 Live Validation",client="Engineering",purpose="explicit external connector validation",legal_basis="public_data")["case_id"]
            for key,value,label in (("usaspending_award_v1",args.us_award_id,"usaspending"),("ted_notice_xml_v1",args.ted_notice,"ted_notice")):
                if not value: continue
                prepared=c.build367.prepare_public_money_source(case_id=cid,connector_key=key,identifier=value,identity=ident)
                sid=prepared["source"]["source_id"]
                c.build367.team_review_crawler_source(identity=ident,case_id=cid,source_id=sid,decision="approve_read_only",rationale="Explicit engineering live validation of official public read-only source")
                q=c.build367.enqueue_public_money_live(case_id=cid,source_id=sid,identity=ident,confirmation="LIVE")
                out=c.build367.run_public_money_live_job(job_id=q["job"]["job_id"],worker_id="live367")
                rec=out["receipt"]; results["receipts"].append(rec); results[label]="pass" if rec.get("externally_validated") else "fail"
    requested=[results[k] for k in ("usaspending","ted_notice") if results[k] != "not_run"]
    results["status"]="pass" if requested and all(x=="pass" for x in requested) else "fail"
    Path(args.output).write_text(json.dumps(results,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps(results,indent=2,sort_keys=True)); return results

if __name__=="__main__": main()

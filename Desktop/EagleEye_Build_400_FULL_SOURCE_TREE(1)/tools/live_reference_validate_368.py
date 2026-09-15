from __future__ import annotations
import argparse, json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description="Build 368 operator-triggered live validation status writer")
    p.add_argument("--federal-register",choices=["not_run","pass","fail"],default="not_run")
    p.add_argument("--internet-archive-metadata",choices=["not_run","pass","fail"],default="not_run")
    p.add_argument("--output",default="LIVE_VALIDATION_BUILD_368_REFERENCE_INTEL.json")
    a=p.parse_args()
    result={"build":"368.0","status":"pass" if a.federal_register==a.internet_archive_metadata=="pass" else "not_run" if a.federal_register==a.internet_archive_metadata=="not_run" else "partial_or_fail","federal_register":a.federal_register,"internet_archive_metadata":a.internet_archive_metadata,"ofac_sdn":"plan_only","unsc_consolidated":"plan_only","nara_catalog":"plan_only","govinfo_package":"plan_only","production_release_ready":False,"truthful_note":"This file records operator-supplied external validation outcomes. Build qualification does not set these fields to pass."}
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__": main()

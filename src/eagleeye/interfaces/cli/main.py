from __future__ import annotations

import argparse
import json

from eagleeye.bootstrap.startup import diagnose, run_browser, run_gui
from eagleeye_pro.version import BUILD_NAME


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=BUILD_NAME)
    parser.add_argument("--diagnose", action="store_true", help="run deterministic local diagnostics")
    parser.add_argument("--selftest", action="store_true", help="run the legacy comprehensive self-test through the compatibility facade")
    parser.add_argument("--init-demo", action="store_true", help="create the local demonstration case")
    parser.add_argument("--serve", action="store_true", help="start the canonical local browser workspace")
    parser.add_argument("--open-browser", action="store_true", help="open the workspace immediately in a browser")
    parser.add_argument("--browser", default="firefox", choices=["firefox", "default"], help="preferred browser")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--gui", action="store_true", help="compatibility alias: browser workspace with automatic browser opening")
    parser.add_argument("--desktop", action="store_true", help="start the optional Tk desktop fallback")
    parser.add_argument("--safe-mode", action="store_true", help="start the diagnostic safe-mode desktop")
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--apply-restore-stage", default="", help="apply a verified Build-125 restore stage while the workspace is closed")
    parser.add_argument("--production-gate", action="store_true", help="run the Build-126 production-candidate gate")
    parser.add_argument("--install-shortcut", action="store_true", help="create the Windows desktop and Start-menu shortcut")
    parser.add_argument("--phase3-gate", action="store_true", help="run the Build-133 Phase-3 production-candidate gate")
    parser.add_argument("--phase3-freeze", action="store_true", help="create a conditional or final Phase-3 freeze")
    parser.add_argument("--runtime-preflight", action="store_true", help="run the Build-134 operational runtime preflight")
    parser.add_argument("--connector-contract", default="", help="run an offline Build-134 connector-package contract by package id")
    parser.add_argument("--phase4-status", action="store_true", help="show Build-134 operational and connector-trust status")
    parser.add_argument("--build135-status", action="store_true", help="show Build-135 profile, Firefox-tab and source-intelligence status")
    parser.add_argument("--provider-health-135", action="store_true", help="run data-minimized Build-135 provider health and contract probes")
    parser.add_argument("--build136-status", action="store_true", help="show Build-136 Firefox stabilization and photo-intake status")
    parser.add_argument("--runtime-diagnostics-136", action="store_true", help="run deterministic Build-136 runtime diagnostics")
    parser.add_argument("--build137-status", action="store_true", help="show Build-137 guided workflow and photo-research status")
    parser.add_argument("--build138-status", action="store_true", help="show Build-138 evidence graph and advanced photo-research status")
    parser.add_argument("--build139-status", action="store_true", help="show Build-139 identity, AI, OPSEC and safe face-analysis status")
    parser.add_argument("--build140-status", action="store_true", help="show Build-140 evidence-grounded AI, OPSEC planning and image-intelligence status")
    parser.add_argument("--build141-status", action="store_true", help="show Build-141 source-quality, change-watch, OPSEC and efficiency status")
    parser.add_argument("--build142-status", action="store_true", help="show Build-142 professional-report and immutable-export status")
    parser.add_argument("--build143-status", action="store_true", help="show Build-143 controlled-collaboration, research-persona and egress-session status")
    parser.add_argument("--build144-status", action="store_true", help="show Build-144 release-candidate audit and verified-backup status")
    parser.add_argument("--build144-audit", default="", help="run the complete Build-144 audit for a case id")
    parser.add_argument("--build144-backup", default="", help="create a verified Build-144 backup for a case id")
    parser.add_argument("--build145-status", action="store_true", help="show the final Phase-4 baseline, maintenance and release-seal status")
    parser.add_argument("--build145-health", default="", help="create the final Build-145 health snapshot for a case id")
    parser.add_argument("--build146-status", action="store_true", help="show Build-146 identity, session and authorization status")
    parser.add_argument("--build147-status", action="store_true", help="show Build-147 social, database, job and OPSEC research status")
    parser.add_argument("--build148-status", action="store_true", help="show Build-148 connector SDK, contracts, health and quarantine status")
    parser.add_argument("--build149-status", action="store_true", help="show Build-149 source ecosystem, local AI planning and OPSEC status")
    parser.add_argument("--build150-status", action="store_true", help="show Build-150 browser evidence capture and hardening status")
    args = parser.parse_args(argv)

    if args.apply_restore_stage:
        from pathlib import Path
        from eagleeye.application.reliability.service import apply_restore_stage
        base = Path(args.base_dir or Path.cwd()).resolve()
        print(json.dumps(apply_restore_stage(base, args.apply_restore_stage), ensure_ascii=False, indent=2))
        return 0

    if args.production_gate or args.install_shortcut or args.phase3_gate or args.phase3_freeze or args.runtime_preflight or args.connector_contract or args.phase4_status or args.build135_status or args.provider_health_135 or args.build136_status or args.runtime_diagnostics_136 or args.build137_status or args.build138_status or args.build139_status or args.build140_status or args.build141_status or args.build142_status or args.build143_status or args.build144_status or args.build144_audit or args.build144_backup or args.build145_status or args.build145_health or args.build146_status or args.build147_status or args.build148_status or args.build149_status or args.build150_status:
        from pathlib import Path
        from eagleeye_pro.core.app_context import AppContext
        base = Path(args.base_dir or Path.cwd()).resolve()
        ctx = AppContext(base_dir=base)
        try:
            if args.build150_status:
                result = ctx.build150.dashboard()
            elif args.build149_status:
                result = ctx.build149.dashboard()
            elif args.build148_status:
                result = ctx.build148.dashboard()
            elif args.build147_status:
                result = ctx.build147.dashboard()
            elif args.build146_status:
                result = ctx.build146.dashboard()
            elif args.build145_health:
                result = ctx.build145.create_health_snapshot(case_id=args.build145_health, actor=ctx.actor)
            elif args.build145_status:
                result = ctx.build145.dashboard()
            elif args.build144_audit:
                result = ctx.build144.run_full_audit(case_id=args.build144_audit, include_optional=True, actor=ctx.actor)
            elif args.build144_backup:
                result = ctx.build144.create_verified_backup(case_id=args.build144_backup, confirmation="VERIFIZIERTES PHASE-4-BACKUP ERZEUGEN", actor=ctx.actor)
            elif args.build144_status:
                result = ctx.build144.dashboard()
            elif args.build143_status:
                result = ctx.build143.dashboard()
            elif args.build142_status:
                result = ctx.build142.dashboard()
            elif args.build141_status:
                result = ctx.build141.dashboard()
            elif args.build140_status:
                result = ctx.build140.dashboard()
            elif args.build139_status:
                result = ctx.build139.dashboard()
            elif args.build138_status:
                result = ctx.build138.dashboard()
            elif args.build137_status:
                result = ctx.build137.dashboard()
            elif args.install_shortcut:
                result = ctx.production_candidate_126.create_windows_shortcut(actor=ctx.actor, include_start_menu=True)
            elif args.runtime_diagnostics_136:
                result = ctx.build136.run_runtime_diagnostics(actor=ctx.actor)
            elif args.build136_status:
                result = ctx.build136.dashboard()
            elif args.provider_health_135:
                result = ctx.build135.run_all_health(actor=ctx.actor)
            elif args.build135_status:
                result = ctx.build135.dashboard()
            elif args.runtime_preflight:
                result = ctx.phase4_operations_134.runtime_preflight(actor=ctx.actor)
            elif args.connector_contract:
                result = ctx.phase4_operations_134.run_contract_check(package_id=args.connector_contract, actor=ctx.actor)
            elif args.phase4_status:
                result = ctx.phase4_operations_134.status()
            elif args.phase3_freeze:
                result = ctx.phase3_production_candidate_133.prepare_freeze(case_id=None, actor=ctx.actor, notes="CLI Phase-3 freeze")
            elif args.phase3_gate:
                result = ctx.phase3_production_candidate_133.run_gate(actor=ctx.actor)
            else:
                result = ctx.production_candidate_126.run_gate(actor=ctx.actor)
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        finally:
            ctx.close()
        return 0

    if args.selftest:
        from eagleeye_pro.main import run_selftest
        print(json.dumps(run_selftest(args.base_dir), ensure_ascii=False, indent=2))
        return 0

    if args.init_demo:
        from eagleeye_pro.core.app_context import AppContext
        from eagleeye_pro.main import create_demo_case
        ctx = AppContext(base_dir=args.base_dir)
        try:
            case = create_demo_case(ctx)
            print(json.dumps({"gate": "DEMO_CASE_CREATED", "case_id": case["case_id"], "db_path": str(ctx.db.path)}, ensure_ascii=False, indent=2))
        finally:
            ctx.close()
        if not (args.serve or args.gui or args.desktop or args.safe_mode):
            return 0

    if args.serve or args.gui:
        return run_browser(args.base_dir, host=args.host, port=args.port, open_browser=(args.open_browser or args.gui), browser=args.browser)

    if args.desktop or args.safe_mode:
        return run_gui(args.base_dir, safe_mode=args.safe_mode)

    print(json.dumps(diagnose(args.base_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

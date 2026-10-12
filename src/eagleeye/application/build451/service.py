import os

from eagleeye_pro.phase20.retrieval_isolation451 import ProcessSurfaceTransport451
from eagleeye_pro.phase20.scanner451 import ScanWithheld451


class Build451RetrievalIsolationService:
    BUILD = "451.0"

    def __init__(self, db, audit, *, build450, actor="local-analyst"):
        self.db, self.audit, self.build450, self.actor = db, audit, build450, actor

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.build450, name)

    def retrieval_isolation_status_451(self):
        profile = os.environ.get("EAGLEEYE_RETRIEVAL_PROFILE", "process")
        return {"build": self.BUILD, "phase": 20, "profile": profile,
                "process_isolation": True, "content_risk_gate": True,
                "scanner_configured": bool(os.environ.get("EAGLEEYE_CLAMD_SOCKET")),
                "contained_profile_requires_scanner": True,
                "unsupported_profile_fails_closed": True,
                "kernel_profile_supported_platform": "Linux x86-64, Landlock ABI >= 3, seccomp",
                "native_windows_kernel_profile_qualified": False,
                "operational_qualification": "HOLD", "production_release_ready": False,
                "next_hard_checkpoint": "455.0", "full_research_workflow_required_at_checkpoint": True}

    def diagnose_retrieval_isolation_451(self):
        transport = ProcessSurfaceTransport451()
        report = {"build": self.BUILD, "process": transport.probe(),
                  "kernel_containment_pass": False, "scanner_fixture_gate_pass": False,
                  "real_source_qualification": "HOLD", "production_release_ready": False}
        try:
            report["kernel"] = transport.containment_probe()
            report["kernel_containment_pass"] = True
        except RuntimeError:
            report["kernel_error"] = "kernel_profile_unavailable"
        if transport.scanner is not None:
            # Harmless standard antivirus test string; no executable or payload file.
            eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
            try:
                clean = transport.scanner.scan(b"EagleEye benign scanner qualification text")
                try:
                    transport.scanner.scan(eicar)
                except ScanWithheld451 as exc:
                    report["scanner_fixture_gate_pass"] = exc.quarantine_metadata["reason"] == "scanner_detection"
                report["scanner"] = clean
            except ScanWithheld451:
                report["scanner_error"] = "scanner_unavailable_or_unqualified"
        self.audit.log("retrieval_isolation451.diagnostic", "operating_profile", details=report)
        return report

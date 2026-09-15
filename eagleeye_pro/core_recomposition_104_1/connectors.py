from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from eagleeye_pro.core.database import new_id

from .events import TypedEventBus1041
from .models import ConnectorRunModel, ConnectorSpecModel, EventType
from .repository import CoreRepository1041


class ConnectorSDK1041:
    """Typed facade around Build-104 connectors.

    The existing provider implementations remain the execution backend, while all calls
    now enter through a validated connector contract and persist a normalized run record.
    """

    def __init__(self, repository: CoreRepository1041, events: TypedEventBus1041, legacy_service: Any):
        self.repository = repository
        self.events = events
        self.legacy = legacy_service
        self.seed_legacy_specs()

    def seed_legacy_specs(self) -> None:
        for row in self.legacy.list_adapters():
            spec = ConnectorSpecModel(
                connector_id=row["adapter_id"], name=row["name"], category=row["category"],
                input_types=[row["input_type"]], output_types=list(row.get("capabilities") or []),
                public_only=bool(row.get("public_only", True)),
                authentication_required=bool(row.get("authentication_required", False)),
                execution_mode=row.get("execution_mode") or "live_public_lookup",
                rate_limit_note=row.get("rate_note") or "", legal_note=row.get("legal_note") or "",
                implementation="eagleeye_pro.source_adapter_execution_104.SourceAdapterExecution104Service",
                enabled=bool(row.get("enabled", True)),
            )
            self.repository.upsert_connector_spec(spec)

    def list_connectors(self) -> list[dict[str, Any]]:
        return [m.model_dump(mode="json") for m in self.repository.list_connector_specs()]

    def execute(self, *, case_id: str, connector_id: str, input_value: str, options: dict[str, Any] | None = None, explicit_live_confirmation: bool = False, actor: str = "local-analyst") -> dict[str, Any]:
        specs = {s.connector_id: s for s in self.repository.list_connector_specs()}
        spec = specs.get(connector_id)
        if not spec or not spec.enabled:
            raise ValueError(f"Connector unavailable: {connector_id}")
        if not spec.public_only:
            raise PermissionError("Build 104.1 executes only public-source connectors.")
        run = ConnectorRunModel(
            run_id=new_id("conrun1041"), case_id=case_id, connector_id=connector_id,
            input_value=input_value, status="running",
        )
        self.repository.save_connector_run(run)
        self.events.publish(case_id=case_id, event_type=EventType.CONNECTOR_STARTED, producer="connector_sdk_104_1", connector_run_id=run.run_id, payload={"connector_id": connector_id})
        result = self.legacy.execute(case_id, connector_id, input_value, options=options or {}, explicit_live_confirmation=explicit_live_confirmation, actor=actor)
        status = result.get("status") or "failed"
        run.status = status
        run.legacy_execution_id = result.get("execution_id")
        run.artifact_id = None
        run.result = result
        run.error = result.get("error_text") or ""
        run.completed_at = datetime.now(timezone.utc)
        self.repository.save_connector_run(run)
        self.events.publish(
            case_id=case_id,
            event_type=EventType.CONNECTOR_COMPLETED if status == "succeeded" else EventType.CONNECTOR_FAILED,
            producer="connector_sdk_104_1", connector_run_id=run.run_id,
            payload={"connector_id": connector_id, "legacy_execution_id": run.legacy_execution_id, "status": status},
        )
        result["connector_run_id_104_1"] = run.run_id
        result["connector_contract_validated"] = True
        return result

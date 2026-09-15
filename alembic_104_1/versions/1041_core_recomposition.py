"""Build 104.1 core recomposition tables.

Revision ID: 1041_core
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "1041_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_artifacts_104_1",
        sa.Column("artifact_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("capture_id", sa.String(64), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("case_id", "capture_id", name="uq_core_artifact_case_capture_104_1"),
    )
    op.create_index("idx_core_artifact_case_104_1", "core_artifacts_104_1", ["case_id", "created_at"])
    op.create_table(
        "core_observations_104_1",
        sa.Column("observation_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("artifact_id", sa.String(64), sa.ForeignKey("core_artifacts_104_1.artifact_id", ondelete="CASCADE"), nullable=False),
        sa.Column("observation_type", sa.String(80), nullable=False),
        sa.Column("value_raw", sa.Text(), nullable=False),
        sa.Column("value_normalized", sa.Text(), nullable=False, server_default=""),
        sa.Column("extractor", sa.String(120), nullable=False),
        sa.Column("extractor_version", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="candidate"),
        sa.Column("character_start", sa.Integer(), nullable=True),
        sa.Column("character_end", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_core_observation_artifact_104_1", "core_observations_104_1", ["artifact_id", "created_at"])
    op.create_table(
        "core_events_104_1",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("producer", sa.String(120), nullable=False),
        sa.Column("artifact_id", sa.String(64), nullable=True),
        sa.Column("connector_run_id", sa.String(64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_core_event_case_104_1", "core_events_104_1", ["case_id", "created_at"])
    op.create_table(
        "connector_registry_104_1",
        sa.Column("connector_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("input_types_json", sa.Text(), nullable=False),
        sa.Column("output_types_json", sa.Text(), nullable=False),
        sa.Column("public_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("authentication_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("execution_mode", sa.String(80), nullable=False),
        sa.Column("rate_limit_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("legal_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("implementation", sa.String(240), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "connector_runs_104_1",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("connector_id", sa.String(100), nullable=False),
        sa.Column("input_value", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("legacy_execution_id", sa.String(64), nullable=True),
        sa.Column("artifact_id", sa.String(64), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_connector_run_case_104_1", "connector_runs_104_1", ["case_id", "started_at"])


def downgrade() -> None:
    op.drop_index("idx_connector_run_case_104_1", table_name="connector_runs_104_1")
    op.drop_table("connector_runs_104_1")
    op.drop_table("connector_registry_104_1")
    op.drop_index("idx_core_event_case_104_1", table_name="core_events_104_1")
    op.drop_table("core_events_104_1")
    op.drop_index("idx_core_observation_artifact_104_1", table_name="core_observations_104_1")
    op.drop_table("core_observations_104_1")
    op.drop_index("idx_core_artifact_case_104_1", table_name="core_artifacts_104_1")
    op.drop_table("core_artifacts_104_1")

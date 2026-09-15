"""Build 105 collection engine tables.

Revision ID: 1050_collection
Revises: 1041_core
"""
from alembic import op
import sqlalchemy as sa

revision = "1050_collection"
down_revision = "1041_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_jobs_105",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("engine", sa.String(30), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("seed_urls_json", sa.Text(), nullable=False),
        sa.Column("policy_json", sa.Text(), nullable=False),
        sa.Column("stats_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("worker_pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("started_at", sa.String(32), nullable=True),
        sa.Column("completed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_collection_job_case_105", "collection_jobs_105", ["case_id", "created_at"])
    op.create_table(
        "collection_pages_105",
        sa.Column("page_id", sa.String(64), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("parent_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("body_path", sa.Text(), nullable=False),
        sa.Column("screenshot_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("capture_id", sa.String(64), nullable=True),
        sa.Column("artifact_id", sa.String(64), nullable=True),
        sa.Column("finding_id", sa.String(64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("headers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("links_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("job_id", "canonical_url", name="uq_collection_page_job_url_105"),
    )
    op.create_index("idx_collection_page_case_105", "collection_pages_105", ["case_id", "fetched_at"])
    op.create_table(
        "collection_robots_decisions_105",
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("policy", sa.String(40), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_collection_robots_job_105", "collection_robots_decisions_105", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_collection_robots_job_105", table_name="collection_robots_decisions_105")
    op.drop_table("collection_robots_decisions_105")
    op.drop_index("idx_collection_page_case_105", table_name="collection_pages_105")
    op.drop_table("collection_pages_105")
    op.drop_index("idx_collection_job_case_105", table_name="collection_jobs_105")
    op.drop_table("collection_jobs_105")

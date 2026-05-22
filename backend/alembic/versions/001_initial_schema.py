"""Initial schema — users, media_files, transcripts, summaries.

Revision ID: 001
Revises: 
Create Date: 2026-05-22

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enable pgcrypto for gen_random_uuid() ─────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── Enum type for file processing status ──────────────────────────────────
    file_status_enum = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="file_status_enum",
        create_type=True,
    )
    file_status_enum.create(op.get_bind(), checkfirst=True)

    # ── Table: users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="UUID matching Supabase auth.users.id",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            comment="User's authenticated email address",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Account profile creation timestamp",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── Table: media_files ────────────────────────────────────────────────────
    op.create_table(
        "media_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique tracking identifier for the media asset",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_media_files_user_id"),
            nullable=False,
            comment="Owner user ID",
        ),
        sa.Column(
            "file_name",
            sa.String(500),
            nullable=False,
            comment="Original filename including extension",
        ),
        sa.Column(
            "storage_path",
            sa.Text,
            nullable=False,
            comment="Supabase Storage bucket path",
        ),
        sa.Column(
            "file_size_bytes",
            sa.BigInteger,
            nullable=False,
            comment="Raw file size in bytes",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed",
                name="file_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
            comment="Processing lifecycle state",
        ),
        sa.Column(
            "error_message",
            sa.Text,
            nullable=True,
            comment="Failure reason when status = 'failed'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Upload initialization timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Last state update timestamp",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_media_files_status",
        ),
    )
    op.create_index("ix_media_files_user_id", "media_files", ["user_id"])
    op.create_index("ix_media_files_status", "media_files", ["status"])

    # Auto-update updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)
    op.execute("""
        CREATE TRIGGER trigger_media_files_updated_at
        BEFORE UPDATE ON media_files
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)

    # ── Table: transcripts ────────────────────────────────────────────────────
    op.create_table(
        "transcripts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique transcript row identifier",
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_files.id", ondelete="CASCADE", name="fk_transcripts_file_id"),
            nullable=False,
            comment="References the parent media asset",
        ),
        sa.Column(
            "raw_text",
            sa.Text,
            nullable=False,
            comment="Full concatenated transcription text",
        ),
        sa.Column(
            "segments",
            postgresql.JSONB,
            nullable=True,
            comment="Structured segments: [{start, end, text, speaker}]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="Worker completion timestamp",
        ),
        sa.UniqueConstraint("file_id", name="uq_transcripts_file_id"),
    )
    op.create_index("ix_transcripts_file_id", "transcripts", ["file_id"])

    # ── Table: summaries ──────────────────────────────────────────────────────
    op.create_table(
        "summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique summary row identifier",
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("media_files.id", ondelete="CASCADE", name="fk_summaries_file_id"),
            nullable=False,
            comment="References the parent media asset",
        ),
        sa.Column(
            "executive_summary",
            sa.Text,
            nullable=False,
            comment="3-5 paragraph narrative summary synthesized by Gemini",
        ),
        sa.Column(
            "key_takeaways",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment='Structured insights: [{"point": "...", "category": "..."}]',
        ),
        sa.Column(
            "action_items",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment='Action items: [{"task": "...", "owner": "...", "priority": "..."}]',
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="LLM synthesis completion timestamp",
        ),
        sa.UniqueConstraint("file_id", name="uq_summaries_file_id"),
    )
    op.create_index("ix_summaries_file_id", "summaries", ["file_id"])


def downgrade() -> None:
    op.drop_table("summaries")
    op.drop_table("transcripts")
    op.execute("DROP TRIGGER IF EXISTS trigger_media_files_updated_at ON media_files")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_table("media_files")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS file_status_enum")

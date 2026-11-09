"""Grant thesis_app to DB login role so SET ROLE enables RLS (Stage 8)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table owner (thesis) bypasses RLS; SET ROLE thesis_app makes policies apply.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesis')
             AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesis_app') THEN
            GRANT thesis_app TO thesis;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesis')
             AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesis_app') THEN
            REVOKE thesis_app FROM thesis;
          END IF;
        END
        $$;
        """
    )

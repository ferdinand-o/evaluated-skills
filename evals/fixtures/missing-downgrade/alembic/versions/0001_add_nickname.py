"""add nickname to users

Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("users", sa.Column("nickname", sa.Text(), nullable=True))


def downgrade():
    pass

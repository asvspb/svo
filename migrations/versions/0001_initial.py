"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-12-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'dates',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'layers',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('clazz', sa.Enum('occupied', 'gray', 'frontline', name='layer_class'), nullable=False),
        sa.Column('date_id', sa.BigInteger(), sa.ForeignKey('dates.id'), nullable=False),
        sa.Column('source_url', sa.String(length=512)),
        sa.Column('geojson', sa.LargeBinary(), nullable=False),
        sa.Column('features_count', sa.Integer()),
        sa.Column('checksum', sa.String(length=64)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('clazz', 'date_id', name='uk_layer_class_date'),
    )

    op.create_table(
        'changes',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('date_prev_id', sa.BigInteger(), sa.ForeignKey('dates.id'), nullable=False),
        sa.Column('date_curr_id', sa.BigInteger(), sa.ForeignKey('dates.id'), nullable=False),
        sa.Column('clazz', sa.Enum('occupied', 'gray', name='change_class'), nullable=False),
        sa.Column('status', sa.Enum('gained', 'lost', name='change_status'), nullable=False),
        sa.Column('area_km2', sa.Float(), nullable=False),
        sa.Column('centroid_lon', sa.Float(), nullable=False),
        sa.Column('centroid_lat', sa.Float(), nullable=False),
        sa.Column('settlement', sa.String(length=128)),
        sa.Column('settlement_distance_km', sa.Float()),
        sa.Column('hash_key', sa.String(length=64)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_changes_date_class', 'changes', ['date_curr_id', 'clazz', 'status'])

    op.create_table(
        'reports',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('date_curr_id', sa.BigInteger(), sa.ForeignKey('dates.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('top3_json', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'subscribers',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('chat_id', sa.BigInteger(), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('subscribers')
    op.drop_table('reports')
    op.drop_index('idx_changes_date_class', table_name='changes')
    op.drop_table('changes')
    op.drop_table('layers')
    op.drop_table('dates')

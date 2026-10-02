"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-02 23:45:27.899085
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_role', sa.String(length=16), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_created', 'audit_logs', ['created_at'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('patient_number', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=32, collation='utf8mb4_unicode_ci'), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254, collation='utf8mb4_unicode_ci'), nullable=False),
    sa.Column('date_of_birth', sa.Date(), nullable=True),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.Column('updated_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('patient_number'),
    sa.UniqueConstraint('username'),
    mysql_auto_increment='1001'
    )
    # SQLAlchemy only emits AUTO_INCREMENT for primary keys; PT-1001, PT-1002, ... come from this column.
    op.execute('ALTER TABLE users MODIFY patient_number INT NOT NULL AUTO_INCREMENT')
    op.create_table('ecg_enrollments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('hea_hash', sa.String(length=64), nullable=False),
    sa.Column('dat_hash', sa.String(length=64), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('dat_filename', sa.String(length=255), nullable=True),
    sa.Column('sampling_rate', sa.Float(), nullable=True),
    sa.Column('sample_count', sa.Integer(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hea_hash', 'dat_hash', name='uq_enrollment_file_hashes'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('medical_records',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('record_date', sa.Date(), nullable=False),
    sa.Column('department', sa.String(length=80), nullable=False),
    sa.Column('doctor', sa.String(length=120), nullable=False),
    sa.Column('record_type', sa.String(length=80), nullable=False),
    sa.Column('diagnosis', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('report_title', sa.String(length=160), nullable=True),
    sa.Column('report_summary', sa.Text(), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_medical_records_user_date', 'medical_records', ['user_id', 'record_date'], unique=False)
    op.create_table('analysis_profiles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('enrollment_id', sa.Uuid(), nullable=True),
    sa.Column('pipeline_version', sa.String(length=32), nullable=False),
    sa.Column('signal_data', sa.JSON(), nullable=False),
    sa.Column('processed_signal_data', sa.JSON(), nullable=False),
    sa.Column('feature_data', sa.JSON(), nullable=False),
    sa.Column('stage_data', sa.JSON(), nullable=False),
    sa.Column('display_metrics', sa.JSON(), nullable=False),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['enrollment_id'], ['ecg_enrollments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'pipeline_version', name='uq_profile_user_version')
    )
    op.create_table('authentication_attempts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('username_attempted', sa.String(length=64), nullable=True),
    sa.Column('result', sa.String(length=16), nullable=False),
    sa.Column('failure_reason', sa.String(length=64), nullable=True),
    sa.Column('authentication_method', sa.String(length=16), nullable=False),
    sa.Column('analysis_profile_id', sa.Uuid(), nullable=True),
    sa.Column('processing_time_ms', sa.Integer(), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
    sa.ForeignKeyConstraint(['analysis_profile_id'], ['analysis_profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auth_attempts_created', 'authentication_attempts', ['created_at'], unique=False)
    op.create_index('ix_auth_attempts_user_created', 'authentication_attempts', ['user_id', 'created_at'], unique=False)
    

def downgrade() -> None:
    op.drop_table('authentication_attempts')
    op.drop_table('analysis_profiles')
    op.drop_table('medical_records')
    op.drop_table('ecg_enrollments')
    op.drop_table('users')
    op.drop_table('audit_logs')
    

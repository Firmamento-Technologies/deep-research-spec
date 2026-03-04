"""Add authentication tables and user_id columns.

Revision ID: 003
Revises: 002
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(20), server_default='user'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('is_verified', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_jti', sa.String(255), nullable=False, unique=True),
        sa.Column('refresh_token', sa.String(500), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
    )
    op.create_index('idx_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('idx_sessions_token_jti', 'sessions', ['token_jti'])
    
    # Add user_id to runs table
    op.add_column('runs', sa.Column('user_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_runs_user_id', 'runs', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_runs_user_id', 'runs', ['user_id'])
    
    # Add user_id to spaces table
    op.add_column('spaces', sa.Column('user_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_spaces_user_id', 'spaces', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_spaces_user_id', 'spaces', ['user_id'])
    
    # Add sections table if not exists
    op.create_table(
        'sections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('doc_id', sa.String, sa.ForeignKey('runs.doc_id', ondelete='CASCADE'), nullable=False),
        sa.Column('section_idx', sa.Integer, nullable=False),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('content', sa.Text),
        sa.Column('status', sa.String(30), server_default='pending'),
        sa.Column('metadata', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_index('idx_spaces_user_id', 'spaces')
    op.drop_constraint('fk_spaces_user_id', 'spaces', type_='foreignkey')
    op.drop_column('spaces', 'user_id')
    
    op.drop_index('idx_runs_user_id', 'runs')
    op.drop_constraint('fk_runs_user_id', 'runs', type_='foreignkey')
    op.drop_column('runs', 'user_id')
    
    op.drop_index('idx_sessions_token_jti', 'sessions')
    op.drop_index('idx_sessions_user_id', 'sessions')
    op.drop_table('sessions')
    
    op.drop_index('idx_users_username', 'users')
    op.drop_index('idx_users_email', 'users')
    op.drop_table('users')
    
    op.drop_table('sections')

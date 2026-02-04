"""Initial migration: create search_request, contract_result, spec_comparison_row tables

Revision ID: 86f539f586af
Revises: 
Create Date: 2026-02-04 10:31:08.476937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '86f539f586af'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    search_status_enum = postgresql.ENUM('RUNNING', 'DONE', 'STOPPED', 'ERROR', name='searchstatus', create_type=True)
    input_source_enum = postgresql.ENUM('MANUAL', 'FILE', name='inputsource', create_type=True)
    match_status_enum = postgresql.ENUM('MATCH', 'DIFF', 'UNKNOWN', name='matchstatus', create_type=True)
    
    search_status_enum.create(op.get_bind(), checkfirst=True)
    input_source_enum.create(op.get_bind(), checkfirst=True)
    match_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create search_request table
    op.create_table('search_request',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', search_status_enum, nullable=False, server_default='RUNNING'),
        sa.Column('input_source', input_source_enum, nullable=False),
        sa.Column('object_name', sa.String(), nullable=False),
        sa.Column('ktru_code', sa.String(), nullable=False),
        sa.Column('okpd2_code', sa.String(), nullable=True),
        sa.Column('customer_region', sa.String(), nullable=False, server_default='СЗФО'),
        sa.Column('law', sa.String(), nullable=False, server_default='44'),
        sa.Column('date_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_to', sa.DateTime(timezone=True), nullable=False),
        sa.Column('execution_statuses', postgresql.ARRAY(sa.String()), nullable=False, server_default='{"Исполнение завершено","Исполнение прекращено"}'),
        sa.Column('limit_contracts', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('found_total', sa.Integer(), nullable=True),
        sa.Column('processed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('nmc_value', sa.Float(), nullable=True),
        sa.Column('selected_contract_ids', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('runtime_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('search_parameters_json', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create contract_result table
    op.create_table('contract_result',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('search_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reestr_number', sa.String(), nullable=False),
        sa.Column('contract_url', sa.String(), nullable=False),
        sa.Column('sign_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(), nullable=False, server_default='RUB'),
        sa.Column('match_type', sa.String(), nullable=False),
        sa.Column('ai_score', sa.Integer(), nullable=False),
        sa.Column('manufacturer_target', sa.String(), nullable=True),
        sa.Column('manufacturer_found', sa.String(), nullable=True),
        sa.Column('manufacturer_match', sa.Boolean(), nullable=True),
        sa.Column('is_2025_plus', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('accepted_for_nmc', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('raw_data_json', postgresql.JSON(), nullable=True),
        sa.Column('contract_price', sa.Float(), nullable=True),
        sa.Column('customer_name', sa.String(), nullable=True),
        sa.Column('supplier_name', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['search_id'], ['search_request.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for contract_result
    op.create_index(op.f('ix_contract_result_reestr_number'), 'contract_result', ['reestr_number'], unique=False)
    op.create_index(op.f('ix_contract_result_search_id'), 'contract_result', ['search_id'], unique=False)
    
    # Create spec_comparison_row table
    op.create_table('spec_comparison_row',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('contract_result_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('target_value', sa.String(), nullable=True),
        sa.Column('actual_value', sa.String(), nullable=True),
        sa.Column('match_status', match_status_enum, nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('unit', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['contract_result_id'], ['contract_result.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for spec_comparison_row
    op.create_index(op.f('ix_spec_comparison_row_contract_result_id'), 'spec_comparison_row', ['contract_result_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_spec_comparison_row_contract_result_id'), table_name='spec_comparison_row')
    op.drop_table('spec_comparison_row')
    
    op.drop_index(op.f('ix_contract_result_search_id'), table_name='contract_result')
    op.drop_index(op.f('ix_contract_result_reestr_number'), table_name='contract_result')
    op.drop_table('contract_result')
    
    op.drop_table('search_request')
    
    # Drop enum types
    match_status_enum = postgresql.ENUM('MATCH', 'DIFF', 'UNKNOWN', name='matchstatus')
    input_source_enum = postgresql.ENUM('MANUAL', 'FILE', name='inputsource')
    search_status_enum = postgresql.ENUM('RUNNING', 'DONE', 'STOPPED', 'ERROR', name='searchstatus')
    
    match_status_enum.drop(op.get_bind(), checkfirst=True)
    input_source_enum.drop(op.get_bind(), checkfirst=True)
    search_status_enum.drop(op.get_bind(), checkfirst=True)

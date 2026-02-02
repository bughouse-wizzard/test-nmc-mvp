-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create search_request table
CREATE TABLE IF NOT EXISTS search_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    input_source VARCHAR(10) NOT NULL DEFAULT 'MANUAL',
    object_name TEXT NOT NULL,
    ktru_code VARCHAR(50) NOT NULL,
    okpd2_code VARCHAR(50),
    customer_region VARCHAR(100) NOT NULL DEFAULT 'СЗФО',
    law VARCHAR(10) NOT NULL DEFAULT '44',
    date_from TIMESTAMP WITH TIME ZONE NOT NULL,
    date_to TIMESTAMP WITH TIME ZONE NOT NULL,
    execution_statuses JSONB NOT NULL DEFAULT '["Исполнение завершено", "Исполнение прекращено"]',
    limit_contracts INTEGER NOT NULL DEFAULT 30,
    found_total INTEGER,
    processed_count INTEGER NOT NULL DEFAULT 0,
    nmc_value DECIMAL(15, 2),
    selected_contract_ids JSONB DEFAULT '[]',
    runtime_ms BIGINT,
    error_message TEXT,
    
    CONSTRAINT valid_status CHECK (status IN ('RUNNING', 'DONE', 'STOPPED', 'ERROR')),
    CONSTRAINT valid_input_source CHECK (input_source IN ('MANUAL', 'FILE'))
);

-- Create contract_result table
CREATE TABLE IF NOT EXISTS contract_result (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID NOT NULL REFERENCES search_request(id) ON DELETE CASCADE,
    reestr_number VARCHAR(100) NOT NULL,
    contract_url TEXT NOT NULL,
    sign_date TIMESTAMP WITH TIME ZONE NOT NULL,
    unit_price DECIMAL(15, 2),
    currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
    match_type VARCHAR(20) NOT NULL,
    ai_score INTEGER NOT NULL CHECK (ai_score >= 0 AND ai_score <= 100),
    manufacturer_target TEXT,
    manufacturer_found TEXT,
    manufacturer_match BOOLEAN,
    is_2025_plus BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_for_nmc BOOLEAN NOT NULL DEFAULT FALSE,
    raw_data_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_match_type CHECK (match_type IN ('IDENTICAL', 'HOMOGENEOUS', 'NO_MATCH')),
    UNIQUE(search_id, reestr_number)
);

-- Create spec_comparison_row table
CREATE TABLE IF NOT EXISTS spec_comparison_row (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_result_id UUID NOT NULL REFERENCES contract_result(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_value TEXT NOT NULL,
    actual_value TEXT NOT NULL,
    match_status VARCHAR(10) NOT NULL,
    weight INTEGER NOT NULL DEFAULT 1,
    
    CONSTRAINT valid_match_status CHECK (match_status IN ('MATCH', 'DIFF', 'UNKNOWN'))
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_search_request_status ON search_request(status);
CREATE INDEX IF NOT EXISTS idx_search_request_created_at ON search_request(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_request_ktru_code ON search_request(ktru_code);
CREATE INDEX IF NOT EXISTS idx_contract_result_search_id ON contract_result(search_id);
CREATE INDEX IF NOT EXISTS idx_contract_result_match_type ON contract_result(match_type);
CREATE INDEX IF NOT EXISTS idx_contract_result_ai_score ON contract_result(ai_score DESC);
CREATE INDEX IF NOT EXISTS idx_spec_comparison_contract_result_id ON spec_comparison_row(contract_result_id);
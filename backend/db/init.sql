-- Initialize database schema for NMCK Calculation System

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Search requests table
CREATE TABLE IF NOT EXISTS search_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    input_source VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    
    -- Search parameters
    object_name TEXT NOT NULL,
    ktru_code VARCHAR(50) NOT NULL,
    okpd2_code VARCHAR(50),
    customer_region VARCHAR(100) DEFAULT 'СЗФО',
    law VARCHAR(20) DEFAULT '44-ФЗ',
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    execution_statuses JSONB DEFAULT '["Исполнение завершено"]',
    limit_contracts INTEGER DEFAULT 30,
    characteristics_text TEXT,
    manufacturer TEXT,
    
    -- Results
    found_total INTEGER,
    processed_count INTEGER DEFAULT 0,
    nmc_value DECIMAL(15, 2),
    selected_contract_ids JSONB DEFAULT '[]',
    runtime_ms BIGINT,
    error_message TEXT,
    
    -- Metadata
    user_id UUID,
    session_id VARCHAR(100),
    
    -- Indexes
    INDEX idx_search_requests_status (status),
    INDEX idx_search_requests_created_at (created_at DESC),
    INDEX idx_search_requests_ktru_code (ktru_code)
);

-- Contract results table
CREATE TABLE IF NOT EXISTS contract_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID NOT NULL REFERENCES search_requests(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Contract information
    reestr_number VARCHAR(100) NOT NULL,
    contract_url TEXT NOT NULL,
    sign_date DATE NOT NULL,
    unit_price DECIMAL(15, 2),
    currency VARCHAR(3) DEFAULT 'RUB',
    
    -- Matching results
    match_type VARCHAR(20) NOT NULL, -- IDENTICAL, HOMOGENEOUS, NO_MATCH
    ai_score INTEGER CHECK (ai_score >= 0 AND ai_score <= 100),
    manufacturer_target TEXT,
    manufacturer_found TEXT,
    manufacturer_match BOOLEAN,
    is_2025_plus BOOLEAN DEFAULT FALSE,
    accepted_for_nmc BOOLEAN DEFAULT FALSE,
    
    -- Raw data
    raw_data_json JSONB,
    
    -- Indexes
    INDEX idx_contract_results_search_id (search_id),
    INDEX idx_contract_results_reestr_number (reestr_number),
    INDEX idx_contract_results_match_type (match_type),
    INDEX idx_contract_results_ai_score (ai_score DESC),
    UNIQUE (search_id, reestr_number)
);

-- Specification comparison table
CREATE TABLE IF NOT EXISTS spec_comparison_rows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_result_id UUID NOT NULL REFERENCES contract_results(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Comparison data
    name TEXT NOT NULL,
    target_value TEXT,
    actual_value TEXT,
    match_status VARCHAR(10) NOT NULL, -- MATCH, DIFF, UNKNOWN
    weight INTEGER DEFAULT 1 CHECK (weight >= 1 AND weight <= 10),
    notes TEXT,
    
    -- Indexes
    INDEX idx_spec_comparison_contract_result_id (contract_result_id),
    INDEX idx_spec_comparison_match_status (match_status)
);

-- Document storage table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID REFERENCES search_requests(id) ON DELETE CASCADE,
    contract_result_id UUID REFERENCES contract_results(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Document information
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    mime_type VARCHAR(100),
    
    -- Metadata
    source_url TEXT,
    download_status VARCHAR(20) DEFAULT 'PENDING',
    error_message TEXT,
    
    -- Indexes
    INDEX idx_documents_search_id (search_id),
    INDEX idx_documents_contract_result_id (contract_result_id)
);

-- Task queue table (for Celery or similar)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Task information
    task_id VARCHAR(100) UNIQUE,
    task_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority INTEGER DEFAULT 0,
    
    -- Task data
    args JSONB,
    kwargs JSONB,
    result JSONB,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms BIGINT,
    
    -- Error handling
    retries INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    traceback TEXT,
    
    -- Indexes
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_created_at (created_at DESC),
    INDEX idx_tasks_task_name (task_name)
);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_search_requests_updated_at 
    BEFORE UPDATE ON search_requests 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at 
    BEFORE UPDATE ON tasks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_search_requests_composite 
    ON search_requests (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contract_results_composite 
    ON contract_results (search_id, ai_score DESC);

-- Insert sample data for testing (optional)
-- INSERT INTO search_requests (object_name, ktru_code, date_from, date_to) 
-- VALUES ('Бумага офисная', '24.11.10', '2023-01-01', '2026-01-01');
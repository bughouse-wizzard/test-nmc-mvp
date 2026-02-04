-- Initialize database for НМЦК Расчет система

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create search_request table
CREATE TABLE search_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'DONE', 'STOPPED', 'ERROR')),
    input_source VARCHAR(10) NOT NULL CHECK (input_source IN ('MANUAL', 'FILE')),
    
    -- Search parameters
    object_name TEXT NOT NULL,
    ktru_code VARCHAR(50) NOT NULL,
    okpd2_code VARCHAR(50),
    customer_region VARCHAR(100) NOT NULL DEFAULT 'СЗФО',
    law VARCHAR(20) NOT NULL DEFAULT '44-ФЗ',
    date_from DATE NOT NULL,
    date_to DATE NOT NULL,
    limit_contracts INTEGER NOT NULL DEFAULT 30,
    execution_statuses JSONB NOT NULL DEFAULT '["Исполнение завершено", "Исполнение прекращено"]',
    
    -- Results
    found_total INTEGER,
    processed_count INTEGER NOT NULL DEFAULT 0,
    nmc_value DECIMAL(15, 2),
    selected_contract_ids JSONB DEFAULT '[]',
    runtime_ms BIGINT,
    error_message TEXT,
    
    -- Metadata
    user_id UUID, -- For future authentication
    file_path TEXT, -- If input source is FILE
    
    -- Indexes
    INDEX idx_search_request_status (status),
    INDEX idx_search_request_created_at (created_at DESC),
    INDEX idx_search_request_ktru (ktru_code)
);

-- Create contract_result table
CREATE TABLE contract_result (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID NOT NULL REFERENCES search_request(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Contract information
    reestr_number VARCHAR(100) NOT NULL,
    contract_url TEXT NOT NULL,
    sign_date DATE NOT NULL,
    unit_price DECIMAL(15, 2),
    currency VARCHAR(3) DEFAULT 'RUB',
    
    -- Matching results
    match_type VARCHAR(20) NOT NULL CHECK (match_type IN ('IDENTICAL', 'HOMOGENEOUS', 'NO_MATCH')),
    ai_score INTEGER NOT NULL CHECK (ai_score >= 0 AND ai_score <= 100),
    
    -- Manufacturer information
    manufacturer_target TEXT,
    manufacturer_found TEXT,
    manufacturer_match BOOLEAN,
    is_2025_plus BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Selection
    accepted_for_nmc BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Raw data
    raw_data_json JSONB NOT NULL DEFAULT '{}',
    
    -- Indexes
    INDEX idx_contract_result_search_id (search_id),
    INDEX idx_contract_result_match_type (match_type),
    INDEX idx_contract_result_ai_score (ai_score DESC),
    INDEX idx_contract_result_reestr_number (reestr_number),
    UNIQUE (search_id, reestr_number)
);

-- Create spec_comparison_row table
CREATE TABLE spec_comparison_row (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_result_id UUID NOT NULL REFERENCES contract_result(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Comparison data
    name TEXT NOT NULL,
    target_value TEXT NOT NULL,
    actual_value TEXT NOT NULL,
    match_status VARCHAR(10) NOT NULL CHECK (match_status IN ('MATCH', 'DIFF', 'UNKNOWN')),
    weight INTEGER NOT NULL DEFAULT 1,
    
    -- Indexes
    INDEX idx_spec_comparison_contract_id (contract_result_id),
    INDEX idx_spec_comparison_match_status (match_status)
);

-- Create document_storage table for uploaded files
CREATE TABLE document_storage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_id UUID REFERENCES search_request(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- File information
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    
    -- Processing status
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processing_error TEXT,
    
    -- Indexes
    INDEX idx_document_storage_search_id (search_id),
    INDEX idx_document_storage_created_at (created_at DESC)
);

-- Create task_queue table for background processing
CREATE TABLE task_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Task information
    task_type VARCHAR(50) NOT NULL,
    search_id UUID NOT NULL REFERENCES search_request(id) ON DELETE CASCADE,
    contract_reestr_number VARCHAR(100),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')),
    priority INTEGER NOT NULL DEFAULT 0,
    
    -- Task data
    input_data JSONB NOT NULL DEFAULT '{}',
    output_data JSONB,
    error_message TEXT,
    
    -- Retry logic
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    
    -- Indexes
    INDEX idx_task_queue_status (status),
    INDEX idx_task_queue_search_id (search_id),
    INDEX idx_task_queue_priority_created (priority DESC, created_at ASC)
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
CREATE TRIGGER update_search_request_updated_at 
    BEFORE UPDATE ON search_request 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for performance
CREATE INDEX idx_contract_result_created_at ON contract_result(created_at DESC);
CREATE INDEX idx_search_request_date_range ON search_request(date_from, date_to);
CREATE INDEX idx_contract_result_sign_date ON contract_result(sign_date DESC);

-- Insert sample data for testing (optional)
-- INSERT INTO search_request (id, created_at, status, input_source, object_name, ktru_code, customer_region, date_from, date_to, limit_contracts)
-- VALUES 
--     (uuid_generate_v4(), NOW() - INTERVAL '2 days', 'DONE', 'MANUAL', 'Бумага офисная А4', '30.11.12.110', 'СЗФО', '2023-01-01', '2024-01-01', 30),
--     (uuid_generate_v4(), NOW() - INTERVAL '1 day', 'RUNNING', 'FILE', 'Принтер лазерный', '32.99.11.190', 'СЗФО', '2023-06-01', '2024-06-01', 20);
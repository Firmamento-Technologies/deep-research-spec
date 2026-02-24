-- Deep Research System — PostgreSQL Init Schema
-- Loaded automatically by docker-compose on first start

-- Document metadata
CREATE TABLE IF NOT EXISTS documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    target_words INT NOT NULL,
    quality_preset VARCHAR(20) DEFAULT 'balanced',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_cost_usd FLOAT DEFAULT 0.0,
    status VARCHAR(20) DEFAULT 'in_progress'
);

-- Section checkpoints
CREATE TABLE IF NOT EXISTS sections (
    doc_id UUID NOT NULL,
    section_idx INT NOT NULL,
    section_scope TEXT,
    target_words INT,
    draft TEXT,
    css_final FLOAT,
    iteration_count INT DEFAULT 0,
    approved_at TIMESTAMP,
    PRIMARY KEY (doc_id, section_idx),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- LLM call tracking
CREATE TABLE IF NOT EXISTS llm_calls (
    id SERIAL PRIMARY KEY,
    doc_id UUID,
    section_idx INT,
    iteration INT,
    agent VARCHAR(100),
    model VARCHAR(100),
    tokens_in INT,
    tokens_out INT,
    cache_read_tokens INT DEFAULT 0,
    cache_creation_tokens INT DEFAULT 0,
    cost_usd FLOAT,
    latency_ms INT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Jury verdicts history
CREATE TABLE IF NOT EXISTS verdicts (
    id SERIAL PRIMARY KEY,
    doc_id UUID,
    section_idx INT,
    iteration INT,
    judge_slot VARCHAR(10),
    dimension VARCHAR(10),
    pass_fail BOOLEAN,
    css_contribution FLOAT,
    confidence VARCHAR(20),
    veto_category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_llm_calls_doc ON llm_calls(doc_id, section_idx);
CREATE INDEX IF NOT EXISTS idx_verdicts_doc ON verdicts(doc_id, section_idx);
CREATE INDEX IF NOT EXISTS idx_sections_doc ON sections(doc_id);

-- Cost aggregation view
CREATE OR REPLACE VIEW document_costs AS
SELECT
    doc_id,
    COUNT(DISTINCT section_idx) as sections_completed,
    SUM(cost_usd) as total_cost,
    AVG(cost_usd) as avg_cost_per_call,
    SUM(cache_read_tokens) as total_cache_hits,
    SUM(cache_creation_tokens) as total_cache_writes
FROM llm_calls
GROUP BY doc_id;

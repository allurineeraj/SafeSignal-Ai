-- SafeSignalAI Supabase Schema Migration (Updated for Final Architecture)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Reports Table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id TEXT UNIQUE NOT NULL,
    report_type TEXT NOT NULL,
    site TEXT NOT NULL,
    location TEXT NOT NULL,
    original_text TEXT NOT NULL,
    original_language TEXT DEFAULT 'English',
    translated_text TEXT,
    report_summary TEXT, -- Added for final architecture
    immediate_action TEXT,
    anonymous INTEGER DEFAULT 0,
    submitted_on_behalf INTEGER DEFAULT 0,
    submitted_by TEXT,
    source_type TEXT DEFAULT 'web_form',
    audio_path TEXT,
    image_path TEXT,
    document_path TEXT,
    immediate_danger INTEGER DEFAULT 0,
    review_priority TEXT,
    report_status TEXT DEFAULT 'Submitted',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Note: Using DO block to add columns if they don't exist to prevent errors on existing databases
DO $$ 
BEGIN 
    BEGIN
        ALTER TABLE reports ADD COLUMN report_summary TEXT;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
END $$;

-- 2. AI Predictions Table
CREATE TABLE IF NOT EXISTS ai_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id TEXT UNIQUE NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    sif_label TEXT,
    sif_score INTEGER,
    confidence REAL,
    priority TEXT,
    activity TEXT,
    hazard TEXT,
    energy_source TEXT,
    exposure TEXT,
    failed_barrier TEXT,
    potential_consequence TEXT,
    life_saving_rules TEXT, -- JSON string array
    evidence_phrases TEXT,  -- JSON string array
    actual_injury TEXT,
    explanation TEXT,
    
    -- Added fields for final architecture
    risk_level TEXT,
    severity TEXT,
    likelihood TEXT,
    unsafe_act TEXT,
    unsafe_condition TEXT,
    equipment TEXT,
    precursor_pattern TEXT,
    precursor_explanation TEXT,
    recommended_corrective_action TEXT,

    llm_provider TEXT,
    llm_model TEXT,
    llm_analysis_status TEXT,
    llm_confidence REAL,
    classifier_mode TEXT,
    model_version TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

DO $$ 
BEGIN 
    BEGIN
        ALTER TABLE ai_predictions ADD COLUMN risk_level TEXT;
        ALTER TABLE ai_predictions ADD COLUMN severity TEXT;
        ALTER TABLE ai_predictions ADD COLUMN likelihood TEXT;
        ALTER TABLE ai_predictions ADD COLUMN unsafe_act TEXT;
        ALTER TABLE ai_predictions ADD COLUMN unsafe_condition TEXT;
        ALTER TABLE ai_predictions ADD COLUMN equipment TEXT;
        ALTER TABLE ai_predictions ADD COLUMN precursor_pattern TEXT;
        ALTER TABLE ai_predictions ADD COLUMN precursor_explanation TEXT;
        ALTER TABLE ai_predictions ADD COLUMN recommended_corrective_action TEXT;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
END $$;


-- 3. HSE Reviews Table
CREATE TABLE IF NOT EXISTS hse_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id TEXT UNIQUE NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    reviewer_name TEXT NOT NULL,
    final_sif_label TEXT NOT NULL,
    final_priority TEXT NOT NULL,
    final_activity TEXT,
    final_hazard TEXT,
    final_energy_source TEXT,
    final_exposure TEXT,
    final_failed_barrier TEXT,
    final_potential_consequence TEXT,
    final_life_saving_rules TEXT, -- JSON string
    final_actual_injury TEXT,
    hse_comments TEXT,
    review_status TEXT NOT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 4. Corrective Actions
CREATE TABLE IF NOT EXISTS corrective_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    action_plan TEXT NOT NULL,
    responsible_department TEXT NOT NULL,
    assigned_to TEXT,
    priority TEXT NOT NULL,
    target_date TEXT NOT NULL,
    status TEXT NOT NULL,
    completion_notes TEXT,
    completed_at TIMESTAMP WITH TIME ZONE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 5. Users (Authentication Demo)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

-- Insert Demo User 
INSERT INTO users (user_id, password_hash, role) 
VALUES ('HSE001', 'HSE@1234', 'HSE Officer') ON CONFLICT DO NOTHING;

-- Migration 001: Create batch-level ingestion tracking
-- Safe to apply when analytics.batch_runs already exists.

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.batch_runs (
    batch_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pipeline_name VARCHAR(100) NOT NULL,
    run_type VARCHAR(30) NOT NULL,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status VARCHAR(30) NOT NULL DEFAULT 'running',

    expected_jobs INTEGER NOT NULL,
    successful_jobs INTEGER NOT NULL DEFAULT 0,
    failed_jobs INTEGER NOT NULL DEFAULT 0,
    skipped_jobs INTEGER NOT NULL DEFAULT 0,

    error_message TEXT,

    CONSTRAINT batch_runs_counts_check CHECK (
        expected_jobs >= 0
        AND successful_jobs >= 0
        AND failed_jobs >= 0
        AND skipped_jobs >= 0
    ),

    CONSTRAINT batch_runs_status_check CHECK (
        status IN (
            'running',
            'success',
            'partial_failure',
            'failed'
        )
    )
);

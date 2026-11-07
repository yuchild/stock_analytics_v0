"""Track batch-level ingestion executions."""

from sqlalchemy import text

from stock_analytics.db.connection import engine


def start_batch(
    pipeline_name: str,
    run_type: str,
    expected_jobs: int,
) -> int:
    """Create a batch execution and return its ID."""

    query = text("""
        INSERT INTO analytics.batch_runs (
            pipeline_name,
            run_type,
            expected_jobs
        )
        VALUES (
            :pipeline_name,
            :run_type,
            :expected_jobs
        )
        RETURNING batch_run_id
    """)

    with engine.begin() as connection:
        return connection.execute(
            query,
            {
                "pipeline_name": pipeline_name,
                "run_type": run_type,
                "expected_jobs": expected_jobs,
            },
        ).scalar_one()


def finish_batch(
    batch_run_id: int,
    status: str,
    successful_jobs: int,
    failed_jobs: int,
    skipped_jobs: int,
    error_message: str | None = None,
) -> None:
    """Finalize an existing batch execution."""

    query = text("""
        UPDATE analytics.batch_runs
        SET
            finished_at = NOW(),
            status = :status,
            successful_jobs = :successful_jobs,
            failed_jobs = :failed_jobs,
            skipped_jobs = :skipped_jobs,
            error_message = :error_message
        WHERE batch_run_id = :batch_run_id
          AND status = 'running'
        RETURNING batch_run_id
    """)

    with engine.begin() as connection:
        updated = connection.execute(
            query,
            {
                "batch_run_id": batch_run_id,
                "status": status,
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "skipped_jobs": skipped_jobs,
                "error_message": error_message,
            },
        ).scalar_one_or_none()

    if updated is None:
        raise ValueError(
            f"Batch {batch_run_id} does not exist or is already finished"
        )

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from check_pipeline_health import check_pipeline

from unittest.mock import patch as mock_patch

SESSION = date(2026, 11, 9)


def test_case(name, batch, missing, expected):
    ingestion = {
        "total_jobs": 220,
        "distinct_symbols": 220,
        "successful_jobs": 220,
        "failed_jobs": 0,
    }

    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(mappings=lambda: MagicMock(one_or_none=lambda: batch)),
        MagicMock(mappings=lambda: MagicMock(one=lambda: ingestion)),
    ]

    context = MagicMock()
    context.__enter__.return_value = connection

    with (
        patch("check_pipeline_health.engine.connect", return_value=context),
        patch("check_pipeline_health.check_completeness", return_value=missing),
    ):
        result = check_pipeline(SESSION)

    assert result == expected, (
        f"{name}: expected {expected}, got {result}"
    )
    print(f"PASS: {name}")


def batch(status="success", count=1, successful=220):
    return {
        "batch_run_id": 100,
        "batch_count": count,
        "status": status,
        "expected_jobs": 220,
        "successful_jobs": successful,
        "failed_jobs": 0,
        "skipped_jobs": 0,
        "finished_at": datetime.now() if status != "running" else None,
    }


test_case("successful batch", batch(), [], 0)
test_case("missing scheduled batch", None, [], 1)
test_case("duplicate batches", batch(count=2), [], 1)
test_case("unfinished batch", batch(status="running"), [], 1)
test_case("failed batch", batch(status="failed", successful=0), [], 1)
test_case("missing price data", batch(), ["AAPL"], 2)


def test_simulated_failed_job():
    ingestion = {
        "total_jobs": 220,
        "distinct_symbols": 220,
        "successful_jobs": 220,
        "failed_jobs": 0,
    }

    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(mappings=lambda: MagicMock(
            one_or_none=lambda: batch()
        )),
        MagicMock(mappings=lambda: MagicMock(
            one=lambda: ingestion
        )),
    ]

    context = MagicMock()
    context.__enter__.return_value = connection

    with (
        mock_patch(
            "check_pipeline_health.engine.connect",
            return_value=context,
        ),
        mock_patch(
            "check_pipeline_health.check_completeness",
            return_value=[],
        ),
    ):
        result = check_pipeline(
            SESSION,
            simulate_failed_job=True,
        )

    assert result == 1, f"Expected DEGRADED (1), got {result}"
    print("PASS: simulated failed job")


test_simulated_failed_job()
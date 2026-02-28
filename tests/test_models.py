from __future__ import annotations

from missionctl.models import (
    ApiResponse,
    ClaimData,
    ConcurrencyData,
    Project,
    Task,
    TaskRun,
)


def test_parse_claim_with_task_and_run() -> None:
    payload = {
        "ok": True,
        "data": {
            "task": {"id": "t1", "status": "in_progress", "attempt_count": 1},
            "task_run": {"id": "r1", "task_id": "t1", "agent_id": "a1", "attempt": 1},
        },
    }
    parsed = ApiResponse[ClaimData].model_validate(payload)
    assert parsed.ok is True
    assert parsed.data is not None
    assert parsed.data.task.id == "t1"
    assert parsed.data.task_run.id == "r1"


def test_parse_claim_with_null_data() -> None:
    payload = {"ok": True, "data": None}
    parsed = ApiResponse[ClaimData].model_validate(payload)
    assert parsed.ok is True
    assert parsed.data is None


def test_parse_concurrency_response() -> None:
    payload = {"ok": True, "data": {"max": 1, "running": 0}}
    parsed = ApiResponse[ConcurrencyData].model_validate(payload)
    assert parsed.data is not None
    assert parsed.data.max == 1
    assert parsed.data.running == 0


def test_parse_task_response() -> None:
    payload = {"ok": True, "data": {"id": "t1", "status": "queued", "priority": "high"}}
    parsed = ApiResponse[Task].model_validate(payload)
    assert parsed.data is not None
    assert parsed.data.id == "t1"
    assert parsed.data.status == "queued"


def test_parse_task_run_response() -> None:
    payload = {
        "ok": True,
        "data": {"id": "r1", "task_id": "t1", "agent_id": "a1", "attempt": 1, "outcome": "success"},
    }
    parsed = ApiResponse[TaskRun].model_validate(payload)
    assert parsed.data is not None
    assert parsed.data.id == "r1"
    assert parsed.data.outcome == "success"


def test_parse_project_response() -> None:
    payload = {"ok": True, "data": {"id": "p1", "name": "Q3", "status": "active"}}
    parsed = ApiResponse[Project].model_validate(payload)
    assert parsed.data is not None
    assert parsed.data.id == "p1"
    assert parsed.data.name == "Q3"


def test_parse_error_response_with_reason() -> None:
    payload = {"ok": False, "reason": "at_concurrency_limit", "data": None}
    parsed = ApiResponse[ClaimData].model_validate(payload)
    assert parsed.ok is False
    assert parsed.reason == "at_concurrency_limit"

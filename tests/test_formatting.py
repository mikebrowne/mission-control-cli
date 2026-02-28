from __future__ import annotations

import json

from missionctl.formatting import (
    format_json,
    format_text_claim,
    format_text_concurrency,
    format_text_detail,
    format_text_list,
)


def test_format_json_outputs_valid_json() -> None:
    payload = {"ok": True, "data": {"id": "x"}}
    out = format_json(payload)
    parsed = json.loads(out)
    assert parsed["ok"] is True
    assert parsed["data"]["id"] == "x"


def test_format_text_claim() -> None:
    payload = {
        "task": {"id": "t1", "attempt_count": 1, "title": "Do thing", "queue": "ops", "priority": "high"},
        "task_run": {"id": "r1"},
    }
    out = format_text_claim(payload)
    assert "Claimed task t1 (attempt 1)" in out
    assert "Run ID: r1" in out
    assert "Title: Do thing" in out
    assert "Queue: ops" in out
    assert "Priority: high" in out


def test_format_text_concurrency() -> None:
    out = format_text_concurrency({"max": 2, "running": 1})
    assert out == "Running: 1 / 2"


def test_format_text_list() -> None:
    out = format_text_list([{"id": "t1", "status": "queued"}], ["id", "status"])
    assert "id=t1" in out
    assert "status=queued" in out


def test_format_text_detail() -> None:
    out = format_text_detail({"id": "t1", "status": "queued"}, ["id", "status"])
    assert "id=t1" in out
    assert "status=queued" in out


def test_format_handles_nulls() -> None:
    assert format_text_claim(None) == "No eligible tasks"
    assert format_text_list([], ["id"]) == "No results"

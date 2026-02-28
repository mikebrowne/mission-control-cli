from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_run_update_body_and_tokens(env_vars: None, runner: CliRunner) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/task-runs/r1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "r1", "outcome": "success"}})
    )
    result = runner.invoke(
        app,
        [
            "task-run",
            "update",
            "--id",
            "r1",
            "--outcome",
            "success",
            "--completed-at",
            "2026-02-27T10:15:00Z",
            "--input-tokens",
            "5000",
            "--output-tokens",
            "2000",
            "--total-tokens",
            "7000",
        ],
    )
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["outcome"] == "success"
    assert sent["completed_at"] == "2026-02-27T10:15:00Z"
    assert sent["token_usage"]["input_tokens"] == 5000
    assert sent["token_usage"]["total_tokens"] == 7000


@respx.mock
def test_task_run_update_sends_null_token_usage_when_not_provided(
    env_vars: None, runner: CliRunner
) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/task-runs/r1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "r1"}})
    )
    result = runner.invoke(app, ["task-run", "update", "--id", "r1"])
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["token_usage"] is None
    assert sent["completed_at"].endswith("Z")


@respx.mock
def test_task_run_create_defaults_started_at(env_vars: None, runner: CliRunner) -> None:
    route = respx.post("https://www.mbrowne.ca/api/mission-control/task-runs").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "r1"}})
    )
    result = runner.invoke(
        app,
        ["task-run", "create", "--task-id", "t1", "--agent-id", "a1", "--attempt", "1"],
    )
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["task_id"] == "t1"
    assert sent["agent_id"] == "a1"
    assert sent["attempt"] == 1
    assert sent["started_at"].endswith("Z")


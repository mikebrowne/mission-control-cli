from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_claim_claimed(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "task": {"id": "t1", "attempt_count": 1, "title": "Do thing", "queue": "ops", "priority": "high"},
                    "task_run": {"id": "r1"},
                },
            },
        )
    )
    result = runner.invoke(app, ["task", "claim", "--agent-id", "a1"])
    assert result.exit_code == 0
    assert "Claimed task t1" in result.stdout
    assert "Run ID: r1" in result.stdout


@respx.mock
def test_task_claim_no_eligible_tasks(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": None})
    )
    result = runner.invoke(app, ["task", "claim", "--agent-id", "a1"])
    assert result.exit_code == 0
    assert "No eligible tasks" in result.stdout


@respx.mock
def test_task_claim_concurrency_limit(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
        return_value=httpx.Response(
            409,
            json={
                "ok": False,
                "reason": "at_concurrency_limit",
                "data": None,
                "concurrency": {"max": 1, "running": 1},
            },
        )
    )
    result = runner.invoke(app, ["task", "claim", "--agent-id", "a1"])
    assert result.exit_code == 0
    assert "At concurrency limit: 1 / 1" in result.stdout


@respx.mock
def test_task_claim_json_outcomes(env_vars: None, runner: CliRunner) -> None:
    route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
        side_effect=[
            httpx.Response(200, json={"ok": True, "data": None}),
            httpx.Response(
                409,
                json={"ok": False, "reason": "at_concurrency_limit", "data": None, "concurrency": {"max": 1, "running": 1}},
            ),
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "data": {"task": {"id": "t1", "status": "in_progress"}, "task_run": {"id": "r1", "task_id": "t1", "attempt": 1}},
                },
            ),
        ]
    )

    first = runner.invoke(app, ["task", "claim", "--agent-id", "a1", "--format", "json"])
    second = runner.invoke(app, ["task", "claim", "--agent-id", "a1", "--format", "json"])
    third = runner.invoke(app, ["task", "claim", "--agent-id", "a1", "--format", "json"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert third.exit_code == 0
    assert json.loads(first.stdout)["data"] is None
    assert json.loads(second.stdout)["reason"] == "at_concurrency_limit"
    assert json.loads(third.stdout)["data"]["task_run"]["id"] == "r1"
    assert route.call_count == 3


def test_task_claim_requires_agent_id(runner: CliRunner) -> None:
    result = runner.invoke(app, ["task", "claim"])
    assert result.exit_code == 2


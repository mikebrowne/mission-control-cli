from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_update_happy_path_done(env_vars: None, runner: CliRunner) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/t1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "status": "done"}})
    )
    result = runner.invoke(app, ["task", "update", "--id", "t1", "--status", "done"])
    assert result.exit_code == 0
    assert route.call_count == 1


@respx.mock
def test_task_update_blocked_requires_reason(env_vars: None, runner: CliRunner) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/t1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "status": "blocked"}})
    )
    result = runner.invoke(app, ["task", "update", "--id", "t1", "--status", "blocked"])
    assert result.exit_code == 2
    assert route.call_count == 0


@respx.mock
def test_task_update_blocked_with_reason_and_detail(env_vars: None, runner: CliRunner) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/t1").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "id": "t1",
                    "status": "blocked",
                    "blocked_reason": "needs_human_input",
                    "blocked_detail": "Need product clarification",
                },
            },
        )
    )
    result = runner.invoke(
        app,
        [
            "task",
            "update",
            "--id",
            "t1",
            "--status",
            "blocked",
            "--blocked-reason",
            "needs_human_input",
            "--blocked-detail",
            "Need product clarification",
        ],
    )
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["blocked_reason"] == "needs_human_input"
    assert sent["blocked_detail"] == "Need product clarification"


@respx.mock
def test_task_update_invalid_transition_returns_exit_1(env_vars: None, runner: CliRunner) -> None:
    respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/t1").mock(
        return_value=httpx.Response(400, json={"ok": False, "reason": "invalid_transition"})
    )
    result = runner.invoke(app, ["task", "update", "--id", "t1", "--status", "done"])
    assert result.exit_code == 1


@respx.mock
def test_task_update_json_format(env_vars: None, runner: CliRunner) -> None:
    respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/t1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "status": "done"}})
    )
    result = runner.invoke(app, ["task", "update", "--id", "t1", "--status", "done", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["status"] == "done"


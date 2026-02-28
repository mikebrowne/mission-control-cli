from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_release_happy_path(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/t1/release").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "status": "queued"}})
    )
    result = runner.invoke(app, ["task", "release", "--id", "t1", "--agent-id", "a1"])
    assert result.exit_code == 0
    assert "Released task t1" in result.stdout


@respx.mock
def test_task_release_includes_optional_reason(env_vars: None, runner: CliRunner) -> None:
    route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/t1/release").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "status": "queued"}})
    )
    result = runner.invoke(
        app,
        ["task", "release", "--id", "t1", "--agent-id", "a1", "--reason", "manual override"],
    )
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["reason"] == "manual override"


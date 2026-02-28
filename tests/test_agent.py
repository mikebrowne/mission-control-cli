from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_agent_concurrency_happy_path(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents/a1/concurrency").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"max": 2, "running": 1}})
    )
    result = runner.invoke(app, ["agent", "concurrency", "--id", "a1"])
    assert result.exit_code == 0
    assert "Running: 1 / 2" in result.stdout


@respx.mock
def test_agent_concurrency_json(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents/a1/concurrency").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"max": 2, "running": 1}})
    )
    result = runner.invoke(app, ["agent", "concurrency", "--id", "a1", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["max"] == 2


@respx.mock
def test_agent_concurrency_api_error(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents/a1/concurrency").mock(
        return_value=httpx.Response(400, json={"ok": False, "reason": "bad"})
    )
    result = runner.invoke(app, ["agent", "concurrency", "--id", "a1"])
    assert result.exit_code == 1


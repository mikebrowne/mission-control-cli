from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from missionctl.cli import app


def test_doctor_missing_env_vars_returns_exit_2(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MC_API_URL", raising=False)
    monkeypatch.delenv("MC_TELEMETRY_SECRET", raising=False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2
    assert "Missing required env var(s)" in result.stdout


@respx.mock
def test_doctor_happy_path_text(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": []})
    )
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "missionctl_version=0.1.0" in result.stdout
    assert "api_reachable=True" in result.stdout
    assert "auth_ok=True" in result.stdout


@respx.mock
def test_doctor_happy_path_json(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": []})
    )
    result = runner.invoke(app, ["doctor", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["api_reachable"] is True
    assert payload["auth_ok"] is True


@respx.mock
def test_doctor_api_unreachable(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        side_effect=httpx.ConnectError("no route")
    )
    result = runner.invoke(app, ["doctor", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["api_reachable"] is False


@respx.mock
def test_doctor_auth_rejected(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    result = runner.invoke(app, ["doctor", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["auth_ok"] is False


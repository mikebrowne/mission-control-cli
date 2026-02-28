from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_expire_leases_text(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/expire-leases").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "expired_count": 3, "data": [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}]},
        )
    )
    result = runner.invoke(app, ["task", "expire-leases"])
    assert result.exit_code == 0
    assert "Expired leases: 3" in result.stdout


@respx.mock
def test_task_expire_leases_json(env_vars: None, runner: CliRunner) -> None:
    respx.post("https://www.mbrowne.ca/api/mission-control/tasks/expire-leases").mock(
        return_value=httpx.Response(
            200,
            json={"ok": True, "expired_count": 2, "data": [{"id": "t1"}, {"id": "t2"}]},
        )
    )
    result = runner.invoke(app, ["task", "expire-leases", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["expired_count"] == 2


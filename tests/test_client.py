from __future__ import annotations

import os

import httpx
import pytest
import respx

from missionctl.client import ApiRequestError, LocalConfigError, MCClient


def test_from_env_requires_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MC_API_URL", raising=False)
    monkeypatch.setenv("MC_TELEMETRY_SECRET", "secret")
    with pytest.raises(LocalConfigError):
        MCClient.from_env()


def test_from_env_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MC_API_URL", "https://www.mbrowne.ca/api/mission-control")
    monkeypatch.delenv("MC_TELEMETRY_SECRET", raising=False)
    with pytest.raises(LocalConfigError):
        MCClient.from_env()


@respx.mock
def test_injects_secret_header(env_vars: None) -> None:
    route = respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": []})
    )
    client = MCClient.from_env()
    status, payload = client.get_json("/agents")
    assert status == 200
    assert payload["ok"] is True
    assert route.called
    assert route.calls[0].request.headers["X-MC-Secret"] == "test-secret"


@respx.mock
def test_constructs_full_url(env_vars: None) -> None:
    route = respx.get("https://www.mbrowne.ca/api/mission-control/settings").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {}})
    )
    client = MCClient.from_env()
    status, _ = client.get_json("settings")
    assert status == 200
    assert route.called


@respx.mock
def test_network_errors_retry_up_to_three(monkeypatch: pytest.MonkeyPatch, env_vars: None) -> None:
    monkeypatch.setattr("missionctl.client.time.sleep", lambda *_: None)
    route = respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"ok": True, "data": []}),
        ]
    )
    client = MCClient.from_env()
    status, payload = client.get_json("/agents", tier1=True)
    assert status == 200
    assert payload["ok"] is True
    assert route.call_count == 3


@respx.mock
def test_5xx_retries_once(monkeypatch: pytest.MonkeyPatch, env_vars: None) -> None:
    monkeypatch.setattr("missionctl.client.time.sleep", lambda *_: None)
    route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
        side_effect=[
            httpx.Response(500, json={"ok": False, "error": "server"}),
            httpx.Response(200, json={"ok": True, "data": None}),
        ]
    )
    client = MCClient.from_env()
    status, payload = client.post_json("/tasks/claim", {"agent_id": "a"}, tier1=True)
    assert status == 200
    assert payload["ok"] is True
    assert route.call_count == 2


@respx.mock
def test_4xx_no_retry(env_vars: None) -> None:
    route = respx.patch("https://www.mbrowne.ca/api/mission-control/tasks/abc").mock(
        return_value=httpx.Response(400, json={"ok": False, "error": "bad"})
    )
    client = MCClient.from_env()
    with pytest.raises(ApiRequestError):
        client.patch_json("/tasks/abc", {"status": "done"}, tier1=True)
    assert route.call_count == 1


@respx.mock
def test_409_returned_normally(env_vars: None) -> None:
    route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/claim").mock(
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
    client = MCClient.from_env()
    status, payload = client.post_json("/tasks/claim", {"agent_id": "a"}, tier1=True)
    assert status == 409
    assert payload["reason"] == "at_concurrency_limit"
    assert route.call_count == 1


@respx.mock
def test_error_message_sanitizes_secret(env_vars: None) -> None:
    secret = os.environ["MC_TELEMETRY_SECRET"]
    route = respx.get("https://www.mbrowne.ca/api/mission-control/agents").mock(
        return_value=httpx.Response(401, text=f"bad secret {secret}")
    )
    client = MCClient.from_env()
    with pytest.raises(ApiRequestError) as exc_info:
        client.get_json("/agents")
    assert "test-secret" not in str(exc_info.value)
    assert "***" in str(exc_info.value)
    assert route.call_count == 1

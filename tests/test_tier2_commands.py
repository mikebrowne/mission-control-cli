from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from missionctl.cli import app


@respx.mock
def test_task_list_maps_filters_to_query(env_vars: None, runner: CliRunner) -> None:
    route = respx.get("https://www.mbrowne.ca/api/mission-control/tasks").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": []})
    )
    result = runner.invoke(
        app,
        [
            "task",
            "list",
            "--project-id",
            "p1",
            "--status",
            "queued",
            "--priority",
            "high",
            "--queue",
            "ops",
            "--task-type",
            "build",
            "--claimed-by",
            "a1",
        ],
    )
    assert result.exit_code == 0
    query = route.calls[0].request.url.params
    assert query["project_id"] == "p1"
    assert query["status"] == "queued"
    assert query["priority"] == "high"
    assert query["queue"] == "ops"
    assert query["task_type"] == "build"
    assert query["claimed_by"] == "a1"


@respx.mock
def test_task_create_sends_expected_body(env_vars: None, runner: CliRunner) -> None:
    route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "t1", "title": "New task"}})
    )
    result = runner.invoke(
        app,
        ["task", "create", "--title", "New task", "--queue", "ops", "--auto-dispatch", "--max-attempts", "4"],
    )
    assert result.exit_code == 0
    sent = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert sent["title"] == "New task"
    assert sent["queue"] == "ops"
    assert sent["auto_dispatch"] is True
    assert sent["max_attempts"] == 4


@respx.mock
def test_task_comment_and_link(env_vars: None, runner: CliRunner) -> None:
    comment_route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/t1/comments").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "c1", "author": "Rachel", "body": "Looks good"}})
    )
    link_route = respx.post("https://www.mbrowne.ca/api/mission-control/tasks/t1/links").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "l1", "label": "PR", "url": "https://example.com"}})
    )

    comment_result = runner.invoke(
        app, ["task", "comment", "--id", "t1", "--author", "Rachel", "--body", "Looks good"]
    )
    link_result = runner.invoke(
        app, ["task", "link", "--id", "t1", "--label", "PR", "--url", "https://example.com"]
    )
    assert comment_result.exit_code == 0
    assert link_result.exit_code == 0
    assert comment_route.call_count == 1
    assert link_route.call_count == 1


@respx.mock
def test_task_run_list_and_get(env_vars: None, runner: CliRunner) -> None:
    list_route = respx.get("https://www.mbrowne.ca/api/mission-control/task-runs").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": [{"id": "r1", "task_id": "t1", "attempt": 1}]})
    )
    get_route = respx.get("https://www.mbrowne.ca/api/mission-control/task-runs/r1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "r1", "task_id": "t1", "attempt": 1}})
    )
    list_result = runner.invoke(app, ["task-run", "list", "--task-id", "t1"])
    get_result = runner.invoke(app, ["task-run", "get", "--id", "r1"])
    assert list_result.exit_code == 0
    assert get_result.exit_code == 0
    assert list_route.calls[0].request.url.params["task_id"] == "t1"
    assert get_route.call_count == 1


@respx.mock
def test_project_crud_commands(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/projects").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": [{"id": "p1", "name": "Q3", "status": "active"}]})
    )
    respx.get("https://www.mbrowne.ca/api/mission-control/projects/p1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "p1", "name": "Q3", "status": "active"}})
    )
    create_route = respx.post("https://www.mbrowne.ca/api/mission-control/projects").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "p1", "name": "Q3"}})
    )
    update_route = respx.patch("https://www.mbrowne.ca/api/mission-control/projects/p1").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "p1", "name": "Q3 Updated"}})
    )

    assert runner.invoke(app, ["project", "list"]).exit_code == 0
    assert runner.invoke(app, ["project", "get", "--id", "p1"]).exit_code == 0
    assert runner.invoke(app, ["project", "create", "--name", "Q3"]).exit_code == 0
    assert runner.invoke(app, ["project", "update", "--id", "p1", "--name", "Q3 Updated"]).exit_code == 0

    create_sent = json.loads(create_route.calls[0].request.content.decode("utf-8"))
    update_sent = json.loads(update_route.calls[0].request.content.decode("utf-8"))
    assert create_sent["name"] == "Q3"
    assert update_sent["name"] == "Q3 Updated"


@respx.mock
def test_commentary_and_settings_commands(env_vars: None, runner: CliRunner) -> None:
    respx.get("https://www.mbrowne.ca/api/mission-control/commentary").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": []})
    )
    add_route = respx.post("https://www.mbrowne.ca/api/mission-control/commentary").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"id": "m1", "author": "Rachel", "body": "Note"}})
    )
    respx.get("https://www.mbrowne.ca/api/mission-control/settings").mock(
        return_value=httpx.Response(200, json={"ok": True, "data": {"timezone": "UTC", "theme": "dark"}})
    )
    assert runner.invoke(app, ["commentary", "list"]).exit_code == 0
    assert runner.invoke(app, ["commentary", "add", "--author", "Rachel", "--body", "Note"]).exit_code == 0
    assert runner.invoke(app, ["settings", "get"]).exit_code == 0
    sent = json.loads(add_route.calls[0].request.content.decode("utf-8"))
    assert sent["author"] == "Rachel"
    assert sent["body"] == "Note"


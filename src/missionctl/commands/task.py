from __future__ import annotations

from urllib.parse import urlencode

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_claim, format_text_detail, format_text_list

app = typer.Typer(no_args_is_help=True)


@app.command("claim")
def claim(
    agent_id: str = typer.Option(..., "--agent-id"),
    queue: str | None = typer.Option(None, "--queue"),
    lease_seconds: int | None = typer.Option(None, "--lease-seconds"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body: dict[str, object] = {"agent_id": agent_id}
    if queue is not None:
        body["queue"] = queue
    if lease_seconds is not None:
        body["lease_duration_seconds"] = lease_seconds

    try:
        status, payload = MCClient.from_env().post_json("/tasks/claim", body, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    if status == 409 or payload.get("reason") == "at_concurrency_limit":
        concurrency = payload.get("concurrency") or {}
        running = concurrency.get("running", 0)
        max_running = concurrency.get("max", 0)
        typer.echo(f"At concurrency limit: {running} / {max_running}")
        return

    typer.echo(format_text_claim(payload.get("data")))


@app.command("update")
def update(
    id: str = typer.Option(..., "--id"),
    status: str = typer.Option(..., "--status"),
    blocked_reason: str | None = typer.Option(None, "--blocked-reason"),
    blocked_detail: str | None = typer.Option(None, "--blocked-detail"),
    next_check_at: str | None = typer.Option(None, "--next-check-at"),
    error_message: str | None = typer.Option(None, "--error-message"),
    escalation_level: int | None = typer.Option(None, "--escalation-level"),
    output_ref: str | None = typer.Option(None, "--output-ref"),
    openclaw_session_key: str | None = typer.Option(None, "--openclaw-session-key"),
    openclaw_run_id: str | None = typer.Option(None, "--openclaw-run-id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")
    if status == "blocked" and not blocked_reason:
        fail_local("--blocked-reason is required when --status blocked")

    body: dict[str, object] = {"status": status}
    if blocked_reason is not None:
        body["blocked_reason"] = blocked_reason
    if blocked_detail is not None:
        body["blocked_detail"] = blocked_detail
    if next_check_at is not None:
        body["next_check_at"] = next_check_at
    if error_message is not None:
        body["error_message"] = error_message
    if escalation_level is not None:
        body["escalation_level"] = escalation_level
    if output_ref is not None:
        body["output_ref"] = output_ref
    if openclaw_session_key is not None:
        body["openclaw_session_key"] = openclaw_session_key
    if openclaw_run_id is not None:
        body["openclaw_run_id"] = openclaw_run_id

    try:
        _, payload = MCClient.from_env().patch_json(f"/tasks/{id}", body, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    if not data:
        typer.echo(f"Updated task {id} status={status}")
        return
    typer.echo(format_text_detail(data, ["id", "status", "blocked_reason", "blocked_detail"]))


@app.command("release")
def release(
    id: str = typer.Option(..., "--id"),
    agent_id: str = typer.Option(..., "--agent-id"),
    reason: str | None = typer.Option(None, "--reason"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body: dict[str, object] = {"agent_id": agent_id}
    if reason is not None:
        body["reason"] = reason

    try:
        _, payload = MCClient.from_env().post_json(f"/tasks/{id}/release", body, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
    else:
        typer.echo(f"Released task {id}")


@app.command("expire-leases")
def expire_leases(
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().post_json("/tasks/expire-leases", {}, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    expired_count = payload.get("expired_count", 0)
    typer.echo(f"Expired leases: {expired_count}")


@app.command("list")
def list_tasks(
    project_id: str | None = typer.Option(None, "--project-id"),
    status: str | None = typer.Option(None, "--status"),
    priority: str | None = typer.Option(None, "--priority"),
    queue: str | None = typer.Option(None, "--queue"),
    task_type: str | None = typer.Option(None, "--task-type"),
    claimed_by: str | None = typer.Option(None, "--claimed-by"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    query = {
        "project_id": project_id,
        "status": status,
        "priority": priority,
        "queue": queue,
        "task_type": task_type,
        "claimed_by": claimed_by,
    }
    query = {k: v for k, v in query.items() if v is not None}
    path = "/tasks"
    if query:
        path = f"/tasks?{urlencode(query)}"

    try:
        _, payload = MCClient.from_env().get_json(path)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "status", "priority", "queue"]))


@app.command("get")
def get_task(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json(f"/tasks/{id}")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "title", "status", "priority", "queue", "task_type"]))


@app.command("create")
def create_task(
    title: str = typer.Option(..., "--title"),
    project_id: str | None = typer.Option(None, "--project-id"),
    description: str | None = typer.Option(None, "--description"),
    status: str | None = typer.Option(None, "--status"),
    priority: str | None = typer.Option(None, "--priority"),
    assigned_agent_id: str | None = typer.Option(None, "--assigned-agent-id"),
    due_date: str | None = typer.Option(None, "--due-date"),
    queue: str | None = typer.Option(None, "--queue"),
    task_type: str | None = typer.Option(None, "--task-type"),
    auto_dispatch: bool = typer.Option(False, "--auto-dispatch"),
    max_attempts: int | None = typer.Option(None, "--max-attempts"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body: dict[str, object] = {"title": title}
    if project_id is not None:
        body["project_id"] = project_id
    if description is not None:
        body["description"] = description
    if status is not None:
        body["status"] = status
    if priority is not None:
        body["priority"] = priority
    if assigned_agent_id is not None:
        body["assigned_agent_id"] = assigned_agent_id
    if due_date is not None:
        body["due_date"] = due_date
    if queue is not None:
        body["queue"] = queue
    if task_type is not None:
        body["task_type"] = task_type
    if auto_dispatch:
        body["auto_dispatch"] = True
    if max_attempts is not None:
        body["max_attempts"] = max_attempts

    try:
        _, payload = MCClient.from_env().post_json("/tasks", body)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "title", "status", "priority"]))


@app.command("comments")
def list_comments(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json(f"/tasks/{id}/comments")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "author", "body", "created_at"]))


@app.command("comment")
def add_comment(
    id: str = typer.Option(..., "--id"),
    author: str = typer.Option(..., "--author"),
    body: str = typer.Option(..., "--body"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().post_json(
            f"/tasks/{id}/comments",
            {"author": author, "body": body},
        )
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "author", "body"]))


@app.command("links")
def list_links(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json(f"/tasks/{id}/links")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "label", "url", "created_at"]))


@app.command("link")
def add_link(
    id: str = typer.Option(..., "--id"),
    label: str = typer.Option(..., "--label"),
    url: str = typer.Option(..., "--url"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().post_json(
            f"/tasks/{id}/links",
            {"label": label, "url": url},
        )
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "label", "url"]))

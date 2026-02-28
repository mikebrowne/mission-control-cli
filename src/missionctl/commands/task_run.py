from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlencode

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_detail, format_text_list

app = typer.Typer(no_args_is_help=True)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@app.command("create")
def create(
    task_id: str = typer.Option(..., "--task-id"),
    agent_id: str = typer.Option(..., "--agent-id"),
    attempt: int = typer.Option(..., "--attempt"),
    started_at: str | None = typer.Option(None, "--started-at"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body = {
        "task_id": task_id,
        "agent_id": agent_id,
        "attempt": attempt,
        "started_at": started_at or _utc_now_iso(),
    }

    try:
        _, payload = MCClient.from_env().post_json("/task-runs", body, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "task_id", "agent_id", "attempt", "started_at"]))


@app.command("update")
def update(
    id: str = typer.Option(..., "--id"),
    outcome: str | None = typer.Option(None, "--outcome"),
    completed_at: str | None = typer.Option(None, "--completed-at"),
    duration_ms: int | None = typer.Option(None, "--duration-ms"),
    error_message: str | None = typer.Option(None, "--error-message"),
    logs_url: str | None = typer.Option(None, "--logs-url"),
    input_tokens: int | None = typer.Option(None, "--input-tokens"),
    output_tokens: int | None = typer.Option(None, "--output-tokens"),
    total_tokens: int | None = typer.Option(None, "--total-tokens"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    token_usage: dict[str, int] | None = None
    if input_tokens is not None or output_tokens is not None or total_tokens is not None:
        token_usage = {}
        if input_tokens is not None:
            token_usage["input_tokens"] = input_tokens
        if output_tokens is not None:
            token_usage["output_tokens"] = output_tokens
        if total_tokens is not None:
            token_usage["total_tokens"] = total_tokens

    body: dict[str, object | None] = {
        "completed_at": completed_at or _utc_now_iso(),
        "token_usage": token_usage,
    }
    if outcome is not None:
        body["outcome"] = outcome
    if duration_ms is not None:
        body["duration_ms"] = duration_ms
    if error_message is not None:
        body["error_message"] = error_message
    if logs_url is not None:
        body["logs_url"] = logs_url

    try:
        _, payload = MCClient.from_env().patch_json(f"/task-runs/{id}", body, tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "task_id", "outcome", "completed_at"]))


@app.command("list")
def list_runs(
    task_id: str | None = typer.Option(None, "--task-id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    path = "/task-runs"
    if task_id is not None:
        path = f"/task-runs?{urlencode({'task_id': task_id})}"

    try:
        _, payload = MCClient.from_env().get_json(path)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "task_id", "agent_id", "attempt", "outcome"]))


@app.command("get")
def get_run(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json(f"/task-runs/{id}")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(
        format_text_detail(
            data,
            ["id", "task_id", "agent_id", "attempt", "outcome", "started_at", "completed_at"],
        )
    )

from __future__ import annotations

from urllib.parse import urlencode

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_detail, format_text_list

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_projects(
    status: str | None = typer.Option(None, "--status"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    path = "/projects"
    if status is not None:
        path = f"/projects?{urlencode({'status': status})}"

    try:
        _, payload = MCClient.from_env().get_json(path)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "name", "status"]))


@app.command("get")
def get_project(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json(f"/projects/{id}")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "name", "status", "description"]))


@app.command("create")
def create_project(
    name: str = typer.Option(..., "--name"),
    description: str | None = typer.Option(None, "--description"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body: dict[str, object] = {"name": name}
    if description is not None:
        body["description"] = description

    try:
        _, payload = MCClient.from_env().post_json("/projects", body)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "name", "status"]))


@app.command("update")
def update_project(
    id: str = typer.Option(..., "--id"),
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    status: str | None = typer.Option(None, "--status"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    body: dict[str, object] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if status is not None:
        body["status"] = status

    if not body:
        fail_local("At least one of --name, --description, or --status is required")

    try:
        _, payload = MCClient.from_env().patch_json(f"/projects/{id}", body)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "name", "status", "description"]))

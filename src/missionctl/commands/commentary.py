from __future__ import annotations

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_detail, format_text_list

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_commentary(
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json("/commentary")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    items = payload.get("data") or []
    typer.echo(format_text_list(items, ["id", "author", "body", "created_at"]))


@app.command("add")
def add_commentary(
    author: str = typer.Option(..., "--author"),
    body: str = typer.Option(..., "--body"),
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().post_json("/commentary", {"author": author, "body": body})
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_detail(data, ["id", "author", "body", "created_at"]))

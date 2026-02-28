from __future__ import annotations

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_detail

app = typer.Typer(no_args_is_help=True)


@app.command("get")
def get_settings(
    format: str = typer.Option("text"),
) -> None:
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    try:
        _, payload = MCClient.from_env().get_json("/settings")
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    fields = list(data.keys()) if isinstance(data, dict) else []
    if not fields:
        typer.echo("No settings")
        return
    typer.echo(format_text_detail(data, fields))

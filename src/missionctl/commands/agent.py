from __future__ import annotations

import typer

from missionctl.client import MCClient
from missionctl.commands.common import fail_local, handle_client_error
from missionctl.formatting import format_json, format_text_concurrency

app = typer.Typer(no_args_is_help=True)


@app.command("concurrency")
def concurrency(
    id: str = typer.Option(..., "--id"),
    format: str = typer.Option("text"),
) -> None:
    """Check runtime concurrency for an agent."""
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")
    try:
        client = MCClient.from_env()
        _, payload = client.get_json(f"/agents/{id}/concurrency", tier1=True)
    except Exception as exc:
        handle_client_error(exc)
        return

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    data = payload.get("data") or {}
    typer.echo(format_text_concurrency(data))

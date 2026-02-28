from __future__ import annotations

import json
from typing import Any

import typer

from missionctl.client import ApiRequestError, LocalConfigError
from missionctl.formatting import format_json


def emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(format_json(payload))
    else:
        typer.echo(json.dumps(payload, ensure_ascii=True))


def fail_local(message: str) -> None:
    typer.echo(message)
    raise typer.Exit(code=2)


def fail_api(message: str) -> None:
    typer.echo(message)
    raise typer.Exit(code=1)


def handle_client_error(exc: Exception) -> None:
    if isinstance(exc, LocalConfigError):
        fail_local(str(exc))
    if isinstance(exc, ApiRequestError):
        fail_api(str(exc))
    fail_api(str(exc))

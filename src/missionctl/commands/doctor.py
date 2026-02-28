from __future__ import annotations

import importlib.util
import os
import platform

import typer

from missionctl import __version__
from missionctl.client import MCClient
from missionctl.commands.common import fail_local
from missionctl.formatting import format_json

app = typer.Typer(invoke_without_command=True, no_args_is_help=False)


@app.callback()
def doctor(
    format: str = typer.Option("text"),
) -> None:
    """Report local dependency and environment readiness."""
    output_format = format.lower()
    if output_format not in {"text", "json"}:
        fail_local("--format must be text or json")

    api_url = os.environ.get("MC_API_URL")
    secret = os.environ.get("MC_TELEMETRY_SECRET")
    if not api_url or not secret:
        missing = []
        if not api_url:
            missing.append("MC_API_URL")
        if not secret:
            missing.append("MC_TELEMETRY_SECRET")
        fail_local(f"Missing required env var(s): {', '.join(missing)}")

    payload: dict[str, object] = {}
    payload["missionctl_version"] = __version__
    payload["python_version"] = platform.python_version()
    payload["python_ok"] = tuple(map(int, platform.python_version_tuple()[:2])) >= (3, 11)

    for pkg in ("pydantic", "typer", "httpx"):
        payload[f"{pkg}_installed"] = importlib.util.find_spec(pkg) is not None

    payload["mc_api_url"] = api_url
    payload["mc_telemetry_secret_present"] = bool(secret)

    api_reachable = False
    auth_ok = False
    try:
        client = MCClient.from_env()
        status, _ = client.get_json("/agents")
        api_reachable = True
        auth_ok = status != 401
    except Exception as exc:
        message = str(exc)
        api_reachable = False
        auth_ok = "401" not in message

    payload["api_reachable"] = api_reachable
    payload["auth_ok"] = auth_ok

    if output_format == "json":
        typer.echo(format_json(payload))
        return

    lines = [
        f"missionctl_version={payload['missionctl_version']}",
        f"python_version={payload['python_version']} ok={payload['python_ok']}",
        f"pydantic={'installed' if payload['pydantic_installed'] else 'missing'}",
        f"typer={'installed' if payload['typer_installed'] else 'missing'}",
        f"httpx={'installed' if payload['httpx_installed'] else 'missing'}",
        f"MC_API_URL={payload['mc_api_url']}",
        f"MC_TELEMETRY_SECRET={'present' if payload['mc_telemetry_secret_present'] else 'missing'}",
        f"api_reachable={payload['api_reachable']}",
        f"auth_ok={payload['auth_ok']}",
    ]
    typer.echo("\n".join(lines))

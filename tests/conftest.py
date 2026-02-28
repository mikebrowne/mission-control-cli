from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def env_vars(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MC_API_URL", "https://www.mbrowne.ca/api/mission-control")
    monkeypatch.setenv("MC_TELEMETRY_SECRET", "test-secret")
    yield
    os.environ.pop("MC_API_URL", None)
    os.environ.pop("MC_TELEMETRY_SECRET", None)

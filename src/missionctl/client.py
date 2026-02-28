from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class LocalConfigError(RuntimeError):
    """Raised when required local configuration is missing."""


class ApiRequestError(RuntimeError):
    """Raised when an API request fails."""


class MCClient:
    def __init__(
        self,
        base_url: str,
        secret: str,
        *,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._secret = secret
        self._http = httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    @classmethod
    def from_env(cls) -> MCClient:
        base_url = os.environ.get("MC_API_URL")
        secret = os.environ.get("MC_TELEMETRY_SECRET")
        if not base_url:
            raise LocalConfigError("MC_API_URL is required")
        if not secret:
            raise LocalConfigError("MC_TELEMETRY_SECRET is required")
        return cls(base_url=base_url, secret=secret)

    def get_json(self, path: str, *, tier1: bool = False) -> tuple[int, dict[str, Any]]:
        return self._request_json("GET", path, tier1=tier1)

    def post_json(
        self, path: str, payload: dict[str, Any], *, tier1: bool = False
    ) -> tuple[int, dict[str, Any]]:
        return self._request_json("POST", path, json_payload=payload, tier1=tier1)

    def patch_json(
        self, path: str, payload: dict[str, Any], *, tier1: bool = False
    ) -> tuple[int, dict[str, Any]]:
        return self._request_json("PATCH", path, json_payload=payload, tier1=tier1)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        tier1: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        network_attempts = 4 if tier1 else 1
        server_attempts = 2 if tier1 else 1
        server_retries = 0

        for network_try in range(network_attempts):
            try:
                response = self._http.request(
                    method=method,
                    url=self._build_url(path),
                    headers={"X-MC-Secret": self._secret},
                    json=json_payload,
                )
            except httpx.RequestError as exc:
                if network_try == network_attempts - 1:
                    raise ApiRequestError(self._sanitize(f"Network error: {exc}")) from exc
                time.sleep(2**network_try)
                continue

            status = response.status_code
            payload = self._parse_json(response)

            if status == 409:
                return status, payload

            if 500 <= status <= 599 and server_retries < (server_attempts - 1):
                server_retries += 1
                time.sleep(2)
                continue

            if 400 <= status <= 499 or 500 <= status <= 599:
                raise ApiRequestError(
                    self._sanitize(f"API error {status}: {self._response_text(response)}")
                )

            return status, payload

        raise ApiRequestError("Unexpected request loop termination")

    def _build_url(self, path: str) -> str:
        clean_path = path.lstrip("/")
        return f"{self.base_url}/{clean_path}"

    def _parse_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"data": data}
        except json.JSONDecodeError:
            return {"raw_text": self._response_text(response)}

    def _response_text(self, response: httpx.Response) -> str:
        try:
            return response.text
        except Exception:
            return "<unreadable-response>"

    def _sanitize(self, message: str) -> str:
        return message.replace(self._secret, "***")

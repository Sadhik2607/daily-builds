"""Thin client for the Power BI REST API endpoints PBI-Pulse needs.

Real endpoints used (Power BI REST API, v1.0/myorg):
  GET /groups
  GET /groups/{groupId}/datasets
  GET /groups/{groupId}/datasets/{datasetId}/refreshes

Docs: https://learn.microsoft.com/rest/api/power-bi/
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .auth import TokenProvider

BASE_URL = "https://api.powerbi.com/v1.0/myorg"
MAX_RETRIES = 3
BACKOFF_SECONDS = 2


class PowerBIClient:
    def __init__(self, token_provider: TokenProvider):
        self._tokens = token_provider
        self._session = requests.Session()

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(
                    url,
                    headers={"Authorization": f"Bearer {self._tokens.get_token()}"},
                    timeout=30,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", BACKOFF_SECONDS))
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:  # pragma: no cover - network
                last_exc = exc
                time.sleep(BACKOFF_SECONDS * attempt)
        raise RuntimeError(f"GET {url} failed after {MAX_RETRIES} attempts: {last_exc}")

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._get("/groups").get("value", [])

    def list_datasets(self, workspace_id: str) -> list[dict[str, Any]]:
        return self._get(f"/groups/{workspace_id}/datasets").get("value", [])

    def list_refreshes(self, workspace_id: str, dataset_id: str, top: int = 5) -> list[dict[str, Any]]:
        data = self._get(
            f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"
        )
        return data.get("value", [])


class DemoPowerBIClient:
    """Reads the same shapes the real client returns, from bundled sample data."""

    def __init__(self, sample_dir: Path):
        self._workspaces = json.loads((sample_dir / "sample_workspaces.json").read_text())
        self._datasets = json.loads((sample_dir / "sample_datasets.json").read_text())
        self._refreshes = json.loads((sample_dir / "sample_refresh_history.json").read_text())

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._workspaces["value"]

    def list_datasets(self, workspace_id: str) -> list[dict[str, Any]]:
        return [d for d in self._datasets["value"] if d["workspaceId"] == workspace_id]

    def list_refreshes(self, workspace_id: str, dataset_id: str, top: int = 5) -> list[dict[str, Any]]:
        history = self._refreshes.get(dataset_id, [])
        return history[:top]

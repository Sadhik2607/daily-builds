"""MSAL client-credentials auth against the Power BI REST API.

Power BI's API sits behind Azure AD. Production BI pipelines authenticate as
a Service Principal (not a user) so scheduled jobs don't depend on anyone's
personal login surviving MFA/password rotation. This module wraps that flow.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import msal

AUTHORITY_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]


@dataclass
class PowerBICredentials:
    tenant_id: str
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> "PowerBICredentials":
        missing = [
            name
            for name in ("PBI_TENANT_ID", "PBI_CLIENT_ID", "PBI_CLIENT_SECRET")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. "
                "Set them or run with --demo."
            )
        return cls(
            tenant_id=os.environ["PBI_TENANT_ID"],
            client_id=os.environ["PBI_CLIENT_ID"],
            client_secret=os.environ["PBI_CLIENT_SECRET"],
        )


class TokenProvider:
    """Caches the bearer token in-process and refreshes ~5 min before expiry."""

    def __init__(self, creds: PowerBICredentials):
        self._creds = creds
        self._app = msal.ConfidentialClientApplication(
            client_id=creds.client_id,
            client_credential=creds.client_secret,
            authority=AUTHORITY_TEMPLATE.format(tenant_id=creds.tenant_id),
        )
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 300:
            return self._token

        result = self._app.acquire_token_for_client(scopes=SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to acquire Power BI token: "
                f"{result.get('error')}: {result.get('error_description')}"
            )

        self._token = result["access_token"]
        self._expires_at = time.time() + int(result.get("expires_in", 3600))
        return self._token

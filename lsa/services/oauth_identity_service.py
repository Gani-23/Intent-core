from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OAuthIdentityError(PermissionError):
    pass


@dataclass(slots=True)
class OAuthIdentity:
    user_id: str
    username: str
    role: str
    apps: tuple[str, ...]
    token_app_id: str | None = None


@dataclass(slots=True)
class OAuthIdentityService:
    validation_url: str
    timeout_seconds: float = 5.0

    def validate_access_token(self, token: str) -> OAuthIdentity:
        bearer = str(token or "").strip()
        if not bearer:
            raise OAuthIdentityError("OAuth bearer token required.")

        request = Request(
            self.validation_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {bearer}",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            status = int(getattr(error, "code", 500) or 500)
            if status in {401, 403}:
                raise OAuthIdentityError("OAuth session is invalid or does not have access.") from error
            raise OAuthIdentityError(f"OAuth validation failed with status {status}.") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise OAuthIdentityError("OAuth validation request failed.") from error

        if not bool(payload.get("success")) or not bool(payload.get("valid", True)):
            raise OAuthIdentityError(str(payload.get("message") or "OAuth session is not valid."))

        user = payload.get("user") or {}
        username = str(user.get("username") or "").strip().lower()
        role = str(user.get("role") or "user").strip().lower() or "user"
        user_id = str(user.get("id") or username).strip() or username
        apps = tuple(
            sorted(
                {
                    str(item).strip().lower()
                    for item in (payload.get("apps") or [])
                    if str(item).strip()
                }
            )
        )
        if not username:
            raise OAuthIdentityError("OAuth validation response did not include a username.")

        token_app_id = str(payload.get("tokenAppId") or "").strip().lower() or None
        return OAuthIdentity(
            user_id=user_id,
            username=username,
            role=role,
            apps=apps,
            token_app_id=token_app_id,
        )

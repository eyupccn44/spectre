import requests
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class CanaryToken:
    uuid: str
    url: str
    created_at: str
    memo: str


@dataclass
class CanaryTrigger:
    request_id: str
    ip: str
    user_agent: str
    method: str
    query: str
    headers: dict
    triggered_at: str


WEBHOOK_SITE = "https://webhook.site"


def create_token(memo: str = "loki-trap") -> CanaryToken:
    """Create a free canary token via webhook.site (no account needed)."""
    try:
        resp = requests.post(
            f"{WEBHOOK_SITE}/token",
            json={
                "default_status": 200,
                "default_content": "OK",
                "default_content_type": "text/plain",
                "timeout": 0,
                "cors": False,
                "expiry": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        token_uuid = data["uuid"]
        return CanaryToken(
            uuid=token_uuid,
            url=f"{WEBHOOK_SITE}/{token_uuid}",
            created_at=datetime.utcnow().isoformat(),
            memo=memo,
        )
    except Exception as e:
        raise RuntimeError(f"Canary token creation failed: {e}")


def get_triggers(token_uuid: str, since: Optional[str] = None) -> List[CanaryTrigger]:
    """Poll webhook.site for new triggers on a canary token."""
    try:
        params = {"sorting": "newest", "per_page": 50}
        resp = requests.get(
            f"{WEBHOOK_SITE}/token/{token_uuid}/requests",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("data", [])

        triggers = []
        for item in items:
            triggered_at = item.get("created_at", "")
            if since and triggered_at <= since:
                continue
            triggers.append(
                CanaryTrigger(
                    request_id=item.get("uuid", ""),
                    ip=item.get("ip", "unknown"),
                    user_agent=item.get("user_agent", "unknown"),
                    method=item.get("method", "GET"),
                    query=item.get("query", ""),
                    headers=item.get("headers", {}),
                    triggered_at=triggered_at,
                )
            )
        return triggers
    except Exception:
        return []


def delete_token(token_uuid: str) -> bool:
    try:
        resp = requests.delete(
            f"{WEBHOOK_SITE}/token/{token_uuid}",
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False

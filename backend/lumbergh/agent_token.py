"""Local token gating the /api/agent surface.

The token file is readable only by the local user, so only local processes can
call the agent API — secure even when the cloud tunnel proxies requests over
localhost (an IP check could not tell those apart).
"""

import hmac
import os
import secrets

from lumbergh.constants import AGENT_TOKEN_FILE


def ensure_token() -> str:
    existing = read_token()
    if existing:
        return existing
    AGENT_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(str(AGENT_TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return token


def read_token() -> str | None:
    try:
        return AGENT_TOKEN_FILE.read_text().strip() or None
    except OSError:
        return None


def verify(candidate: str | None) -> bool:
    stored = read_token()
    if not stored or not candidate:
        return False
    return hmac.compare_digest(stored, candidate)

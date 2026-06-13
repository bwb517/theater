from fastapi import Request
from slowapi import Limiter


def _client_ip(request: Request) -> str:
    """Rate-limit key that works behind a Caddy reverse proxy.

    Caddy sets X-Forwarded-For to the real client IP. Takes the first (leftmost)
    address in the comma-separated list, which is the original client. Falls back
    to request.client.host for local dev where no proxy is present.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host


limiter = Limiter(key_func=_client_ip)

import re

CRLF_PATTERN = re.compile(r"[\r\n]+")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_header_value(value: str, max_length: int = 200) -> str:
    """Prevent email/header injection via CRLF."""
    cleaned = CRLF_PATTERN.sub(" ", value)
    cleaned = CONTROL_CHARS.sub("", cleaned).strip()
    return cleaned[:max_length]


def sanitize_text_field(value: str, max_length: int = 2000) -> str:
    cleaned = CRLF_PATTERN.sub(" ", value)
    cleaned = CONTROL_CHARS.sub("", cleaned).strip()
    return cleaned[:max_length]


def get_client_ip(request, trust_proxy: bool) -> str:
    """
    Use X-Forwarded-For only behind a trusted reverse proxy (Railway, etc.).
    Otherwise attackers can bypass rate limiting by spoofing the header.
    """
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

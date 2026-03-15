"""Secret redaction for trace events.

Scans event data for values that look like secrets (API keys, tokens,
passwords, connection strings) and replaces them with [REDACTED].

Patterns detected:
  - API keys: sk-*, ghp_*, gho_*, github_pat_*, xoxb-*, xoxp-*,
    AKIA*, key-*, Bearer *, token-*
  - Passwords: any value for keys containing "password", "secret",
    "token", "key", "auth", "credential", "api_key", "apikey"
  - Connection strings: postgres://, mysql://, mongodb://, redis://
  - Base64-encoded long strings (likely tokens)
  - AWS access keys, JWT tokens

Works on nested dicts and lists. Redacts values, not keys.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Keys whose values should always be redacted (case-insensitive)
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "credential",
    "credentials",
    "private_key",
    "privatekey",
    "client_secret",
    "connection_string",
    "database_url",
    "db_url",
}

# Regex patterns that match secret-looking values
SECRET_PATTERNS = [
    # OpenAI
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    # GitHub tokens
    re.compile(r"gh[ps]_[a-zA-Z0-9]{36,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{22,}"),
    # Slack tokens
    re.compile(r"xox[bpras]-[a-zA-Z0-9\-]{10,}"),
    # AWS access keys
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # Bearer tokens
    re.compile(r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*"),
    # Connection strings
    re.compile(r"(postgres|mysql|mongodb|redis|amqp)://[^\s]+"),
    # Generic key-* and token-* prefixes
    re.compile(r"key-[a-zA-Z0-9]{16,}"),
    re.compile(r"token-[a-zA-Z0-9]{16,}"),
    # JWT tokens (three base64 segments separated by dots)
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
    # Anthropic keys
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
    # Generic long hex strings (40+ chars, likely tokens)
    re.compile(r"[0-9a-f]{40,}"),
]


def _is_sensitive_key(key: str) -> bool:
    """Check if a key name suggests its value is a secret."""
    return key.lower().strip() in SENSITIVE_KEYS


def _contains_secret(value: str) -> bool:
    """Check if a string value matches any secret pattern."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            return True
    return False


def redact_value(value: str) -> str:
    """Redact secrets from a string value.

    Replaces matched patterns with [REDACTED] inline.
    If the entire string is a secret, returns [REDACTED].
    """
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_data(data: Any, parent_key: str = "") -> Any:
    """Recursively redact secrets from event data.

    Handles dicts, lists, and string values.
    """
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(v, str) and _is_sensitive_key(k):
                result[k] = REDACTED
            else:
                result[k] = redact_data(v, parent_key=k)
        return result

    if isinstance(data, list):
        return [redact_data(item, parent_key=parent_key) for item in data]

    if isinstance(data, str):
        if _is_sensitive_key(parent_key):
            return REDACTED
        if _contains_secret(data):
            return redact_value(data)
        return data

    return data

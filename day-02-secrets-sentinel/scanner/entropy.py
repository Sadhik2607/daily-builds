"""
entropy.py — Shannon entropy analysis for detecting high-entropy strings
that look like secrets even when they don't match a known pattern.

Shannon entropy: H = -Σ p(c) * log2(p(c))
- Random 256-bit key:  ~8.0 bits/char
- UUID:                ~3.5 bits/char
- English prose:       ~4.0 bits/char
- Base64 secret:       >5.0 bits/char
"""

import math
import re
import string
from dataclasses import dataclass
from typing import List, Optional

# Threshold tuning
BASE64_CHARS     = string.ascii_letters + string.digits + "+/="
HEX_CHARS        = string.hexdigits
MIN_SECRET_LEN   = 20        # ignore very short strings
MAX_SECRET_LEN   = 512       # ignore very long strings (probably not a key)
ENTROPY_B64_MIN  = 4.5       # flag base64-looking strings above this
ENTROPY_HEX_MIN  = 3.2       # flag hex-looking strings above this
GENERIC_MIN      = 3.8       # flag generic high-entropy strings above this

# Context keywords that increase suspicion near a high-entropy string
SUSPECT_KEYWORDS = {
    "key", "secret", "token", "password", "passwd", "pwd", "auth",
    "credential", "api", "jwt", "bearer", "private", "cert", "signing",
    "encryption", "decrypt", "hash", "salt", "hmac",
}


@dataclass
class EntropyFinding:
    value: str
    entropy: float
    charset: str           # "base64", "hex", "mixed"
    line_no: int
    line: str
    context_keyword: Optional[str]


def shannon_entropy(data: str, charset: str) -> float:
    """Compute Shannon entropy of `data` restricted to `charset`."""
    filtered = [c for c in data if c in charset]
    if len(filtered) < MIN_SECRET_LEN:
        return 0.0
    freq = {}
    for c in filtered:
        freq[c] = freq.get(c, 0) + 1
    total = len(filtered)
    return -sum((count / total) * math.log2(count / total) for count in freq.values())


def _is_base64_like(s: str) -> bool:
    ratio = sum(1 for c in s if c in BASE64_CHARS) / max(len(s), 1)
    return ratio > 0.90


def _is_hex_like(s: str) -> bool:
    ratio = sum(1 for c in s if c in HEX_CHARS) / max(len(s), 1)
    return ratio > 0.92


def _context_keyword(line: str) -> Optional[str]:
    """Return the first suspect keyword found in the line, or None."""
    lower = line.lower()
    for kw in SUSPECT_KEYWORDS:
        if kw in lower:
            return kw
    return None


# Tokenize: grab quoted strings or long alphanumeric runs
_TOKEN_RE = re.compile(
    r"""(?:["'])([A-Za-z0-9+/=!@#$%^&*()_\-]{""" + str(MIN_SECRET_LEN) + r""",""" + str(MAX_SECRET_LEN) + r"""})(?:["'])|"""
    r"""([A-Za-z0-9+/=]{""" + str(MIN_SECRET_LEN) + r""",""" + str(MAX_SECRET_LEN) + r"""})"""
)


def scan_for_entropy(content: str, threshold_override: Optional[float] = None) -> List[EntropyFinding]:
    """
    Scan file content for high-entropy strings that may be secrets.

    Returns a list of EntropyFinding objects sorted by entropy descending.
    """
    findings: List[EntropyFinding] = []
    lines = content.splitlines()

    for line_no, line in enumerate(lines, start=1):
        # Skip comment lines and obvious non-code
        stripped = line.lstrip()
        if stripped.startswith(("#", "//", "*", "<!--", "--")):
            continue

        ctx_kw = _context_keyword(line)

        for match in _TOKEN_RE.finditer(line):
            candidate = match.group(1) or match.group(2)
            if not candidate:
                continue

            # Skip common non-secret patterns
            if _looks_like_uuid(candidate):
                continue
            if _looks_like_url_path(candidate):
                continue

            # Determine charset and threshold
            if _is_base64_like(candidate):
                charset = "base64"
                threshold = threshold_override or ENTROPY_B64_MIN
                ent = shannon_entropy(candidate, BASE64_CHARS)
            elif _is_hex_like(candidate):
                charset = "hex"
                threshold = threshold_override or ENTROPY_HEX_MIN
                ent = shannon_entropy(candidate, HEX_CHARS)
            else:
                charset = "mixed"
                threshold = threshold_override or GENERIC_MIN
                ent = shannon_entropy(candidate, string.printable)

            # Raise threshold if no suspicious keyword nearby
            effective_threshold = threshold if ctx_kw else threshold + 0.8

            if ent >= effective_threshold:
                findings.append(EntropyFinding(
                    value=_redact(candidate),
                    entropy=round(ent, 3),
                    charset=charset,
                    line_no=line_no,
                    line=line.rstrip(),
                    context_keyword=ctx_kw,
                ))

    return sorted(findings, key=lambda f: f.entropy, reverse=True)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_UUID_RE   = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_URL_PATH  = re.compile(r"^[a-zA-Z0-9/_\-.]{0,}$")

def _looks_like_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(s))

def _looks_like_url_path(s: str) -> bool:
    return "/" in s and len(s) < 80 and bool(_URL_PATH.match(s))

def _redact(value: str) -> str:
    """Show first 4 and last 4 chars; redact the middle for display."""
    if len(value) <= 10:
        return "****"
    return value[:4] + "*" * (len(value) - 8) + value[-4:]

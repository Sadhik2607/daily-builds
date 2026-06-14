"""
detector.py — Core scanning engine.

Orchestrates:
  1. File discovery (respects .secretsignore + binary detection)
  2. Regex pattern matching (patterns.py)
  3. Entropy analysis (entropy.py)
  4. Deduplication and severity scoring
  5. Returns a structured list of Finding objects
"""

import hashlib
import os
import re
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from .patterns import SECRET_PATTERNS, SecretPattern, SEVERITY_CRITICAL, SEVERITY_HIGH
from .entropy import scan_for_entropy, EntropyFinding

# ──────────────────────────────────────────────────────────────────────────────
# File discovery constants
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".tox",
    "venv", ".venv", "env", ".env_dir", "dist", "build", ".terraform",
    ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
}

DEFAULT_IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar", ".war",
    ".pyc", ".pyo",
    ".lock",       # package-lock.json, yarn.lock — too many false positives
}

# Extensions we always want to scan
ALWAYS_SCAN = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb", ".php", ".java",
    ".cs", ".cpp", ".c", ".h", ".rs", ".swift", ".kt",
    ".env", ".cfg", ".conf", ".config", ".ini", ".toml", ".yaml", ".yml",
    ".json", ".xml", ".tf", ".tfvars", ".hcl",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".dockerfile", ".dockercompose",
    ".properties", ".pem", ".key", ".crt", ".cer",
    ".npmrc", ".pip", ".gemspec",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB


# ──────────────────────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    """A single detected secret or high-entropy string."""
    file: str                  # relative path
    line_no: int
    line: str                  # raw line (truncated at 200 chars)
    pattern_id: str
    pattern_name: str
    severity: str
    matched_value: str         # redacted display value
    entropy: Optional[float]   # set for entropy findings
    hint: str = ""
    roles: List[str] = field(default_factory=list)
    fingerprint: str = ""      # SHA-256 of (file + line_no + pattern_id) for dedup

    def __post_init__(self):
        raw = f"{self.file}:{self.line_no}:{self.pattern_id}:{self.matched_value}"
        self.fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ScanStats:
    files_scanned: int = 0
    files_skipped: int = 0
    lines_scanned: int = 0
    findings_total: int = 0
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    elapsed_seconds: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Ignore list loader
# ──────────────────────────────────────────────────────────────────────────────

def load_ignore_patterns(root: Path) -> List[str]:
    """Load patterns from .secretsignore file at root."""
    ignore_file = root / ".secretsignore"
    patterns = []
    if ignore_file.exists():
        with open(ignore_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def _is_ignored(path: str, ignore_patterns: List[str]) -> bool:
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Binary detection
# ──────────────────────────────────────────────────────────────────────────────

def _is_binary(file_path: Path) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
        if not chunk:
            return False
        # If it decodes as UTF-8, it's text (covers emoji, unicode, box-drawing chars)
        try:
            chunk.decode("utf-8")
            return False
        except UnicodeDecodeError:
            pass
        # Fall back: if >30% null or control bytes (excl. tab/LF/CR), treat as binary
        non_text = sum(1 for b in chunk if b == 0 or (b < 9) or (13 < b < 32))
        return non_text / len(chunk) > 0.10
    except OSError:
        return True


# ──────────────────────────────────────────────────────────────────────────────
# Main scanner class
# ──────────────────────────────────────────────────────────────────────────────

class SecretDetector:
    def __init__(
        self,
        root: str,
        enable_entropy: bool = True,
        entropy_threshold: Optional[float] = None,
        severity_filter: Optional[str] = None,   # min severity to report
        patterns: Optional[List[SecretPattern]] = None,
        extra_ignore: Optional[List[str]] = None,
    ):
        self.root = Path(root).resolve()
        self.enable_entropy = enable_entropy
        self.entropy_threshold = entropy_threshold
        self.severity_filter = severity_filter
        self.patterns = patterns or SECRET_PATTERNS
        self.ignore_patterns = load_ignore_patterns(self.root)
        if extra_ignore:
            self.ignore_patterns.extend(extra_ignore)
        self._seen_fingerprints: Set[str] = set()

    # ── Public entry point ───────────────────────────────────────────────────

    def scan(self) -> tuple[List[Finding], ScanStats]:
        """Recursively scan self.root and return (findings, stats)."""
        import time
        start = time.monotonic()
        stats = ScanStats()
        all_findings: List[Finding] = []

        for file_path in self._iter_files():
            stats.files_scanned += 1
            findings = self._scan_file(file_path, stats)
            all_findings.extend(findings)

        # Sort: CRITICAL first, then HIGH, then by file+line
        severity_order = {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, "MEDIUM": 2, "LOW": 3}
        all_findings.sort(key=lambda f: (severity_order.get(f.severity, 9), f.file, f.line_no))

        # Populate stats
        stats.findings_total    = len(all_findings)
        stats.findings_critical = sum(1 for f in all_findings if f.severity == "CRITICAL")
        stats.findings_high     = sum(1 for f in all_findings if f.severity == "HIGH")
        stats.findings_medium   = sum(1 for f in all_findings if f.severity == "MEDIUM")
        stats.findings_low      = sum(1 for f in all_findings if f.severity == "LOW")
        stats.elapsed_seconds   = round(time.monotonic() - start, 2)

        return all_findings, stats

    # ── File iteration ───────────────────────────────────────────────────────

    def _iter_files(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Prune ignored/hidden directories in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in DEFAULT_IGNORE_DIRS
                and not d.startswith(".")
                and not _is_ignored(d, self.ignore_patterns)
            ]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                rel = str(fpath.relative_to(self.root))

                if _is_ignored(rel, self.ignore_patterns):
                    continue

                ext = fpath.suffix.lower()
                # Skip well-known binary/non-secret extensions
                if ext in DEFAULT_IGNORE_EXTENSIONS:
                    continue

                # Only scan if explicitly in ALWAYS_SCAN or no extension (Makefile, Dockerfile)
                if ext and ext not in ALWAYS_SCAN:
                    continue

                if fpath.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue

                if _is_binary(fpath):
                    continue

                yield fpath

    # ── Single file scan ─────────────────────────────────────────────────────

    def _scan_file(self, file_path: Path, stats: ScanStats) -> List[Finding]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            stats.files_skipped += 1
            return []

        rel = str(file_path.relative_to(self.root))
        lines = content.splitlines()
        stats.lines_scanned += len(lines)
        findings: List[Finding] = []

        # 1. Regex pattern scan
        for pattern in self.patterns:
            for match in pattern.regex.finditer(content):
                line_no = content[: match.start()].count("\n") + 1
                raw_line = lines[line_no - 1] if line_no <= len(lines) else ""
                matched = match.group(0)[:200]

                finding = Finding(
                    file=rel,
                    line_no=line_no,
                    line=raw_line[:200],
                    pattern_id=pattern.id,
                    pattern_name=pattern.name,
                    severity=pattern.severity,
                    matched_value=_redact_match(matched),
                    entropy=None,
                    hint=pattern.hint,
                    roles=pattern.roles,
                )
                if self._is_severity_eligible(finding.severity):
                    if finding.fingerprint not in self._seen_fingerprints:
                        self._seen_fingerprints.add(finding.fingerprint)
                        findings.append(finding)

        # 2. Entropy scan (if enabled)
        if self.enable_entropy:
            for ef in scan_for_entropy(content, self.entropy_threshold):
                finding = Finding(
                    file=rel,
                    line_no=ef.line_no,
                    line=ef.line[:200],
                    pattern_id="ENTROPY",
                    pattern_name=f"High Entropy ({ef.charset})",
                    severity=SEVERITY_HIGH if ef.context_keyword else "MEDIUM",
                    matched_value=ef.value,
                    entropy=ef.entropy,
                    hint=f"Near keyword: '{ef.context_keyword}'" if ef.context_keyword else "No keyword context",
                    roles=["DevSecOps"],
                )
                if self._is_severity_eligible(finding.severity):
                    if finding.fingerprint not in self._seen_fingerprints:
                        self._seen_fingerprints.add(finding.fingerprint)
                        findings.append(finding)

        return findings

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _is_severity_eligible(self, severity: str) -> bool:
        if not self.severity_filter:
            return True
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return order.get(severity, 9) <= order.get(self.severity_filter, 9)


def _redact_match(value: str) -> str:
    """Show enough chars to recognise the type without exposing the full secret."""
    if len(value) <= 8:
        return "***"
    return value[:6] + "..." + value[-4:]

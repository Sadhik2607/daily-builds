"""
Error pattern library — 40+ signatures with severity mapping.
Each pattern is matched against each log line via regex.
"""

from dataclasses import dataclass, field
from typing import List

CRITICAL = "CRITICAL"
ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"


@dataclass
class Pattern:
    id: str
    name: str
    regex: str
    severity: str
    category: str
    tags: List[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Pattern library
# ---------------------------------------------------------------------------
PATTERNS: List[Pattern] = [
    # ── Database ────────────────────────────────────────────────────────────
    Pattern(
        id="db_conn_exhausted",
        name="Database connection pool exhausted",
        regex=r"(?i)(connection\s+pool\s+exhausted|too\s+many\s+connections|max_connections\s+reached)",
        severity=CRITICAL,
        category="database",
        tags=["db", "connection"],
        description="All connections in the pool are in use; new requests will fail.",
    ),
    Pattern(
        id="db_deadlock",
        name="Database deadlock detected",
        regex=r"(?i)(deadlock\s+detected|deadlock\s+found|lock\s+wait\s+timeout|could\s+not\s+serialize)",
        severity=ERROR,
        category="database",
        tags=["db", "lock"],
    ),
    Pattern(
        id="db_query_timeout",
        name="Database query timeout",
        regex=r"(?i)(query\s+timeout|statement\s+timeout|execution\s+timeout.*(?:ms|sec|s)\b)",
        severity=ERROR,
        category="database",
        tags=["db", "timeout"],
    ),
    Pattern(
        id="db_replication_lag",
        name="Database replication lag",
        regex=r"(?i)(replication\s+lag|replica\s+behind|slave\s+lag)",
        severity=WARNING,
        category="database",
        tags=["db", "replication"],
    ),
    Pattern(
        id="db_schema_mismatch",
        name="Database schema mismatch",
        regex=r"(?i)(column\s+\S+\s+does\s+not\s+exist|relation\s+\S+\s+does\s+not\s+exist|unknown\s+column)",
        severity=ERROR,
        category="database",
        tags=["db", "schema"],
    ),

    # ── Memory ──────────────────────────────────────────────────────────────
    Pattern(
        id="oom_killer",
        name="OOM Killer invoked",
        regex=r"(?i)(oom.?kill|out\s+of\s+memory:\s+kill|killed\s+process\s+\d+.*memory)",
        severity=CRITICAL,
        category="memory",
        tags=["oom", "memory", "kernel"],
    ),
    Pattern(
        id="java_heap",
        name="Java heap space exhausted",
        regex=r"(?i)(java\.lang\.OutOfMemoryError.*[Hh]eap|GC\s+overhead\s+limit\s+exceeded)",
        severity=CRITICAL,
        category="memory",
        tags=["java", "heap", "memory"],
    ),
    Pattern(
        id="mem_high",
        name="High memory usage warning",
        regex=r"(?i)(memory\s+usage.*(?:9[0-9]|100)\s*%|available\s+memory.*(?:low|critical))",
        severity=WARNING,
        category="memory",
        tags=["memory"],
    ),

    # ── Disk / Storage ──────────────────────────────────────────────────────
    Pattern(
        id="disk_full",
        name="Disk full / no space left",
        regex=r"(?i)(no\s+space\s+left\s+on\s+device|disk\s+(?:full|space.*critical)|ENOSPC)",
        severity=CRITICAL,
        category="disk",
        tags=["disk", "storage"],
    ),
    Pattern(
        id="disk_high",
        name="Disk usage high",
        regex=r"(?i)(disk\s+usage.*(?:8[5-9]|9[0-9]|100)\s*%|filesystem.*(?:8[5-9]|9[0-9]|100)\s*%)",
        severity=WARNING,
        category="disk",
        tags=["disk"],
    ),
    Pattern(
        id="io_error",
        name="Disk I/O error",
        regex=r"(?i)(I/O\s+error|input/output\s+error|EIO|disk\s+read\s+error|disk\s+write\s+error)",
        severity=ERROR,
        category="disk",
        tags=["disk", "io"],
    ),

    # ── Network ─────────────────────────────────────────────────────────────
    Pattern(
        id="conn_refused",
        name="Connection refused",
        regex=r"(?i)(connection\s+refused|ECONNREFUSED|connect\s+ECONNREFUSED)",
        severity=ERROR,
        category="network",
        tags=["network", "connection"],
    ),
    Pattern(
        id="conn_timeout",
        name="Connection timeout",
        regex=r"(?i)(connection\s+timed?\s+out|ETIMEDOUT|connect\s+ETIMEDOUT|request\s+timeout)",
        severity=ERROR,
        category="network",
        tags=["network", "timeout"],
    ),
    Pattern(
        id="dns_failure",
        name="DNS resolution failure",
        regex=r"(?i)(dns\s+resolution\s+fail|name\s+or\s+service\s+not\s+known|ENOTFOUND|could\s+not\s+resolve\s+host)",
        severity=ERROR,
        category="network",
        tags=["network", "dns"],
    ),
    Pattern(
        id="ssl_error",
        name="SSL/TLS certificate error",
        regex=r"(?i)(ssl\s+(?:handshake|certificate|cert)\s+(?:error|fail|expired|chain|broken)|certificate\s+verify\s+fail|CERTIFICATE_VERIFY_FAILED|SSL_ERROR)",
        severity=CRITICAL,
        category="network",
        tags=["ssl", "tls", "cert", "security"],
    ),
    Pattern(
        id="http_5xx",
        name="HTTP 5xx server error",
        regex=r'(?i)(" |\s)(5[0-9]{2})(\s|")',
        severity=ERROR,
        category="http",
        tags=["http", "5xx"],
    ),
    Pattern(
        id="http_429",
        name="HTTP 429 rate limit",
        regex=r'(?i)(429\s+Too\s+Many\s+Requests|rate\s+limit\s+exceeded|throttled)',
        severity=WARNING,
        category="http",
        tags=["http", "ratelimit"],
    ),

    # ── Auth / Security ─────────────────────────────────────────────────────
    Pattern(
        id="auth_fail",
        name="Authentication failure",
        regex=r"(?i)(authentication\s+fail|auth(entication)?\s+error|invalid\s+credentials|login\s+fail|incorrect\s+password|401\s+Unauthorized)",
        severity=WARNING,
        category="security",
        tags=["auth", "security"],
    ),
    Pattern(
        id="perm_denied",
        name="Permission denied",
        regex=r"(?i)(permission\s+denied|access\s+denied|403\s+Forbidden|EACCES|not\s+authorized)",
        severity=WARNING,
        category="security",
        tags=["authz", "security"],
    ),
    Pattern(
        id="brute_force",
        name="Possible brute-force / account lockout",
        regex=r"(?i)(account\s+lock(ed)?|too\s+many\s+(?:failed\s+)?login|brute.?force)",
        severity=CRITICAL,
        category="security",
        tags=["security", "brute-force"],
    ),
    Pattern(
        id="token_expired",
        name="Token / session expired",
        regex=r"(?i)(token\s+(?:expired|invalid)|session\s+(?:expired|invalid)|jwt\s+expired|TokenExpiredError)",
        severity=INFO,
        category="security",
        tags=["auth", "session"],
    ),

    # ── Application exceptions ───────────────────────────────────────────────
    Pattern(
        id="null_pointer",
        name="Null pointer / NoneType error",
        regex=r"(?i)(NullPointerException|NoneType.*has\s+no\s+attribute|AttributeError.*NoneType|null\s+reference)",
        severity=ERROR,
        category="application",
        tags=["exception", "null"],
    ),
    Pattern(
        id="unhandled_exception",
        name="Unhandled exception",
        regex=r"(?i)(Traceback\s*\(most\s+recent\s+call\s+last\)|UnhandledException|uncaught\s+exception)",
        severity=ERROR,
        category="application",
        tags=["exception"],
    ),
    Pattern(
        id="stack_overflow",
        name="Stack overflow / recursion error",
        regex=r"(?i)(StackOverflowError|RecursionError|maximum\s+recursion\s+depth\s+exceeded|stack\s+overflow)",
        severity=ERROR,
        category="application",
        tags=["exception", "stack"],
    ),
    Pattern(
        id="segfault",
        name="Segmentation fault",
        regex=r"(?i)(segmentation\s+fault|sigsegv|core\s+dumped|signal\s+11)",
        severity=CRITICAL,
        category="application",
        tags=["crash", "segfault"],
    ),
    Pattern(
        id="panic",
        name="Panic / fatal crash",
        regex=r"(?i)(panic:?\s+\w|fatal\s+error|kernel\s+panic|SIGSEGV|SIGABRT|abort\(\))",
        severity=CRITICAL,
        category="application",
        tags=["crash", "panic"],
    ),

    # ── Service / Process ────────────────────────────────────────────────────
    Pattern(
        id="service_restart",
        name="Service restarted unexpectedly",
        regex=r"(?i)(service.*restart(ed)?|process.*restart(ed)?|supervisord.*RESTARTING|systemd.*restarting)",
        severity=WARNING,
        category="service",
        tags=["service", "restart"],
    ),
    Pattern(
        id="process_killed",
        name="Process killed / terminated",
        regex=r"(?i)(process\s+\d+\s+killed|SIGKILL|killed\s+by\s+signal|process\s+terminated)",
        severity=WARNING,
        category="service",
        tags=["process", "killed"],
    ),
    Pattern(
        id="health_check_fail",
        name="Health check failure",
        regex=r"(?i)(health\s+check\s+fail|unhealthy|readiness\s+probe\s+fail|liveness\s+probe\s+fail)",
        severity=ERROR,
        category="service",
        tags=["health", "k8s"],
    ),

    # ── Kubernetes ───────────────────────────────────────────────────────────
    Pattern(
        id="k8s_crashloop",
        name="Kubernetes CrashLoopBackOff",
        regex=r"(?i)(CrashLoopBackOff|Back-off\s+restarting\s+failed\s+container)",
        severity=CRITICAL,
        category="kubernetes",
        tags=["k8s", "pod", "crash"],
    ),
    Pattern(
        id="k8s_eviction",
        name="Kubernetes pod eviction",
        regex=r"(?i)(pod\s+evict(ed)?|eviction.*pod|The\s+node\s+was\s+low\s+on\s+resource)",
        severity=ERROR,
        category="kubernetes",
        tags=["k8s", "pod", "eviction"],
    ),
    Pattern(
        id="k8s_pending",
        name="Kubernetes pod stuck in Pending",
        regex=r"(?i)(pod.*Pending.*\d+[mh]|failed\s+to\s+schedule\s+pod)",
        severity=WARNING,
        category="kubernetes",
        tags=["k8s", "pod", "pending"],
    ),

    # ── CI/CD ────────────────────────────────────────────────────────────────
    Pattern(
        id="build_fail",
        name="Build failure",
        regex=r"(?i)(build\s+fail(ed)?|compilation\s+error|make.*Error\s+\d+|exit\s+code\s+[1-9])",
        severity=ERROR,
        category="cicd",
        tags=["ci", "build"],
    ),
    Pattern(
        id="test_fail",
        name="Test failure",
        regex=r"(?i)(test.*fail(ed)?|FAILED.*test|assertion\s+error|AssertionError|\d+\s+test.*fail)",
        severity=ERROR,
        category="cicd",
        tags=["ci", "test"],
    ),
    Pattern(
        id="deploy_fail",
        name="Deployment failure",
        regex=r"(?i)(deploy(ment)?\s+fail(ed)?|rollout.*fail|release.*fail)",
        severity=CRITICAL,
        category="cicd",
        tags=["cd", "deploy"],
    ),

    # ── Deprecation / Config ─────────────────────────────────────────────────
    Pattern(
        id="deprecated",
        name="Deprecated API or function usage",
        regex=r"(?i)(DeprecationWarning|deprecated|will\s+be\s+removed\s+in|use\s+\S+\s+instead)",
        severity=INFO,
        category="application",
        tags=["deprecation"],
    ),
    Pattern(
        id="config_missing",
        name="Configuration key missing",
        regex=r"(?i)(config.*not\s+found|missing\s+required\s+(?:config|env|setting|variable)|KeyError:)",
        severity=ERROR,
        category="config",
        tags=["config"],
    ),
    Pattern(
        id="rate_limit_self",
        name="Self-imposed rate limit exceeded",
        regex=r"(?i)(rate\s+limit\s+hit|self.?throttl|backoff\s+triggered|retry\s+after\s+\d+)",
        severity=WARNING,
        category="application",
        tags=["ratelimit"],
    ),
]


def get_by_severity(severity: str) -> List[Pattern]:
    return [p for p in PATTERNS if p.severity == severity]


def get_by_category(category: str) -> List[Pattern]:
    return [p for p in PATTERNS if p.category == category]

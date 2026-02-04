from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Iterable

import rfc8785

from ..utils import normalize_relpath, sha256_hex, utc_now_rfc3339, uuidv7


DEFAULT_POLICY_VERSION = "v1.0.0"
DEFAULT_SCHEMA_VERSION = "1.0.0"
DEFAULT_SPEC_VERSION = "v1"
DEFAULT_SIZE_LIMIT_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class DetectorRule:
    rule_id: str
    severity: str
    classification: str
    patterns: tuple[str, ...]
    flags: int = re.MULTILINE

    @cached_property
    def compiled_patterns(self) -> list[re.Pattern[str]]:
        return [re.compile(pattern, self.flags) for pattern in self.patterns]

    def compile(self) -> list[re.Pattern[str]]:
        return self.compiled_patterns


@dataclass(frozen=True)
class Detector:
    detector_id: str
    version: str
    rules: tuple[DetectorRule, ...]

    def config(self) -> dict[str, object]:
        return {
            "rules": [
                {
                    "id": rule.rule_id,
                    "severity": rule.severity,
                    "class": rule.classification,
                    "patterns": list(rule.patterns),
                }
                for rule in self.rules
            ]
        }

    def config_hash(self) -> str:
        canonical = rfc8785.dumps(self.config()).encode("utf-8")
        return sha256_hex(canonical)


@dataclass(frozen=True)
class RedactionDecision:
    path: str
    decision: str
    classification: str
    reasons: list[str]
    detector_hits: list[str]


@dataclass(frozen=True)
class RedactionFinding:
    path: str
    rule_id: str
    severity: str
    locations: list[dict[str, int]]


@dataclass
class RedactionPolicy:
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    detectors: list[Detector] = field(default_factory=list)
    policy_version: str = DEFAULT_POLICY_VERSION
    size_limit_bytes: int = DEFAULT_SIZE_LIMIT_BYTES
    include_sensitive: bool = False
    allow_forbidden: bool = False

    @classmethod
    def openclaw_default(cls) -> "RedactionPolicy":
        return cls(
            allowlist=default_allowlist(),
            denylist=default_denylist(),
            detectors=[builtin_detector()],
        )

    def scan_workspace(self, workspace_root: Path) -> dict[str, object]:
        capsule_id = str(uuidv7())
        created_at = utc_now_rfc3339()
        detector_entries = [
            {
                "id": detector.detector_id,
                "version": detector.version,
                "config_hash": detector.config_hash(),
            }
            for detector in self.detectors
        ]

        decisions: list[RedactionDecision] = []
        findings: list[RedactionFinding] = []

        for file_path in iter_workspace_files(workspace_root):
            rel_path = normalize_relpath(file_path, workspace_root)
            size_bytes = file_path.stat().st_size

            deny_reason = self._match_denylist(rel_path)
            if deny_reason:
                decisions.append(
                    RedactionDecision(
                        path=rel_path,
                        decision="include_encrypted" if self.allow_forbidden else "exclude",
                        classification="forbidden",
                        reasons=[deny_reason],
                        detector_hits=[],
                    )
                )
                continue

            if self.size_limit_bytes and size_bytes > self.size_limit_bytes:
                decisions.append(
                    RedactionDecision(
                        path=rel_path,
                        decision="include_encrypted" if self.allow_forbidden else "exclude",
                        classification="forbidden",
                        reasons=["size_limit"],
                        detector_hits=[],
                    )
                )
                continue

            if not self._match_allowlist(rel_path):
                decisions.append(
                    RedactionDecision(
                        path=rel_path,
                        decision="exclude",
                        classification="private",
                        reasons=["not_allowlisted"],
                        detector_hits=[],
                    )
                )
                continue

            detector_hits, hit_classes, file_findings = self._scan_file(file_path, rel_path)
            findings.extend(file_findings)
            classification = classify_hit_classes(hit_classes)

            decision = "include_encrypted"
            if classification == "forbidden" and not self.allow_forbidden:
                decision = "exclude"
            if classification == "sensitive" and not self.include_sensitive:
                decision = "exclude"

            reasons = ["allowlist", *detector_hits]
            decisions.append(
                RedactionDecision(
                    path=rel_path,
                    decision=decision,
                    classification=classification,
                    reasons=reasons,
                    detector_hits=detector_hits,
                )
            )

        report = {
            "spec_version": DEFAULT_SPEC_VERSION,
            "schema_version": DEFAULT_SCHEMA_VERSION,
            "policy_version": self.policy_version,
            "created_at": created_at,
            "capsule_id": capsule_id,
            "detectors": detector_entries,
            "decisions": [
                {
                    "path": decision.path,
                    "decision": decision.decision,
                    "class": decision.classification,
                    "reasons": decision.reasons,
                    "detector_hits": decision.detector_hits,
                }
                for decision in decisions
            ],
            "findings": [
                {
                    "path": finding.path,
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "locations": finding.locations,
                }
                for finding in findings
            ],
            "findings_summary": build_findings_summary(decisions, findings),
        }
        return report

    def _match_allowlist(self, rel_path: str) -> bool:
        return matches_any(rel_path, self.allowlist)

    def _match_denylist(self, rel_path: str) -> str | None:
        for pattern in self.denylist:
            if match_glob(rel_path, pattern):
                return f"denylist:{pattern}"
        return None

    def _scan_file(
        self, file_path: Path, rel_path: str
    ) -> tuple[list[str], set[str], list[RedactionFinding]]:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], set(), []

        detector_hits: list[str] = []
        hit_classes: set[str] = set()
        findings: list[RedactionFinding] = []

        for detector in self.detectors:
            for rule in detector.rules:
                locations = find_rule_locations(text, rule)
                if not locations:
                    continue
                detector_hits.append(rule.rule_id)
                hit_classes.add(rule.classification)
                findings.append(
                    RedactionFinding(
                        path=rel_path,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        locations=locations,
                    )
                )
        return detector_hits, hit_classes, findings


def iter_workspace_files(workspace_root: Path) -> Iterable[Path]:
    resolved_root = workspace_root.resolve()
    for path in sorted(workspace_root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            resolved = path.resolve()
            if resolved.is_relative_to(resolved_root):
                yield path


def matches_any(rel_path: str, patterns: Iterable[str]) -> bool:
    return any(match_glob(rel_path, pattern) for pattern in patterns)


def match_glob(rel_path: str, pattern: str) -> bool:
    return PurePosixPath(rel_path).match(pattern)


def build_findings_summary(
    decisions: list[RedactionDecision], findings: list[RedactionFinding]
) -> dict[str, object]:
    by_class = {"public": 0, "private": 0, "sensitive": 0, "forbidden": 0}
    by_decision = {
        "exclude": 0,
        "include_encrypted": 0,
        "include_redacted": 0,
        "include_plaintext": 0,
    }
    for decision in decisions:
        if decision.classification in by_class:
            by_class[decision.classification] += 1
        if decision.decision in by_decision:
            by_decision[decision.decision] += 1
    return {
        "total": len(findings),
        "by_class": by_class,
        "by_decision": by_decision,
    }


def classify_hit_classes(hit_classes: set[str]) -> str:
    if "forbidden" in hit_classes:
        return "forbidden"
    if "sensitive" in hit_classes:
        return "sensitive"
    if "private" in hit_classes:
        return "private"
    return "public"


def find_rule_locations(text: str, rule: DetectorRule) -> list[dict[str, int]]:
    locations: list[dict[str, int]] = []
    for pattern in rule.compile():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            locations.append({"line": line})
    return locations


def builtin_detector() -> Detector:
    return Detector(
        detector_id="builtin-basic",
        version="1.0.0",
        rules=(
            DetectorRule(
                rule_id="forbidden:api-key",
                severity="high",
                classification="forbidden",
                patterns=(
                    r"\bsk-[A-Za-z0-9]{16,}\b",
                    r"\bghp_[A-Za-z0-9]{20,}\b",
                    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
                    r"\bAIza[0-9A-Za-z\-_]{35}\b",
                ),
            ),
            DetectorRule(
                rule_id="forbidden:jwt",
                severity="high",
                classification="forbidden",
                patterns=(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",),
            ),
            DetectorRule(
                rule_id="forbidden:private-key-block",
                severity="high",
                classification="forbidden",
                patterns=(r"-----BEGIN [A-Z ]*PRIVATE KEY-----",),
            ),
            DetectorRule(
                rule_id="sensitive:cookie-session",
                severity="medium",
                classification="sensitive",
                patterns=(r"\"(?:session|csrf|auth|token)\"\s*:",),
            ),
        ),
    )


def default_allowlist() -> list[str]:
    return [
        "MEMORY.md",
        "memory/**/*.md",
        "memory/**/*.json",
        "memory/*.md",
        "memory/*.json",
        "SOUL.md",
        "USER.md",
        "IDENTITY.md",
        "AGENTS.md",
        "TOOLS.md",
        "HEARTBEAT.md",
        "projects/**/STATUS.md",
    ]


def default_denylist() -> list[str]:
    return [
        ".env",
        "**/.env",
        "**/*.pem",
        "**/*id_rsa*",
        "**/*private_key*",
        "**/*token*",
        "**/*secret*",
        "**/*cookies*.json",
        "**/*_cookies.json",
        "memory/moltbook.json",
        "**/Cookies",
        "**/cookies.sqlite",
        "**/cookies.db",
        "**/Login Data",
        "**/Web Data",
        "**/Local State",
        "**/Sessions/*",
        "**/Session Storage/*",
        "**/Local Storage/*",
    ]

"""Data types for compliance findings."""

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR   = "ERROR"
    WARNING = "WARNING"
    INFO    = "INFO"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    rule: str
    subject: str
    message: str
    detail: str = ""


@dataclass
class ComplianceReport:
    ontology_iri: str
    findings: list[Finding] = field(default_factory=list)
    reference_iris: list[str] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        rule: str,
        subject: str,
        message: str,
        detail: str = "",
    ) -> None:
        self.findings.append(Finding(severity, rule, subject, message, detail))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def is_compliant(self) -> bool:
        return len(self.errors) == 0

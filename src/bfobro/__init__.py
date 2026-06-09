"""BFOBRO — BFO compliance checker for OWL ontologies."""

from .checker import check_ontology
from .findings import ComplianceReport, Finding, Severity

__all__ = ["check_ontology", "ComplianceReport", "Finding", "Severity"]

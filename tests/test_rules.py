"""Unit tests for BFO compliance rules."""

import textwrap

import pytest
from rdflib import Graph

from bfobro import check_ontology, Severity
from bfobro.findings import ComplianceReport
from bfobro.rules import (
    check_disjointness_violations,
    check_unknown_bfo_iris,
    check_orphaned_classes,
    check_declared_disjoint_with,
)


def _graph_from_ttl(ttl: str) -> Graph:
    g = Graph()
    g.parse(data=textwrap.dedent(ttl), format="turtle")
    return g


PREFIXES = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix bfo: <http://purl.obolibrary.org/obo/BFO_> .
@prefix ex: <http://example.org/> .
"""


class TestDisjointnessViolations:
    def test_clean_ontology_no_findings(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:MyProcess a owl:Class ;
            rdfs:subClassOf bfo:0000015 .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_disjointness_violations(g, r)
        assert not r.errors

    def test_continuant_and_occurrent_raises_error(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:BadClass a owl:Class ;
            rdfs:subClassOf bfo:0000002 ;
            rdfs:subClassOf bfo:0000003 .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_disjointness_violations(g, r)
        assert any(
            f.rule == "disjointness-violation" and f.severity == Severity.ERROR
            for f in r.findings
        )

    def test_transitive_disjointness_detected(self):
        # ex:A -> bfo:Process (occurrent); ex:B -> ex:A AND bfo:IndependentContinuant
        g = _graph_from_ttl(PREFIXES + """
        ex:A a owl:Class ; rdfs:subClassOf bfo:0000015 .
        ex:B a owl:Class ;
            rdfs:subClassOf ex:A ;
            rdfs:subClassOf bfo:0000004 .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_disjointness_violations(g, r)
        assert r.errors


class TestUnknownBFOIRIs:
    def test_known_bfo_iri_no_warning(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:X a owl:Class ; rdfs:subClassOf bfo:0000015 .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_unknown_bfo_iris(g, r)
        unknown = [f for f in r.findings if f.rule == "unknown-bfo-iri"]
        assert not unknown

    def test_unknown_bfo_iri_warns(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:X a owl:Class ; rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_9999999> .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_unknown_bfo_iris(g, r)
        assert any(f.rule == "unknown-bfo-iri" for f in r.findings)


class TestOrphanedClasses:
    def test_bfo_rooted_class_not_orphan(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:MyObject a owl:Class ; rdfs:subClassOf bfo:0000030 .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_orphaned_classes(g, r)
        orphans = [f for f in r.findings if f.rule == "orphaned-class"]
        assert not orphans

    def test_floating_class_is_orphan(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:FloatingClass a owl:Class .
        bfo:0000015 a owl:Class .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_orphaned_classes(g, r)
        orphans = [f for f in r.findings if f.rule == "orphaned-class"]
        assert orphans


class TestDeclaredDisjointWith:
    def test_disjoint_with_superclass_is_error(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:Child a owl:Class ;
            rdfs:subClassOf ex:Parent ;
            owl:disjointWith ex:Parent .
        ex:Parent a owl:Class .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_declared_disjoint_with(g, r)
        assert any(
            f.rule == "disjoint-subclass-contradiction" and f.severity == Severity.ERROR
            for f in r.findings
        )

    def test_valid_disjoint_no_error(self):
        g = _graph_from_ttl(PREFIXES + """
        ex:Cat a owl:Class ; rdfs:subClassOf bfo:0000030 .
        ex:Dog a owl:Class ; rdfs:subClassOf bfo:0000030 ; owl:disjointWith ex:Cat .
        """)
        r = ComplianceReport(ontology_iri="test")
        check_declared_disjoint_with(g, r)
        assert not any(f.rule == "disjoint-subclass-contradiction" for f in r.findings)

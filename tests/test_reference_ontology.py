"""Tests for the --reference / middle-ontology compliance path."""

import textwrap
from pathlib import Path

import pytest
from rdflib import Graph

from bfobro import check_ontology, Severity
from bfobro.findings import ComplianceReport


PREFIXES = """\
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix bfo:  <http://purl.obolibrary.org/obo/BFO_> .
@prefix mid:  <http://example.org/middle/> .
@prefix ex:   <http://example.org/eval/> .
"""


def _write_ttl(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(PREFIXES + body), encoding="utf-8")
    return p


class TestReferenceOntologyCompliance:
    def test_eval_class_rooted_through_middle_onto(self, tmp_path):
        """Eval class extends a middle-onto class that extends BFO -> not orphaned."""
        ref = _write_ttl(tmp_path, "middle.ttl", """
        mid:PhysicalDevice a owl:Class ;
            rdfs:subClassOf bfo:0000030 .
        """)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        ex:Sensor a owl:Class ;
            rdfs:subClassOf mid:PhysicalDevice .
        """)
        report = check_ontology(eval_onto, references=[ref])
        orphans = [f for f in report.findings if f.rule == "orphaned-class"]
        assert not orphans, f"Unexpected orphan findings: {orphans}"

    def test_eval_class_not_rooted_when_middle_missing(self, tmp_path):
        """Without the reference ontology loaded, BFO alignment cannot be assessed.

        The eval file references mid:PhysicalDevice but that class has no BFO
        parent in the graph.  The checker either reports no-bfo-reference (no BFO
        IRIs at all) or orphaned-class (BFO IRIs present but chain is broken).
        Either way, ex:Sensor must not be given a clean bill of health.
        """
        # Include one real BFO IRI so the orphan rule runs (not short-circuits)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        bfo:0000001 a owl:Class .
        mid:PhysicalDevice a owl:Class .
        ex:Sensor a owl:Class ;
            rdfs:subClassOf mid:PhysicalDevice .
        """)
        report = check_ontology(eval_onto)
        # ex:Sensor's chain stops at mid:PhysicalDevice which has no BFO ancestor
        orphans = [f for f in report.findings if f.rule == "orphaned-class"]
        subjects = " ".join(f.subject + f.detail for f in orphans)
        assert "Sensor" in subjects or "PhysicalDevice" in subjects

    def test_disjointness_detected_through_reference(self, tmp_path):
        """A disjointness violation traced through two hops via the reference onto."""
        ref = _write_ttl(tmp_path, "middle.ttl", """
        mid:EventType  a owl:Class ; rdfs:subClassOf bfo:0000015 .
        mid:ThingType  a owl:Class ; rdfs:subClassOf bfo:0000030 .
        """)
        # ex:Bad is both an EventType (Occurrent) and a ThingType (IndependentContinuant)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        ex:Bad a owl:Class ;
            rdfs:subClassOf mid:EventType ;
            rdfs:subClassOf mid:ThingType .
        """)
        report = check_ontology(eval_onto, references=[ref])
        assert not report.is_compliant
        assert any(f.rule == "disjointness-violation" for f in report.errors)

    def test_reference_iri_captured_in_report(self, tmp_path):
        """The report records the IRI of the loaded reference ontology."""
        ref = _write_ttl(tmp_path, "middle.ttl", """
        <http://example.org/MiddleOnto> a owl:Ontology .
        mid:Artifact a owl:Class ; rdfs:subClassOf bfo:0000030 .
        """)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        ex:Hammer a owl:Class ; rdfs:subClassOf mid:Artifact .
        """)
        report = check_ontology(eval_onto, references=[ref])
        assert "http://example.org/MiddleOnto" in report.reference_iris

    def test_reference_classes_not_evaluated(self, tmp_path):
        """Classes that belong only to the reference onto are not flagged as orphaned."""
        ref = _write_ttl(tmp_path, "cco_stub.ttl", """
        mid:InformationEntity a owl:Class ;
            rdfs:subClassOf bfo:0000031 .
        """)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        ex:Document a owl:Class ;
            rdfs:subClassOf mid:InformationEntity .
        """)
        report = check_ontology(eval_onto, references=[ref])
        # mid:InformationEntity should NOT appear as orphaned — it's in the reference
        ref_class_findings = [
            f for f in report.findings
            if "InformationEntity" in f.subject or "InformationEntity" in f.detail
        ]
        assert not ref_class_findings

    def test_multiple_references_merged(self, tmp_path):
        """Two separate reference ontologies are both used for ancestry resolution."""
        ref1 = _write_ttl(tmp_path, "ref1.ttl", """
        mid:Agent a owl:Class ; rdfs:subClassOf bfo:0000030 .
        """)
        ref2 = _write_ttl(tmp_path, "ref2.ttl", """
        mid:Role  a owl:Class ; rdfs:subClassOf bfo:0000023 .
        """)
        eval_onto = _write_ttl(tmp_path, "eval.ttl", """
        ex:SoftwareAgent a owl:Class ; rdfs:subClassOf mid:Agent .
        ex:AdminRole      a owl:Class ; rdfs:subClassOf mid:Role .
        """)
        report = check_ontology(eval_onto, references=[ref1, ref2])
        orphans = [f for f in report.findings if f.rule == "orphaned-class"]
        assert not orphans

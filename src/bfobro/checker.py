"""Main BFO compliance checker."""

from pathlib import Path

from rdflib import Graph, OWL, RDF, RDFS
from rdflib.term import URIRef

from .findings import ComplianceReport
from .rules import ALL_RULES


def _ontology_iri(graph: Graph) -> str:
    for s in graph.subjects(RDF.type, OWL.Ontology):
        return str(s)
    return "<unknown>"


def _declared_classes(graph: Graph) -> set[URIRef]:
    """Classes explicitly declared or used as subclass subjects in *graph*."""
    classes: set[URIRef] = set()
    for s in graph.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            classes.add(s)
    for s, _, _ in graph.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef):
            classes.add(s)
    return classes


def _declared_properties(graph: Graph) -> set[URIRef]:
    """Properties explicitly declared or used as subproperty subjects in *graph*."""
    props: set[URIRef] = set()
    for ptype in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
        for s in graph.subjects(RDF.type, ptype):
            if isinstance(s, URIRef):
                props.add(s)
    for s, _, _ in graph.triples((None, RDFS.subPropertyOf, None)):
        if isinstance(s, URIRef):
            props.add(s)
    return props


def check_ontology(
    source: str | Path,
    fmt: str | None = None,
    references: list[str | Path] | None = None,
    ref_fmt: str | None = None,
) -> ComplianceReport:
    """Load *source* and run all BFO compliance rules.

    Parameters
    ----------
    source:
        File path or URL of the ontology to evaluate.
    fmt:
        RDFLib format hint for *source* (e.g. ``"turtle"``, ``"xml"``).
        Auto-detected when omitted.
    references:
        Optional list of reference ontology paths or URLs (e.g. BFO or CCO)
        to load as background knowledge.  Their class hierarchy is used for
        ancestor lookups but their classes are not themselves evaluated.
    ref_fmt:
        RDFLib format hint applied to all reference ontologies.
        Auto-detected when omitted.
    """
    # --- load reference ontologies into a background graph ---
    background = Graph()
    ref_iris: list[str] = []
    for ref in (references or []):
        background.parse(str(ref), format=ref_fmt)

    for iri in background.subjects(RDF.type, OWL.Ontology):
        ref_iris.append(str(iri))

    # --- load the evaluation ontology ---
    eval_graph = Graph()
    eval_graph.parse(str(source), format=fmt)

    ontology_iri = _ontology_iri(eval_graph)

    # Classes and properties declared in the evaluation ontology — rules are scoped to these.
    eval_classes = _declared_classes(eval_graph)
    eval_properties = _declared_properties(eval_graph)

    # --- merge into one graph for ancestry lookups ---
    merged = Graph()
    for triple in background:
        merged.add(triple)
    for triple in eval_graph:
        merged.add(triple)

    report = ComplianceReport(
        ontology_iri=ontology_iri,
        reference_iris=ref_iris,
    )

    for rule in ALL_RULES:
        rule(merged, report, eval_classes=eval_classes, eval_properties=eval_properties)

    return report

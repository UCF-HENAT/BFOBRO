"""BFO compliance rules.

Each public function receives (graph, report, eval_classes) and appends Findings.
eval_classes, when provided, limits which classes are checked to those declared
in the evaluation ontology (excluding any reference/background ontologies).
"""

from collections import deque

from rdflib import Graph, OWL, RDF, RDFS, URIRef
from rdflib.term import Node

from .bfo_terms import (
    ALL_BFO_CLASSES,
    ALL_BFO_PROPERTIES,
    BFO,
    BFO_GRAPH,
    BFO_INVERSE_PAIRS,
    CONTINUANT,
    DISJOINT_PAIRS,
    ENTITY,
    LABELS,
    OCCURRENT,
    PROPERTY_CONSTRAINTS,
    _is_bfo_iri,
)
from .findings import ComplianceReport, Severity

_EvalClasses = set[URIRef] | None
_EvalProps   = set[URIRef] | None


# ── helpers ───────────────────────────────────────────────────────────────────

def _label(graph: Graph, node: Node) -> str:
    if not isinstance(node, URIRef):
        return str(node)
    lbl = LABELS.get(node)
    if lbl:
        return lbl
    for _, _, o in graph.triples((node, RDFS.label, None)):
        return str(o)
    iri = str(node)
    return iri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _classes(graph: Graph, eval_classes: _EvalClasses = None) -> list[URIRef]:
    """Named OWL classes in *graph*, optionally filtered to *eval_classes*."""
    classes: set[URIRef] = set()
    for s in graph.subjects(RDF.type, OWL.Class):
        if isinstance(s, URIRef):
            classes.add(s)
    for s, _, _ in graph.triples((None, RDFS.subClassOf, None)):
        if isinstance(s, URIRef):
            classes.add(s)
    if eval_classes is not None:
        classes &= eval_classes
    return list(classes)


def _properties(graph: Graph, eval_classes: _EvalClasses = None) -> list[URIRef]:
    props: set[URIRef] = set()
    for ptype in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
        for s in graph.subjects(RDF.type, ptype):
            if isinstance(s, URIRef):
                props.add(s)
    return list(props)


def _superclasses(graph: Graph, cls: URIRef) -> set[URIRef]:
    """All (direct + transitive) superclasses via rdfs:subClassOf.

    For BFO-namespace nodes, the bundled BFO_GRAPH is also consulted so that
    the BFO hierarchy is always resolved even when bfo-core.ttl is not
    explicitly imported by the ontology under evaluation.
    """
    visited: set[URIRef] = set()
    queue = [cls]
    while queue:
        current = queue.pop()
        for _, _, parent in graph.triples((current, RDFS.subClassOf, None)):
            if isinstance(parent, URIRef) and parent not in visited:
                visited.add(parent)
                queue.append(parent)
        if _is_bfo_iri(str(current)):
            for _, _, parent in BFO_GRAPH.triples((current, RDFS.subClassOf, None)):
                if isinstance(parent, URIRef) and parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
    return visited


def _find_path(graph: Graph, cls: URIRef, target: URIRef) -> list[URIRef] | None:
    """BFS shortest rdfs:subClassOf path from *cls* to *target*. Returns the full
    node list including both endpoints, or None if no path exists."""
    queue: deque[tuple[URIRef, list[URIRef]]] = deque([(cls, [cls])])
    visited: set[URIRef] = {cls}
    while queue:
        current, path = queue.popleft()
        sources = list(graph.triples((current, RDFS.subClassOf, None)))
        if _is_bfo_iri(str(current)):
            sources += list(BFO_GRAPH.triples((current, RDFS.subClassOf, None)))
        for _, _, parent in sources:
            if not isinstance(parent, URIRef):
                continue
            new_path = path + [parent]
            if parent == target:
                return new_path
            if parent not in visited:
                visited.add(parent)
                queue.append((parent, new_path))
    return None


def _format_path(graph: Graph, path: list[URIRef]) -> str:
    return " → ".join(_label(graph, node) for node in path)


# ── rule 1 : disjointness violations ─────────────────────────────────────────

def _superproperties(graph: Graph, prop: URIRef) -> set[URIRef]:
    """All (direct + transitive) superproperties via rdfs:subPropertyOf."""
    visited: set[URIRef] = set()
    queue = [prop]
    while queue:
        current = queue.pop()
        for _, _, parent in graph.triples((current, RDFS.subPropertyOf, None)):
            if isinstance(parent, URIRef) and parent not in visited:
                visited.add(parent)
                queue.append(parent)
    return visited


# ── rule 1 : disjointness violations ─────────────────────────────────────────

def check_disjointness_violations(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Flag classes that are subclasses of two BFO-disjoint categories."""
    for cls in _classes(graph, eval_classes):
        if _is_bfo_iri(str(cls)):
            continue
        ancestors = _superclasses(graph, cls)
        for a, b in DISJOINT_PAIRS:
            if a in ancestors and b in ancestors:
                path_a = _find_path(graph, cls, a)
                path_b = _find_path(graph, cls, b)
                detail_lines = [f"Class IRI: {cls}"]
                if path_a:
                    detail_lines.append(f"Path to {_label(graph, a)}: {_format_path(graph, path_a)}")
                if path_b:
                    detail_lines.append(f"Path to {_label(graph, b)}: {_format_path(graph, path_b)}")
                report.add(
                    Severity.ERROR,
                    "disjointness-violation",
                    _label(graph, cls),
                    f"Subclass of both {_label(graph, a)} and {_label(graph, b)}, "
                    "which BFO declares disjoint.",
                    "\n".join(detail_lines),
                )


# ── rule 2 : unknown BFO IRIs ─────────────────────────────────────────────────

def check_unknown_bfo_iris(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Flag references to BFO IRIs that do not exist in BFO 2020.

    When eval_classes is set, only triples whose subject is in eval_classes
    (or whose subject/predicate/object is a BFO IRI used by an eval class)
    are scanned.  In practice we scan the full merged graph but deduplicate,
    which is acceptable — unknown BFO IRIs are equally bad regardless of origin.
    """
    seen: set[URIRef] = set()
    for s, p, o in graph:
        for node in (s, p, o):
            if isinstance(node, URIRef) and _is_bfo_iri(str(node)) and node not in seen:
                seen.add(node)
                if node not in ALL_BFO_CLASSES and node not in ALL_BFO_PROPERTIES:
                    report.add(
                        Severity.WARNING,
                        "unknown-bfo-iri",
                        str(node),
                        "IRI looks like a BFO term but is not recognised in BFO 2020.",
                        "Possible typo or reference to a retired/draft term.",
                    )


# ── rule 3 : property domain/range violations ─────────────────────────────────

def check_property_constraints(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Flag properties whose declared domain/range conflicts with BFO constraints."""
    for prop, (expected_domain, expected_range) in PROPERTY_CONSTRAINTS.items():
        for declared_domain in graph.objects(prop, RDFS.domain):
            if not isinstance(declared_domain, URIRef):
                continue
            if expected_domain is None:
                continue
            anc = _superclasses(graph, declared_domain) | {declared_domain}
            if expected_domain not in anc:
                report.add(
                    Severity.WARNING,
                    "property-domain-mismatch",
                    _label(graph, prop),
                    f"Declared domain {_label(graph, declared_domain)} is not a "
                    f"subclass of the BFO-required domain {_label(graph, expected_domain)}.",
                    f"Property: {prop}",
                )

        for declared_range in graph.objects(prop, RDFS.range):
            if not isinstance(declared_range, URIRef):
                continue
            if expected_range is None:
                continue
            anc = _superclasses(graph, declared_range) | {declared_range}
            if expected_range not in anc:
                report.add(
                    Severity.WARNING,
                    "property-range-mismatch",
                    _label(graph, prop),
                    f"Declared range {_label(graph, declared_range)} is not a "
                    f"subclass of the BFO-required range {_label(graph, expected_range)}.",
                    f"Property: {prop}",
                )


# ── rule 4 : orphaned classes ─────────────────────────────────────────────────

def check_orphaned_classes(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Warn about evaluation classes that have no ancestry path to any BFO term."""
    uses_bfo = any(_is_bfo_iri(str(n)) for n in graph.all_nodes() if isinstance(n, URIRef))
    if not uses_bfo:
        report.add(
            Severity.INFO,
            "no-bfo-reference",
            "ontology",
            "No BFO IRIs detected. Cannot assess BFO alignment.",
        )
        return

    for cls in _classes(graph, eval_classes):
        if _is_bfo_iri(str(cls)):
            continue
        ancestors = _superclasses(graph, cls)
        if ENTITY not in ancestors and not any(_is_bfo_iri(str(a)) for a in ancestors):
            report.add(
                Severity.WARNING,
                "orphaned-class",
                _label(graph, cls),
                "Class has no superclass path to any BFO term.",
                f"Class IRI: {cls}",
            )


# ── rule 5 : continuant/occurrent polysemy ────────────────────────────────────

def check_continuant_occurrent_polysemy(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Detect properties used with both Continuant and Occurrent in domain/range."""
    for prop in _properties(graph, eval_classes):
        domains = list(graph.objects(prop, RDFS.domain))
        continuant_domains = [
            d for d in domains
            if isinstance(d, URIRef) and CONTINUANT in (_superclasses(graph, d) | {d})
        ]
        occurrent_domains = [
            d for d in domains
            if isinstance(d, URIRef) and OCCURRENT in (_superclasses(graph, d) | {d})
        ]
        if continuant_domains and occurrent_domains:
            report.add(
                Severity.WARNING,
                "mixed-continuant-occurrent-domain",
                _label(graph, prop),
                "Property has declared domains in both bfo:Continuant and bfo:Occurrent hierarchies.",
                f"Property: {prop}",
            )


# ── rule 6 : BFO inverse property consistency ────────────────────────────────

def check_inverse_property_consistency(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Flag BFO inverse pairs where only one direction is declared.

    The pairs are derived directly from owl:inverseOf assertions in bfo-core.ttl,
    so they stay in sync with the bundled ontology file automatically.
    """
    all_props = set(_properties(graph, eval_classes))
    for p, q in BFO_INVERSE_PAIRS:
        p_used = p in all_props or any(graph.triples((None, p, None)))
        q_used = q in all_props or any(graph.triples((None, q, None)))
        if p_used and not q_used:
            report.add(
                Severity.INFO,
                "missing-bfo-inverse",
                _label(graph, p),
                f"BFO property used without its declared inverse {_label(graph, q)}.",
            )
        elif q_used and not p_used:
            report.add(
                Severity.INFO,
                "missing-bfo-inverse",
                _label(graph, q),
                f"BFO property used without its declared inverse {_label(graph, p)}.",
            )


# ── rule 7 : declared disjoint-with cross-check ───────────────────────────────

def check_declared_disjoint_with(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Check owl:disjointWith declarations for conflicts with BFO hierarchy."""
    for a, _, b in graph.triples((None, OWL.disjointWith, None)):
        if not isinstance(a, URIRef) or not isinstance(b, URIRef):
            continue
        # Only flag when at least one side belongs to the evaluation ontology.
        if eval_classes is not None and a not in eval_classes and b not in eval_classes:
            continue
        anc_a = _superclasses(graph, a)
        anc_b = _superclasses(graph, b)
        if b in anc_a:
            report.add(
                Severity.ERROR,
                "disjoint-subclass-contradiction",
                _label(graph, a),
                f"Class is declared disjoint from {_label(graph, b)} but is also its subclass.",
                f"IRI: {a}",
            )
        if a in anc_b:
            report.add(
                Severity.ERROR,
                "disjoint-subclass-contradiction",
                _label(graph, b),
                f"Class is declared disjoint from {_label(graph, a)} but is also its subclass.",
                f"IRI: {b}",
            )


# ── rule 8 : non-BFO-compliant external references ───────────────────────────

def check_non_bfo_compliant_references(
    graph: Graph,
    report: ComplianceReport,
    eval_classes: _EvalClasses = None,
    eval_properties: _EvalProps = None,
) -> None:
    """Warn when an eval class or property references an external term with no BFO ancestry.

    Checks rdfs:subClassOf / owl:equivalentClass for classes, and
    rdfs:subPropertyOf / owl:equivalentProperty for object/datatype properties.
    Annotation properties are skipped — they are not expected to root in BFO.
    """
    eval_cls_set: set[URIRef] = eval_classes or set()
    eval_prop_set: set[URIRef] = eval_properties or set()

    # Classes
    for cls in _classes(graph, eval_classes):
        if _is_bfo_iri(str(cls)):
            continue
        for predicate, rule_id, pred_label in (
            (RDFS.subClassOf,     "non-bfo-compliant-superclass",        "superclass"),
            (OWL.equivalentClass, "non-bfo-compliant-equivalent-class",  "equivalent class"),
        ):
            for _, _, ref in graph.triples((cls, predicate, None)):
                if not isinstance(ref, URIRef):
                    continue
                if _is_bfo_iri(str(ref)):
                    continue
                if ref in eval_cls_set:
                    continue
                if any(_is_bfo_iri(str(a)) for a in _superclasses(graph, ref)):
                    continue
                report.add(
                    Severity.WARNING,
                    rule_id,
                    _label(graph, cls),
                    f"References external {pred_label} {_label(graph, ref)}, "
                    "which has no superclass path to any BFO term.",
                    f"Class IRI: {cls}\nReferenced IRI: {ref}",
                )

    # Object and datatype properties only (annotation properties are not BFO-rooted)
    obj_data_props: set[URIRef] = set()
    for ptype in (OWL.ObjectProperty, OWL.DatatypeProperty):
        for s in graph.subjects(RDF.type, ptype):
            if isinstance(s, URIRef) and s in eval_prop_set:
                obj_data_props.add(s)

    for prop in obj_data_props:
        if _is_bfo_iri(str(prop)):
            continue
        for predicate, rule_id, pred_label in (
            (RDFS.subPropertyOf,     "non-bfo-compliant-super-property",       "super-property"),
            (OWL.equivalentProperty, "non-bfo-compliant-equivalent-property",  "equivalent property"),
        ):
            for _, _, ref in graph.triples((prop, predicate, None)):
                if not isinstance(ref, URIRef):
                    continue
                if _is_bfo_iri(str(ref)):
                    continue
                if ref in eval_prop_set:
                    continue
                if any(_is_bfo_iri(str(p)) for p in _superproperties(graph, ref) | {ref}):
                    continue
                report.add(
                    Severity.INFO,
                    rule_id,
                    _label(graph, prop),
                    f"References external {pred_label} {_label(graph, ref)}, "
                    "which has no super-property path to any BFO property.",
                    f"Property IRI: {prop}\nReferenced IRI: {ref}",
                )


ALL_RULES = [
    check_disjointness_violations,
    check_unknown_bfo_iris,
    check_property_constraints,
    check_orphaned_classes,
    check_continuant_occurrent_polysemy,
    check_inverse_property_consistency,
    check_declared_disjoint_with,
    check_non_bfo_compliant_references,
]

"""BFO 2020 term constants and live graph, loaded from the bundled ontology file.

Everything except PROPERTY_CONSTRAINTS is derived directly from bfo-core.ttl
at import time, so the checker automatically stays in sync with the TTL.
"""

from itertools import combinations
from pathlib import Path

from rdflib import Graph, OWL, RDF, RDFS, URIRef
from rdflib.collection import Collection

BFO = "http://purl.obolibrary.org/obo/BFO_"

# bfo-core.ttl is pulled from the BFO-2020 git submodule.
# If the submodule has not been initialised, run:
#   git submodule update --init --recursive
_SUBMODULE_TTL = (
    Path(__file__).parent / "bfo-2020" / "21838-2" / "owl" / "bfo-core.ttl"
)
_BUNDLED_TTL = Path(__file__).parent / "ontology" / "bfo-core.ttl"

if _SUBMODULE_TTL.exists():
    _TTL = _SUBMODULE_TTL
elif _BUNDLED_TTL.exists():
    _TTL = _BUNDLED_TTL
else:
    raise FileNotFoundError(
        "bfo-core.ttl not found. "
        "Initialise the BFO-2020 submodule with:\n"
        "  git submodule update --init --recursive"
    )


def bfo(local: str) -> URIRef:
    return URIRef(f"{BFO}{local}")


def _is_bfo_iri(iri: str) -> bool:
    return iri.startswith(BFO)


# ── Named class constants ─────────────────────────────────────────────────────
# Stable Python aliases for BFO 2020 class IRIs used throughout the rule engine.

ENTITY                      = bfo("0000001")
CONTINUANT                  = bfo("0000002")
OCCURRENT                   = bfo("0000003")
INDEPENDENT_CONTINUANT      = bfo("0000004")
SPATIAL_REGION              = bfo("0000006")
TEMPORAL_REGION             = bfo("0000008")
SPATIOTEMPORAL_REGION       = bfo("0000011")
PROCESS                     = bfo("0000015")
DISPOSITION                 = bfo("0000016")
REALIZABLE_ENTITY           = bfo("0000017")
QUALITY                     = bfo("0000019")
SPECIFICALLY_DEP_CONTINUANT = bfo("0000020")
ROLE                        = bfo("0000023")
FIAT_OBJECT_PART            = bfo("0000024")
ONE_DIM_SPATIAL_REGION      = bfo("0000026")
OBJECT_AGGREGATE            = bfo("0000027")
THREE_DIM_SPATIAL_REGION    = bfo("0000028")
SITE                        = bfo("0000029")
OBJECT                      = bfo("0000030")
GENERICALLY_DEP_CONTINUANT  = bfo("0000031")
FUNCTION                    = bfo("0000034")
PROCESS_BOUNDARY            = bfo("0000035")
TEMPORAL_INTERVAL           = bfo("0000038")
MATERIAL_ENTITY             = bfo("0000040")
IMMATERIAL_ENTITY           = bfo("0000141")
CONTINUANT_FIAT_BOUNDARY    = bfo("0000140")
HISTORY                     = bfo("0000182")
TEMPORAL_INSTANT            = bfo("0000203")
ZERO_DIM_TEMPORAL_REGION    = bfo("0000148")

# ── Named property constants (BFO 2020 IRIs) ─────────────────────────────────
HAS_REALIZATION             = bfo("0000054")
REALIZES                    = bfo("0000055")
PARTICIPATES_IN             = bfo("0000056")
HAS_PARTICIPANT             = bfo("0000057")
IS_CONCRETIZED_BY           = bfo("0000058")
CONCRETIZES                 = bfo("0000059")
PRECEDED_BY                 = bfo("0000062")
PRECEDES                    = bfo("0000063")
OCCURS_IN                   = bfo("0000066")
GENERICALLY_DEPENDS_ON      = bfo("0000084")
IS_CARRIER_OF               = bfo("0000101")
EXISTS_AT                   = bfo("0000108")
HAS_MEMBER_PART             = bfo("0000115")
HAS_OCCURRENT_PART          = bfo("0000117")
HAS_TEMPORAL_PART           = bfo("0000121")
LOCATION_OF                 = bfo("0000124")
MATERIAL_BASIS_OF           = bfo("0000127")
MEMBER_PART_OF              = bfo("0000129")
OCCURRENT_PART_OF           = bfo("0000132")
TEMPORAL_PART_OF            = bfo("0000139")
LOCATED_IN                  = bfo("0000171")
CONTINUANT_PART_OF          = bfo("0000176")
HAS_CONTINUANT_PART         = bfo("0000178")
ENVIRONS                    = bfo("0000183")   # alt label: "contains process"
HISTORY_OF                  = bfo("0000184")
HAS_HISTORY                 = bfo("0000185")
SPECIFICALLY_DEPENDED_ON_BY = bfo("0000194")
SPECIFICALLY_DEPENDS_ON     = bfo("0000195")
BEARER_OF                   = bfo("0000196")
INHERES_IN                  = bfo("0000197")
OCCUPIES_TEMPORAL_REGION    = bfo("0000199")
OCCUPIES_SPATIOTEMPORAL_REG = bfo("0000200")
OCCUPIES_SPATIAL_REGION     = bfo("0000210")
SPATIALLY_PROJECTS_ONTO     = bfo("0000216")
HAS_MATERIAL_BASIS          = bfo("0000218")


# ── Load the BFO 2020 graph ───────────────────────────────────────────────────

BFO_GRAPH: Graph = Graph()
BFO_GRAPH.parse(str(_TTL), format="turtle")


# ── Sets derived from the graph ───────────────────────────────────────────────

ALL_BFO_CLASSES: frozenset[URIRef] = frozenset(
    s for s in BFO_GRAPH.subjects(RDF.type, OWL.Class)
    if isinstance(s, URIRef) and _is_bfo_iri(str(s))
)

ALL_BFO_PROPERTIES: frozenset[URIRef] = frozenset(
    s for s in BFO_GRAPH.subjects(RDF.type, OWL.ObjectProperty)
    if isinstance(s, URIRef) and _is_bfo_iri(str(s))
)

LABELS: dict[URIRef, str] = {
    s: str(o)
    for s, _, o in BFO_GRAPH.triples((None, RDFS.label, None))
    if isinstance(s, URIRef) and _is_bfo_iri(str(s))
}

BFO_INVERSE_PAIRS: list[tuple[URIRef, URIRef]] = [
    (s, o)
    for s, _, o in BFO_GRAPH.triples((None, OWL.inverseOf, None))
    if isinstance(s, URIRef) and isinstance(o, URIRef)
    and _is_bfo_iri(str(s)) and _is_bfo_iri(str(o))
]


def _extract_disjoint_pairs(graph: Graph) -> list[tuple[URIRef, URIRef]]:
    """Extract all disjoint class pairs from owl:disjointWith and owl:AllDisjointClasses."""
    seen: set[frozenset] = set()
    pairs: list[tuple[URIRef, URIRef]] = []

    def _add(a: URIRef, b: URIRef) -> None:
        key = frozenset((a, b))
        if key not in seen:
            seen.add(key)
            pairs.append((a, b))

    # Pairwise owl:disjointWith
    for s, _, o in graph.triples((None, OWL.disjointWith, None)):
        if isinstance(s, URIRef) and isinstance(o, URIRef) \
                and _is_bfo_iri(str(s)) and _is_bfo_iri(str(o)):
            _add(s, o)

    # N-ary owl:AllDisjointClasses
    for node in graph.subjects(RDF.type, OWL.AllDisjointClasses):
        members_node = graph.value(node, OWL.members)
        if members_node is None:
            continue
        members = [
            m for m in Collection(graph, members_node)
            if isinstance(m, URIRef) and _is_bfo_iri(str(m))
        ]
        for a, b in combinations(members, 2):
            _add(a, b)

    return pairs


DISJOINT_PAIRS: list[tuple[URIRef, URIRef]] = _extract_disjoint_pairs(BFO_GRAPH)


# ── Curated property constraint table ────────────────────────────────────────
# BFO's OWL domain/range expressions use complex union/intersection restrictions
# that require OWL reasoning to evaluate. This table captures the conceptual
# intent as simple class constraints for lightweight checking.

PROPERTY_CONSTRAINTS: dict[URIRef, tuple[URIRef | None, URIRef | None]] = {
    PARTICIPATES_IN:    (INDEPENDENT_CONTINUANT,        PROCESS),
    HAS_PARTICIPANT:    (PROCESS,                       INDEPENDENT_CONTINUANT),
    INHERES_IN:         (SPECIFICALLY_DEP_CONTINUANT,   INDEPENDENT_CONTINUANT),
    BEARER_OF:          (INDEPENDENT_CONTINUANT,        SPECIFICALLY_DEP_CONTINUANT),
    HAS_REALIZATION:    (REALIZABLE_ENTITY,              PROCESS),
    REALIZES:           (PROCESS,                       REALIZABLE_ENTITY),
    OCCURS_IN:          (PROCESS,                       MATERIAL_ENTITY),
    PRECEDED_BY:        (OCCURRENT,                     OCCURRENT),
    PRECEDES:           (OCCURRENT,                     OCCURRENT),
    IS_CONCRETIZED_BY:  (GENERICALLY_DEP_CONTINUANT,    SPECIFICALLY_DEP_CONTINUANT),
    CONCRETIZES:        (SPECIFICALLY_DEP_CONTINUANT,   GENERICALLY_DEP_CONTINUANT),
}

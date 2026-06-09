# BFOBRO

BFO compliance checker for OWL ontologies.

BFOBRO loads any RDFLib-readable ontology and checks it against the structural
rules of [Basic Formal Ontology (BFO) 2020](https://basic-formal-ontology.org/).
Conflicts are printed as a colour-coded report with severity levels and rule
identifiers, making it easy to track down specific violations.

---

## Requirements

- Python >= 3.12
- pip / pipx

---

## Environment setup

It is recommended to install BFOBRO inside an isolated environment. Choose
either the standard `venv` approach or Conda/Mamba.

### Option A — Python venv

```bash
# Create the environment (do this once)
python -m venv .venv

# Activate — Linux / macOS
source .venv/bin/activate

# Activate — Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Activate — Windows (cmd.exe)
.venv\Scripts\activate.bat

# Confirm the right Python is active
python --version   # should be 3.12+
```

Deactivate when you are done:

```bash
deactivate
```

### Option B — Conda / Mamba

```bash
# Create the environment (do this once)
conda create -n bfobro python=3.12

# Activate
conda activate bfobro

# Confirm
python --version   # should be 3.12+
```

Deactivate when you are done:

```bash
conda deactivate
```

> **Tip:** Replace `conda` with `mamba` in any command above for faster
> dependency resolution if you have Mamba installed.

---

## Installation

With your environment active, install BFOBRO using one of the methods below.

### From source (development)

```bash
git clone https://github.com/UCF-HENAT/BFOBRO.git
cd BFOBRO
pip install -e ".[dev]"
```

### From a wheel / PyPI (once published)

```bash
pip install bfobro
```

For an isolated global install without managing an environment manually, use
[pipx](https://pipx.pypa.io/) (handles its own venv internally):

```bash
pipx install bfobro
```

---

## CLI usage

```
bfobro <ontology> [--format FORMAT] [--errors-only]
```

| Argument | Description |
|---|---|
| `ontology` | Path or URL to the ontology file to evaluate |
| `--format`, `-f` | RDFLib format hint for the evaluation ontology: `turtle`, `xml`, `n3`, `nt`, `json-ld`. Auto-detected when omitted. |
| `--reference`, `-r` | Path or URL of a reference ontology (BFO, CCO, or any middle ontology) whose hierarchy is used as background knowledge. Repeatable. |
| `--ref-format` | RDFLib format hint applied to all reference ontologies. |
| `--errors-only`, `-e` | Exit with code `1` if any **ERROR**-level findings are present (useful in CI pipelines). |

### Examples

```bash
# Basic check — Turtle file
bfobro my_ontology.ttl

# Check through a middle ontology (e.g. CCO)
bfobro my_ontology.ttl --reference cco.ttl

# Multiple reference ontologies
bfobro my_ontology.ttl -r bfo.owl -r cco.ttl

# RDF/XML with explicit format
bfobro my_ontology.owl --format xml

# CI-friendly: fail the build on errors
bfobro my_ontology.ttl --reference cco.ttl --errors-only
```

### Reference ontologies

Many domain ontologies do not directly subclass BFO terms — instead they extend
a *middle ontology* such as the
[Common Core Ontologies (CCO)](https://github.com/CommonCoreOntology/CommonCoreOntologies)
that is itself BFO-rooted.  Without loading the middle ontology, BFOBRO cannot
trace the ancestry chain back to BFO and will report orphaned classes.

Using `--reference` loads the middle ontology as background knowledge.  Its
classes and properties are used for ancestor lookups but are **not themselves
evaluated** for compliance — only the classes declared in the primary evaluation
ontology are checked.

```
eval.ttl  →  cco.ttl  →  bfo.owl
               ↑
          loaded via --reference
```

### Example output

```
+--------------- BFOBRO -- BFO Compliance Report ---------------+
| Ontology: https://example.org/MyOntology                      |
+---------------------------------------------------------------+

 Severity     | Rule                          | Subject            | Message
--------------+-------------------------------+--------------------+------------------------------------------
 X ERROR       | disjointness-violation        | ex:HybridThing     | Subclass of both bfo:Continuant and
               |                               |                    | bfo:Occurrent, which BFO declares disjoint.
               |                               |                    | Class IRI: https://example.org/HybridThing
 ! WARNING     | orphaned-class                | ex:FloatingConcept | Class has no superclass path to any BFO term.
 ! WARNING     | unknown-bfo-iri               | BFO_9999999        | IRI looks like a BFO term but is not
               |                               |                    | recognised in BFO 2020.
 i INFO        | missing-bfo-inverse           | bfo:participatesIn | BFO property used without its declared
               |                               |                    | inverse bfo:hasParticipant.

X NOT COMPLIANT  --  1 error(s), 2 warning(s), 1 info(s)
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Ran successfully (findings may still be present unless `--errors-only`) |
| `1` | ERROR-level findings present (only when `--errors-only` is set) |
| `2` | Failed to load the ontology |

---

## Library usage

```python
from bfobro import check_ontology

report = check_ontology("my_ontology.ttl")

print(f"Ontology: {report.ontology_iri}")
print(f"Compliant: {report.is_compliant}")

for finding in report.findings:
    print(f"[{finding.severity.value}] {finding.rule}: {finding.message}")
```

### Printing with Rich

```python
from rich.console import Console
from bfobro import check_ontology
from bfobro.report_printer import print_report

report = check_ontology("my_ontology.ttl")
print_report(report, Console())
```

### Filtering by severity

```python
from bfobro import check_ontology, Severity

report = check_ontology("my_ontology.ttl")

errors   = report.errors           # list[Finding] — ERROR only
warnings = report.warnings         # list[Finding] — WARNING only

# Manual filter for a specific rule
disjointness_errors = [
    f for f in report.findings
    if f.rule == "disjointness-violation"
]
```

---

## Compliance rules

| Rule ID | Severity | Description |
|---|---|---|
| `disjointness-violation` | ERROR | Class inherits (directly or transitively) from two BFO-disjoint categories, e.g. `bfo:Continuant` and `bfo:Occurrent`. |
| `disjoint-subclass-contradiction` | ERROR | An `owl:disjointWith` assertion is made between a class and its own superclass. |
| `unknown-bfo-iri` | WARNING | A BFO-namespace IRI (`http://purl.obolibrary.org/obo/BFO_…`) is used but does not exist in BFO 2020 — likely a typo or retired term. |
| `property-domain-mismatch` | WARNING | A BFO property is given a declared domain that is not a subclass of the BFO-required domain. |
| `property-range-mismatch` | WARNING | A BFO property is given a declared range that is not a subclass of the BFO-required range. |
| `orphaned-class` | WARNING | A non-BFO class has no superclass path to any BFO term (only reported when BFO IRIs are present in the ontology). |
| `mixed-continuant-occurrent-domain` | WARNING | A property has declared domains spanning both `bfo:Continuant` and `bfo:Occurrent` hierarchies. |
| `missing-bfo-inverse` | INFO | A BFO property is used but its declared BFO inverse is absent. |
| `no-bfo-reference` | INFO | No BFO IRIs were detected; BFO alignment cannot be assessed. |

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=bfobro --cov-report=term-missing
```

---

## Supported ontology formats

Any format supported by RDFLib 7:

| Format | Typical extension |
|---|---|
| Turtle | `.ttl` |
| RDF/XML | `.owl`, `.rdf`, `.xml` |
| N-Triples | `.nt` |
| N3 | `.n3` |
| JSON-LD | `.jsonld`, `.json` |
| TriG | `.trig` |

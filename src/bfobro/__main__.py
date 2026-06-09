"""CLI entry point: ``python -m bfobro`` or ``bfobro`` after install."""

import argparse
import sys

from rich.console import Console

from .checker import check_ontology
from .report_printer import print_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bfobro",
        description="Check an OWL ontology for BFO 2020 compliance.",
    )
    parser.add_argument(
        "ontology",
        help="Path or URL to the ontology file (Turtle, RDF/XML, N-Triples, JSON-LD …)",
    )
    parser.add_argument(
        "--format", "-f",
        dest="fmt",
        default=None,
        metavar="FORMAT",
        help="RDFLib format hint (turtle, xml, n3, nt, json-ld). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--reference", "-r",
        dest="references",
        metavar="REF",
        action="append",
        default=[],
        help=(
            "Path or URL of a reference ontology (e.g. BFO or CCO) whose class "
            "hierarchy is used as background knowledge.  May be repeated to load "
            "multiple reference ontologies.  Classes from reference ontologies are "
            "not themselves evaluated for compliance."
        ),
    )
    parser.add_argument(
        "--ref-format",
        dest="ref_fmt",
        default=None,
        metavar="FORMAT",
        help="RDFLib format hint applied to all reference ontologies.",
    )
    parser.add_argument(
        "--errors-only", "-e",
        action="store_true",
        help="Exit with code 1 if any errors are found (useful for CI pipelines).",
    )

    args = parser.parse_args(argv)
    console = Console()

    try:
        report = check_ontology(
            args.ontology,
            fmt=args.fmt,
            references=args.references or None,
            ref_fmt=args.ref_fmt,
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to load ontology:[/] {exc}")
        return 2

    print_report(report, console)

    if args.errors_only:
        return 1 if not report.is_compliant else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

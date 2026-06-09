"""Pretty-print a ComplianceReport using Rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from .findings import ComplianceReport, Severity

_SEVERITY_STYLE: dict[Severity, str] = {
    Severity.ERROR:   "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO:    "dim cyan",
}

_SEVERITY_ICON: dict[Severity, str] = {
    Severity.ERROR:   "[bold red]X ERROR  [/]",
    Severity.WARNING: "[bold yellow]! WARNING[/]",
    Severity.INFO:    "[cyan]i INFO   [/]",
}


def print_report(report: ComplianceReport, console: Console | None = None) -> None:
    c = console or Console(highlight=False, safe_box=True)

    c.print()
    body = f"[bold]Ontology:[/]  {report.ontology_iri}"
    if report.reference_iris:
        refs = "\n".join(f"  {iri}" for iri in report.reference_iris)
        body += f"\n[bold]Reference:[/]\n{refs}"
    c.print(Panel(
        body,
        title="[bold blue]BFOBRO -- BFO Compliance Report[/]",
        expand=False,
    ))

    if not report.findings:
        c.print("[bold green]OK No issues found. Ontology appears BFO-compliant.[/]")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("Severity", width=12, no_wrap=True)
    table.add_column("Rule", style="dim", no_wrap=True)
    table.add_column("Subject")
    table.add_column("Message")

    for f in sorted(report.findings, key=lambda x: (x.severity.value, x.rule)):
        icon = _SEVERITY_ICON[f.severity]
        msg = f.message
        if f.detail:
            msg += f"\n[dim]{f.detail}[/dim]"
        table.add_row(icon, f.rule, f.subject, msg)

    c.print(table)

    errors   = len(report.errors)
    warnings = len(report.warnings)
    infos    = len(report.findings) - errors - warnings

    summary_parts = []
    if errors:
        summary_parts.append(f"[bold red]{errors} error(s)[/]")
    if warnings:
        summary_parts.append(f"[bold yellow]{warnings} warning(s)[/]")
    if infos:
        summary_parts.append(f"[cyan]{infos} info(s)[/]")

    verdict = (
        "[bold red]X NOT COMPLIANT[/]" if not report.is_compliant
        else "[bold green]OK COMPLIANT (with warnings)[/]"
    )
    c.print(f"\n{verdict}  --  {', '.join(summary_parts)}\n")

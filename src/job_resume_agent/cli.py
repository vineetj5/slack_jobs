from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import AppConfig
from .greenhouse import GreenhouseJobExtractor
from .scraper import JobScraper
from .workflow import AgenticJobSearchWorkflow

app = typer.Typer(help="Scrape jobs and generate a tailored resume through an agentic workflow.")
console = Console()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@app.command()
def scrape(
    source: list[str] = typer.Option(..., "--source", help="Local HTML/JSON path or remote URL."),
    output: str = typer.Option("output/jobs.json", "--output", help="Path to write scraped jobs JSON."),
) -> None:
    scraper = JobScraper(AppConfig())
    jobs = scraper.collect(source)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([job.model_dump() for job in jobs], indent=2),
        encoding="utf-8",
    )
    console.print(f"Wrote {len(jobs)} jobs to {output_path}")


@app.command()
def greenhouse(
    board: list[str] = typer.Option(
        ...,
        "--board",
        help="Greenhouse board token or URL, for example 'airbnb' or 'https://boards.greenhouse.io/airbnb'.",
    ),
    output: str = typer.Option(
        "output/greenhouse_jobs.json",
        "--output",
        help="Path to write filtered jobs.",
    ),
    output_format: str = typer.Option(
        "json",
        "--format",
        help="Output format: json or csv.",
    ),
    hours: float = typer.Option(
        1.0,
        "--hours",
        help="Only include jobs posted/updated within the last N hours (default: 1).",
    ),
) -> None:
    extractor = GreenhouseJobExtractor(AppConfig(), posted_within_hours=hours)
    jobs = extractor.collect(board)

    if output_format == "json":
        extractor.write_json(jobs, output)
    elif output_format == "csv":
        extractor.write_csv(jobs, output)
    else:
        raise typer.BadParameter("--format must be 'json' or 'csv'")

    console.print(f"Wrote {len(jobs)} Greenhouse jobs to {Path(output)}")


@app.command()
def run(
    profile: str = typer.Option(..., "--profile", help="Path to YAML candidate profile."),
    source: list[str] = typer.Option(..., "--source", help="Local HTML/JSON path or remote URL."),
    outdir: str = typer.Option("output/run", "--outdir", help="Output directory for artifacts."),
    top_k: int = typer.Option(3, "--top-k", help="Number of top job matches to keep."),
) -> None:
    workflow = AgenticJobSearchWorkflow(_project_root())
    artifacts = workflow.run(profile_path=profile, sources=source, outdir=outdir, top_k=top_k)

    table = Table(title="Top Job Matches")
    table.add_column("Role")
    table.add_column("Company")
    table.add_column("Score")
    for match in artifacts.matches:
        table.add_row(match.job.title, match.job.company, f"{match.score:.0f}")
    console.print(table)
    console.print(f"Artifacts written to {Path(outdir).resolve()}")


@app.command()
def demo() -> None:
    root = _project_root()
    workflow = AgenticJobSearchWorkflow(root)
    outdir = root / "output" / "demo"
    workflow.run(
        profile_path=root / "data" / "sample_profile.yaml",
        sources=[str(root / "data" / "sample_jobs.html")],
        outdir=outdir,
        top_k=3,
    )
    console.print(f"Demo complete. Open {outdir}")


if __name__ == "__main__":
    app()

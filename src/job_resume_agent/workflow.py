from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from .config import AppConfig
from .llm import LLMClient
from .models import AgentStepResult, CandidateProfile, JobMatch, WorkflowArtifacts
from .resume import build_application_notes, build_resume_draft, render_resume, score_job
from .greenhouse import GreenhouseJobExtractor
from .scraper import JobScraper


class AgenticJobSearchWorkflow:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.config = AppConfig()
        self.scraper = JobScraper(self.config)
        self.llm = LLMClient(self.config)

    def load_profile(self, profile_path: str | Path) -> CandidateProfile:
        data = yaml.safe_load(Path(profile_path).read_text(encoding="utf-8"))
        return CandidateProfile(**data)

    def run(
        self,
        profile_path: str | Path,
        sources: list[str],
        outdir: str | Path,
        top_k: int = 3,
    ) -> WorkflowArtifacts:
        output_dir = Path(outdir)
        output_dir.mkdir(parents=True, exist_ok=True)
        steps: list[AgentStepResult] = []

        profile = self.load_profile(profile_path)
        planner_notes = self._planner_step(profile, steps)
        jobs = self._scraper_step(sources, steps)
        matches = self._analyst_step(profile, jobs, planner_notes, top_k, steps)
        resume = self._resume_step(profile, matches[0], steps)
        notes = self._writer_notes_step(profile, matches, steps)
        report = self._build_report(steps, planner_notes, profile, matches)

        artifacts = WorkflowArtifacts(
            jobs=jobs,
            matches=matches,
            resume=resume,
            notes=notes,
            report=report,
        )
        self._write_outputs(output_dir, profile, artifacts)
        return artifacts

    def _planner_step(self, profile: CandidateProfile, steps: list[AgentStepResult]) -> str:
        started = datetime.utcnow()
        objective = "Create targeting strategy for the search."
        query_terms = profile.target_roles or [profile.title]
        location_terms = profile.target_locations or [profile.location]
        notes = (
            f"Focus on roles like {', '.join(query_terms)} in {', '.join(location_terms)}. "
            f"Prioritize keywords: {', '.join(profile.preferred_keywords or profile.skills[:5])}."
        )
        steps.append(
            AgentStepResult(
                name="PlannerAgent",
                objective=objective,
                status="completed",
                details=notes,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        return notes

    def _scraper_step(self, sources: list[str], steps: list[AgentStepResult]):
        started = datetime.utcnow()
        objective = "Scrape and normalize jobs from the requested sources."

        # Split sources: Greenhouse board tokens/URLs vs generic sources
        greenhouse_sources = [
            s for s in sources
            if "greenhouse.io" in s or (not s.startswith("http") and "." not in s)
        ]
        other_sources = [s for s in sources if s not in greenhouse_sources]

        jobs: list = []

        if greenhouse_sources:
            gh_extractor = GreenhouseJobExtractor(
                config=self.config,
                posted_within_hours=1.0,  # Only jobs posted in the last 1 hour
            )
            jobs.extend(gh_extractor.collect(greenhouse_sources))

        if other_sources:
            jobs.extend(self.scraper.collect(other_sources))

        details = (
            f"Collected {len(jobs)} jobs from {len(sources)} source(s) "
            f"({len(greenhouse_sources)} Greenhouse, {len(other_sources)} generic). "
            "Greenhouse results filtered to jobs posted in the last 1 hour."
        )
        steps.append(
            AgentStepResult(
                name="ScraperAgent",
                objective=objective,
                status="completed",
                details=details,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        return jobs

    def _analyst_step(
        self,
        profile: CandidateProfile,
        jobs,
        planner_notes: str,
        top_k: int,
        steps: list[AgentStepResult],
    ) -> list[JobMatch]:
        started = datetime.utcnow()
        objective = "Score job matches and rank the best opportunities."
        matches = [score_job(profile, job_posting=job) for job in jobs]
        matches.sort(key=lambda item: item.score, reverse=True)
        selected = matches[:top_k]
        details = f"Ranked {len(matches)} jobs. Top pick: {selected[0].job.title} at {selected[0].job.company}."

        if self.llm.enabled and selected:
            details += " LLM enhancement is available for future ranking refinement."
        details += f" Planner guidance used: {planner_notes}"

        steps.append(
            AgentStepResult(
                name="AnalystAgent",
                objective=objective,
                status="completed",
                details=details,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        return selected

    def _resume_step(self, profile: CandidateProfile, top_match: JobMatch, steps: list[AgentStepResult]):
        started = datetime.utcnow()
        objective = "Tailor a resume draft for the best-fit job."
        draft = build_resume_draft(profile, top_match)
        details = f"Tailored resume for {top_match.job.title} at {top_match.job.company}."
        steps.append(
            AgentStepResult(
                name="ResumeAgent",
                objective=objective,
                status="completed",
                details=details,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        return draft

    def _writer_notes_step(self, profile: CandidateProfile, matches: list[JobMatch], steps: list[AgentStepResult]) -> str:
        started = datetime.utcnow()
        objective = "Create recruiter outreach and application notes."
        notes = build_application_notes(profile, matches)
        details = f"Produced notes for {len(matches)} prioritized applications."
        steps.append(
            AgentStepResult(
                name="WriterAgent",
                objective=objective,
                status="completed",
                details=details,
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        )
        return notes

    def _build_report(
        self,
        steps: list[AgentStepResult],
        planner_notes: str,
        profile: CandidateProfile,
        matches: list[JobMatch],
    ) -> str:
        lines = [
            "# Workflow Report",
            "",
            f"Candidate: {profile.name}",
            f"Target strategy: {planner_notes}",
            "",
            "## Agent execution",
        ]
        for step in steps:
            lines.append(f"- {step.name}: {step.details}")
        if matches:
            lines.extend(
                [
                    "",
                    "## Best match",
                    f"- {matches[0].job.title} at {matches[0].job.company} ({matches[0].score:.0f}/100)",
                ]
            )
        return "\n".join(lines)

    def _write_outputs(self, outdir: Path, profile: CandidateProfile, artifacts: WorkflowArtifacts) -> None:
        template_dir = self.config.template_dir(self.project_root)
        resume_markdown = render_resume(template_dir, profile, artifacts.resume)

        (outdir / "jobs.json").write_text(
            json.dumps([job.model_dump() for job in artifacts.jobs], indent=2),
            encoding="utf-8",
        )
        (outdir / "matches.json").write_text(
            json.dumps([match.model_dump() for match in artifacts.matches], indent=2),
            encoding="utf-8",
        )
        (outdir / "tailored_resume.md").write_text(resume_markdown, encoding="utf-8")
        (outdir / "application_notes.md").write_text(artifacts.notes, encoding="utf-8")
        (outdir / "workflow_report.md").write_text(artifacts.report, encoding="utf-8")


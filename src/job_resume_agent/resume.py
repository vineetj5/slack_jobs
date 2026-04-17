from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import CandidateProfile, JobMatch, ResumeDraft


def score_job(profile: CandidateProfile, job: JobMatch | None = None, job_posting=None) -> JobMatch:
    posting = job.job if job else job_posting
    description = f"{posting.title} {posting.description} {' '.join(posting.tags)}".lower()
    profile_skills = {skill.lower(): skill for skill in profile.skills}
    preferred = {kw.lower(): kw for kw in profile.preferred_keywords}

    matched = sorted({display for token, display in {**profile_skills, **preferred}.items() if token in description})
    missing = sorted([skill for skill in profile.skills if skill not in matched])

    role_bonus = 20 if any(role.lower() in posting.title.lower() for role in profile.target_roles or [profile.title]) else 0
    location_bonus = 10 if any(loc.lower() in posting.location.lower() for loc in profile.target_locations or [profile.location]) else 0
    skill_score = min(len(matched) * 12, 60)
    tag_score = min(len(posting.tags) * 2, 10)
    score = min(skill_score + role_bonus + location_bonus + tag_score, 100)

    rationale = (
        f"Matched {len(matched)} relevant keywords, role alignment bonus {role_bonus}, "
        f"location bonus {location_bonus}, and tag signal {tag_score}."
    )
    return JobMatch(
        job=posting,
        score=float(score),
        matched_skills=matched,
        missing_skills=missing,
        rationale=rationale,
    )


def build_resume_draft(profile: CandidateProfile, match: JobMatch) -> ResumeDraft:
    tailored_bullets: list[str] = []
    emphasized = match.matched_skills[:5]
    for item in profile.experience[:3]:
        for achievement in item.achievements[:2]:
            tailored_bullets.append(
                f"{achievement} while building strengths in {', '.join(emphasized) or 'cross-functional delivery'}."
            )

    headline = f"{profile.title} targeting {match.job.title} at {match.job.company}"
    summary = list(profile.summary[:3])
    if emphasized:
        summary.append(
            f"Strong alignment with {match.job.company}'s needs in {', '.join(emphasized)}."
        )

    ordered_skills = list(dict.fromkeys(match.matched_skills + profile.skills))
    return ResumeDraft(
        headline=headline,
        summary=summary,
        skills=ordered_skills[:12],
        selected_experience=profile.experience[:3],
        tailored_bullets=tailored_bullets[:6],
        target_job_title=match.job.title,
        target_company=match.job.company,
    )


def render_resume(template_dir: Path, profile: CandidateProfile, draft: ResumeDraft) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("resume.md.j2")
    return template.render(profile=profile, draft=draft)


def build_application_notes(profile: CandidateProfile, matches: list[JobMatch]) -> str:
    lines = [
        f"# Application Notes for {profile.name}",
        "",
        "## Recommended priorities",
    ]
    for index, match in enumerate(matches, start=1):
        lines.append(
            f"{index}. {match.job.title} at {match.job.company} ({match.score:.0f}/100) - {match.rationale}"
        )
    lines.extend(
        [
            "",
            "## Outreach angle",
            "Lead with quantified impact, emphasize the matched skills, and mention why the company mission fits your background.",
        ]
    )
    return "\n".join(lines)


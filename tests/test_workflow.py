from pathlib import Path

from job_resume_agent.workflow import AgenticJobSearchWorkflow


def test_demo_workflow(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = AgenticJobSearchWorkflow(root)
    artifacts = workflow.run(
        profile_path=root / "data" / "sample_profile.yaml",
        sources=[str(root / "data" / "sample_jobs.html")],
        outdir=tmp_path,
        top_k=2,
    )

    assert len(artifacts.jobs) == 3
    assert len(artifacts.matches) == 2
    assert artifacts.matches[0].score >= artifacts.matches[1].score
    assert "Jane Doe" in (tmp_path / "tailored_resume.md").read_text(encoding="utf-8")
    assert (tmp_path / "workflow_report.md").exists()

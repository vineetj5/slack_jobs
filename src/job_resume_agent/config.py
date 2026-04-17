from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    user_agent: str = os.getenv(
        "JOB_RESUME_AGENT_USER_AGENT",
        "job-resume-agent/0.1 (+local project)",
    )

    @staticmethod
    def template_dir(project_root: Path) -> Path:
        return project_root / "templates"


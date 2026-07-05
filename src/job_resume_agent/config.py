from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    user_agent: str = os.getenv(
        "JOB_NOTIFIER_USER_AGENT",
        "job-notifier/0.1 (+local project)",
    )

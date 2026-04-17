import pytest

from job_resume_agent.greenhouse import normalize_greenhouse_board, role_matches_title


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("openai", "openai"),
        ("https://boards.greenhouse.io/openai", "openai"),
        ("https://boards.greenhouse.io/openai/jobs/12345", "openai"),
        ("https://job-boards.greenhouse.io/openai", "openai"),
        ("https://boards-api.greenhouse.io/v1/boards/openai/jobs?content=true", "openai"),
    ],
)
def test_normalize_greenhouse_board(value: str, expected: str) -> None:
    assert normalize_greenhouse_board(value) == expected


@pytest.mark.parametrize(
    "title",
    [
        "Machine Learning Engineer, Infrastructure",
        "New Grad Software Engineer, Data Platform",
        "Healthcare Data Scientist",
        "C/C++ Engineer - Computer Vision",
    ],
)
def test_role_matches_title(title: str) -> None:
    assert role_matches_title(title)


def test_role_does_not_match_unrelated_title() -> None:
    assert not role_matches_title("Payroll Manager")

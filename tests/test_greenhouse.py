# pyrefly: ignore [missing-import]
import pytest

from job_resume_agent.greenhouse import get_target_region, normalize_greenhouse_board, role_matches_title


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


@pytest.mark.parametrize(
    ("title", "should_match"),
    [
        ("Data Analyst II", True),         # High similarity to "Data Analyst"
        ("Junior Data Analyst", True),     # High similarity to "Data Analyst" / "Junior Data Analyst"
        ("Finance Manager", False),        # Unrelated domain, no 70%+ similarity matching target roles
        ("Director of Data Science", False), # Low similarity to "Data Scientist" / "Data Engineer"
    ],
)
def test_role_similarity_threshold(title: str, should_match: bool) -> None:
    assert role_matches_title(title) == should_match


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("New York, NY", "USA"),
        ("Remote, United States", "USA"),
        ("US", "USA"),
        ("Bengaluru, India", "INDIA"),
        ("Toronto, Canada", None),
        ("London, UK", None),
        ("Remote", None),
        ("Unknown", None),
    ],
)
def test_get_target_region_requires_explicit_usa_signal(location: str, expected: str | None) -> None:
    assert get_target_region(location) == expected

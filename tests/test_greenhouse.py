# pyrefly: ignore [missing-import]
import pytest

from job_resume_agent.greenhouse import (
    get_target_region,
    normalize_greenhouse_board,
    role_matches_title,
    is_india_internship_title,
    role_matches_title_india,
)


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


def test_is_india_internship_title() -> None:
    assert is_india_internship_title("Software Engineer Intern")
    assert is_india_internship_title("SDE Intern")
    assert is_india_internship_title("Data Analyst Internship")
    assert is_india_internship_title("AI co-op")
    assert not is_india_internship_title("Marketing Intern")
    assert not is_india_internship_title("Software Engineer")


def test_role_matches_title_india() -> None:
    assert role_matches_title_india("Software Engineer Intern")
    assert role_matches_title_india("SDE Intern")
    assert role_matches_title_india("Data Analyst II")
    assert not role_matches_title_india("Staff Software Engineer Intern")
    assert not role_matches_title_india("Finance Manager")


def test_check_experience_india() -> None:
    from job_resume_agent.greenhouse import check_experience
    # 1. Internship titles should always be True for India
    assert check_experience("Required: 5 years of experience", region="INDIA", title="SDE Intern")
    
    # 2. "new grad" in description/title should be True for India
    assert check_experience("Required: 3 years of experience. Target: new grads.", region="INDIA", title="Software Engineer")
    assert check_experience("Required: 3 years of experience.", region="INDIA", title="New Grad Software Engineer")

    # 3. India experience filter (min experience <= 1 year)
    assert check_experience("We require 0 years of experience.", region="INDIA", title="Software Engineer")
    assert check_experience("We require 0+ years of experience.", region="INDIA", title="Software Engineer")
    assert check_experience("We require 1+ years of experience.", region="INDIA", title="Software Engineer")
    assert check_experience("We require 0-1 years of experience.", region="INDIA", title="Software Engineer")
    assert check_experience("We require 1 year of experience.", region="INDIA", title="Software Engineer")
    assert not check_experience("We require 2 years of experience.", region="INDIA", title="Software Engineer")
    assert not check_experience("We require 2+ years of experience.", region="INDIA", title="Software Engineer")

    # 4. Default / USA experience filter (min experience <= 3 years)
    assert check_experience("We require 2+ years of experience.", region="USA", title="Software Engineer")
    assert not check_experience("We require 4+ years of experience.", region="USA", title="Software Engineer")

from run_workday_jobs import parse_workday_url


def test_parse_myworkdayjobs_url_with_dc_and_query() -> None:
    feed = parse_workday_url(
        "Nvidia",
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?locationHierarchy1=abc123&q=software+engineer",
    )

    assert feed.company == "Nvidia"
    assert feed.tenant == "nvidia"
    assert feed.site == "NVIDIAExternalCareerSite"
    assert feed.api_base == "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite"
    assert feed.public_base == "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
    assert feed.search_text == "software engineer"
    assert feed.applied_facets == {"locationHierarchy1": ["abc123"]}


def test_parse_localized_job_url() -> None:
    feed = parse_workday_url(
        "Adobe",
        "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/Austin/Software-Engineer_R1",
    )

    assert feed.tenant == "adobe"
    assert feed.site == "external_experienced"
    assert feed.api_base == "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced"


def test_parse_cxs_api_url() -> None:
    feed = parse_workday_url(
        "Intel",
        "https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/External/jobs",
    )

    assert feed.tenant == "intel"
    assert feed.site == "External"
    assert feed.public_base == "https://intel.wd1.myworkdayjobs.com/External"


def test_parse_myworkdaysite_url() -> None:
    feed = parse_workday_url(
        "Example",
        "https://wd1.myworkdaysite.com/recruiting/example/External",
    )

    assert feed.tenant == "example"
    assert feed.site == "External"
    assert feed.api_base == "https://wd1.myworkdaysite.com/wday/cxs/example/External"
    assert feed.public_base == "https://wd1.myworkdaysite.com/recruiting/example/External"

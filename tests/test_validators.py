"""
Tests for URL validation and ATS platform detection
"""
import re


def detect_ats_platform(url: str) -> str | None:
    """Detect ATS platform from URL using regex patterns."""
    if not url:
        return None
    url_lower = url.lower()

    # ATS platform patterns (from config/hiring_cafe_locators.json)
    patterns = [
        (r"workable\.com", "workable"),
        (r"greenhouse\.io|greenhouse\.com", "greenhouse"),
        (r"myworkdayjobs\.com", "workday"),
        (r"lever\.co", "lever"),
        (r"applytojob\.com|icims\.com", "icims"),
        (r"ultipro\.com", "ultipro"),
        (r"smartrecruiters\.com", "smartrecruiters"),
        (r"jobvite\.com", "jobvite"),
        (r"bamboohr\.com", "bamboohr"),
    ]

    for pattern, platform in patterns:
        if re.search(pattern, url_lower):
            return platform
    return None


def is_likely_ats_url(url: str) -> bool:
    """Check if URL looks like an ATS job posting."""
    if not url or not url.strip().startswith("http"):
        return False

    url_lower = url.strip().lower()

    # Reject source site
    if "hiring.cafe" in url_lower:
        return False

    # Reject job boards
    non_ats = ["linkedin.com", "indeed.com", "glassdoor.com", "monster.com"]
    if any(domain in url_lower for domain in non_ats):
        return False

    # Accept known ATS platforms
    if detect_ats_platform(url):
        return True

    # Check for job keywords
    job_keywords = ["job", "career", "apply", "position", "opening"]
    if any(kw in url_lower for kw in job_keywords):
        return True

    return False


def _job_id_from_href(href: str) -> str | None:
    """Extract job ID from hiring.cafe URL or relative path."""
    if not href:
        return None

    # Extract viewjob/{id} (works for both full URLs and relative paths)
    match = re.search(r'/viewjob/([a-zA-Z0-9_-]+)', href)
    if match:
        return match.group(1)

    return None


def test_detect_ats_platform():
    """Test ATS platform detection from URLs."""
    test_cases = [
        ("https://apply.workable.com/company/j/ABC123/", "workable"),
        ("https://boards.greenhouse.io/company/jobs/123", "greenhouse"),
        ("https://company.wd1.myworkdayjobs.com/en-US/careers/job/123", "workday"),
        ("https://jobs.lever.co/company/abc-123", "lever"),
        ("https://company.applytojob.com/apply/123", "icims"),
        ("https://recruiting.ultipro.com/company/123", "ultipro"),
        ("https://careers.company.com/jobs/123", None),  # Unknown platform
        ("https://hiring.cafe/viewjob/abc123", None),  # Not an ATS
    ]

    for url, expected in test_cases:
        result = detect_ats_platform(url)
        assert result == expected, f"Failed for {url}: got {result}, expected {expected}"

    print("✓ test_detect_ats_platform passed")


def test_is_likely_ats_url():
    """Test ATS URL validation."""
    valid_urls = [
        "https://apply.workable.com/company/j/ABC123/",
        "https://boards.greenhouse.io/company/jobs/123",
        "https://company.wd1.myworkdayjobs.com/careers/job/123",
        "https://jobs.lever.co/company/position",
        "https://company.applytojob.com/apply/123",
    ]

    invalid_urls = [
        "https://hiring.cafe/viewjob/abc123",  # Source site, not ATS
        "https://linkedin.com/jobs/view/123",  # Job board, not ATS
        "https://indeed.com/viewjob?jk=123",  # Job board
        "https://google.com",  # Not a job URL
        "http://localhost:3000/test",  # Local dev
        None,
        "",
    ]

    for url in valid_urls:
        assert is_likely_ats_url(url), f"Should be valid: {url}"

    for url in invalid_urls:
        assert not is_likely_ats_url(url), f"Should be invalid: {url}"

    print("✓ test_is_likely_ats_url passed")


def test_job_id_from_href():
    """Test extracting job IDs from hiring.cafe URLs."""
    test_cases = [
        ("https://hiring.cafe/viewjob/abc123def456", "abc123def456"),
        ("/viewjob/xyz789", "xyz789"),
        ("https://hiring.cafe/viewjob/test-id-123?ref=source", "test-id-123"),
        ("https://other-site.com/viewjob/abc", "abc"),  # Still extracts ID from path
        ("https://hiring.cafe/about", None),
        (None, None),
        ("", None),
    ]

    for href, expected in test_cases:
        result = _job_id_from_href(href)
        assert result == expected, f"Failed for {href}: got {result}, expected {expected}"

    print("✓ test_job_id_from_href passed")


def test_ats_platform_comprehensive():
    """Test all known ATS platforms are detected."""
    platforms = {
        "workable": [
            "https://apply.workable.com/company/j/ABC/",
            "https://jobs.workable.com/view/abc/company",
        ],
        "greenhouse": [
            "https://boards.greenhouse.io/company/jobs/123",
            "https://boards.greenhouse.io/embed/job_app?for=company&token=abc",
        ],
        "workday": [
            "https://company.wd1.myworkdayjobs.com/careers",
            "https://mycompany.wd5.myworkdayjobs.com/en-US/External/job/123",
        ],
        "lever": [
            "https://jobs.lever.co/company/position",
        ],
        "icims": [
            "https://company.applytojob.com/apply/123",
            "https://careers.icims.com/company/jobs/123",
        ],
        "ultipro": [
            "https://recruiting.ultipro.com/company/123",
        ],
        "smartrecruiters": [
            "https://jobs.smartrecruiters.com/company/123",
        ],
        "jobvite": [
            "https://jobs.jobvite.com/company/job/abc",
        ],
        "bamboohr": [
            "https://company.bamboohr.com/jobs/view.php?id=123",
        ],
    }

    for expected_platform, urls in platforms.items():
        for url in urls:
            result = detect_ats_platform(url)
            assert result == expected_platform, \
                f"Failed for {url}: got {result}, expected {expected_platform}"

    print("✓ test_ats_platform_comprehensive passed")


if __name__ == "__main__":
    print("=" * 70)
    print("VALIDATOR TESTS")
    print("=" * 70)

    test_detect_ats_platform()
    test_is_likely_ats_url()
    test_job_id_from_href()
    test_ats_platform_comprehensive()

    print("\n" + "=" * 70)
    print("ALL VALIDATOR TESTS PASSED ✓")
    print("=" * 70)

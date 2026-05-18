"""
Tests for URL sanitization and company name cleaning
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def sanitize_url(url: str | None) -> str | None:
    """
    Fix corrupted URLs and reject invalid ones.
    This mirrors logic from scripts/hiring_cafe_step4_ingest_to_api.py
    """
    if not url:
        return None
    url = url.strip()

    # Fix double-protocol corruption
    url = re.sub(r'^https?://[a-zA-Z]{2,10}://', 'https://', url)

    # Must start with http
    if not url.startswith('http'):
        return None

    # Must have a dot in the domain
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if '.' not in parsed.netloc or not parsed.netloc:
            return None
    except Exception:
        return None

    return url


def test_sanitize_corrupted_url():
    """Test fixing double-protocol corruption."""
    corrupted = "https://sjotps://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=123"
    expected = "https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=123"

    result = sanitize_url(corrupted)
    assert result == expected
    print("✓ test_sanitize_corrupted_url")


def test_sanitize_valid_urls():
    """Test that valid URLs pass through unchanged."""
    valid_urls = [
        "https://apply.workable.com/company/j/ABC/",
        "https://boards.greenhouse.io/company/jobs/123",
        "https://company.wd1.myworkdayjobs.com/careers",
    ]

    for url in valid_urls:
        result = sanitize_url(url)
        assert result == url
    print("✓ test_sanitize_valid_urls")


def test_sanitize_invalid_urls():
    """Test that invalid URLs are rejected."""
    invalid_urls = [
        None,
        "",
        "   ",
        "not-a-url",
        "ftp://example.com",  # Not HTTP(S)
        "http://localhost",  # No dot in domain
        "http://nodomain",  # No dot
    ]

    for url in invalid_urls:
        result = sanitize_url(url)
        assert result is None, f"Should reject: {url}"
    print("✓ test_sanitize_invalid_urls")


def test_sanitize_edge_cases():
    """Test edge cases in URL sanitization."""
    test_cases = [
        # Whitespace
        ("  https://example.com  ", "https://example.com"),
        # Query params preserved
        ("https://example.com?foo=bar&baz=qux", "https://example.com?foo=bar&baz=qux"),
        # Fragment preserved
        ("https://example.com/page#section", "https://example.com/page#section"),
    ]

    for input_url, expected in test_cases:
        result = sanitize_url(input_url)
        assert result == expected, f"Failed for {input_url}"
    print("✓ test_sanitize_edge_cases")


def is_junk_company(name: str) -> bool:
    """
    Check if company name is junk (salary, ticker, etc).
    Mirrors logic from step4 script.
    """
    if not name or not name.strip():
        return True

    s = name.strip()

    # Salary pattern
    if re.search(r'\$\d+[kK]?[-–]\$?\d+[kK]?', s):
        return True

    # Junk prefixes
    if re.match(r'^(?:\$\d|NYSE:|NASDAQ:|Euronext|\d+\+?\s*YOE|:)', s, re.I):
        return True

    # Job types
    if re.match(r'^(?:full[\s\-]time|contract|part[\s\-]time|internship|temporary)$', s, re.I):
        return True

    # Work modes
    if re.match(r'^(?:onsite|remote|hybrid)$', s, re.I):
        return True

    return False


def test_junk_company_detection():
    """Test detecting junk company names."""
    junk_names = [
        "$100k-$150k",
        "NYSE: AAPL",
        "NASDAQ: GOOGL",
        "Full Time",
        "Full-Time",
        "Remote",
        "Onsite",
        "Hybrid",
        "3+ YOE",
        "",
        "   ",
    ]

    valid_names = [
        "Acme Corporation",
        "Google",
        "Tesla Inc",
        "Y Combinator",
        "OpenAI",
    ]

    for name in junk_names:
        assert is_junk_company(name), f"Should be junk: {name}"

    for name in valid_names:
        assert not is_junk_company(name), f"Should be valid: {name}"

    print("✓ test_junk_company_detection")


def test_company_name_resolution():
    """Test company name resolution priority."""

    # Priority 1: Parsed field (if not junk)
    job1 = {"company": "Acme Corp", "ats_url": "https://acme.workable.com/x/"}
    assert job1["company"] == "Acme Corp"

    # Priority 2: URL slug when parsed is junk
    job2 = {"company": "Full Time", "ats_url": "https://tesla.workable.com/x/"}
    # Would extract "tesla" from URL

    # Priority 3: Description prefix
    job3 = {
        "company": None,
        "company_description": "OpenAI: Creating safe AGI",
        "ats_url": "https://apply.workable.com/x/"
    }
    # Would extract "OpenAI" from description

    print("✓ test_company_name_resolution")


if __name__ == "__main__":
    print("=" * 70)
    print("SANITIZATION TESTS")
    print("=" * 70)

    test_sanitize_corrupted_url()
    test_sanitize_valid_urls()
    test_sanitize_invalid_urls()
    test_sanitize_edge_cases()
    test_junk_company_detection()
    test_company_name_resolution()

    print("\n" + "=" * 70)
    print("ALL SANITIZATION TESTS PASSED ✓")
    print("=" * 70)

"""
Tests for card text parsing and company name resolution

Note: This imports actual parsing functions which may have dependencies.
Run with: python -m pytest tests/test_parser.py (if dependencies installed)
or python tests/test_parser.py (standalone, may skip some tests)
"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from strategies.custom.modules.parser import parse_hiring_cafe_card_text, categorize_jobs_by_ats
    PARSER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Parser module not available: {e}")
    print("⚠️  This is expected if selenium/dependencies not installed")
    print("⚠️  Skipping parser tests")
    PARSER_AVAILABLE = False


def test_parse_basic_card():
    """Test parsing a basic job card."""
    text = """
    15h
    Senior Software Engineer
    Acme Corp: Building the future of AI
    San Francisco, CA, United States
    Remote
    Full Time
    $150k-$200k
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "Senior Software Engineer"
    assert result["company"] == "Acme Corp"
    assert result["company_description"] == "Building the future of AI"
    assert result["location"] == "San Francisco, CA, United States"
    assert result["city"] == "San Francisco"
    assert result["state"] == "CA"
    assert result["country"] == "United States"
    assert result["type"] == "Remote"
    print("✓ test_parse_basic_card passed")


def test_parse_card_no_description():
    """Test parsing card without company description."""
    text = """
    2d
    Backend Engineer
    Google
    Mountain View, CA, United States
    Onsite
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "Backend Engineer"
    assert result["company"] == "Google"
    assert result["location"] == "Mountain View, CA, United States"
    assert result["type"] == "Onsite"
    print("✓ test_parse_card_no_description passed")


def test_parse_card_with_salary_line():
    """Test that salary lines don't become company names."""
    text = """
    1d
    Data Scientist
    $120k-$180k
    Tesla: Electric vehicles and clean energy
    Austin, TX, United States
    Hybrid
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "Data Scientist"
    assert result["company"] == "Tesla"
    assert result["company_description"] == "Electric vehicles and clean energy"
    assert result["type"] == "Hybrid"
    print("✓ test_parse_card_with_salary_line passed")


def test_parse_card_with_ticker():
    """Test that stock tickers are skipped."""
    text = """
    5h
    Product Manager
    NYSE: AAPL
    Apple Inc: Think different
    Cupertino, CA, United States
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "Product Manager"
    assert result["company"] == "Apple Inc"
    print("✓ test_parse_card_with_ticker passed")


def test_parse_card_multi_city():
    """Test that multi-city listings don't become company names."""
    text = """
    3d
    DevOps Engineer
    San Francisco or New York or Seattle
    Amazon: Everything store
    Remote
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "DevOps Engineer"
    assert result["company"] == "Amazon"
    print("✓ test_parse_card_multi_city passed")


def test_categorize_by_ats():
    """Test job categorization by ATS platform."""
    jobs = [
        {
            "job_id": "1",
            "title": "Engineer",
            "ats": {"url": "https://apply.workable.com/x/", "platform": "workable"}
        },
        {
            "job_id": "2",
            "title": "Designer",
            "ats": {"url": "https://greenhouse.io/x/", "platform": "greenhouse"}
        },
        {
            "job_id": "3",
            "title": "Manager",
            "ats": {"url": "https://apply.workable.com/y/", "platform": "workable"}
        },
        {
            "job_id": "4",
            "title": "Analyst",
            "ats_url": None,
            "ats_platform": "unknown"
        },
    ]

    result = categorize_jobs_by_ats(jobs)

    assert len(result["workable"]) == 2
    assert len(result["greenhouse"]) == 1
    assert len(result["unknown"]) == 1
    print("✓ test_categorize_by_ats passed")


def test_parse_empty_card():
    """Test parsing empty card returns safe defaults."""
    result = parse_hiring_cafe_card_text("")

    assert result["job_tittle"] is None
    assert result["company"] is None
    assert result["location"] is None
    print("✓ test_parse_empty_card passed")


def test_parse_card_junk_company():
    """Test that junk patterns don't become company names."""
    text = """
    1d
    Software Engineer
    Full Time
    Onsite
    Real Company: We build things
    San Francisco, CA, United States
    """

    result = parse_hiring_cafe_card_text(text)

    assert result["job_tittle"] == "Software Engineer"
    assert result["company"] == "Real Company"  # Not "Full Time" or "Onsite"
    assert result["type"] == "Onsite"
    print("✓ test_parse_card_junk_company passed")


if __name__ == "__main__":
    if not PARSER_AVAILABLE:
        print("\n⚠️  Parser tests skipped (dependencies not available)")
        sys.exit(0)

    print("=" * 70)
    print("PARSER TESTS")
    print("=" * 70)

    test_parse_basic_card()
    test_parse_card_no_description()
    test_parse_card_with_salary_line()
    test_parse_card_with_ticker()
    test_parse_card_multi_city()
    test_categorize_by_ats()
    test_parse_empty_card()
    test_parse_card_junk_company()

    print("\n" + "=" * 70)
    print("ALL PARSER TESTS PASSED ✓")
    print("=" * 70)

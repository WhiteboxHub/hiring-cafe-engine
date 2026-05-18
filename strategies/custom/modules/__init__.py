"""
Hiring Cafe Strategy Modules

Refactored from the monolithic hiring_cafe.py into focused modules:
- validators.py: URL validation, junk detection, ATS platform detection
- parser.py: Card text parsing, company name resolution
- scraper.py: Scrolling, URL extraction, job listing extraction
- ats_extractor.py: ATS URL extraction logic with multi-layer fallback
"""

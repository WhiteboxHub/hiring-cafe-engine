/*
  Job Application Engine - DuckDB Schema
  Single database for both configuration and history
  Version: 1.0
*/

-- =====================================================
-- CONFIGURATION TABLES
-- =====================================================

-- 1. ATS Platforms (Strategy Definitions)
CREATE TABLE IF NOT EXISTS ats_platforms (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    class_handler VARCHAR(100) NOT NULL,  -- e.g., 'strategies.custom.InsightGlobalStrategy'
    is_headless_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Job Sites (Company Configurations)
CREATE TABLE IF NOT EXISTS job_sites (
    id INTEGER PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,
    ats_platform_id INTEGER,
    category VARCHAR(50) NOT NULL CHECK (category IN ('System integrator', 'Consulting firm', 'Staffing vendor', 'Product Company')),
    
    -- Navigation & Templates
    search_url_template TEXT NOT NULL,  -- URL with {keyword}, {location} placeholders
    apply_url_template TEXT,            -- URL with {job_id} placeholder
    
    -- Bot Defense & Network
    cf_clearance_required BOOLEAN DEFAULT FALSE,
    proxy_region VARCHAR(10) DEFAULT 'US',
    
    -- Operational Flags
    is_active BOOLEAN DEFAULT TRUE,
    max_applications_per_run INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (ats_platform_id) REFERENCES ats_platforms(id)
);

-- 3. Site Selectors (CSS/XPath Configurations as JSON)
CREATE TABLE IF NOT EXISTS site_selectors (
    id INTEGER PRIMARY KEY,
    ats_platform_id INTEGER,  -- Default selectors for generic ATS
    job_site_id INTEGER,      -- Specific override for a single site
    
    type VARCHAR(20) NOT NULL CHECK (type IN ('listing', 'application')),
    config_json JSON NOT NULL,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (ats_platform_id) REFERENCES ats_platforms(id),
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- 4. Job Listings (Discovered Jobs Queue)
CREATE SEQUENCE IF NOT EXISTS job_listings_id_seq;
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY DEFAULT nextval('job_listings_id_seq'),
    job_site_id INTEGER NOT NULL,
    
    -- Job Data
    external_job_id VARCHAR(100) NOT NULL,
    job_title VARCHAR(255),
    job_url TEXT NOT NULL,
    
    -- Pipeline State
    status VARCHAR(20) DEFAULT 'discovered' CHECK (status IN ('discovered', 'ready_to_apply', 'applied', 'failed', 'blacklisted')),
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (job_site_id, external_job_id),
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- =====================================================
-- HISTORY TABLES
-- =====================================================

-- 5. Applications (Submission History)
CREATE SEQUENCE IF NOT EXISTS applications_id_seq;
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY DEFAULT nextval('applications_id_seq'),
    job_site_id INTEGER NOT NULL,
    job_listing_id INTEGER,
    
    job_title VARCHAR(255),
    job_url TEXT,
    
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
    error_message TEXT,
    
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id),
    FOREIGN KEY (job_listing_id) REFERENCES job_listings(id)
);

-- 6. Metrics (Performance Tracking)
CREATE TABLE IF NOT EXISTS metrics (
    id BIGINT PRIMARY KEY,
    run_date DATE NOT NULL,
    job_site_id INTEGER,
    
    total_jobs_found INTEGER DEFAULT 0,
    total_applications_attempted INTEGER DEFAULT 0,
    total_applications_successful INTEGER DEFAULT 0,
    total_applications_failed INTEGER DEFAULT 0,
    
    avg_application_time_seconds FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- =====================================================
-- SEED DATA: Insight Global Configuration
-- =====================================================

-- Insert Strategy
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (1, 'Insight Global Custom', 'strategies.custom.InsightGlobalStrategy', false);

-- Insert Site
INSERT OR IGNORE INTO job_sites (
    id,
    company_name,
    domain,
    ats_platform_id,
    category,
    search_url_template,
    apply_url_template,
    cf_clearance_required,
    is_active
)
VALUES (
    1,
    'Insight Global',
    'insightglobal.com',
    1,
    'Staffing vendor',
    'https://insightglobal.com/jobs/',
    'https://jobs.insightglobal.com/users/jobapplynoaccount.aspx?jobid={job_id}',
    false,
    true
);

-- Insert Listing Selectors
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    1,
    1,
    'listing',
    '{
        "container": "div.result",
        "pagination_type": "click_next",
        "pagination_selector": "a[title=\"Page Forward\"]",
        "fields": {
            "job_id": {
                "selector": "button[id=\"btnSaveJob\"]",
                "attr": "jobId"
            },
            "title": {
                "selector": ".job-title a",
                "type": "text"
            },
            "url": {
                "selector": ".job-title a",
                "attr": "href"
            }
        }
    }'::JSON
);

-- Insert Application Selectors
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    2,
    1,
    'application',
    '{
        "flow_type": "legacy_form",
        "form_fields": {
            "first_name": "input[name*=\"FirstName\"]",
            "last_name": "input[name*=\"LastName\"]",
            "email": "input[name*=\"Email\"]",
            "phone": "input[name*=\"Phone\"]",
            "resume_upload": "input[type=\"file\"]",
            "submit_btn": "#ContentPlaceHolder1_cmdApply"
        }
    }'::JSON
);

-- =====================================================
-- SEED DATA: LanceSoft Configuration
-- =====================================================

-- Insert JobDiva ATS Platform
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required) VALUES (
    2,
    'JobDiva',
    'strategies.custom.LanceSoftStrategy',
    false  -- Keep browser visible for debugging
);

-- Insert LanceSoft Job Site
INSERT OR IGNORE INTO job_sites (id, ats_platform_id, company_name, domain, category, search_url_template, is_active) VALUES (
    2,
    2,
    'LanceSoft',
    'lancesoft.com',
    'Staffing vendor',
    'https://www2.jobdiva.com/portal/?a=3djdnw5yqdh8wl3frr5t6561tvvokq01affwpxt3lcutzo4f8yt1aeiy3msk02or&compid=0&SearchString=',
    true  -- Enabled for active job searching
);

-- Insert LanceSoft Listing Selectors (for job discovery)
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (
    3,
    2,
    'listing',
    '{
        "search_input": "#root > div > div > div:nth-child(2) > div:nth-child(1) > div > div.col > form > div > input",
        "search_button": "button.btn.jd-btn",
        "container": "div.list-group-item.list-group-item-action",
        "pagination_type": "click_next",
        "pagination_selector": "button.jd-btn-outline.jd-btn-small.jd-btn-square[aria-label=\"Next Page\"]",
        "fields": {
            "title": {
                "selector": "span.text-capitalize.jd-nav-label.notranslate",
                "type": "text"
            },
            "details_button": {
                "selector": "button.btn.jd-btn",
                "type": "button"
            },
            "job_id": {
                "selector": "div.d-flex.text-muted small:nth-child(3)",
                "type": "text"
            },
            "location": {
                "selector": "div.d-flex.text-muted small:nth-child(4)",
                "type": "text"
            },
            "salary": {
                "selector": "div.d-flex.text-muted small:nth-child(1)",
                "type": "text"
            }
        }
    }'::JSON
);

-- Insert LanceSoft Application Selectors (for applying to jobs)
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (
    4,
    2,
    'application',
    '{
        "flow_type": "jobdiva_portal",
        "apply_button": "#root > div > div > div:nth-child(4) > div:nth-child(1) > button",
        "quick_apply_option": "#applyOptionsModal > div > div > div.modal-body > div > button:nth-child(3) > span",
        "form_fields": {
            "first_name": "input[placeholder*=\"First Name\" i]",
            "last_name": "input[placeholder*=\"Last Name\" i]",
            "email": "input[type=\"email\"]",
            "phone": "input[type=\"tel\"]",
            "resume_upload": "#quickApplyModal > div > div > div:nth-child(1) > div.modal-body-main.notranslate > div > div > div:nth-child(4) > div > div:nth-child(1) > div > div:nth-child(5) > label > svg",
            "submit_btn": "#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button",
            "next_btn": "button.btn.jd-btn-outline"
        },
        "eeo_form": {
            "gender_no_answer": "input[type=\"radio\"][value*=\"not wish\" i]",
            "ethnicity_no_answer": "#quickApplyModal > div > div > div:nth-child(1) > div.modal-body-main.notranslate > div.job-app-main > div > div:nth-child(3) > div:nth-child(4)",
            "race_asian": "#quickApplyModal > div > div > div:nth-child(1) > div.modal-body-main.notranslate > div.job-app-main > div > div:nth-child(4) > div:nth-child(5) > span.radio-buttons-label",
            "veteran_no_answer": "#quickApplyModal > div > div > div:nth-child(1) > div.modal-body-main.notranslate > div.job-app-main > div > div.radio-buttons-div > div:nth-child(7) > input[type=checkbox]",
            "save_btn": "#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button > span > span"
        }
    }'::JSON
);


-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active);
CREATE INDEX IF NOT EXISTS idx_job_listings_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at);
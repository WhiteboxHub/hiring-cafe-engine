import duckdb
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

# Connect to database
conn = duckdb.connect(settings.DUCKDB_PATH)

print("=" * 70)
print("DATABASE CONTENT SUMMARY")
print("=" * 70)

# Show all tables
print("\n📊 TABLES IN DATABASE:")
tables = conn.execute("SHOW TABLES").fetchall()
for table in tables:
    print(f"  ✓ {table[0]}")

# Row counts
print("\n📈 ROW COUNTS:")
for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
    print(f"  {table[0]}: {count} rows")

# Configuration data
print("\n" + "=" * 70)
print("CONFIGURATION DATA")
print("=" * 70)

print("\n🔧 ATS PLATFORMS:")
platforms = conn.execute("SELECT id, name, class_handler FROM ats_platforms").fetchall()
for p in platforms:
    print(f"  ID {p[0]}: {p[1]} -> {p[2]}")

print("\n🏢 JOB SITES:")
sites = conn.execute("SELECT id, company_name, domain, category, is_active FROM job_sites").fetchall()
for s in sites:
    status = "✓ Active" if s[4] else "✗ Inactive"
    print(f"  ID {s[0]}: {s[1]} ({s[2]}) - {s[3]} [{status}]")

print("\n🎯 SITE SELECTORS:")
selectors = conn.execute("SELECT id, job_site_id, type FROM site_selectors").fetchall()
for sel in selectors:
    print(f"  ID {sel[0]}: Job Site {sel[1]} - Type: {sel[2]}")

# History data
print("\n" + "=" * 70)
print("HISTORY DATA")
print("=" * 70)

job_count = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
print(f"\n📋 JOB LISTINGS: {job_count} jobs discovered")

if job_count > 0:
    print("\n  Status breakdown:")
    statuses = conn.execute("SELECT status, COUNT(*) FROM job_listings GROUP BY status").fetchall()
    for status in statuses:
        print(f"    - {status[0]}: {status[1]}")

app_count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
print(f"\n✉️ APPLICATIONS: {app_count} applications submitted")

if app_count > 0:
    print("\n  Status breakdown:")
    app_statuses = conn.execute("SELECT status, COUNT(*) FROM applications GROUP BY status").fetchall()
    for status in app_statuses:
        print(f"    - {status[0]}: {status[1]}")

metrics_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
print(f"\n📊 METRICS: {metrics_count} metric records")

conn.close()

print("\n" + "=" * 70)
print("✅ Database check complete!")
print("=" * 70)

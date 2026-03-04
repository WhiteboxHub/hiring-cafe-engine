import csv
from pathlib import Path
from datetime import datetime


class CSVTracker:
    def __init__(self, directory: str = "data"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file(self, site_name: str) -> Path:
        return self.directory / f"{site_name}_jobs.csv"

    def _headers(self):
        return [
            "external_id",
            "job_title",
            "job_url",
            "location",
            "job_type",
            "salary",
            "description",
            "requirements",
            "posted_date",
            "company",
            "industry",
            "status",
            "attempts",
            "last_error",
            "discovered_at",
            "updated_at",
        ]

    def ensure_file(self, site_name: str):
        f = self._file(site_name)
        if not f.exists():
            with f.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self._headers())
                writer.writeheader()

    def _read(self, site_name: str):
        f = self._file(site_name)
        if not f.exists():
            return []
        with f.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return list(reader)

    def _write(self, site_name: str, rows):
        f = self._file(site_name)
        with f.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self._headers())
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    def add_discovered_jobs(self, site_name: str, jobs: list) -> int:
        """Appends new jobs that are not already present. Returns number of new rows added."""
        self.ensure_file(site_name)
        existing = {r['job_url'] for r in self._read(site_name)}
        to_append = []
        now = datetime.utcnow().isoformat()
        for job in jobs:
            url = job.get('job_url')
            if not url or url in existing:
                continue
            to_append.append({
                'external_id': job.get('external_id', ''),
                'job_title': job.get('job_title', ''),
                'job_url': url,
                'location': job.get('location', ''),
                'job_type': job.get('job_type', ''),
                'salary': job.get('salary', ''),
                'description': job.get('description', ''),
                'requirements': job.get('requirements', ''),
                'posted_date': job.get('posted_date', ''),
                'company': job.get('company', ''),
                'industry': job.get('industry', ''),
                'status': 'discovered',
                'attempts': '0',
                'last_error': '',
                'discovered_at': now,
                'updated_at': now,
            })
        if to_append:
            f = self._file(site_name)
            with f.open('a', newline='', encoding='utf-8') as fh:
                writer = csv.DictWriter(fh, fieldnames=self._headers())
                for r in to_append:
                    writer.writerow(r)
        return len(to_append)

    def update_job_status(self, site_name: str, job_url: str, status: str, attempts_inc: int = 0, last_error: str | None = None) -> bool:
        """Updates the row for job_url. Returns True when an update happened."""
        self.ensure_file(site_name)
        rows = self._read(site_name)
        changed = False
        now = datetime.utcnow().isoformat()
        for r in rows:
            if r.get('job_url') == job_url:
                # update attempts
                try:
                    current_attempts = int(r.get('attempts', '0'))
                except Exception:
                    current_attempts = 0
                r['attempts'] = str(current_attempts + attempts_inc)
                r['status'] = status
                if last_error is not None:
                    r['last_error'] = last_error
                r['updated_at'] = now
                changed = True
        if changed:
            self._write(site_name, rows)
        return changed

    def get_jobs(self, site_name: str, status: str | None = None) -> list:
        """Returns list of rows; optionally filter by status."""
        rows = self._read(site_name)
        if status:
            return [r for r in rows if r.get('status') == status]
        return rows


# module-level default tracker
tracker = CSVTracker()

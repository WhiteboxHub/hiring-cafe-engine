import json
import smtplib
from email.message import EmailMessage
from pathlib import Path

from config.settings import settings
from core.logger import logger

APPLICATION_NAME = "Hiring.Cafe Data Pipeline"


class EmailReporter:
    @staticmethod
    def send_report(by_ats_json_path: str):
        """
        Reads the by_ats.json file and sends an HTML summary report via SMTP.
        """
        # Validate SMTP configuration
        if not all([settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.REPORT_RECEIVER_EMAIL]):
            logger.warning("[EMAIL] SMTP configurations are not fully set up. Skipping email report.")
            return

        json_path = Path(by_ats_json_path)
        if not json_path.exists():
            logger.error(f"[EMAIL] Report file not found: {by_ats_json_path}")
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[EMAIL] Failed to open/parse {by_ats_json_path}: {e}")
            return

        # Extract data for the report
        source = data.get("source", "hiring.cafe")
        platforms = data.get("platforms", [])
        by_ats = data.get("by_ats", {})
        
        total_jobs = sum(len(jobs) for jobs in by_ats.values())
        
        # Build HTML table for platforms
        table_rows = ""
        for platform in sorted(platforms):
            count = len(by_ats.get(platform, []))
            table_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{platform}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold; color: #3498db;">{count}</td>
            </tr>
            """

        # HTML Template
        html_content = f"""
        <html>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; color: #333; margin: 0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                    <h2 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 15px; margin-top: 0;">{APPLICATION_NAME} — Result Summary</h2>
                    
                    <p style="font-size: 16px; color: #555;">The automated scraping pipeline has completed. Below is the summary of jobs found on <strong>{source}</strong>.</p>

                    <div style="background: #ebf5fb; border-radius: 8px; padding: 20px; margin-bottom: 25px;">
                        <span style="display: block; font-size: 14px; color: #5dade2; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">Total Jobs Discovered</span>
                        <span style="font-size: 32px; font-weight: bold; color: #2e86c1;">{total_jobs}</span>
                    </div>

                    <h3 style="color: #2c3e50; font-size: 18px; margin-bottom: 15px;">Breakdown by Platform</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="text-align: left; padding: 10px; border-bottom: 2px solid #dee2e6; color: #7f8c8d;">ATS Platform</th>
                                <th style="text-align: right; padding: 10px; border-bottom: 2px solid #dee2e6; color: #7f8c8d;">Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>

                    <p style="font-size: 13px; color: #95a5a6; margin-top: 35px; border-top: 1px solid #eee; padding-top: 20px; text-align: center;">
                        This is an automated report from {APPLICATION_NAME}.<br>
                        The full data set is attached as a JSON file.
                    </p>
                </div>
            </body>
        </html>
        """

        msg = EmailMessage()
        msg["Subject"] = f"[{APPLICATION_NAME}] {total_jobs} jobs discovered on {source}"
        msg['From'] = settings.SENDER_EMAIL or settings.SMTP_USERNAME
        msg['To'] = settings.REPORT_RECEIVER_EMAIL
        
        msg.set_content(
            f"{APPLICATION_NAME}: Please enable HTML to view this report summary. "
            f"The full data set in JSON format is attached."
        )
        msg.add_alternative(html_content, subtype='html')

        # Attach the JSON file
        try:
            with open(json_path, 'rb') as f:
                json_data = f.read()
            msg.add_attachment(
                json_data,
                maintype="application",
                subtype="json",
                filename=json_path.name,
            )
            logger.info(f"[EMAIL] Attached {json_path.name} to the email.")
        except Exception as file_err:
            logger.warning(f"[EMAIL] Could not attach JSON report: {file_err}")

        # Send the email
        try:
            logger.info(f"[EMAIL] Connecting to {settings.SMTP_SERVER}:{settings.SMTP_PORT} to send report...")
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"[EMAIL] Successfully sent report to {settings.REPORT_RECEIVER_EMAIL}")
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send email: {e}")


email_reporter = EmailReporter()

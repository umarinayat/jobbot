"""Email notifier: renders an HTML digest and sends it over SMTP."""

from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import Job

log = logging.getLogger("jobbot.notifier")


def render_html(jobs: list[Job]) -> str:
    """Build a clean, self-contained HTML email body."""
    rows = []
    for j in jobs:
        skills = ", ".join(html.escape(s) for s in j.matched_skills) or "&mdash;"
        loc = html.escape(j.location or ("Remote" if j.remote else ""))
        age = f"{j.age_days:.0f}d ago" if j.age_days is not None else ""
        rows.append(
            f"""
        <tr>
          <td style="padding:12px 14px;border-bottom:1px solid #eee;">
            <a href="{html.escape(j.url)}" style="font-size:15px;font-weight:600;color:#1f4e79;text-decoration:none;">
              {html.escape(j.title)}</a>
            <div style="color:#555;font-size:13px;margin-top:2px;">
              {html.escape(j.company) or "Unknown company"} &middot; {loc} &middot;
              <span style="text-transform:capitalize;">{html.escape(j.source)}</span> {age}
            </div>
            <div style="color:#1a7f37;font-size:12px;margin-top:4px;">
              score {j.score} &nbsp;|&nbsp; matched: {skills}
            </div>
          </td>
        </tr>"""
        )

    return f"""\
<!DOCTYPE html>
<html><body style="margin:0;background:#f6f7f9;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:620px;margin:0 auto;padding:20px;">
    <h2 style="color:#1a1a1a;margin:0 0 4px;">JobBot &mdash; {len(jobs)} new matching job{'s' if len(jobs)!=1 else ''}</h2>
    <p style="color:#666;font-size:13px;margin:0 0 16px;">Ranked by how well they match your skills.</p>
    <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #eee;border-radius:8px;overflow:hidden;">
      {''.join(rows)}
    </table>
    <p style="color:#999;font-size:11px;margin-top:16px;">
      Sent by your self-hosted JobBot. Tune matches in <code>config.yaml</code>.
    </p>
  </div>
</body></html>"""


def send_email(jobs: list[Job]) -> None:
    """Send the digest. Reads credentials from environment variables."""
    if not jobs:
        log.info("no new jobs; nothing to send")
        return

    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    recipient = os.environ.get("EMAIL_TO", sender)
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    if not sender or not password:
        raise RuntimeError(
            "EMAIL_ADDRESS and EMAIL_APP_PASSWORD must be set to send email."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[JobBot] {len(jobs)} new job match{'es' if len(jobs)!=1 else ''}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(render_html(jobs), "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, [r.strip() for r in recipient.split(",")], msg.as_string())
    log.info("email sent to %s (%d jobs)", recipient, len(jobs))

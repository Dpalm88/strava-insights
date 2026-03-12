"""
Strava Weekly Report - Email Lambda Handler
Pulls the latest training summary from DynamoDB
and sends a formatted weekly report via AWS SES.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Triggered by EventBridge after the insights pipeline completes,
    or on its own weekly schedule. Pulls the latest summary from
    DynamoDB and sends a formatted HTML email via SES.
    """
    import boto3
    from botocore.exceptions import ClientError
    from storage import DynamoStorage

    logger.info("Weekly report emailer started")

    try:
        dynamo = DynamoStorage(table=os.environ["DYNAMO_TABLE"])
        summaries = dynamo.list_summaries(limit=1)

        if not summaries:
            logger.warning("No summaries found in DynamoDB — skipping email")
            return {"statusCode": 204, "body": "No summaries available"}

        summary = summaries[0]
        logger.info(f"Loaded summary: {summary.get('summary_id')}")

        html_body = build_html_report(summary)
        text_body = build_text_report(summary)

        send_email(
            to_address=os.environ["REPORT_EMAIL_TO"],
            from_address=os.environ["REPORT_EMAIL_FROM"],
            subject=f"🏃 Weekly Training Report — {datetime.utcnow().strftime('%B %d, %Y')}",
            html_body=html_body,
            text_body=text_body,
        )

        logger.info("Weekly report sent successfully")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Report sent", "summary_id": summary.get("summary_id")}),
        }

    except Exception as e:
        logger.error(f"Emailer failed: {str(e)}", exc_info=True)
        raise


def send_email(to_address, from_address, subject, html_body, text_body):
    """Send email via AWS SES."""
    import boto3
    from botocore.exceptions import ClientError
    ses = boto3.client("ses")
    try:
        ses.send_email(
            Source=from_address,
            Destination={"ToAddresses": [to_address]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"Email sent to {to_address}")
    except ClientError as e:
        logger.error(f"SES send failed: {e.response['Error']['Message']}")
        raise


def build_html_report(summary: dict) -> str:
    """Build a clean HTML email from the training summary."""
    trends = summary.get("performance_trends", {})
    recent = trends.get("last_4_weeks", {})
    prior = trends.get("prior_4_weeks", {})
    bests = summary.get("best_efforts", {})
    weekly = summary.get("weekly_summary", [])[:4]  # Last 4 weeks

    trend_arrow = {
        "up": "&#x2191; Trending Up",
        "down": "&#x2193; Trending Down",
        "flat": "&#x2192; Holding Steady",
    }.get(trends.get("trend", "flat"), "&#x2192; Holding Steady")

    trend_color = {
        "up": "#2e7d32",
        "down": "#c62828",
        "flat": "#e65100",
    }.get(trends.get("trend", "flat"), "#555")

    # Weekly rows
    weekly_rows = ""
    for week in weekly:
        weekly_rows += f"""
        <tr>
          <td style="padding:8px 12px; border-bottom:1px solid #eee;">{week.get('week','')}</td>
          <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{week.get('runs',0)}</td>
          <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{week.get('total_miles',0)}</td>
          <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{week.get('avg_pace','N/A')}</td>
          <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{week.get('total_elevation_ft',0)} ft</td>
        </tr>"""

    # Best effort rows
    best_rows = ""
    distance_labels = {
        "5K": "5K",
        "10K": "10K",
        "half_marathon": "Half Marathon",
        "marathon": "Marathon",
    }
    for key, label in distance_labels.items():
        if key in bests:
            b = bests[key]
            best_rows += f"""
            <tr>
              <td style="padding:8px 12px; border-bottom:1px solid #eee;">{label}</td>
              <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{b.get('distance_miles','')} mi</td>
              <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{b.get('time','')}</td>
              <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{b.get('pace','')} /mi</td>
              <td style="padding:8px 12px; border-bottom:1px solid #eee; text-align:center;">{b.get('date','')}</td>
            </tr>"""

    if not best_rows:
        best_rows = '<tr><td colspan="5" style="padding:12px; color:#888; text-align:center;">No race-distance efforts found yet</td></tr>'

    mileage_change = trends.get("mileage_change_miles", 0)
    change_str = f"+{mileage_change}" if mileage_change > 0 else str(mileage_change)

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#f5f5f5; font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5; padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#1F4E79; padding:28px 32px;">
            <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:bold;">🏃 Weekly Training Report</h1>
            <p style="margin:6px 0 0; color:#90CAF9; font-size:14px;">Generated {datetime.utcnow().strftime('%B %d, %Y')}</p>
          </td>
        </tr>

        <!-- Trend Banner -->
        <tr>
          <td style="padding:20px 32px; background:#f8f9fa; border-bottom:1px solid #eee;">
            <span style="font-size:18px; font-weight:bold; color:{trend_color};">{trend_arrow}</span>
            <span style="margin-left:16px; color:#555; font-size:14px;">{change_str} miles vs prior 4 weeks</span>
          </td>
        </tr>

        <!-- 4-Week Comparison -->
        <tr>
          <td style="padding:24px 32px 0;">
            <h2 style="margin:0 0 16px; font-size:15px; color:#1F4E79; text-transform:uppercase; letter-spacing:0.5px;">4-Week Comparison</h2>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="50%" style="padding-right:8px;">
                  <div style="background:#E3F2FD; border-radius:6px; padding:16px 20px;">
                    <p style="margin:0 0 4px; font-size:12px; color:#555; text-transform:uppercase;">Last 4 Weeks</p>
                    <p style="margin:0; font-size:28px; font-weight:bold; color:#1F4E79;">{recent.get('total_miles', 0)} mi</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#555;">{recent.get('runs', 0)} runs &nbsp;•&nbsp; {recent.get('avg_pace', 'N/A')} avg pace</p>
                  </div>
                </td>
                <td width="50%" style="padding-left:8px;">
                  <div style="background:#F5F5F5; border-radius:6px; padding:16px 20px;">
                    <p style="margin:0 0 4px; font-size:12px; color:#555; text-transform:uppercase;">Prior 4 Weeks</p>
                    <p style="margin:0; font-size:28px; font-weight:bold; color:#555;">{prior.get('total_miles', 0)} mi</p>
                    <p style="margin:4px 0 0; font-size:13px; color:#555;">{prior.get('runs', 0)} runs &nbsp;•&nbsp; {prior.get('avg_pace', 'N/A')} avg pace</p>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Weekly Breakdown -->
        <tr>
          <td style="padding:24px 32px 0;">
            <h2 style="margin:0 0 12px; font-size:15px; color:#1F4E79; text-transform:uppercase; letter-spacing:0.5px;">Weekly Breakdown</h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eee; border-radius:6px; overflow:hidden;">
              <tr style="background:#f8f9fa;">
                <th style="padding:10px 12px; text-align:left; font-size:12px; color:#555; font-weight:600;">Week</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Runs</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Miles</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Avg Pace</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Elevation</th>
              </tr>
              {weekly_rows}
            </table>
          </td>
        </tr>

        <!-- Best Efforts -->
        <tr>
          <td style="padding:24px 32px;">
            <h2 style="margin:0 0 12px; font-size:15px; color:#1F4E79; text-transform:uppercase; letter-spacing:0.5px;">Best Efforts</h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #eee; border-radius:6px; overflow:hidden;">
              <tr style="background:#f8f9fa;">
                <th style="padding:10px 12px; text-align:left; font-size:12px; color:#555; font-weight:600;">Distance</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Miles</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Time</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Pace</th>
                <th style="padding:10px 12px; text-align:center; font-size:12px; color:#555; font-weight:600;">Date</th>
              </tr>
              {best_rows}
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px; background:#f8f9fa; border-top:1px solid #eee;">
            <p style="margin:0; font-size:12px; color:#999; text-align:center;">
              Strava Training Insights &nbsp;•&nbsp; Powered by AWS Lambda + SES
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_text_report(summary: dict) -> str:
    """Plain text fallback for email clients that don't render HTML."""
    trends = summary.get("performance_trends", {})
    recent = trends.get("last_4_weeks", {})
    prior = trends.get("prior_4_weeks", {})
    bests = summary.get("best_efforts", {})
    weekly = summary.get("weekly_summary", [])[:4]

    lines = [
        f"WEEKLY TRAINING REPORT — {datetime.utcnow().strftime('%B %d, %Y')}",
        "=" * 50,
        "",
        "4-WEEK COMPARISON",
        f"  Last 4 weeks : {recent.get('total_miles', 0)} miles | {recent.get('runs', 0)} runs | {recent.get('avg_pace', 'N/A')} avg pace",
        f"  Prior 4 weeks: {prior.get('total_miles', 0)} miles | {prior.get('runs', 0)} runs | {prior.get('avg_pace', 'N/A')} avg pace",
        f"  Trend        : {trends.get('trend', 'N/A').upper()} ({trends.get('mileage_change_miles', 0):+.1f} miles)",
        "",
        "WEEKLY BREAKDOWN",
    ]

    for week in weekly:
        lines.append(
            f"  {week.get('week',''):<12} {week.get('runs',0)} runs  "
            f"{week.get('total_miles',0)} mi  {week.get('avg_pace','N/A')} pace"
        )

    lines += ["", "BEST EFFORTS"]
    distance_labels = {
        "5K": "5K          ",
        "10K": "10K         ",
        "half_marathon": "Half Marathon",
        "marathon": "Marathon    ",
    }
    for key, label in distance_labels.items():
        if key in bests:
            b = bests[key]
            lines.append(f"  {label}: {b.get('time','')} ({b.get('pace','')} /mi) on {b.get('date','')}")

    lines += ["", "-" * 50, "Strava Training Insights | AWS Lambda + SES"]
    return "\n".join(lines)

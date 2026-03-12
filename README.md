# Strava Training Insights

A serverless AWS pipeline that pulls your Strava run data, analyzes training trends, and stores processed summaries for review — built with Python, AWS Lambda, S3, DynamoDB, and Terraform.

## What It Does

- **Fetches** your recent runs from the Strava API (OAuth token refresh handled automatically)
- **Stores** raw activity data as JSON in S3 for full auditability
- **Analyzes** your training across three dimensions:
  - Weekly mileage and pace summaries (last 12 weeks)
  - Performance trends comparing recent vs prior 4-week blocks
  - Best efforts at common race distances (5K, 10K, half, full)
- **Writes** processed summaries to DynamoDB for fast retrieval
- **Runs automatically** every Monday morning via EventBridge

## Architecture

```
EventBridge (Mon 8:00 AM)          EventBridge (Mon 8:30 AM)
        │                                    │
        ▼                                    ▼
AWS Lambda — Insights Pipeline    AWS Lambda — Email Reporter
   ├── Strava API ──► fetch runs      ├── DynamoDB ──► load summary
   ├── S3          ◄── raw JSON       └── SES      ──► send email
   ├── DynamoDB    ◄── summaries
   └── CloudWatch  ── logs
```

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Compute | AWS Lambda (x2) |
| Storage | S3 (raw), DynamoDB (summaries) |
| Email | AWS SES |
| Scheduling | EventBridge (cron) |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| External API | Strava API v3 |

## Getting Started

### 1. Strava API Setup

1. Go to [Strava API Settings](https://www.strava.com/settings/api) and create an app
2. Note your `Client ID` and `Client Secret`
3. Get your refresh token via the OAuth flow (see [Strava OAuth docs](https://developers.strava.com/docs/authentication/))

### 2. AWS Prerequisites

- AWS account with appropriate permissions
- S3 bucket for Terraform remote state
- Update `terraform/main.tf` backend config with your state bucket name

### 3. Verify your email address in SES

Before sending emails, AWS SES requires you to verify the sender address:

```bash
aws ses verify-email-identity --email-address you@example.com
```

Check your inbox and click the verification link.

### 4. Deploy with Terraform

```bash
cd terraform
terraform init
terraform apply \
  -var="strava_client_id=YOUR_CLIENT_ID" \
  -var="strava_client_secret=YOUR_CLIENT_SECRET" \
  -var="strava_refresh_token=YOUR_REFRESH_TOKEN" \
  -var="report_email_to=you@example.com" \
  -var="report_email_from=you@example.com"
```

### 5. CI/CD via GitHub Actions

Add these secrets to your GitHub repo:

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `STRAVA_CLIENT_ID` | Strava app client ID |
| `STRAVA_CLIENT_SECRET` | Strava app client secret |
| `STRAVA_REFRESH_TOKEN` | Strava OAuth refresh token |
| `REPORT_EMAIL_TO` | Recipient email address |
| `REPORT_EMAIL_FROM` | SES-verified sender address |

Push to `main` to trigger automatic deployment.

## Running Tests Locally

```bash
pip install -r requirements.txt pytest pytest-cov
pytest tests/ -v --cov=src
```

## Project Structure

```
strava-insights/
├── src/
│   ├── handler.py          # Insights Lambda — fetches + analyzes
│   ├── reporter.py         # Reporter Lambda — builds + emails report
│   ├── strava_client.py    # Strava API + OAuth
│   ├── analyzer.py         # Training analysis logic
│   └── storage.py          # S3 + DynamoDB helpers
├── terraform/
│   ├── main.tf             # All AWS resources (2 Lambdas, SES, S3, DynamoDB)
│   ├── variables.tf        # Input variables
│   └── outputs.tf          # Resource outputs
├── tests/
│   ├── test_analyzer.py    # Analyzer unit tests
│   └── test_reporter.py    # Reporter unit tests (no AWS needed)
├── .github/workflows/
│   └── deploy.yml          # CI/CD pipeline
├── requirements.txt
└── .gitignore
```

## Sample Output

```json
{
  "weekly_summary": [
    { "week": "2026-W10", "runs": 4, "total_miles": 32.5, "avg_pace": "8:12" },
    { "week": "2026-W09", "runs": 5, "total_miles": 38.1, "avg_pace": "8:24" }
  ],
  "performance_trends": {
    "last_4_weeks": { "runs": 18, "total_miles": 128.4, "avg_pace": "8:15" },
    "prior_4_weeks": { "runs": 16, "total_miles": 112.0, "avg_pace": "8:31" },
    "mileage_change_miles": 16.4,
    "trend": "up"
  },
  "best_efforts": {
    "5K":           { "date": "2026-02-15", "time": "0:21:30", "pace": "6:55" },
    "half_marathon":{ "date": "2026-01-12", "time": "1:48:00", "pace": "8:14" }
  }
}
```

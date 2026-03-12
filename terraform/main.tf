terraform {
  required_version = ">= 1.3"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "strava-insights/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# -------------------------------------------------------------------
# S3 — raw activity storage
# -------------------------------------------------------------------
resource "aws_s3_bucket" "activities" {
  bucket = "${var.project_name}-activities-${var.environment}"
}

resource "aws_s3_bucket_versioning" "activities" {
  bucket = aws_s3_bucket.activities.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "activities" {
  bucket = aws_s3_bucket.activities.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "activities" {
  bucket                  = aws_s3_bucket.activities.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -------------------------------------------------------------------
# DynamoDB — processed summaries
# -------------------------------------------------------------------
resource "aws_dynamodb_table" "summaries" {
  name         = "${var.project_name}-summaries-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "summary_id"

  attribute {
    name = "summary_id"
    type = "S"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# -------------------------------------------------------------------
# IAM — Lambda execution role
# -------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.activities.arn,
          "${aws_s3_bucket.activities.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Scan"]
        Resource = aws_dynamodb_table.summaries.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# -------------------------------------------------------------------
# Lambda — main function
# -------------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "strava_insights" {
  function_name    = "${var.project_name}-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 60
  memory_size      = 256

  environment {
    variables = {
      STRAVA_CLIENT_ID     = var.strava_client_id
      STRAVA_CLIENT_SECRET = var.strava_client_secret
      STRAVA_REFRESH_TOKEN = var.strava_refresh_token
      S3_BUCKET            = aws_s3_bucket.activities.bucket
      DYNAMO_TABLE         = aws_dynamodb_table.summaries.name
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# -------------------------------------------------------------------
# EventBridge — weekly schedule trigger
# -------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "weekly_trigger" {
  name                = "${var.project_name}-weekly-${var.environment}"
  description         = "Trigger Strava insights pipeline every Monday morning"
  schedule_expression = "cron(0 8 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.weekly_trigger.name
  target_id = "StravaInsightsLambda"
  arn       = aws_lambda_function.strava_insights.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.strava_insights.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_trigger.arn
}

# -------------------------------------------------------------------
# CloudWatch — log groups with retention
# -------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.strava_insights.function_name}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "reporter_logs" {
  name              = "/aws/lambda/${aws_lambda_function.reporter.function_name}"
  retention_in_days = 30
}

# -------------------------------------------------------------------
# IAM — extend Lambda role to allow SES sends
# -------------------------------------------------------------------
resource "aws_iam_role_policy" "ses_policy" {
  name = "${var.project_name}-ses-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ses:SendEmail", "ses:SendRawEmail"]
      Resource = "*"
    }]
  })
}

# -------------------------------------------------------------------
# Lambda — weekly email reporter
# -------------------------------------------------------------------
resource "aws_lambda_function" "reporter" {
  function_name    = "${var.project_name}-reporter-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "reporter.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      DYNAMO_TABLE       = aws_dynamodb_table.summaries.name
      REPORT_EMAIL_TO    = var.report_email_to
      REPORT_EMAIL_FROM  = var.report_email_from
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

# -------------------------------------------------------------------
# EventBridge — trigger reporter 30 min after insights pipeline
# Insights runs at 08:00 Monday, reporter runs at 08:30 Monday
# -------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "reporter_trigger" {
  name                = "${var.project_name}-reporter-weekly-${var.environment}"
  description         = "Trigger weekly email report every Monday morning"
  schedule_expression = "cron(30 8 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "reporter_target" {
  rule      = aws_cloudwatch_event_rule.reporter_trigger.name
  target_id = "StravaReporterLambda"
  arn       = aws_lambda_function.reporter.arn
}

resource "aws_lambda_permission" "allow_eventbridge_reporter" {
  statement_id  = "AllowEventBridgeInvokeReporter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reporter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reporter_trigger.arn
}

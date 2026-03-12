output "lambda_function_name" {
  description = "Insights Lambda function name"
  value       = aws_lambda_function.strava_insights.function_name
}

output "reporter_function_name" {
  description = "Reporter Lambda function name"
  value       = aws_lambda_function.reporter.function_name
}

output "s3_bucket_name" {
  description = "S3 bucket for raw activity data"
  value       = aws_s3_bucket.activities.bucket
}

output "dynamodb_table_name" {
  description = "DynamoDB table for processed summaries"
  value       = aws_dynamodb_table.summaries.name
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for insights Lambda"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "reporter_log_group" {
  description = "CloudWatch log group for reporter Lambda"
  value       = aws_cloudwatch_log_group.reporter_logs.name
}

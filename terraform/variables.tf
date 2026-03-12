variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "strava-insights"
}

variable "environment" {
  description = "Deployment environment (dev, prod)"
  type        = string
  default     = "prod"
}

variable "strava_client_id" {
  description = "Strava API client ID"
  type        = string
  sensitive   = true
}

variable "strava_client_secret" {
  description = "Strava API client secret"
  type        = string
  sensitive   = true
}

variable "strava_refresh_token" {
  description = "Strava OAuth refresh token"
  type        = string
  sensitive   = true
}

variable "report_email_to" {
  description = "Email address to send the weekly report to"
  type        = string
}

variable "report_email_from" {
  description = "SES-verified sender email address"
  type        = string
}

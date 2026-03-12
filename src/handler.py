"""
Strava Training Insights - Lambda Handler
Fetches Strava activities, stores raw data in S3,
processes summaries and writes to DynamoDB.
"""

import json
import logging
import os
from datetime import datetime

from strava_client import StravaClient
from storage import S3Storage, DynamoStorage
from analyzer import TrainingAnalyzer

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    Triggered on a schedule (EventBridge) or manually.
    """
    logger.info("Strava Insights pipeline started")

    try:
        # Init clients
        strava = StravaClient(
            client_id=os.environ["STRAVA_CLIENT_ID"],
            client_secret=os.environ["STRAVA_CLIENT_SECRET"],
            refresh_token=os.environ["STRAVA_REFRESH_TOKEN"],
        )
        s3 = S3Storage(bucket=os.environ["S3_BUCKET"])
        dynamo = DynamoStorage(table=os.environ["DYNAMO_TABLE"])
        analyzer = TrainingAnalyzer()

        # Fetch recent activities from Strava
        activities = strava.get_activities(limit=50)
        logger.info(f"Fetched {len(activities)} activities from Strava")

        # Store raw data in S3
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        s3_key = f"raw/{timestamp}_activities.json"
        s3.put_json(s3_key, activities)
        logger.info(f"Raw data stored to s3://{os.environ['S3_BUCKET']}/{s3_key}")

        # Analyze and generate summaries
        weekly_summary = analyzer.weekly_summary(activities)
        performance_trends = analyzer.performance_trends(activities)
        # Use streams for accurate segment-based best efforts (fastest 5K within a 10K, etc.)
        # Falls back gracefully if streams are unavailable for any activity
        best_efforts = analyzer.best_efforts_with_streams(activities, strava)

        # Build full summary payload
        summary = {
            "generated_at": timestamp,
            "weekly_summary": weekly_summary,
            "performance_trends": performance_trends,
            "best_efforts": best_efforts,
        }

        # Store processed summary in DynamoDB
        dynamo.put_summary(summary_id=timestamp, summary=summary)
        logger.info("Summary written to DynamoDB")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Pipeline completed successfully",
                "activities_processed": len(activities),
                "summary_id": timestamp,
            }),
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise

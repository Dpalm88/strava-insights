"""
Storage Helpers
S3 for raw activity dumps, DynamoDB for processed summaries.
"""

import json
import logging
from decimal import Decimal
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def _decimal_default(obj):
    """JSON serializer that handles Decimal types from DynamoDB."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class S3Storage:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.client = boto3.client("s3")

    def put_json(self, key: str, data: list | dict) -> None:
        """Store a JSON object in S3."""
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(data, default=str),
                ContentType="application/json",
            )
            logger.info(f"Stored to s3://{self.bucket}/{key}")
        except ClientError as e:
            logger.error(f"S3 put failed for key {key}: {e}")
            raise

    def get_json(self, key: str) -> list | dict:
        """Retrieve and parse a JSON object from S3."""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read())
        except ClientError as e:
            logger.error(f"S3 get failed for key {key}: {e}")
            raise

    def list_keys(self, prefix: str = "raw/") -> list:
        """List all keys under a prefix."""
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]


class DynamoStorage:
    def __init__(self, table: str):
        self.table_name = table
        self.dynamo = boto3.resource("dynamodb")
        self.table = self.dynamo.Table(table)

    def put_summary(self, summary_id: str, summary: dict) -> None:
        """Write a processed training summary to DynamoDB."""
        try:
            item = {
                "summary_id": summary_id,
                "created_at": datetime.utcnow().isoformat(),
                **summary,
            }
            # DynamoDB doesn't support float — convert to Decimal
            item = json.loads(json.dumps(item, default=str), parse_float=Decimal)
            self.table.put_item(Item=item)
            logger.info(f"Summary {summary_id} written to DynamoDB")
        except ClientError as e:
            logger.error(f"DynamoDB put failed for {summary_id}: {e}")
            raise

    def get_summary(self, summary_id: str) -> dict | None:
        """Retrieve a summary by ID."""
        try:
            response = self.table.get_item(Key={"summary_id": summary_id})
            item = response.get("Item")
            if item:
                return json.loads(json.dumps(item, default=_decimal_default))
            return None
        except ClientError as e:
            logger.error(f"DynamoDB get failed for {summary_id}: {e}")
            raise

    def list_summaries(self, limit: int = 10) -> list:
        """Scan all summaries and return the most recent ones sorted by summary_id desc.
        Note: DynamoDB's Limit param controls items *evaluated* before filtering,
        not items returned — so we scan the full table and sort in Python instead.
        """
        response = self.table.scan()
        items = response.get("Items", [])
        sorted_items = sorted(
            json.loads(json.dumps(items, default=_decimal_default)),
            key=lambda x: x.get("summary_id", ""),
            reverse=True,
        )
        return sorted_items[:limit]

"""
Training Analyzer
Processes raw Strava activity data into meaningful summaries,
trends, and best efforts.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Conversion helpers
METERS_TO_MILES = 0.000621371
MPS_TO_MIN_PER_MILE = 26.8224  # (1 / meters_per_second) * 1609.34 / 60


class TrainingAnalyzer:

    def _meters_to_miles(self, meters: float) -> float:
        return round(meters * METERS_TO_MILES, 2)

    def _speed_to_pace(self, speed_mps: float) -> str:
        """Convert m/s to min/mile string e.g. '8:30'"""
        if not speed_mps or speed_mps == 0:
            return "N/A"
        seconds_per_mile = MPS_TO_MIN_PER_MILE / speed_mps * 60
        minutes = int(seconds_per_mile // 60)
        seconds = int(seconds_per_mile % 60)
        return f"{minutes}:{seconds:02d}"

    def _parse_date(self, date_str: str) -> datetime:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")

    def weekly_summary(self, activities: list) -> list:
        """
        Group runs by ISO week and summarize mileage,
        elevation, and average pace per week.
        """
        logger.info("Generating weekly summaries")
        weeks = defaultdict(lambda: {
            "runs": 0,
            "total_miles": 0.0,
            "total_elevation_ft": 0.0,
            "total_seconds": 0,
            "avg_pace": "N/A",
        })

        for activity in activities:
            date = self._parse_date(activity["start_date"])
            week_key = date.strftime("%Y-W%W")
            w = weeks[week_key]
            w["runs"] += 1
            w["total_miles"] += self._meters_to_miles(activity.get("distance", 0))
            w["total_elevation_ft"] += round(
                activity.get("total_elevation_gain", 0) * 3.28084, 1
            )
            w["total_seconds"] += activity.get("moving_time", 0)

        # Calculate avg pace per week
        summaries = []
        for week, data in sorted(weeks.items(), reverse=True):
            if data["total_miles"] > 0:
                avg_speed = (data["total_miles"] * 1609.34) / data["total_seconds"] if data["total_seconds"] > 0 else 0
                data["avg_pace"] = self._speed_to_pace(avg_speed / 1609.34 * MPS_TO_MIN_PER_MILE / 60)
            data["week"] = week
            data["total_miles"] = round(data["total_miles"], 2)
            summaries.append(data)

        return summaries[:12]  # Last 12 weeks

    def performance_trends(self, activities: list) -> dict:
        """
        Calculate pace and mileage trends over 4-week blocks
        to show whether fitness is improving.
        """
        logger.info("Calculating performance trends")
        now = datetime.utcnow()
        periods = {
            "last_4_weeks": now - timedelta(weeks=4),
            "weeks_4_to_8": now - timedelta(weeks=8),
            "weeks_8_to_12": now - timedelta(weeks=12),
        }

        def bucket_activities(start, end=None):
            return [
                a for a in activities
                if start <= self._parse_date(a["start_date"]) <= (end or now)
            ]

        recent = bucket_activities(periods["last_4_weeks"])
        prior = bucket_activities(periods["weeks_4_to_8"], periods["last_4_weeks"])

        def avg_pace_for_bucket(bucket):
            if not bucket:
                return "N/A"
            total_dist = sum(a.get("distance", 0) for a in bucket)
            total_time = sum(a.get("moving_time", 0) for a in bucket)
            if total_dist == 0 or total_time == 0:
                return "N/A"
            avg_mps = total_dist / total_time
            return self._speed_to_pace(avg_mps)

        recent_miles = round(sum(self._meters_to_miles(a.get("distance", 0)) for a in recent), 2)
        prior_miles = round(sum(self._meters_to_miles(a.get("distance", 0)) for a in prior), 2)
        mileage_change = round(recent_miles - prior_miles, 2)

        return {
            "last_4_weeks": {
                "runs": len(recent),
                "total_miles": recent_miles,
                "avg_pace": avg_pace_for_bucket(recent),
            },
            "prior_4_weeks": {
                "runs": len(prior),
                "total_miles": prior_miles,
                "avg_pace": avg_pace_for_bucket(prior),
            },
            "mileage_change_miles": mileage_change,
            "trend": "up" if mileage_change > 0 else "down" if mileage_change < 0 else "flat",
        }

    def best_efforts(self, activities: list) -> dict:
        """
        Find best (fastest) efforts for common race distances.
        """
        logger.info("Calculating best efforts")
        distance_targets = {
            "5K": 5000,
            "10K": 10000,
            "half_marathon": 21097,
            "marathon": 42195,
        }
        tolerance = 0.10  # 10% tolerance on distance

        bests = {}
        for label, target_meters in distance_targets.items():
            low = target_meters * (1 - tolerance)
            high = target_meters * (1 + tolerance)
            candidates = [
                a for a in activities
                if low <= a.get("distance", 0) <= high
            ]
            if candidates:
                fastest = min(candidates, key=lambda a: a.get("moving_time", float("inf")))
                bests[label] = {
                    "date": fastest["start_date"][:10],
                    "distance_miles": self._meters_to_miles(fastest["distance"]),
                    "time": str(timedelta(seconds=fastest["moving_time"])),
                    "pace": self._speed_to_pace(
                        fastest["distance"] / fastest["moving_time"]
                        if fastest.get("moving_time") else 0
                    ),
                }

        return bests

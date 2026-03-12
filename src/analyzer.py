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

        # Calculate avg pace per week — total distance / total time = avg m/s
        summaries = []
        for week, data in sorted(weeks.items(), reverse=True):
            if data["total_miles"] > 0 and data["total_seconds"] > 0:
                total_meters = data["total_miles"] / METERS_TO_MILES
                avg_mps = total_meters / data["total_seconds"]
                data["avg_pace"] = self._speed_to_pace(avg_mps)
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
        Find best (fastest pace) efforts for common race distances.
        Uses a tight 5% tolerance to avoid matching training runs at
        race distances — sorts by pace (speed) not raw time.
        """
        logger.info("Calculating best efforts")
        distance_targets = {
            "5K": 5000,
            "10K": 10000,
            "half_marathon": 21097,
            "marathon": 42195,
        }
        tolerance = 0.05  # tightened to 5% to avoid false matches

        bests = {}
        for label, target_meters in distance_targets.items():
            low = target_meters * (1 - tolerance)
            high = target_meters * (1 + tolerance)
            candidates = [
                a for a in activities
                if low <= a.get("distance", 0) <= high
                and a.get("moving_time", 0) > 0
            ]
            # Filter out walks/hikes — anything slower than 15:00/mile is not a run effort
            # 15:00/mile = 0.001118 m/s
            MIN_PACE_MPS = 1 / (15 * 60 / 1609.34)
            candidates = [a for a in candidates if a["distance"] / a["moving_time"] >= MIN_PACE_MPS]

            if candidates:
                # Sort by best pace (highest speed = lowest seconds per meter)
                fastest = max(candidates, key=lambda a: a["distance"] / a["moving_time"])
                bests[label] = {
                    "date": fastest["start_date"][:10],
                    "distance_miles": self._meters_to_miles(fastest["distance"]),
                    "time": str(timedelta(seconds=fastest["moving_time"])),
                    "pace": self._speed_to_pace(fastest["distance"] / fastest["moving_time"]),
                }

        return bests

    def fastest_segment(self, streams: dict, target_distance_m: float) -> dict | None:
        """
        Find the fastest segment of exactly target_distance_m within a run
        using a two-pointer sliding window over the distance stream.

        How it works:
        - distance[] and time[] are parallel arrays — distance[i] is how far
          the athlete has run at time[i] seconds into the activity
        - We use two pointers (left, right) and advance right until the window
          covers at least target_distance_m, then record the elapsed time
        - Slide left forward and repeat — O(n) over the stream length
        - Return the window with the lowest elapsed time (fastest pace)

        Returns a dict with time_seconds and pace, or None if stream is too short.
        """
        distances = streams.get('time', [])  # confusingly named — these are the time values
        times = streams.get('time', [])
        dist_data = streams.get('distance', [])
        time_data = streams.get('time', [])

        if not dist_data or not time_data or len(dist_data) < 2:
            return None

        # Must be long enough to contain the target distance
        if dist_data[-1] < target_distance_m:
            return None

        best_time = float('inf')
        best_start_idx = 0
        best_end_idx = 0
        left = 0

        for right in range(1, len(dist_data)):
            window_dist = dist_data[right] - dist_data[left]

            # Slide left pointer forward while window still covers target
            while window_dist > target_distance_m and left < right - 1:
                left += 1
                window_dist = dist_data[right] - dist_data[left]

            if window_dist >= target_distance_m:
                elapsed = time_data[right] - time_data[left]
                if elapsed < best_time:
                    best_time = elapsed
                    best_start_idx = left
                    best_end_idx = right

        if best_time == float('inf'):
            return None

        pace = self._speed_to_pace(target_distance_m / best_time)
        return {
            'time_seconds': best_time,
            'time': str(timedelta(seconds=int(best_time))),
            'pace': pace,
            'distance_miles': self._meters_to_miles(target_distance_m),
        }

    def best_efforts_with_streams(self, activities: list, strava_client) -> dict:
        """
        Enhanced best efforts that uses GPS streams to find fastest segments.
        For each distance target, checks all eligible activities for their
        fastest split of that distance — not just whole-activity efforts.

        Falls back to activity-level best_efforts() if streams are unavailable.
        """
        logger.info('Calculating best efforts using GPS streams')
        distance_targets = {
            '5K': 5000,
            '10K': 10000,
            'half_marathon': 21097,
            'marathon': 42195,
        }

        # Only fetch streams for runs long enough to contain each target
        bests = {}
        for label, target_m in distance_targets.items():
            best_for_distance = None
            best_time = float('inf')

            eligible = [a for a in activities if a.get('distance', 0) >= target_m * 0.95]
            logger.info(f'{label}: checking {len(eligible)} eligible activities')

            for activity in eligible:
                try:
                    streams = strava_client.get_streams(activity['id'])
                    if not streams:
                        continue
                    result = self.fastest_segment(streams, target_m)
                    if result and result['time_seconds'] < best_time:
                        best_time = result['time_seconds']
                        best_for_distance = {
                            **result,
                            'date': activity['start_date'][:10],
                            'activity_name': activity.get('name', ''),
                        }
                except Exception as e:
                    logger.warning(f'Stream fetch failed for {activity["id"]}: {e}')
                    continue

            if best_for_distance:
                bests[label] = best_for_distance

        return bests

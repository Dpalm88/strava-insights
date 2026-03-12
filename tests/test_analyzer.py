"""
Unit tests for the TrainingAnalyzer.
Uses sample Strava activity data — no AWS or API calls needed.
"""

import pytest
from datetime import datetime, timedelta
from src.analyzer import TrainingAnalyzer


def make_activity(distance_m, moving_time_s, days_ago=1, type="Run"):
    """Helper to create a mock Strava activity."""
    date = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "type": type,
        "distance": distance_m,
        "moving_time": moving_time_s,
        "total_elevation_gain": 50,
        "start_date": date,
        "average_speed": distance_m / moving_time_s if moving_time_s else 0,
    }


@pytest.fixture
def analyzer():
    return TrainingAnalyzer()


@pytest.fixture
def sample_activities():
    return [
        make_activity(8046, 2700, days_ago=1),    # 5 miles, 45 min
        make_activity(16093, 5400, days_ago=3),   # 10 miles, 90 min
        make_activity(4828, 1500, days_ago=5),    # 3 miles, 25 min
        make_activity(8046, 2600, days_ago=10),   # 5 miles, ~43 min
        make_activity(21097, 7200, days_ago=14),  # half marathon, 2hrs
        make_activity(5000, 1500, days_ago=20),   # 5K-ish
    ]


class TestMetricConversions:
    def test_meters_to_miles(self, analyzer):
        assert analyzer._meters_to_miles(1609.34) == pytest.approx(1.0, abs=0.01)

    def test_speed_to_pace_zero(self, analyzer):
        assert analyzer._speed_to_pace(0) == "N/A"

    def test_speed_to_pace_valid(self, analyzer):
        # 3.35 m/s ≈ 8:00/mile
        pace = analyzer._speed_to_pace(3.35)
        assert ":" in pace
        minutes = int(pace.split(":")[0])
        assert 7 <= minutes <= 9


class TestWeeklySummary:
    def test_returns_list(self, analyzer, sample_activities):
        result = analyzer.weekly_summary(sample_activities)
        assert isinstance(result, list)

    def test_weekly_mileage_positive(self, analyzer, sample_activities):
        result = analyzer.weekly_summary(sample_activities)
        for week in result:
            assert week["total_miles"] > 0

    def test_week_key_format(self, analyzer, sample_activities):
        result = analyzer.weekly_summary(sample_activities)
        for week in result:
            assert "W" in week["week"]

    def test_run_count(self, analyzer, sample_activities):
        result = analyzer.weekly_summary(sample_activities)
        total_runs = sum(w["runs"] for w in result)
        assert total_runs == len(sample_activities)


class TestPerformanceTrends:
    def test_returns_required_keys(self, analyzer, sample_activities):
        result = analyzer.performance_trends(sample_activities)
        assert "last_4_weeks" in result
        assert "prior_4_weeks" in result
        assert "trend" in result
        assert "mileage_change_miles" in result

    def test_trend_value(self, analyzer, sample_activities):
        result = analyzer.performance_trends(sample_activities)
        assert result["trend"] in ("up", "down", "flat")

    def test_recent_miles_positive(self, analyzer, sample_activities):
        result = analyzer.performance_trends(sample_activities)
        assert result["last_4_weeks"]["total_miles"] > 0


class TestBestEfforts:
    def test_detects_half_marathon(self, analyzer, sample_activities):
        result = analyzer.best_efforts(sample_activities)
        assert "half_marathon" in result

    def test_detects_5k(self, analyzer, sample_activities):
        result = analyzer.best_efforts(sample_activities)
        assert "5K" in result

    def test_best_effort_has_required_fields(self, analyzer, sample_activities):
        result = analyzer.best_efforts(sample_activities)
        for distance, effort in result.items():
            assert "date" in effort
            assert "time" in effort
            assert "pace" in effort
            assert "distance_miles" in effort

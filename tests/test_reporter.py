"""
Unit tests for the weekly email reporter.
Tests HTML/text generation without hitting AWS SES.
"""

import sys
sys.path.insert(0, 'src')

from reporter import build_html_report, build_text_report

SAMPLE_SUMMARY = {
    "summary_id": "2026-03-10T08-00-00",
    "generated_at": "2026-03-10T08-00-00",
    "performance_trends": {
        "last_4_weeks": {"runs": 16, "total_miles": 128.4, "avg_pace": "8:15"},
        "prior_4_weeks": {"runs": 14, "total_miles": 112.0, "avg_pace": "8:31"},
        "mileage_change_miles": 16.4,
        "trend": "up",
    },
    "weekly_summary": [
        {"week": "2026-W10", "runs": 4, "total_miles": 32.5, "avg_pace": "8:12", "total_elevation_ft": 420},
        {"week": "2026-W09", "runs": 5, "total_miles": 38.1, "avg_pace": "8:24", "total_elevation_ft": 510},
        {"week": "2026-W08", "runs": 3, "total_miles": 28.0, "avg_pace": "8:30", "total_elevation_ft": 310},
        {"week": "2026-W07", "runs": 4, "total_miles": 29.8, "avg_pace": "8:45", "total_elevation_ft": 380},
    ],
    "best_efforts": {
        "5K": {"date": "2026-02-15", "distance_miles": 3.11, "time": "0:21:30", "pace": "6:55"},
        "half_marathon": {"date": "2026-01-12", "distance_miles": 13.1, "time": "1:48:00", "pace": "8:14"},
    },
}

EMPTY_SUMMARY = {
    "summary_id": "2026-03-10T08-00-00",
    "performance_trends": {
        "last_4_weeks": {"runs": 0, "total_miles": 0, "avg_pace": "N/A"},
        "prior_4_weeks": {"runs": 0, "total_miles": 0, "avg_pace": "N/A"},
        "mileage_change_miles": 0,
        "trend": "flat",
    },
    "weekly_summary": [],
    "best_efforts": {},
}


class TestHTMLReport:
    def test_returns_string(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert isinstance(result, str)

    def test_contains_mileage(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert "128.4" in result

    def test_contains_pace(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert "8:15" in result

    def test_contains_best_effort_5k(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert "5K" in result
        assert "6:55" in result

    def test_contains_trend_up(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert "Trending Up" in result

    def test_contains_weekly_rows(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert "2026-W10" in result
        assert "32.5" in result

    def test_handles_empty_best_efforts(self):
        result = build_html_report(EMPTY_SUMMARY)
        assert "No race-distance efforts found" in result

    def test_handles_flat_trend(self):
        result = build_html_report(EMPTY_SUMMARY)
        assert "Holding Steady" in result

    def test_is_valid_html(self):
        result = build_html_report(SAMPLE_SUMMARY)
        assert result.strip().startswith("<!DOCTYPE html")
        assert "</html>" in result


class TestTextReport:
    def test_returns_string(self):
        result = build_text_report(SAMPLE_SUMMARY)
        assert isinstance(result, str)

    def test_contains_mileage(self):
        result = build_text_report(SAMPLE_SUMMARY)
        assert "128.4" in result

    def test_contains_trend(self):
        result = build_text_report(SAMPLE_SUMMARY)
        assert "UP" in result

    def test_contains_best_effort(self):
        result = build_text_report(SAMPLE_SUMMARY)
        assert "Half Marathon" in result
        assert "1:48:00" in result

    def test_contains_weekly_rows(self):
        result = build_text_report(SAMPLE_SUMMARY)
        assert "2026-W10" in result

    def test_handles_empty_summary(self):
        result = build_text_report(EMPTY_SUMMARY)
        assert isinstance(result, str)
        assert "FLAT" in result


# Run tests directly if no pytest available
if __name__ == "__main__":
    import traceback

    tests = [
        TestHTMLReport, TestTextReport
    ]
    passed = 0
    failed = 0

    for test_class in tests:
        instance = test_class()
        for method_name in [m for m in dir(instance) if m.startswith("test_")]:
            try:
                getattr(instance, method_name)()
                print(f"  PASS  {test_class.__name__}::{method_name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {test_class.__name__}::{method_name}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)

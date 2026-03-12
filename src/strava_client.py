"""
Strava API Client
Handles OAuth token refresh and activity fetching.
"""

import logging
import requests

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None

    def _refresh_access_token(self) -> str:
        """Exchange refresh token for a fresh access token."""
        logger.info("Refreshing Strava access token")
        response = requests.post(
            STRAVA_AUTH_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        logger.info("Access token refreshed successfully")
        return self.access_token

    def _get_headers(self) -> dict:
        if not self.access_token:
            self._refresh_access_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_activities(self, limit: int = 50) -> list:
        """
        Fetch recent activities from Strava.
        Returns a list of activity dicts filtered to runs only.
        """
        logger.info(f"Fetching up to {limit} activities from Strava")
        params = {"per_page": limit, "page": 1}
        response = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=self._get_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        activities = response.json()

        # Filter to runs only
        runs = [a for a in activities if a.get("type") == "Run"]
        logger.info(f"Filtered to {len(runs)} runs from {len(activities)} total activities")
        return runs

    def get_activity_detail(self, activity_id: int) -> dict:
        """Fetch detailed data for a single activity."""
        response = requests.get(
            f"{STRAVA_API_BASE}/activities/{activity_id}",
            headers=self._get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_admin_user, get_current_user_optional, get_current_user
from app.core.db import get_db
from app.main import app
from app.models.user import User, Generation, SiteVisit


class AdminMetricsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(app.dependency_overrides.clear)

        # Mock Admin User
        self.admin_user = User(
            id=uuid.uuid4(),
            email="admin@creatorbot.ai",
            role="admin",
            is_active=True,
        )

        # Mock Regular User
        self.regular_user = User(
            id=uuid.uuid4(),
            email="user@creatorbot.ai",
            role="user",
            is_active=True,
        )

    def test_record_visit_anonymous(self):
        """Verify anonymous visitors can record a visit without authentication."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user_optional] = lambda: None

        res = self.client.post(
            "/api/analytics/visit",
            json={"visitor_id": "anon_test_123", "path": "/", "referrer": "https://google.com"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "recorded"})
        self.assertTrue(mock_db.add.called)
        added_obj = mock_db.add.call_args[0][0]
        self.assertIsInstance(added_obj, SiteVisit)
        self.assertEqual(added_obj.visitor_id, "anon_test_123")
        self.assertIsNone(added_obj.user_id)
        self.assertEqual(added_obj.path, "/")

    def test_record_visit_authenticated(self):
        """Verify logged-in user visits associate the user account."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user_optional] = lambda: self.regular_user

        res = self.client.post(
            "/api/analytics/visit",
            json={"visitor_id": "anon_test_456", "path": "/admin"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "recorded"})
        added_obj = mock_db.add.call_args[0][0]
        self.assertEqual(added_obj.user_id, self.regular_user.id)
        self.assertEqual(added_obj.path, "/admin")

    def test_record_visit_empty_id(self):
        """Verify empty visitor ID is safely ignored."""
        mock_db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        res = self.client.post(
            "/api/analytics/visit",
            json={"visitor_id": "   ", "path": "/"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ignored", "reason": "empty_visitor_id"})

    def test_metrics_overview_unauthorized_without_admin(self):
        """Unauthorized requests to admin metrics endpoint should return 401 or 403."""
        res = self.client.get("/api/admin/metrics/overview")
        self.assertIn(res.status_code, [401, 403])

    def test_metrics_overview_forbidden_for_regular_user(self):
        """Regular users should be rejected with 403 Forbidden."""
        app.dependency_overrides[get_current_user] = lambda: self.regular_user

        res = self.client.get("/api/admin/metrics/overview")
        self.assertEqual(res.status_code, 403)

    def test_metrics_overview_calculations(self):
        """Verify admin metrics returns the 4 KPI metrics and 7-day trend."""
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Mock execute calls in order:
        # 1. Total site visits
        mock_res1 = MagicMock()
        mock_res1.scalar.return_value = 150

        # 2. Live visitors today
        mock_res2 = MagicMock()
        mock_res2.scalar.return_value = 42

        # 3. Total images generated
        mock_res3 = MagicMock()
        mock_res3.scalar.return_value = 98

        # 4. Images generated today
        mock_res4 = MagicMock()
        mock_res4.scalar.return_value = 17

        # 5. Visits trend
        mock_res5 = MagicMock()
        mock_res5.all.return_value = [(today_str, 55, 42)]

        # 6. Generations trend
        mock_res6 = MagicMock()
        mock_res6.all.return_value = [(today_str, 17)]

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            mock_res1,
            mock_res2,
            mock_res3,
            mock_res4,
            mock_res5,
            mock_res6,
        ]
        app.dependency_overrides[get_db] = lambda: mock_db

        res = self.client.get("/api/admin/metrics/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check the 4 core metrics
        self.assertEqual(data["total_site_visits"], 150)
        self.assertEqual(data["live_visitors_today"], 42)
        self.assertEqual(data["total_images_generated"], 98)
        self.assertEqual(data["images_generated_today"], 17)

        # Check 7-day trends structure
        self.assertEqual(len(data["daily_trends"]), 7)
        today_trend = next((t for t in data["daily_trends"] if t["date"] == today_str), None)
        self.assertIsNotNone(today_trend)
        self.assertEqual(today_trend["visits"], 55)
        self.assertEqual(today_trend["unique_visitors"], 42)
        self.assertEqual(today_trend["generations"], 17)


if __name__ == "__main__":
    unittest.main()

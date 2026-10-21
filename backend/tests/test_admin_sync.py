import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_admin_user, get_current_user
from app.core.config import settings, Settings
from app.core.db import get_db
from app.main import app
from app.models.user import User, UserCredit


class AdminRoleSyncTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(app.dependency_overrides.clear)

    def test_comma_separated_admin_emails_parsing(self):
        """Verifies whitespace-trimmed comma-separated emails in settings."""
        custom_settings = Settings(
            ADMIN_EMAILS=" first.admin@example.com, second.admin@example.com , THIRD.ADMIN@EXAMPLE.COM "
        )
        self.assertEqual(
            custom_settings.admin_emails_list,
            ["first.admin@example.com", "second.admin@example.com", "third.admin@example.com"],
        )

    def test_list_users_dynamically_shows_admin_for_all_configured_emails(self):
        """Verifies that list_users dynamically reports 'admin' role for all emails in ADMIN_EMAILS."""
        admin_caller = User(
            id=uuid.uuid4(),
            email="primary@example.com",
            role="admin",
            is_active=True,
        )
        user_two = User(
            id=uuid.uuid4(),
            email="second@example.com",
            role="user",  # Still marked as 'user' in DB from earlier signup
            is_active=True,
            credit=UserCredit(balance=10),
        )
        regular_user = User(
            id=uuid.uuid4(),
            email="regular@example.com",
            role="user",
            is_active=True,
            credit=UserCredit(balance=5),
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [admin_caller, user_two, regular_user]
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_admin_user] = lambda: admin_caller

        with patch.object(settings, "ADMIN_EMAILS", "primary@example.com,second@example.com"):
            res = self.client.get("/api/admin/users")

        self.assertEqual(res.status_code, 200)
        users = res.json()
        roles_by_email = {u["email"]: u["role"] for u in users}

        self.assertEqual(roles_by_email["primary@example.com"], "admin")
        self.assertEqual(roles_by_email["second@example.com"], "admin")
        self.assertEqual(roles_by_email["regular@example.com"], "user")

    def test_get_admin_user_grants_access_for_secondary_configured_admin(self):
        """Verifies get_admin_user dependency allows access if caller email is in ADMIN_EMAILS."""
        secondary_admin = User(
            id=uuid.uuid4(),
            email="secondary@example.com",
            role="user",  # Even if role is 'user' in DB
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_res)

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: secondary_admin

        with patch.object(settings, "ADMIN_EMAILS", "first@example.com,secondary@example.com"):
            res = self.client.get("/api/admin/themes")

        self.assertEqual(res.status_code, 200)

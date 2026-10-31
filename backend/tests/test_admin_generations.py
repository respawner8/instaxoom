import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_admin_user, get_current_user
from app.core.db import get_db
from app.main import app
from app.models.user import User, Generation


class AdminGenerationsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(app.dependency_overrides.clear)

        self.admin_user = User(
            id=uuid.uuid4(),
            email="admin@creatorbot.ai",
            role="admin",
            is_active=True,
        )

        self.regular_user = User(
            id=uuid.uuid4(),
            email="regular@creatorbot.ai",
            role="user",
            is_active=True,
        )

    def test_list_generations_requires_admin(self):
        """Verify non-admin users cannot access the admin generations endpoint."""
        app.dependency_overrides[get_current_user] = lambda: self.regular_user
        # get_admin_user will raise 403 since regular_user.role == 'user'
        res = self.client.get("/api/admin/generations")
        self.assertEqual(res.status_code, 403)

    def test_list_generations_paginated_with_input_and_output(self):
        """Verify admin can retrieve paginated generations with input and output image URLs."""
        mock_user = User(
            id=uuid.uuid4(),
            email="creator@example.com",
            name="Creator User",
            avatar_url="https://example.com/avatar.jpg",
            role="user",
            is_active=True,
        )

        gen1 = Generation(
            id=uuid.uuid4(),
            user_id=mock_user.id,
            job_id="job_001",
            theme_id="trend-cyberpunk",
            theme_title="Neon Cyberpunk",
            prompt="Futuristic neon cyber portrait",
            aspect_ratio="4:5",
            engine="azure",
            image_url="https://blob.example.com/outputs/job_001.png",
            thumbnail_url="https://blob.example.com/outputs/job_001_thumb.webp",
            input_image_url="https://blob.example.com/inputs/job_001_input.webp",
            created_at=datetime.now(timezone.utc),
            user=mock_user,
        )

        gen2 = Generation(
            id=uuid.uuid4(),
            user_id=mock_user.id,
            job_id="job_002",
            theme_id="trend-old-money",
            theme_title="Old Money Aesthetic",
            prompt="Classic vintage polo portrait",
            aspect_ratio="4:5",
            engine="azure",
            image_url="https://blob.example.com/outputs/job_002.png",
            thumbnail_url="https://blob.example.com/outputs/job_002_thumb.webp",
            input_image_url="https://blob.example.com/inputs/job_002_input.webp",
            created_at=datetime.now(timezone.utc),
            user=mock_user,
        )

        mock_db = AsyncMock()

        # First query is count, second is items
        count_res = MagicMock()
        count_res.scalar.return_value = 2

        data_res = MagicMock()
        data_res.scalars.return_value.all.return_value = [gen1, gen2]

        mock_db.execute = AsyncMock(side_effect=[count_res, data_res])

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        res = self.client.get("/api/admin/generations?page=1&page_size=5")
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 5)
        self.assertEqual(data["total_pages"], 1)
        self.assertEqual(len(data["items"]), 2)

        first = data["items"][0]
        self.assertEqual(first["job_id"], "job_001")
        self.assertEqual(first["theme_id"], "trend-cyberpunk")
        self.assertEqual(first["input_image_url"], "https://blob.example.com/inputs/job_001_input.webp")
        self.assertEqual(first["image_url"], "https://blob.example.com/outputs/job_001.png")
        self.assertEqual(first["thumbnail_url"], "https://blob.example.com/outputs/job_001_thumb.webp")
        self.assertEqual(first["user"]["email"], "creator@example.com")

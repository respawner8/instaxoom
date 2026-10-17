import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_admin_user, get_current_user_optional
from app.core.db import get_db
from app.main import app
from app.models.user import ThemePreset, User


class ThemeManagerApiTests(unittest.TestCase):
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

    def test_list_themes_unauthorized_without_admin(self):
        # Without any auth override, calling /api/admin/themes should fail with 401/403
        response = self.client.get("/api/admin/themes")
        self.assertIn(response.status_code, [401, 403])

    def test_list_themes_as_admin(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        mock_theme = ThemePreset(
            id="trend-perfect-headshot",
            title="Perfect Headshot",
            category="Professional",
            tagline="Studio quality headshot",
            prompt_template="executive portrait, studio lighting",
            hashtags=["#headshot", "#creatorbot"],
            preview_image_url="https://example.com/photo.jpg",
            is_active=True,
            order_index=0,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_theme]
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        response = self.client.get("/api/admin/themes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "trend-perfect-headshot")
        self.assertEqual(data[0]["title"], "Perfect Headshot")

    def test_create_theme_success(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No collision
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        payload = {
            "title": "Anime Watercolor",
            "category": "Animation",
            "tagline": "Whimsical watercolor portrait",
            "prompt_template": "watercolor anime masterpiece portrait",
            "hashtags": ["#Anime", "#Art"],
            "preview_image_url": "https://example.com/anime.jpg",
            "is_active": True,
            "order_index": 5,
        }

        response = self.client.post("/api/admin/themes", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "created")
        self.assertEqual(data["theme"]["title"], "Anime Watercolor")
        self.assertTrue(data["theme"]["id"].startswith("trend-anime-watercolor"))
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    def test_create_theme_validates_required_fields(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user
        mock_db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        # Missing title
        res = self.client.post("/api/admin/themes", json={"title": "", "prompt_template": "some prompt"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("title is required", res.json()["detail"].lower())

        # Missing prompt
        res = self.client.post("/api/admin/themes", json={"title": "Some Theme", "prompt_template": "  "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("prompt template is required", res.json()["detail"].lower())

    def test_create_theme_duplicate_id_rejected(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        existing_preset = ThemePreset(id="trend-existing", title="Existing", prompt_template="test")
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_preset
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        payload = {
            "id": "trend-existing",
            "title": "Existing Dupe",
            "prompt_template": "some prompt",
        }
        res = self.client.post("/api/admin/themes", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("already exists", res.json()["detail"])

    def test_update_theme_success_and_clear_preview_url(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        existing = ThemePreset(
            id="trend-update-me",
            title="Old Title",
            category="Old Category",
            tagline="Old Tagline",
            prompt_template="old prompt",
            preview_image_url="https://example.com/old.jpg",
            is_active=True,
            order_index=1,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        # Update title and explicitly set preview_image_url to null
        payload = {
            "title": "New Updated Title",
            "preview_image_url": None,
            "is_active": False,
        }

        response = self.client.put("/api/admin/themes/trend-update-me", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "updated")
        self.assertEqual(existing.title, "New Updated Title")
        self.assertIsNone(existing.preview_image_url)
        self.assertFalse(existing.is_active)
        mock_db.commit.assert_awaited_once()

    def test_update_theme_not_found(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        res = self.client.put("/api/admin/themes/nonexistent", json={"title": "Test"})
        self.assertEqual(res.status_code, 404)

    def test_delete_theme_success(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        existing = ThemePreset(
            id="trend-to-delete",
            title="Delete Me",
            prompt_template="to be deleted",
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_result
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        response = self.client.delete("/api/admin/themes/trend-to-delete")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "deleted")
        self.assertEqual(data["id"], "trend-to-delete")
        mock_db.delete.assert_awaited_once_with(existing)
        mock_db.commit.assert_awaited_once()

    def test_delete_theme_not_found(self):
        app.dependency_overrides[get_admin_user] = lambda: self.admin_user

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        res = self.client.delete("/api/admin/themes/nonexistent")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

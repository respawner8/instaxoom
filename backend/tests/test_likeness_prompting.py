import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.services.azure_image_client import azure_image_client


class LikenessPromptingTests(unittest.TestCase):
    def test_surgical_likeness_prompt_in_images_edit(self):
        """
        Verify that azure_image_client constructs a surgical identity-anchoring prompt
        for client.images.edit that explicitly locks face geometry, bone structure,
        eyes, nose, and lips, while only modifying wardrobe, background, and lighting.
        """
        captured_edit_call = {}

        async def run_test():
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_item = MagicMock()
            mock_item.b64_json = None
            mock_item.url = "https://example.com/generated_portrait.png"
            mock_resp.data = [mock_item]

            async def mock_edit(**kwargs):
                captured_edit_call.update(kwargs)
                return mock_resp

            mock_client.images.edit = AsyncMock(side_effect=mock_edit)

            with patch("openai.AsyncOpenAI", return_value=mock_client):
                with patch("httpx.AsyncClient") as mock_httpx:
                    mock_dl_resp = MagicMock()
                    mock_dl_resp.status_code = 200
                    mock_dl_resp.content = b"fake-png-content"
                    mock_httpx_inst = AsyncMock()
                    mock_httpx_inst.get = AsyncMock(return_value=mock_dl_resp)
                    mock_httpx.return_value.__aenter__.return_value = mock_httpx_inst

                    with patch("app.services.azure_image_client.storage_service.upload_portrait_with_thumbnail", new=AsyncMock(return_value=("https://blob/img.png", "https://blob/thumb.webp"))):
                        with patch.object(settings, "AZURE_AI_API_KEY", "mock-key"):
                            res = await azure_image_client._do_execute_attempt(
                                base_url="https://mock.azure.com/openai/v1",
                                deployment_name="gpt-image-2.5-flare",
                                photo_bytes=b"sample-photo",
                                prompt="1990s yearbook portrait, blue studio backdrop",
                                size="1024x1024",
                                output_filename="test_output.png",
                            )
                            return res

        result = asyncio.run(run_test())

        self.assertIsNotNone(result)
        self.assertIn("prompt", captured_edit_call)
        edit_prompt = captured_edit_call["prompt"]

        # Assert key identity-anchoring keywords
        self.assertIn("Preserve the exact face", edit_prompt)
        self.assertIn("facial features, bone structure, eye shape, nose, mouth contours, skin tone", edit_prompt)
        self.assertIn("100% fidelity", edit_prompt)
        self.assertIn("Do not alter or beautify their natural facial geometry", edit_prompt)
        self.assertIn("Only modify the wardrobe, background setting, and lighting aesthetic to match: 1990s yearbook portrait, blue studio backdrop.", edit_prompt)


if __name__ == "__main__":
    unittest.main()

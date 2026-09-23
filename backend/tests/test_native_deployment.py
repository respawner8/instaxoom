import asyncio
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api.trends import build_workflow_prompt, comfy_client
from app.core.config import settings
from app.main import app
from app.services.comfy_client import ComfyUIClient


class NativeDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cwd = patch("app.api.trends.os.getcwd", return_value=self.directory.name)
        self.cwd.start()
        self.addCleanup(self.cwd.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def generate(self):
        return self.client.post(
            "/api/trends/generate",
            files={"photos": ("reference.png", b"reference", "image/png")},
        )

    def test_amd_workflow_uses_cpu_face_analysis(self):
        with patch.object(settings, "PULID_PROVIDER", "CPU"):
            graph = build_workflow_prompt("portrait", "reference.png", use_pulid=True)
        self.assertEqual(graph["12"]["inputs"]["provider"], "CPU")
        self.assertEqual(graph["7"]["inputs"]["model"], ["14", 0])

    def test_cuda_face_analysis_remains_supported(self):
        with patch.object(settings, "PULID_PROVIDER", "CUDA"):
            graph = build_workflow_prompt("portrait", "reference.png", use_pulid=True)
        self.assertEqual(graph["12"]["inputs"]["provider"], "CUDA")

    def test_busy_native_generator_rejects_another_request(self):
        with (
            patch.object(settings, "SINGLE_GENERATION_AT_A_TIME", True),
            patch("app.api.trends.generation_lock") as lock,
        ):
            lock.locked.return_value = True
            response = self.generate()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "30")

    def test_oversized_photo_is_rejected_before_dispatch(self):
        with (
            patch.object(settings, "MAX_PHOTO_BYTES", 4),
            patch.object(comfy_client, "queue_prompt", new_callable=AsyncMock) as queue,
        ):
            response = self.generate()
        self.assertEqual(response.status_code, 413)
        queue.assert_not_awaited()

    def test_required_pulid_does_not_fall_back(self):
        with (
            patch.object(settings, "REQUIRE_PULID", True),
            patch.object(comfy_client, "upload_image", new_callable=AsyncMock),
            patch.object(
                comfy_client, "queue_prompt", new_callable=AsyncMock,
                side_effect=RuntimeError("PuLID is unavailable"),
            ) as queue,
        ):
            response = self.generate()
        self.assertEqual(response.status_code, 500)
        self.assertIn("PuLID is unavailable", response.json()["detail"])
        self.assertEqual(queue.await_count, 1)

    def test_required_reference_upload_failure_is_reported(self):
        with (
            patch.object(settings, "REQUIRE_PULID", True),
            patch.object(
                comfy_client, "upload_image", new_callable=AsyncMock,
                side_effect=RuntimeError("Upload failed"),
            ),
            patch.object(comfy_client, "queue_prompt", new_callable=AsyncMock) as queue,
        ):
            response = self.generate()
        self.assertEqual(response.status_code, 502)
        queue.assert_not_awaited()

    def test_optional_fallback_is_reported_and_timeout_is_configurable(self):
        history = {"outputs": {"9": {"images": [{"filename": "portrait.png"}]}}}
        with (
            patch.object(settings, "REQUIRE_PULID", False),
            patch.object(settings, "INFERENCE_TIMEOUT_SECONDS", 600.0),
            patch.object(comfy_client, "upload_image", new_callable=AsyncMock),
            patch.object(
                comfy_client, "queue_prompt", new_callable=AsyncMock,
                side_effect=[RuntimeError("PuLID is unavailable"), "prompt-id"],
            ) as queue,
            patch.object(
                comfy_client, "wait_for_completion", new_callable=AsyncMock,
                return_value=history,
            ) as completion,
        ):
            response = self.generate()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identity_conditioning"], "none")
        self.assertEqual(queue.await_count, 2)
        self.assertEqual(completion.await_args.kwargs["timeout_seconds"], 600.0)

    def test_native_dev_graph_uses_original_pulid_sampling(self):
        with patch.object(settings, "FLUX_UNET_NAME", "flux1-dev-fp8.safetensors"):
            graph = build_workflow_prompt("portrait", "reference.png", use_pulid=True, seed=123)
        self.assertEqual(graph["1"]["class_type"], "UNETLoader")
        self.assertEqual(graph["1"]["inputs"]["unet_name"], "flux1-dev-fp8.safetensors")
        self.assertEqual(graph["4"]["class_type"], "EmptyLatentImage")
        self.assertEqual(graph["14"]["class_type"], "ApplyPulidFlux")
        self.assertEqual(graph["14"]["inputs"]["weight"], 0.85)
        self.assertEqual(graph["7"]["inputs"]["steps"], 20)
        self.assertEqual(graph["7"]["inputs"]["scheduler"], "simple")
        self.assertEqual(graph["15"]["inputs"]["guidance"], 3.5)
        self.assertEqual(graph["9"]["inputs"]["images"], ["8", 0])
        self.assertEqual(sum(node["class_type"] == "KSampler" for node in graph.values()), 1)

    def test_multiple_photos_use_first_reference_and_original_output_shape(self):
        history = {"outputs": {"9": {"images": [{"filename": "portrait.png"}]}}}
        with (
            patch.object(comfy_client, "upload_image", new_callable=AsyncMock) as upload,
            patch.object(comfy_client, "queue_prompt", new_callable=AsyncMock, return_value="prompt-id") as queue,
            patch.object(comfy_client, "wait_for_completion", new_callable=AsyncMock, return_value=history),
        ):
            response = self.client.post(
                "/api/trends/generate",
                files=[("photos", ("first.png", b"first")), ("photos", ("second.png", b"second"))],
                data={"prompt": "Custom portrait"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["photos_received"], 2)
        self.assertEqual(response.json()["dimensions"], {"width": 864, "height": 1080})
        self.assertEqual(response.json()["identity_conditioning"], "pulid")
        graph = queue.await_args.args[0]
        self.assertEqual(graph["10"]["inputs"]["image"], upload.await_args_list[0].args[1])
        self.assertEqual(graph["5"]["inputs"]["text"], "Custom portrait")
        self.assertEqual(graph["7"]["inputs"]["model"], ["14", 0])


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    def socket_context(self, socket):
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=socket)
        context.__aexit__ = AsyncMock(return_value=False)
        return context

    async def test_silent_socket_polls_completed_history(self):
        client = ComfyUIClient()
        socket = AsyncMock()
        socket.recv.side_effect = asyncio.TimeoutError
        history = {"outputs": {"9": {"images": [{"filename": "portrait.png"}]}}}
        with (
            patch("app.services.comfy_client.websockets.connect", return_value=self.socket_context(socket)),
            patch.object(client, "get_history", new_callable=AsyncMock, return_value=history),
        ):
            result = await client.wait_for_completion("prompt-id", "client-id", 1.0)
        self.assertEqual(result, history)

    async def test_execution_error_is_not_swallowed_by_polling_fallback(self):
        client = ComfyUIClient()
        socket = AsyncMock()
        socket.recv.return_value = json.dumps({
            "type": "execution_error",
            "data": {"prompt_id": "prompt-id", "exception_message": "Model loading failed"},
        })
        with patch(
            "app.services.comfy_client.websockets.connect", return_value=self.socket_context(socket)
        ):
            with self.assertRaisesRegex(RuntimeError, "Model loading failed"):
                await client.wait_for_completion("prompt-id", "client-id", 1.0)


if __name__ == "__main__":
    unittest.main()

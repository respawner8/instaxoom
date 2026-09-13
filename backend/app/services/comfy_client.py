import asyncio
import json
import time
from typing import Dict, Any, Optional
import httpx
import websockets
from app.core.config import settings


class ComfyUIClient:
    """
    Client for communicating with headless ComfyUI inference instance
    via REST and WebSockets with polling fallback.
    """

    def __init__(self):
        self.base_url = settings.COMFYUI_URL
        self.ws_url = settings.COMFYUI_WS_URL

    async def queue_prompt(self, workflow_prompt: Dict[str, Any], client_id: str) -> str:
        """
        Sends a parameterized workflow graph to ComfyUI /prompt endpoint.
        Returns prompt_id.
        """
        payload = {
            "prompt": workflow_prompt,
            "client_id": client_id,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/prompt", json=payload)
            if response.status_code == 200:
                data = response.json()
                prompt_id = data.get("prompt_id")
                if not prompt_id:
                    raise RuntimeError(f"No prompt_id in ComfyUI response: {data}")
                return prompt_id
            else:
                raise RuntimeError(f"ComfyUI rejected prompt ({response.status_code}): {response.text}")

    async def wait_for_completion(self, prompt_id: str, client_id: str, timeout_seconds: float = 120.0) -> Dict[str, Any]:
        """
        Listens to ComfyUI WebSocket messages until the prompt finishes.
        Falls back to HTTP polling if WebSocket is unavailable or disconnects.
        """
        start_time = time.time()

        try:
            ws_uri = f"{self.ws_url}?clientId={client_id}"
            async with websockets.connect(ws_uri, open_timeout=10.0) as ws:
                while time.time() - start_time < timeout_seconds:
                    remaining_time = max(1.0, timeout_seconds - (time.time() - start_time))
                    try:
                        out = await asyncio.wait_for(ws.recv(), timeout=remaining_time)
                    except asyncio.TimeoutError:
                        break

                    if isinstance(out, str):
                        message = json.loads(out)
                        msg_type = message.get("type")
                        data = message.get("data", {})

                        if msg_type == "executing":
                            # If node is None and prompt_id matches, execution is complete
                            if data.get("node") is None and data.get("prompt_id") == prompt_id:
                                return await self.get_history(prompt_id)
        except Exception as ws_err:
            print(f"[ComfyUIClient] WebSocket notice: {ws_err}. Falling back to polling.")

        # Polling fallback: check /history/{prompt_id} periodically
        while time.time() - start_time < timeout_seconds:
            history = await self.get_history(prompt_id)
            if history and "outputs" in history:
                return history
            await asyncio.sleep(2.0)

        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout_seconds} seconds.")

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """
        Fetches execution history for a given prompt_id.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(f"{self.base_url}/history/{prompt_id}")
                if response.status_code == 200:
                    data = response.json()
                    return data.get(prompt_id, {})
            except Exception as e:
                print(f"[ComfyUIClient] Error fetching history for {prompt_id}: {e}")
        return {}

    def extract_output_filename(self, history_data: Dict[str, Any]) -> Optional[str]:
        """
        Extracts the first generated output image filename from ComfyUI history.
        """
        outputs = history_data.get("outputs", {})
        for _, node_output in outputs.items():
            images = node_output.get("images", [])
            if images and isinstance(images, list):
                filename = images[0].get("filename")
                if filename:
                    return filename
        return None

    async def get_image_url(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """
        Constructs URL to retrieve output image from ComfyUI view endpoint.
        """
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"


comfy_client = ComfyUIClient()

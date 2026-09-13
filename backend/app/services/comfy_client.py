import json
import uuid
import httpx
import websockets
from typing import Dict, Any, Optional
from app.core.config import settings


class ComfyUIClient:
    """
    Client for communicating with headless ComfyUI inference instance
    via REST and WebSockets.
    """

    def __init__(self):
        self.base_url = settings.COMFYUI_URL
        self.ws_url = settings.COMFYUI_WS_URL

    async def queue_prompt(self, workflow_prompt: Dict[str, Any], client_id: str) -> Optional[str]:
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
                return data.get("prompt_id")
            else:
                raise RuntimeError(f"ComfyUI rejected prompt: {response.text}")

    async def wait_for_completion(self, prompt_id: str, client_id: str) -> Dict[str, Any]:
        """
        Listens to ComfyUI WebSocket messages until the prompt finishes,
        returning output image details.
        """
        ws_uri = f"{self.ws_url}?clientId={client_id}"
        async with websockets.connect(ws_uri) as ws:
            while True:
                out = await ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    msg_type = message.get("type")
                    data = message.get("data", {})

                    if msg_type == "executing":
                        # If node is None and prompt_id matches, execution is complete
                        if data.get("node") is None and data.get("prompt_id") == prompt_id:
                            break

        # Fetch output history
        async with httpx.AsyncClient(timeout=30.0) as client:
            history_resp = await client.get(f"{self.base_url}/history/{prompt_id}")
            if history_resp.status_code == 200:
                history_data = history_resp.json()
                return history_data.get(prompt_id, {})
            return {}

    async def get_image_url(self, filename: str, subfolder: str = "", folder_type: str = "output") -> str:
        """
        Constructs URL to retrieve output image from ComfyUI view endpoint.
        """
        return f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"


comfy_client = ComfyUIClient()

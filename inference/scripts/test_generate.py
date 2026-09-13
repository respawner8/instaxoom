"""
Test generation script for instaXoom inference engine.
Sends a 4:5 portrait generation job to ComfyUI, streams progress, and downloads the output image.
"""
import json
import urllib.request
import urllib.parse
import time
import sys
from pathlib import Path

COMFY_HOST = "localhost:8188"
PROMPT_FILE = Path(__file__).resolve().parent.parent / "workflows" / "daily_trend_flux_img2img.json"


def test_generation():
    print(f"[*] Reading workflow from: {PROMPT_FILE}")
    with open(PROMPT_FILE, "r") as f:
        prompt_data = json.load(f)

    # Optional: randomize seed for a fresh image
    prompt_data["7"]["inputs"]["seed"] = int(time.time()) % 10000000

    payload = json.dumps({"prompt": prompt_data}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{COMFY_HOST}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    print("[*] Submitting prompt to ComfyUI...")
    start_time = time.time()
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read())
            prompt_id = res.get("prompt_id")
            print(f"[+] Prompt successfully queued! Job ID: {prompt_id}")
    except Exception as e:
        print(f"[-] Failed to queue prompt: {e}")
        return

    # Poll history for completion
    print("[*] Waiting for RTX 4060 generation to finish...")
    last_node = ""
    while True:
        try:
            time.sleep(1.0)
            hist_req = urllib.request.Request(f"http://{COMFY_HOST}/history/{prompt_id}")
            with urllib.request.urlopen(hist_req) as resp:
                history = json.loads(resp.read())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    if "9" in outputs:
                        images = outputs["9"].get("images", [])
                        if images:
                            img_info = images[0]
                            duration = time.time() - start_time
                            print(f"\n[✓] Generation finished in {duration:.1f} seconds!")
                            filename = img_info["filename"]
                            subfolder = img_info.get("subfolder", "")
                            
                            # Download output image
                            view_url = f"http://{COMFY_HOST}/view?filename={filename}&subfolder={subfolder}&type=output"
                            output_path = Path("test_output_4x5.png")
                            urllib.request.urlretrieve(view_url, output_path)
                            print(f"[✓] Saved test portrait to: {output_path.resolve()}")
                            print(f"[✓] Image size: {output_path.stat().st_size // 1024} KB")
                            return
        except Exception as e:
            print(f"    Waiting... ({e})")

        elapsed = time.time() - start_time
        print(f"\r    Elapsed time: {elapsed:.1f}s...", end="", flush=True)


if __name__ == "__main__":
    test_generation()

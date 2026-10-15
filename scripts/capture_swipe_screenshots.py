import asyncio
import json
import base64
import urllib.request
import subprocess
from pathlib import Path
import os

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", str(Path(__file__).resolve().parent.parent / "scratch")))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

async def main():
    profile_dir = Path("/tmp/chrome_swipe_profile")
    if profile_dir.exists():
        import shutil
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True)

    target_url = "http://127.0.0.1:8000/?run=test_A_cold_verify"
    chrome_cmd = [
        "google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-port=9227",
        "--window-size=1920,1080",
        target_url
    ]
    proc = subprocess.Popen(chrome_cmd)
    try:
        await asyncio.sleep(4)
        import websockets
        pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9227/json").read())
        page = [p for p in pages if "8000" in p.get("url", "")][0]
        ws_url = page["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            msg_id = [1]
            async def send_cdp(method, params=None):
                mid = msg_id[0]
                msg_id[0] += 1
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == mid:
                        return resp

            async def evaluate_js(expr):
                res = await send_cdp("Runtime.evaluate", {
                    "expression": expr,
                    "awaitPromise": True,
                    "returnByValue": True
                })
                return res.get("result", {}).get("result", {}).get("value")

            async def capture_screenshot(out_path: Path):
                res = await send_cdp("Page.captureScreenshot", {"format": "png"})
                data = res["result"]["data"]
                out_path.write_bytes(base64.b64decode(data))
                print(f"Saved screenshot: {out_path} ({len(data)} b64 bytes)")

            await send_cdp("Page.enable")

            # Wait until run data has loaded
            for _ in range(20):
                loaded = await evaluate_js("Boolean(window.currentRunData && window.map)")
                if loaded:
                    break
                await asyncio.sleep(0.5)

            print("Run data loaded. Activating Before/After slider...")
            await evaluate_js("toggleS2Slider(true)")
            await asyncio.sleep(3)

            # Zoom to confluence near Syabrubesi [28.163, 85.338] at zoom level 15
            print("Zooming to confluence [28.163, 85.338], zoom 15...")
            await evaluate_js("""(() => {
                map.setView([28.163, 85.338], 15, { animate: false });
                updateS2SwipePosition();
            })()""")
            await asyncio.sleep(2)

            # 1. Slider at 50%
            print("Configuring slider at 50%...")
            await evaluate_js("""(() => {
                const range = document.getElementById("s2-range-slider");
                range.value = 50;
                updateS2SwipePosition();
            })()""")
            await asyncio.sleep(1.5)
            await capture_screenshot(ARTIFACTS_DIR / "screenshot_trishuli_swipe_50.png")

            # 2. Slider at 25%
            print("Configuring slider at 25%...")
            await evaluate_js("""(() => {
                const range = document.getElementById("s2-range-slider");
                range.value = 25;
                updateS2SwipePosition();
            })()""")
            await asyncio.sleep(1.5)
            await capture_screenshot(ARTIFACTS_DIR / "screenshot_trishuli_swipe_25.png")

            # 3. Slider at 75%
            print("Configuring slider at 75%...")
            await evaluate_js("""(() => {
                const range = document.getElementById("s2-range-slider");
                range.value = 75;
                updateS2SwipePosition();
            })()""")
            await asyncio.sleep(1.5)
            await capture_screenshot(ARTIFACTS_DIR / "screenshot_trishuli_swipe_75.png")

            # 4. Hide analysis layers toggle at 50%
            print("Configuring slider at 50% with Hide Analysis Layers active...")
            await evaluate_js("""(() => {
                const range = document.getElementById("s2-range-slider");
                range.value = 50;
                updateS2SwipePosition();
                const chk = document.getElementById("chk-hide-analysis-layers");
                if (chk) {
                    chk.checked = true;
                    toggleS2AnalysisLayers();
                }
            })()""")
            await asyncio.sleep(1.5)
            await capture_screenshot(ARTIFACTS_DIR / "screenshot_trishuli_swipe_50_hidden_layers.png")
            print("All 4 screenshots captured successfully!")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(main())

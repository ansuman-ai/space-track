import asyncio
import json
import base64
import urllib.request
import subprocess
from pathlib import Path
import os
import websockets

ARTIFACTS_DIR = Path("/home/zeus/.gemini/antigravity/brain/9e2afbf7-ac9b-4fd3-9cad-b12786f88814")

async def send_cdp(ws, method, params=None, msg_id=[1]):
    mid = msg_id[0]
    msg_id[0] += 1
    req = {"id": mid, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == mid:
            return resp

async def capture_screenshot(ws, out_path: Path):
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"})
    data = res["result"]["data"]
    out_path.write_bytes(base64.b64decode(data))
    print(f"Saved screenshot: {out_path.name} ({len(data)} b64 bytes)")

async def evaluate_js(ws, expr):
    res = await send_cdp(ws, "Runtime.evaluate", {
        "expression": expr,
        "awaitPromise": True,
        "returnByValue": True
    })
    return res.get("result", {}).get("value")

async def main():
    profile_dir = Path("/tmp/chrome_v107_recapture")
    if profile_dir.exists():
        import shutil
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True)

    chrome_cmd = [
        "google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-port=9224",
        "--window-size=1920,1080",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    try:
        await asyncio.sleep(2)
        pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9224/json").read())
        page = next(p for p in pages if p.get("type") == "page")
        ws_url = page["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            await send_cdp(ws, "Page.enable")
            await send_cdp(ws, "Runtime.enable")

            # 1. Start Screen
            print("Capturing 1: Start Screen...")
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/"})
            await asyncio.sleep(4)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_start_screen.png")

            # 2. Search Result & Editable 10x10 km Box
            print("Capturing 2: Search Result & 10x10 km Box...")
            await evaluate_js(ws, """(() => {
                const inp = document.getElementById('start-search-input');
                inp.value = 'Melamchi';
                document.getElementById('btn-start-search').click();
            })()""")
            await asyncio.sleep(2)
            await evaluate_js(ws, """(() => {
                const first = document.querySelector('.start-search-item');
                if (first) first.click();
            })()""")
            await asyncio.sleep(3)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_start_search_box.png")

            # 3. Melamchi Before/After (pre and post)
            print("Capturing 3: Melamchi Before/After...")
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/?run=test_B_cold_verify"})
            await asyncio.sleep(4)
            await evaluate_js(ws, "toggleS2Slider(true);")
            await asyncio.sleep(3)
            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 0;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_melamchi_s2_pre.png")

            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 100;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_melamchi_s2_post.png")

            # 4. Trishuli Before/After (pre and post)
            print("Capturing 4: Trishuli Before/After...")
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/?run=verify_final7_A"})
            await asyncio.sleep(4)
            await evaluate_js(ws, "toggleS2Slider(true);")
            await asyncio.sleep(3)
            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 0;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_trishuli_s2_pre.png")

            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 100;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_trishuli_s2_post.png")

            # 5. Chamoli Before/After (pre and post)
            print("Capturing 5: Chamoli Before/After...")
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/?run=run_20261013_194053_chamoli_disaster_2021"})
            await asyncio.sleep(4)
            await evaluate_js(ws, "toggleS2Slider(true);")
            await asyncio.sleep(3)
            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 0;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_chamoli_s2_pre.png")

            await evaluate_js(ws, """(() => {
                const slider = document.getElementById('s2-range-slider');
                slider.value = 100;
                slider.dispatchEvent(new Event('input'));
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_chamoli_s2_post.png")

            # 6. Finished Run View
            print("Capturing 6: Finished Run Normal View...")
            await evaluate_js(ws, "toggleS2Slider(false);")
            await asyncio.sleep(2)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_finished_run_view.png")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(main())

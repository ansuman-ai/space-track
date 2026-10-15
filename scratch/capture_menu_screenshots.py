import asyncio
import json
import base64
import urllib.request
import subprocess
from pathlib import Path
import os
import shutil
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
    profile_dir = Path("/tmp/chrome_menu_capture")
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True)

    chrome_cmd = [
        "google-chrome",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={profile_dir}",
        "--remote-debugging-port=9225",
        "--window-size=1920,1080",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    try:
        await asyncio.sleep(2)
        pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9225/json").read())
        page = next(p for p in pages if p.get("type") == "page")
        ws_url = page["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            await send_cdp(ws, "Page.enable")
            await send_cdp(ws, "Runtime.enable")

            scenarios = [
                {
                    "name": "screenshot_menu_1366_trishuli_copilot_closed.png",
                    "url": "http://127.0.0.1:8000/?run=test_A_cold_verify",
                    "width": 1366,
                    "height": 768,
                    "open_copilot": False
                },
                {
                    "name": "screenshot_menu_1366_trishuli_copilot_open.png",
                    "url": "http://127.0.0.1:8000/?run=test_A_cold_verify",
                    "width": 1366,
                    "height": 768,
                    "open_copilot": True
                },
                {
                    "name": "screenshot_menu_1920_melamchi_copilot_closed.png",
                    "url": "http://127.0.0.1:8000/?run=test_B_cold_verify",
                    "width": 1920,
                    "height": 1080,
                    "open_copilot": False
                },
                {
                    "name": "screenshot_menu_1920_melamchi_copilot_open.png",
                    "url": "http://127.0.0.1:8000/?run=test_B_cold_verify",
                    "width": 1920,
                    "height": 1080,
                    "open_copilot": True
                },
                {
                    "name": "screenshot_menu_1366_start_screen.png",
                    "url": "http://127.0.0.1:8000/",
                    "width": 1366,
                    "height": 768,
                    "open_copilot": False
                }
            ]

            for s in scenarios:
                print(f"Testing {s['name']} (width={s['width']}, copilot={s['open_copilot']})...")
                await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                    "width": s["width"],
                    "height": s["height"],
                    "deviceScaleFactor": 1,
                    "mobile": False
                })

                await send_cdp(ws, "Page.navigate", {"url": s["url"]})
                await asyncio.sleep(2.5)

                if s["open_copilot"]:
                    await evaluate_js(ws, """
                        const cpBtn = document.getElementById("btn-floating-copilot");
                        if (cpBtn) cpBtn.click();
                    """)
                    await asyncio.sleep(1)

                await evaluate_js(ws, """
                    const btnMore = document.getElementById("btn-more-menu");
                    if (btnMore) btnMore.click();
                """)
                await asyncio.sleep(0.5)

                out_p = ARTIFACTS_DIR / s["name"]
                await capture_screenshot(ws, out_p)

    finally:
        proc.terminate()
        proc.wait()
        if profile_dir.exists():
            shutil.rmtree(profile_dir)

if __name__ == "__main__":
    asyncio.run(main())

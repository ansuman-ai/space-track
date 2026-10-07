import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets
from pathlib import Path

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
    import base64
    out_path.write_bytes(base64.b64decode(data))
    print(f"Saved screenshot: {out_path} ({len(data)} b64 bytes)")

async def evaluate_js(ws, expr):
    res = await send_cdp(ws, "Runtime.evaluate", {
        "expression": expr,
        "awaitPromise": True,
        "returnByValue": True
    })
    return res.get("result", {}).get("value")

async def main():
    profile_dir = Path("/tmp/chrome_phase2_profile")
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
        "--remote-debugging-port=9222",
        "--window-size=1920,1080",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    try:
        await asyncio.sleep(2)
        pages = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
        page = next(p for p in pages if p.get("type") == "page")
        ws_url = page["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50*1024*1024) as ws:
            await send_cdp(ws, "Page.enable")
            await send_cdp(ws, "Runtime.enable")
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/"})
            await asyncio.sleep(4)

            # Open New Analysis Modal
            print("Opening New Analysis modal...")
            await evaluate_js(ws, "document.getElementById('btn-new-run').click()")
            await asyncio.sleep(1)

            # Click Trishuli preset
            print("Selecting Trishuli preset...")
            await evaluate_js(ws, "document.querySelector('[data-preset=\"trishuli\"]').click()")
            await asyncio.sleep(0.5)

            # Set custom event name
            await evaluate_js(ws, "document.getElementById('input-event-name').value = 'Trishuli Rapid Assessment (Phase 2)'")
            await asyncio.sleep(0.5)

            # Submit
            print("Submitting new analysis pipeline...")
            await evaluate_js(ws, "document.getElementById('btn-submit-new-run').click()")
            
            # Wait for execution to be active
            await asyncio.sleep(4)
            print("Capturing in-progress screenshot...")
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_phase2_in_progress.png")

            # Poll until finished
            print("Waiting for run completion...")
            for i in range(120): # up to 240s
                await asyncio.sleep(2)
                res_raw = await evaluate_js(ws, """JSON.stringify((() => {
                    const el = document.getElementById('progress-card-title');
                    const fill = document.getElementById('progress-bar-fill');
                    const msg = document.getElementById('progress-current-msg');
                    const elapsed = document.getElementById('progress-elapsed');
                    return {
                        title: el ? el.textContent : '',
                        fill: fill ? fill.style.width : '',
                        msg: msg ? msg.textContent : '',
                        elapsed: elapsed ? elapsed.textContent : ''
                    };
                })())""")
                res = json.loads(res_raw) if res_raw else {}
                print(f"Progress ({res.get('elapsed')}): {res.get('fill')} - {res.get('title')} | {res.get('msg')}")
                if "Completed" in res.get("title", "") or "Complete" in res.get("title", "") or "DEGRADED" in res.get("title", ""):
                    print("Run completed!")
                    break

            # Allow 3s for final layers and cards to render
            await asyncio.sleep(3)
            print("Capturing finished screenshot...")
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_phase2_finished.png")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(main())

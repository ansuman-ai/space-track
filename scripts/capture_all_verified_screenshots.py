import asyncio
import json
import base64
import urllib.request
import subprocess
from pathlib import Path
import os

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", str(Path(__file__).resolve().parent.parent / "scratch")))

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
    print(f"Saved screenshot: {out_path} ({len(data)} b64 bytes)")

async def evaluate_js(ws, expr):
    res = await send_cdp(ws, "Runtime.evaluate", {
        "expression": expr,
        "awaitPromise": True,
        "returnByValue": True
    })
    return res.get("result", {}).get("value")

async def main():
    profile_dir = Path("/tmp/chrome_verify_profile")
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

            # 1. Load Trishuli with Offline Basemap (DEM Hillshade + OSM vectors + Devanagari labels)
            # Zoom to Syabrubesi / Dhunche
            target_url = "http://127.0.0.1:8000/?run=run_20261007_221101_trishuli_rapid_assessmen&lat=28.16&lng=85.35&zoom=14"
            print(f"Navigating to: {target_url}")
            await send_cdp(ws, "Page.navigate", {"url": target_url})
            await asyncio.sleep(4)

            # Ensure offline basemap is active
            await evaluate_js(ws, """(() => {
                const radio = document.querySelector('input[name="basemap"][value="offline"]');
                if (radio && !radio.checked) {
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change'));
                }
            })()""")
            await asyncio.sleep(2)

            print("Capturing Trishuli zoomed with offline DEM hillshade and OSM vectors...")
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_trishuli_offline_basemap_zoomed.png")

            # Also capture Trishuli overview with offline basemap
            await evaluate_js(ws, "map.setView([28.175, 85.36], 12)")
            await asyncio.sleep(2)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_trishuli_offline_basemap_overview.png")

            # 2. Capture Phase 2 Finished View (showing the newly executed run selected with all cards)
            await evaluate_js(ws, "document.getElementById('new-run-modal').classList.add('hidden')")
            await evaluate_js(ws, "zoomToDamagedArea(currentRunData)")
            await asyncio.sleep(2)
            print("Capturing finished run overview...")
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_phase2_finished.png")

            # 3. Test Invalid Input Modal Error Display
            print("Testing invalid input error modal...")
            await evaluate_js(ws, "document.getElementById('btn-new-run').click()")
            await asyncio.sleep(0.5)
            # Enter inverted bbox (West 85.5 > East 85.3)
            await evaluate_js(ws, """(() => {
                document.getElementById('input-event-date').value = '2026-08-26';
                document.getElementById('input-bbox-w').value = '85.5000';
                document.getElementById('input-bbox-s').value = '28.1000';
                document.getElementById('input-bbox-e').value = '85.3000';
                document.getElementById('input-bbox-n').value = '28.2500';
                document.getElementById('btn-submit-new-run').click();
            })()""")
            await asyncio.sleep(1)
            await capture_screenshot(ws, ARTIFACTS_DIR / "screenshot_phase2_error_handling.png")
            print("Captured error handling screenshot.")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(main())

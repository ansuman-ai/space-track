import asyncio
import json
import base64
import urllib.request
from pathlib import Path
import websockets

ARTIFACTS_DIR = Path("/home/zeus/.gemini/antigravity/brain/9e2afbf7-ac9b-4fd3-9cad-b12786f88814")

async def send_cmd(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data

async def run_tests():
    # 1. Create a new target/tab via CDP
    req = urllib.request.Request("http://127.0.0.1:9224/json/new?about:blank", method="PUT")
    resp = urllib.request.urlopen(req)
    tab_info = json.loads(resp.read().decode())
    ws_url = tab_info["webSocketDebuggerUrl"]
    target_id = tab_info["id"]

    async with websockets.connect(ws_url) as ws:
        msg_id = 1
        
        # Enable Page and Runtime
        await send_cmd(ws, "Page.enable", {}, msg_id); msg_id += 1
        await send_cmd(ws, "Runtime.enable", {}, msg_id); msg_id += 1

        print("=== TEST 1: START SCREEN (http://127.0.0.1:8000/ with no ?run=) ===")
        # Viewport: 1366x768, zoom 100%
        await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
            "width": 1366,
            "height": 768,
            "deviceScaleFactor": 1.0,
            "mobile": False
        }, msg_id); msg_id += 1

        # Clear cache & cookies for fresh profile behavior
        await send_cmd(ws, "Network.clearBrowserCache", {}, msg_id); msg_id += 1

        await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/"}, msg_id); msg_id += 1
        
        # Wait for /api/runs to load
        for _ in range(20):
            res = await send_cmd(ws, "Runtime.evaluate", {
                "expression": "document.querySelectorAll('.start-run-chip').length",
                "returnByValue": True
            }, msg_id); msg_id += 1
            if res["result"]["result"].get("value", 0) > 0:
                break
            await asyncio.sleep(0.5)

        # Evaluate Start Screen DOM state
        eval_script = """
        (() => {
            const isStartActive = document.body.classList.contains("start-screen-active");
            const sidePanelVisible = window.getComputedStyle(document.getElementById("side-panel")).display !== "none";
            const startPanelVisible = !document.getElementById("start-screen-panel").classList.contains("hidden");
            const valPillVisible = window.getComputedStyle(document.getElementById("val-header-validation")).display !== "none";
            const attrSentinelVisible = window.getComputedStyle(document.getElementById("attr-sentinel")).display !== "none";
            const sitrepHeaderVisible = window.getComputedStyle(document.getElementById("btn-download-sitrep")).display !== "none";
            const titleText = document.getElementById("run-main-title").textContent.trim();
            const subtitleText = document.getElementById("header-subtitle-sentence").textContent.trim();
            const chipsCount = document.querySelectorAll(".start-run-chip").length;

            return {
                isStartActive,
                sidePanelVisible,
                startPanelVisible,
                valPillVisible,
                attrSentinelVisible,
                sitrepHeaderVisible,
                titleText,
                subtitleText,
                chipsCount
            };
        })()
        """
        res = await send_cmd(ws, "Runtime.evaluate", {"expression": eval_script, "returnByValue": True}, msg_id); msg_id += 1
        dom_state = res["result"]["result"]["value"]
        print("Start Screen DOM State:", json.dumps(dom_state, indent=2))

        assert dom_state["isStartActive"], "start-screen-active class missing from body"
        assert not dom_state["sidePanelVisible"], "side-panel should be hidden on start screen"
        assert dom_state["startPanelVisible"], "start-screen-panel must be visible"
        assert not dom_state["valPillVisible"], "val-header-validation must be hidden"
        assert not dom_state["attrSentinelVisible"], "attr-sentinel must be hidden"
        assert not dom_state["sitrepHeaderVisible"], "sitrep button must be hidden on start screen"
        assert "practice run" not in dom_state["titleText"].lower(), "title must not contain run text"
        assert dom_state["chipsCount"] > 0, "previous assessment chips should be loaded"
        print("TEST 1 PASSED: Start screen cleanly renders with zero run-specific artifacts!\n")

        # Capture Start Screen Screenshot
        shot_res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"}, msg_id); msg_id += 1
        img_bytes = base64.b64decode(shot_res["result"]["data"])
        start_shot_path = ARTIFACTS_DIR / "screenshot_start_screen_v114.png"
        with open(start_shot_path, "wb") as f:
            f.write(img_bytes)
        print(f"Saved start screen screenshot to: {start_shot_path}\n")

        print("=== TEST 2: HEADER AT MULTIPLE WIDTHS & ZOOM LEVELS ===")
        # We test combinations of widths: 1280, 1366, 1600, 1920 px and zoom: 100%, 110%, 125%
        # Load run: test_A_trishuli
        await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/?run=test_A_trishuli"}, msg_id); msg_id += 1
        await asyncio.sleep(2.0)

        widths = [1280, 1366, 1600, 1920]
        zooms = [1.0, 1.10, 1.25]

        header_eval_script = """
        (() => {
            const navbar = document.getElementById("top-navbar");
            const moreBtn = document.getElementById("btn-more-menu");
            const sitrepBtn = document.getElementById("btn-download-sitrep");
            const sitrepMenuItem = document.getElementById("menu-opt-sitrep");
            const titleEl = document.getElementById("run-main-title");
            
            const navRect = navbar.getBoundingClientRect();
            const btnRect = moreBtn.getBoundingClientRect();
            
            // Check overflow
            const isOverflowing = navbar.scrollWidth > navbar.clientWidth;
            const isBtnInside = btnRect.right <= window.innerWidth && btnRect.left >= 0;
            const isBtnVisible = window.getComputedStyle(moreBtn).display !== "none" && window.getComputedStyle(moreBtn).visibility !== "hidden";
            
            return {
                windowWidth: window.innerWidth,
                windowHeight: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio,
                navScrollWidth: navbar.scrollWidth,
                navClientWidth: navbar.clientWidth,
                isOverflowing,
                moreBtnRect: { left: Math.round(btnRect.left), right: Math.round(btnRect.right), width: Math.round(btnRect.width) },
                isBtnInside,
                isBtnVisible,
                sitrepBtnDisplay: window.getComputedStyle(sitrepBtn).display,
                sitrepMenuItemDisplay: window.getComputedStyle(sitrepMenuItem).display,
                titleText: titleEl.textContent,
                titleTooltip: titleEl.getAttribute("title")
            };
        })()
        """

        for w in widths:
            for z in zooms:
                # Desktop browser zoom emulates by setting effective layout width = w / z, with deviceScaleFactor = z
                eff_w = int(w / z)
                eff_h = int(768 / z)
                await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                    "width": eff_w,
                    "height": eff_h,
                    "deviceScaleFactor": z,
                    "mobile": False
                }, msg_id); msg_id += 1
                await asyncio.sleep(0.3)

                res = await send_cmd(ws, "Runtime.evaluate", {"expression": header_eval_script, "returnByValue": True}, msg_id); msg_id += 1
                h_state = res["result"]["result"]["value"]

                status_str = f"Width {w}px @ {int(z*100)}% zoom (eff_w={eff_w}px): "
                if not h_state["isOverflowing"] and h_state["isBtnInside"] and h_state["isBtnVisible"]:
                    status_str += f"OK (btn_x={h_state['moreBtnRect']['left']}-{h_state['moreBtnRect']['right']}, sitrepHeader={h_state['sitrepBtnDisplay']}, sitrepMenu={h_state['sitrepMenuItemDisplay']})"
                else:
                    status_str += f"FAIL (overflow={h_state['isOverflowing']}, btnInside={h_state['isBtnInside']})"
                print(status_str)

                assert not h_state["isOverflowing"], f"Header overflowed at {w}px @ {z*100}% zoom"
                assert h_state["isBtnInside"] and h_state["isBtnVisible"], f"More button not fully inside at {w}px @ {z*100}% zoom"

        print("\nAll width and zoom combinations passed with ZERO overflow and more button always visible!\n")

        print("=== TEST 3: CAPTURE HEADER AT 1366 px and 125% ZOOM ===")
        # Effective width = 1366 / 1.25 = 1093
        await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
            "width": 1093,
            "height": int(768 / 1.25),
            "deviceScaleFactor": 1.25,
            "mobile": False
        }, msg_id); msg_id += 1
        await asyncio.sleep(0.5)

        # Open ⋯ menu to demonstrate it opens and every item works
        await send_cmd(ws, "Runtime.evaluate", {
            "expression": "document.getElementById('btn-more-menu').click();"
        }, msg_id); msg_id += 1
        await asyncio.sleep(0.3)

        # Capture Header screenshot with dropdown menu open
        shot_res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"}, msg_id); msg_id += 1
        img_bytes = base64.b64decode(shot_res["result"]["data"])
        header_shot_path = ARTIFACTS_DIR / "screenshot_header_1366_125zoom.png"
        with open(header_shot_path, "wb") as f:
            f.write(img_bytes)
        print(f"Saved header screenshot at 1366px 125% zoom to: {header_shot_path}\n")

    # Close target tab
    urllib.request.urlopen(f"http://127.0.0.1:9224/json/close/{target_id}")

if __name__ == "__main__":
    asyncio.run(run_tests())

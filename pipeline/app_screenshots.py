"""Retake the app screenshots in exports/app_screenshots/.

    python pipeline/app_screenshots.py

Starts the app locally, opens each page in headless Chrome (the same browser kaleido uses for the
chart PNGs), saves a full-page PNG at laptop width (1440 px) and phone width (390 px), trims the empty
space at the bottom, then stops the app. Not part of run_all.py: run it by hand after the data or the
app changes. Needs Pillow (pip install pillow) for the trim.
"""
import asyncio
import base64
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import choreographer as choreo
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exports" / "app_screenshots"
PORT = 8517
LOAD_SECONDS = 15   # first render of each page (charts draw late)
CLICK_SECONDS = 10  # after switching kidney -> cancer
SETTLE_SECONDS = 8  # after resizing to the full page height

# name: (url path, button to click first or None)
DESKTOP = {
    "1_home": ("", None),
    "2_state_explorer": ("state-explorer", None),
    "3_scorecard": ("scorecard", None),
    "4_specialist_gaps_kidney": ("specialist-gaps", None),
    "4b_specialist_gaps_cancer": ("specialist-gaps", "Cancer care"),
    "5_centre_model_dialysis": ("centre-model", None),
    "5b_centre_model_radiotherapy": ("centre-model", "Radiotherapy centre"),
    "6_cost_pressure": ("cost-pressure", None),
    "7_under_the_hood": ("under-the-hood", None),
}
PHONE = {
    "phone_1_home": ("", None),
    "phone_2_state_explorer": ("state-explorer", None),
    "phone_5_centre_model": ("centre-model", None),
}


async def shoot(browser, width: int, name: str, path: str, button: str | None) -> None:
    tab = await browser.create_tab("about:blank")

    async def viewport(height: int) -> None:
        await tab.send_command("Emulation.setDeviceMetricsOverride", params={
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 700})

    async def js(expression: str):
        r = await tab.send_command("Runtime.evaluate", params={"expression": expression, "returnByValue": True})
        return r["result"]["result"].get("value")

    await viewport(4000)  # tall from the start so every chart is on screen and draws
    await tab.send_command("Page.navigate", params={"url": f"http://localhost:{PORT}/{path}"})
    await asyncio.sleep(LOAD_SECONDS)
    if button:
        found = await js(f"(()=>{{const b=[...document.querySelectorAll('button')]"
                         f".find(x=>x.innerText.trim()==={button!r}); if(b){{b.click(); return true}} return false}})()")
        if not found:
            raise SystemExit(f"{name}: button {button!r} not found")
        await asyncio.sleep(CLICK_SECONDS)
    height = int(await js("document.querySelector('[data-testid=\"stMain\"]').scrollHeight") or 900)
    await viewport(min(height + 40, 9000))
    await asyncio.sleep(SETTLE_SECONDS)
    shot = await tab.send_command("Page.captureScreenshot", params={"format": "png"})
    file = OUT / f"{name}.png"
    file.write_bytes(base64.b64decode(shot["result"]["data"]))
    trim_bottom(file)
    print(f"  saved {file.relative_to(ROOT)}")


def trim_bottom(file: Path, margin: int = 40) -> None:
    """Cut the empty background below the footer."""
    im = Image.open(file).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 2, im.height - 2)))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        im.crop((0, 0, im.width, min(im.height, box[3] + margin))).save(file, optimize=True)


async def run_all() -> None:
    async with choreo.Browser(headless=True) as browser:
        # warm-up: the first page load after start-up renders blank, so load once and throw it away
        tab = await browser.create_tab("about:blank")
        await tab.send_command("Page.navigate", params={"url": f"http://localhost:{PORT}/"})
        await asyncio.sleep(LOAD_SECONDS)
        for width, pages in ((1440, DESKTOP), (390, PHONE)):
            for name, (path, button) in pages.items():
                await shoot(browser, width, name, path, button)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py"),
                            "--server.port", str(PORT), "--server.headless", "true"], cwd=ROOT)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit("The app did not start")
        asyncio.run(run_all())
    finally:
        app.terminate()



if __name__ == "__main__":
    main()

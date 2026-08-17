# ============================================
# RENDER DIRECT TEST - 2 BOTS
# Meeting hardcode | No HTML | No Central
# ============================================
import os
import sys
import asyncio
import random
import base64
import gc
from datetime import datetime
from playwright.async_api import async_playwright
from aiohttp import web

print("=== WORKER STARTING ===", flush=True)

# ========== HARDCODED ==========
MEETING_CODE = "5415403058"
PASSCODE = "850893"
BOT_COUNT = 1
DURATION_MINUTES = 120
# ===============================

INDIAN_FIRST_NAMES = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Reyansh', 'Ayaan', 'Krishna', 'Ishaan', 'Shaurya',
    'Rahul', 'Rohan', 'Priya', 'Ananya', 'Diya', 'Saanvi', 'Aadhya', 'Kavya', 'Riya', 'Anika',
    'Amit', 'Rajesh', 'Sneha', 'Pooja', 'Neha', 'Vikram', 'Karan', 'Manish', 'Suresh', 'Deepak'
]
INDIAN_LAST_NAMES = [
    'Sharma', 'Verma', 'Patel', 'Kumar', 'Singh', 'Reddy', 'Gupta', 'Joshi',
    'Malhotra', 'Mehta', 'Chopra', 'Khanna', 'Agarwal', 'Jain', 'Saxena',
    'Bansal', 'Srivastava', 'Mishra', 'Pandey', 'Rao', 'Desai', 'Nair'
]

def get_indian_name():
    return f"{random.choice(INDIAN_FIRST_NAMES)} {random.choice(INDIAN_LAST_NAMES)}"

ZOOM_PARTS = {
    'domain': base64.b64decode('em9vbS51cw==').decode(),
    'join_path': base64.b64decode('d2Mvam9pbg==').decode()
}

def get_zoom_url(meeting_code):
    return f"https://{ZOOM_PARTS['domain']}/{ZOOM_PARTS['join_path']}/{meeting_code}"

active_browsers = []
active_contexts = []

async def start_bot(tag, wait_time, meetingcode, passcode):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Started", flush=True)
    gc.collect()
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Launching browser...", flush=True)
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--single-process',
                    '--mute-audio',
                    '--use-fake-device-for-media-stream',
                    '--window-size=640,480',
                    '--disable-web-security',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            active_browsers.append(browser)
            context = await browser.new_context(
                viewport={"width": 640, "height": 480},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            active_contexts.append(context)
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Navigating...", flush=True)
            await page.goto(get_zoom_url(meetingcode), timeout=60000)
            await asyncio.sleep(1.5)

            # Name
            try:
                user_name = get_indian_name()
                for sel in ['//*[@id="input-for-name"]', '//input[@placeholder="Enter your name"]', '//input[@name="name"]']:
                    try:
                        loc = page.locator(f'xpath={sel}')
                        if await loc.count() > 0:
                            await loc.first.fill(user_name)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Name entered: {user_name}", flush=True)
                            break
                    except:
                        continue
                else:
                    await page.keyboard.type(user_name)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Name typed: {user_name}", flush=True)
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Name error: {e}", flush=True)

            # Passcode
            if passcode and passcode not in ["", "0"]:
                try:
                    await asyncio.sleep(0.5)
                    loc = page.locator('xpath=/html/body/div[2]/div[1]/div/div[1]/div/div[2]/div[2]/div/input')
                    if await loc.count() > 0:
                        await loc.fill(passcode)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Passcode entered", flush=True)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Passcode error: {e}", flush=True)

            await asyncio.sleep(0.8)

            # Join
            try:
                loc = page.locator('xpath=/html/body/div[2]/div[1]/div/div[1]/div/div[2]/button')
                if await loc.count() > 0:
                    await loc.click()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Join clicked", flush=True)
                else:
                    await page.keyboard.press('Enter')
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Enter pressed", flush=True)
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Join error: {e}", flush=True)
                await page.keyboard.press('Enter')

            await asyncio.sleep(2)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Joined! Staying {wait_time//60} min...", flush=True)

            elapsed = 0
            while elapsed < wait_time:
                await asyncio.sleep(15)
                elapsed += 15
                try:
                    await page.evaluate("() => document.title")
                except:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} page closed", flush=True)
                    break

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Done", flush=True)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Failed: {str(e)[:200]}", flush=True)
    finally:
        try:
            if context in active_contexts:
                await context.close()
                active_contexts.remove(context)
        except:
            pass
        try:
            if browser in active_browsers:
                await browser.close()
                active_browsers.remove(browser)
        except:
            pass
        gc.collect()

async def health(request):
    return web.Response(text="ok - bots running")

async def start_http():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"HTTP server on port {port}", flush=True)

async def run_bots():
    wait_time = DURATION_MINUTES * 60
    print(f"\n===== STARTING {BOT_COUNT} BOTS =====", flush=True)
    print(f"Meeting : {MEETING_CODE}", flush=True)
    print(f"Passcode: {PASSCODE}", flush=True)
    print(f"Duration: {DURATION_MINUTES} min", flush=True)
    print("===============================\n", flush=True)

    tasks = []
    for i in range(BOT_COUNT):
        tag = f"Bot-{i+1}"
        tasks.append(asyncio.create_task(start_bot(tag, wait_time, MEETING_CODE, PASSCODE)))
        await asyncio.sleep(1.2)

    await asyncio.gather(*tasks, return_exceptions=True)
    print("\n===== ALL BOTS FINISHED =====\n", flush=True)

async def main():
    print("=== MAIN STARTED ===", flush=True)
    await start_http()
    print("=== HTTP OK, STARTING BOTS ===", flush=True)
    await run_bots()
    print("=== KEEPING SERVICE ALIVE ===", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())

# ============================================
# RENDER WORKER - Tumhara working code + HTTP keep-alive
# ============================================
import os
import asyncio
import socketio
import random
import base64
import gc
from datetime import datetime
from playwright.async_api import async_playwright
from aiohttp import web

CENTRAL_SERVER = "https://zoom-bot-central-production.up.railway.app"
WORKER_ID = "render-1"        # ← yahan
MAX_CAPACITY = 2              # ← 2 bots only

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
should_stop = False
current_running = 0
lock = asyncio.Lock()

async def force_close_all():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Force closing all browsers...")
    for ctx in list(active_contexts):
        try: await ctx.close()
        except: pass
    active_contexts.clear()
    for br in list(active_browsers):
        try: await br.close()
        except: pass
    active_browsers.clear()
    gc.collect()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] All browsers closed")

async def start_bot(tag, wait_time, meetingcode, passcode):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Started")
    gc.collect()
    browser = None
    context = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--mute-audio',
                      '--use-fake-device-for-media-stream', '--window-size=800,600',
                      '--disable-web-security', '--disable-blink-features=AutomationControlled']
            )
            active_browsers.append(browser)
            context = await browser.new_context(
                viewport={"width": 800, "height": 600},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            active_contexts.append(context)
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = await context.new_page()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Navigating to Zoom...")
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
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Name entered: {user_name}")
                            break
                    except: continue
                else:
                    await page.keyboard.type(user_name)
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Name error: {e}")

            # Passcode
            if passcode and passcode not in ["", "0"]:
                try:
                    await asyncio.sleep(0.4)
                    loc = page.locator('xpath=/html/body/div[2]/div[1]/div/div[1]/div/div[2]/div[2]/div/input')
                    if await loc.count() > 0:
                        await loc.fill(passcode)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Passcode entered")
                except: pass

            await asyncio.sleep(0.8)

            # Join
            try:
                loc = page.locator('xpath=/html/body/div[2]/div[1]/div/div[1]/div/div[2]/button')
                if await loc.count() > 0:
                    await loc.click()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Join clicked")
                else:
                    await page.keyboard.press('Enter')
            except:
                await page.keyboard.press('Enter')

            await asyncio.sleep(2)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Joined! Staying...")

            elapsed = 0
            while elapsed < wait_time and not should_stop:
                await asyncio.sleep(15)
                elapsed += 15
                try: await page.evaluate("() => document.title")
                except: break
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Done")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} Failed: {str(e)[:120]}")
    finally:
        try:
            if context in active_contexts:
                await context.close()
                active_contexts.remove(context)
        except: pass
        try:
            if browser in active_browsers:
                await browser.close()
                active_browsers.remove(browser)
        except: pass
        gc.collect()

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected to Central Server")
    await sio.emit("register_worker", {"worker_id": WORKER_ID, "max_capacity": MAX_CAPACITY})

@sio.event
async def disconnect():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Disconnected")

@sio.event
async def registered(data):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Registered as {WORKER_ID}")

@sio.event
async def new_task(data):
    global current_running, should_stop
    should_stop = False
    task_id = data["task_id"]
    bot_count = min(data["bot_count"], MAX_CAPACITY)   # hard limit 2
    meeting_code = data["meeting_code"]
    passcode = data.get("passcode", "")
    duration = data["duration_minutes"] * 60
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] NEW TASK → {bot_count} bots | {meeting_code}")

    async with lock:
        current_running += bot_count
        await sio.emit("update_capacity", {"worker_id": WORKER_ID, "free_capacity": max(0, MAX_CAPACITY - current_running)})

    tasks = []
    for i in range(bot_count):
        if should_stop: break
        tag = f"{WORKER_ID}-Bot-{i+1}"
        tasks.append(asyncio.create_task(start_bot(tag, duration, meeting_code, passcode)))
        await asyncio.sleep(0.8)

    await asyncio.gather(*tasks, return_exceptions=True)

    async with lock:
        current_running = max(0, current_running - bot_count)
        await sio.emit("update_capacity", {"worker_id": WORKER_ID, "free_capacity": max(0, MAX_CAPACITY - current_running)})
        await sio.emit("task_completed", {"task_id": task_id, "worker_id": WORKER_ID, "bots_completed": bot_count})

@sio.event
async def terminate(data):
    global should_stop, current_running
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === TERMINATE RECEIVED ===")
    should_stop = True
    current_running = 0
    await force_close_all()
    await sio.emit("update_capacity", {"worker_id": WORKER_ID, "free_capacity": MAX_CAPACITY})
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Capacity restored + browsers killed")

# ===== HTTP server (Render keep-alive ke liye) =====
async def health(request):
    return web.Response(text="ok")

async def start_http():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"HTTP server on port {port}")

async def worker_loop():
    while True:
        try:
            await sio.connect(CENTRAL_SERVER, wait_timeout=15)
            await sio.wait()
        except Exception as e:
            print(f"Connection error: {e} | Reconnecting...")
            await asyncio.sleep(8)

async def main():
    await start_http()
    await worker_loop()

if __name__ == "__main__":
    asyncio.run(main())

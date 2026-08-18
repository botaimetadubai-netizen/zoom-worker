# main.py
import asyncio
import random
import time
import gc
import base64
import os
from datetime import datetime
from contextlib import asynccontextmanager

import psutil
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from playwright.async_api import async_playwright
import nest_asyncio

nest_asyncio.apply()

# ------------------------------------------------------------
#  CONFIG
# ------------------------------------------------------------
MAX_BOTS = 100
BROWSER_ARGS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-software-rasterizer',
    '--disable-extensions',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',
    '--disable-features=PermissionPrompt',
    '--disable-notifications',
    '--disable-popup-blocking',
    '--disable-camera',
    '--disable-video-capture',
    '--mute-audio',
    '--use-fake-device-for-media-stream',
    '--use-file-for-fake-audio-capture=/dev/null',
    '--window-size=800,600',
    '--max_old_space_size=256',
    '--js-flags=--max-old-space-size=256',
    '--disable-site-isolation-trials',
    '--disable-web-security',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disk-cache-size=0',
    '--media-cache-size=0'
]

ZOOM_PARTS = {
    'domain': base64.b64decode('em9vbS51cw==').decode(),
    'join_path': base64.b64decode('d2Mvam9pbg==').decode()
}

def get_zoom_url(meeting_code):
    return f"https://{ZOOM_PARTS['domain']}/{ZOOM_PARTS['join_path']}/{meeting_code}"

# ------------------------------------------------------------
#  NAME GENERATOR (Indian + English, realistic)
# ------------------------------------------------------------
INDIAN_FIRST = [
    'Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Reyansh', 'Ayaan', 'Krishna', 'Ishaan', 'Shaurya',
    'Rahul', 'Rohan', 'Priya', 'Ananya', 'Diya', 'Saanvi', 'Aadhya', 'Kavya', 'Riya', 'Anika',
    'Amit', 'Rajesh', 'Sneha', 'Pooja', 'Neha', 'Vikram', 'Karan', 'Manish', 'Suresh', 'Deepak',
    'Aisha', 'Meera', 'Arnav', 'Ishita', 'Kabir', 'Zara', 'Ira', 'Ivy', 'Eva', 'Leo', 'Mia', 'Noah'
]
INDIAN_LAST = [
    'Sharma', 'Verma', 'Patel', 'Kumar', 'Singh', 'Reddy', 'Gupta', 'Joshi',
    'Malhotra', 'Mehta', 'Chopra', 'Khanna', 'Agarwal', 'Jain', 'Saxena',
    'Bansal', 'Srivastava', 'Mishra', 'Pandey', 'Rao', 'Desai', 'Nair'
]
ENGLISH_FIRST = [
    'James', 'Oliver', 'Harry', 'Jack', 'Charlie', 'Thomas', 'Oscar', 'William', 'George', 'Arthur',
    'Noah', 'Liam', 'Mason', 'Ethan', 'Logan', 'Lucas', 'Mia', 'Emma', 'Sophia', 'Olivia', 'Ava', 'Isabella',
    'Emily', 'Abigail', 'Charlotte', 'Ella', 'Chloe', 'Grace', 'Amelia'
]
ENGLISH_LAST = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
    'Wilson', 'Taylor', 'Anderson', 'Thomas', 'Jackson', 'White', 'Harris', 'Martin', 'Thompson', 'Moore'
]
EMOJIS = ['😎', '🔥', '✨', '🚀', '💪', '🎯', '👑', '🙌', '💯', '🤙']

def generate_name():
    """Return a realistic Indian/English name with occasional numbers, suffix, emoji."""
    style = random.choice(['full', 'full_lower', 'first_num', 'first_suffix', 'first_emoji', 'full_english', 'first_english'])
    
    if style == 'full':
        return f"{random.choice(INDIAN_FIRST)} {random.choice(INDIAN_LAST)}"
    elif style == 'full_lower':
        f = random.choice(INDIAN_FIRST).lower()
        l = random.choice(INDIAN_LAST).lower()
        return f"{f} {l}"
    elif style == 'first_num':
        return f"{random.choice(INDIAN_FIRST)}{random.randint(10, 999)}"
    elif style == 'first_suffix':
        suffix = random.choice([' bhai', ' ji', ' sir', ' mam'])
        return f"{random.choice(INDIAN_FIRST)}{suffix}"
    elif style == 'first_emoji':
        return f"{random.choice(INDIAN_FIRST)} {random.choice(EMOJIS)}"
    elif style == 'full_english':
        return f"{random.choice(ENGLISH_FIRST)} {random.choice(ENGLISH_LAST)}"
    else:  # first_english
        return random.choice(ENGLISH_FIRST)

# ------------------------------------------------------------
#  GLOBAL STATE
# ------------------------------------------------------------
class BotManager:
    def __init__(self):
        self.tasks = set()          # asyncio tasks
        self.count = 0
        self.lock = asyncio.Lock()
        self.browser = None
        self.playwright = None

    async def start_browser(self):
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=BROWSER_ARGS
            )
            print("✅ Shared browser launched")

    async def stop_browser(self):
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            self.browser = None
            self.playwright = None
            print("🛑 Browser closed")

    async def launch_bot(self, meeting_code, passcode, duration_sec, name=None):
        """Create a new bot (context + page) and join the meeting."""
        if self.browser is None:
            await self.start_browser()

        # Use provided name or generate random
        display_name = name if name else generate_name()

        # Create isolated context
        context = await self.browser.new_context(
            viewport={"width": 800, "height": 600},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            zoom_url = get_zoom_url(meeting_code)
            await page.goto(zoom_url, timeout=45000)
            
            # Wait a tiny bit for page to stabilize
            await asyncio.sleep(0.3)

            # ---------- FILL NAME ----------
            name_selectors = [
                '//*[@id="input-for-name"]',
                '//input[@placeholder="Enter your name"]',
                '//input[@name="name"]'
            ]
            name_filled = False
            for sel in name_selectors:
                try:
                    loc = page.locator(f'xpath={sel}')
                    if await loc.count() > 0:
                        await loc.first.wait_for(state="visible", timeout=2000)
                        await loc.first.fill(display_name)
                        name_filled = True
                        break
                except:
                    continue
            if not name_filled:
                await page.keyboard.type(display_name)

            # ---------- PASSCODE ----------
            if passcode and passcode.strip():
                try:
                    pass_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/div[2]/div/input'
                    pass_loc = page.locator(f'xpath={pass_xpath}')
                    if await pass_loc.count() > 0:
                        await pass_loc.fill(passcode)
                except:
                    pass

            # ---------- JOIN (immediately) ----------
            try:
                join_xpath = '/html/body/div[2]/div[1]/div/div[1]/div/div[2]/button'
                join_btn = page.locator(f'xpath={join_xpath}')
                if await join_btn.count() > 0:
                    await join_btn.click()
                else:
                    await page.keyboard.press('Enter')
            except:
                await page.keyboard.press('Enter')

            # ---------- STAY IN MEETING ----------
            # Attempt to join audio if prompt appears
            try:
                audio_btn = page.locator('xpath=//button[contains(text(), "Join Audio")]')
                if await audio_btn.count() > 0:
                    await audio_btn.click()
            except:
                pass

            # Keep the bot alive for the requested duration
            elapsed = 0
            while elapsed < duration_sec:
                await asyncio.sleep(5)  # check every 5s
                elapsed += 5
                if elapsed % 30 == 0:
                    gc.collect()  # periodic cleanup

        except asyncio.CancelledError:
            # Bot was asked to stop
            pass
        except Exception as e:
            print(f"Bot error: {e}")
        finally:
            # Clean up resources
            await page.close()
            await context.close()
            # Remove task from manager
            async with self.lock:
                self.count -= 1
                # Remove this task from the set (we'll find it by its task object)
            # The task will be removed by the wrapper

    async def add_bots(self, meeting_code, passcode, count, duration_min, custom_names=None):
        """Start `count` bots. Returns list of tasks."""
        async with self.lock:
            if self.count + count > MAX_BOTS:
                raise ValueError(f"Cannot exceed {MAX_BOTS} total bots. Currently {self.count} active.")
            self.count += count

        duration_sec = duration_min * 60
        tasks = []
        for i in range(count):
            name = None
            if custom_names and i < len(custom_names):
                name = custom_names[i]
            task = asyncio.create_task(self.launch_bot(meeting_code, passcode, duration_sec, name))
            tasks.append(task)
            self.tasks.add(task)
            # Small delay to avoid overwhelming the browser
            await asyncio.sleep(0.1)

        # Remove task from set when done
        for t in tasks:
            t.add_done_callback(self.tasks.discard)

        return tasks

    def get_status(self):
        return {
            "active_bots": self.count,
            "max_bots": MAX_BOTS,
            "tasks": len(self.tasks)
        }

    async def stop_all(self):
        """Cancel all running bots."""
        for task in list(self.tasks):
            if not task.done():
                task.cancel()
        # Wait for them to finish cancellation
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        async with self.lock:
            self.count = 0
        await self.stop_browser()

# Global manager
manager = BotManager()

# ------------------------------------------------------------
#  FASTAPI APP
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre‑launch the browser (speeds up first bot)
    await manager.start_browser()
    yield
    # Shutdown: kill all bots and close browser
    await manager.stop_all()
    await manager.stop_browser()

app = FastAPI(lifespan=lifespan)

# Serve a simple HTML UI (embedded)
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Zoom Bot Controller</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #2c3e50; }
        input, button { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        .row { display: flex; gap: 10px; }
        .row > * { flex: 1; }
        .btn { background: #3498db; color: white; border: none; padding: 10px; cursor: pointer; font-weight: bold; }
        .btn-danger { background: #e74c3c; }
        .status { background: #ecf0f1; padding: 10px; border-radius: 4px; margin: 15px 0; }
        .footer { margin-top: 30px; font-size: 0.9em; color: #7f8c8d; }
        #log { background: #fff; padding: 10px; height: 150px; overflow-y: auto; border: 1px solid #ccc; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>🚀 Zoom Bot</h1>
    <div class="status" id="status">Loading status...</div>
    <form id="botForm">
        <label>Meeting ID</label>
        <input type="text" id="meeting" placeholder="123456789" required>

        <label>Passcode (optional)</label>
        <input type="text" id="passcode" placeholder="leave blank if none">

        <label>Number of Bots (max 100)</label>
        <input type="number" id="count" value="5" min="1" max="100" required>

        <label>Duration (minutes)</label>
        <input type="number" id="duration" value="2" min="1" required>

        <label>Custom Names (one per line, optional)</label>
        <textarea id="names" rows="3" placeholder="Arjun Seth&#10;Mira bhai 😎&#10;Akash783"></textarea>

        <button type="submit" class="btn">▶ Start Bots</button>
    </form>
    <button id="stopBtn" class="btn btn-danger">⏹ Stop All Bots</button>
    <div id="log">Log will appear here...</div>
    <div class="footer">Zoom Bot Central — controlled from Railway</div>

    <script>
        const statusDiv = document.getElementById('status');
        const logDiv = document.getElementById('log');
        const form = document.getElementById('botForm');
        const stopBtn = document.getElementById('stopBtn');

        async function fetchStatus() {
            try {
                const res = await fetch('/status');
                const data = await res.json();
                statusDiv.innerHTML = `
                    <strong>Active Bots:</strong> ${data.active_bots} / ${data.max_bots} &nbsp;|&nbsp;
                    <strong>Tasks:</strong> ${data.tasks}
                `;
            } catch(e) { /* ignore */ }
        }

        function appendLog(msg) {
            const time = new Date().toLocaleTimeString();
            logDiv.innerHTML += `[${time}] ${msg}\n`;
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const meeting = document.getElementById('meeting').value.trim();
            const passcode = document.getElementById('passcode').value.trim();
            const count = parseInt(document.getElementById('count').value);
            const duration = parseInt(document.getElementById('duration').value);
            const namesText = document.getElementById('names').value;
            const names = namesText.split('\\n').map(s => s.trim()).filter(Boolean);

            appendLog(`🚀 Starting ${count} bots for meeting ${meeting}...`);
            try {
                const res = await fetch('/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ meeting_code: meeting, passcode, count, duration, custom_names: names })
                });
                const data = await res.json();
                if (res.ok) {
                    appendLog(`✅ Started ${data.started} bots.`);
                } else {
                    appendLog(`❌ Error: ${data.detail || 'Unknown'}`);
                }
            } catch(e) {
                appendLog(`❌ Request failed: ${e.message}`);
            }
            fetchStatus();
        });

        stopBtn.addEventListener('click', async () => {
            appendLog('⏹ Stopping all bots...');
            try {
                const res = await fetch('/stop', { method: 'POST' });
                const data = await res.json();
                appendLog(`✅ ${data.message}`);
            } catch(e) {
                appendLog(`❌ Stop failed: ${e.message}`);
            }
            fetchStatus();
        });

        // Poll status every 3s
        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_PAGE

@app.post("/start")
async def start_bots(
    meeting_code: str,
    count: int = Query(..., ge=1, le=MAX_BOTS),
    passcode: str = "",
    duration: int = Query(2, ge=1, le=60),
    custom_names: list[str] = []
):
    """Start new bots."""
    if count > MAX_BOTS:
        raise HTTPException(400, f"Count exceeds maximum of {MAX_BOTS}")
    try:
        tasks = await manager.add_bots(
            meeting_code=meeting_code,
            passcode=passcode,
            count=count,
            duration_min=duration,
            custom_names=custom_names
        )
        return {"started": len(tasks), "active": manager.count}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/stop")
async def stop_bots():
    """Stop all running bots."""
    await manager.stop_all()
    return {"message": "All bots stopped"}

@app.get("/status")
async def status():
    return manager.get_status()

# ------------------------------------------------------------
#  RUN (for local testing, Railway uses uvicorn)
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")

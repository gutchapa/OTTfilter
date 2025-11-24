import os
from playwright.sync_api import sync_playwright
import subprocess
import time
import pytest

FRONTEND_URL = "http://localhost:47921"
API_SERVER_CMD = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend/app"]

@pytest.fixture(scope="session", autouse=True)
def start_servers():
    # 1) Start the API server
    api = subprocess.Popen(API_SERVER_CMD)
    # 2) Serve static frontend build via Python HTTP server
    # 2) Serve static frontend build via Python HTTP server
    frontend = subprocess.Popen([
        "python3", "-m", "http.server", "47921", "--directory", "frontend/build"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Give them a moment
    time.sleep(2)
    yield
    api.terminate()
    api.wait()

def test_chat_persistence():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Load the app
        page.goto(FRONTEND_URL)
        # Send a message
        page.fill('textarea[name="chat-input"]', "Hello world")
        page.click('button:has-text("Send")')
        # Wait for the response bubble
        page.wait_for_selector('.chat-message.ai:has-text("Hello world")', timeout=5000)

        # Restart the API server to simulate a crash/restart
        subprocess.call(["pkill", "-f", "uvicorn"])
        api = subprocess.Popen(API_SERVER_CMD)
        time.sleep(1)

        # Reload page and verify the original message is still present
        page.reload()
        assert page.inner_text(".chat-history") .find("Hello world") != -1

        browser.close()
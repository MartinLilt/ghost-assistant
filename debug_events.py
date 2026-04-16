"""Quick test: print a line on every mouse click for 10 seconds."""
import time
from opp_server.event_monitor import GlobalEventMonitor

clicks = []

def on_click():
    t = time.strftime("%H:%M:%S")
    clicks.append(t)
    print(f"[{t}] CLICK detected! (total: {len(clicks)})", flush=True)

def on_scroll():
    print(f"[{time.strftime('%H:%M:%S')}] SCROLL pause", flush=True)

monitor = GlobalEventMonitor(on_click=on_click, on_scroll=on_scroll, scroll_throttle=2.0)
monitor.start()
print("Listening for clicks and scrolls for 15 seconds — click anywhere...")
time.sleep(15)
monitor.stop()
print(f"Done. Total clicks detected: {len(clicks)}")


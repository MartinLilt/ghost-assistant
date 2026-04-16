"""Quick test: show overlay window with streaming text."""
import time
import threading
import AppKit
from opp_server.overlay import OverlayWindow

overlay = OverlayWindow()

def stream_text():
    time.sleep(0.8)  # wait for window to open
    overlay.set_header("[22:00:01] click · localhost:4999/test")
    time.sleep(0.3)
    response = (
        "The screen shows a coding challenge. "
        "The task asks you to implement a binary search algorithm. "
        "Here is the solution:\n\n"
        "def binary_search(arr, target):\n"
        "    left, right = 0, len(arr) - 1\n"
        "    while left <= right:\n"
        "        mid = (left + right) // 2\n"
        "        if arr[mid] == target: return mid\n"
        "        elif arr[mid] < target: left = mid + 1\n"
        "        else: right = mid - 1\n"
        "    return -1"
    )
    for word in response.split(" "):
        overlay.append(word + " ")
        time.sleep(0.04)
    print("Stream done — overlay should show text. Press Ctrl-C to quit.")

threading.Thread(target=stream_text, daemon=True).start()

# Build overlay on main thread, then run macOS event loop
overlay.build()
AppKit.NSRunLoop.mainRunLoop().runUntilDate_(AppKit.NSDate.distantFuture())



from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXWindowsAttribute,
    kAXValueAttribute,
    kAXTitleAttribute,
)
from opp_server.ax_reader import get_pid_by_name

pid = get_pid_by_name("Google Chrome")
print(f"PID: {pid}")
root = AXUIElementCreateApplication(pid)

err, wins = AXUIElementCopyAttributeValue(root, kAXWindowsAttribute, None)
print(f"Windows err={err}, count={len(wins) if wins else 0}")

def probe(el, depth=0, limit=4):
    if depth > limit:
        return
    err, role = AXUIElementCopyAttributeValue(el, kAXRoleAttribute, None)
    err2, val = AXUIElementCopyAttributeValue(el, kAXValueAttribute, None)
    err3, title = AXUIElementCopyAttributeValue(el, kAXTitleAttribute, None)
    indent = "  " * depth
    print(f"{indent}role={role} | title={str(title)[:60]} | val={str(val)[:60]}")
    err4, children = AXUIElementCopyAttributeValue(el, kAXChildrenAttribute, None)
    if err4 == 0 and children:
        for ch in children[:3]:
            probe(ch, depth + 1, limit)

"""Deep AX tree text scanner for Chrome."""
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    kAXFocusedWindowAttribute,
    kAXMainWindowAttribute,
    kAXChildrenAttribute,
)
import Quartz
import time

# Find Chrome PID
pid = None
for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID):
    if "chrome" in w.get("kCGWindowOwnerName", "").lower():
        pid = w["kCGWindowOwnerPID"]
        break

print(f"Chrome PID: {pid}")
root = AXUIElementCreateApplication(pid)
AXUIElementSetAttributeValue(root, "AXEnhancedUserInterface", True)
time.sleep(0.5)


def find_text(el, depth=0, max_depth=25):
    if depth > max_depth:
        return
    for attr in ("AXValue", "AXTitle", "AXDescription"):
        e, v = AXUIElementCopyAttributeValue(el, attr, None)
        if e == 0 and v and len(str(v).strip()) > 2:
            print(f"  d={depth} [{attr}] {str(v)[:120]}")
    e, ch = AXUIElementCopyAttributeValue(el, kAXChildrenAttribute, None)
    if e == 0 and ch:
        for c in ch:
            find_text(c, depth + 1, max_depth)


for attr in (kAXFocusedWindowAttribute, kAXMainWindowAttribute):
    e, w = AXUIElementCopyAttributeValue(root, attr, None)
    if e == 0 and w:
        print(f"\n--- Window via {attr} ---")
        find_text(w, max_depth=25)
        break



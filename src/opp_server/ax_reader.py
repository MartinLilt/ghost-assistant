"""
ax_reader.py — reads visible text from any macOS app via Accessibility API.

Requires: System Settings → Privacy & Security → Accessibility → enable Terminal/IDE.
"""
from __future__ import annotations

import sys
from typing import Iterator

if sys.platform != "darwin":
    raise RuntimeError("ax_reader requires macOS")

from ApplicationServices import (  # type: ignore[import]
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyAttributeNames,
    kAXChildrenAttribute,
    kAXValueAttribute,
    kAXTitleAttribute,
    kAXDescriptionAttribute,
    kAXRoleAttribute,
    kAXWindowsAttribute,
    kAXMainWindowAttribute,
    kAXFocusedWindowAttribute,
    kAXFocusedUIElementAttribute,
)
import Quartz  # type: ignore[import]

# Roles whose text content we want to capture
_TEXT_ROLES = {
    "AXStaticText",
    "AXTextField",
    "AXTextArea",
    "AXHeading",
    "AXLink",
    "AXButton",
    "AXCell",
    "AXRow",
    "AXMenuBarItem",
    "AXMenuItem",
    "AXWebArea",
}

_CONTAINER_ROLES = {
    "AXGroup",
    "AXGenericElement",
    "AXScrollArea",
    "AXList",
    "AXTable",
    "AXLayoutArea",
    "AXSection",
}

_MAX_DEPTH = 60  # safety limit for recursive traversal


def get_pid_by_name(app_name: str) -> int | None:
    """Return PID of the first running app whose name contains *app_name*."""
    running = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
    )
    seen: set[int] = set()
    for win in running:
        owner = win.get("kCGWindowOwnerName", "")
        pid = win.get("kCGWindowOwnerPID", -1)
        if app_name.lower() in owner.lower() and pid not in seen:
            seen.add(pid)
            return pid
    return None


def _get_attr(element, attr: str) -> str | None:
    """Safely read a single AX attribute as a string."""
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    if err == 0 and value is not None:
        return str(value)
    return None


def _walk(element, depth: int = 0) -> Iterator[str]:
    """Recursively yield non-empty text strings from the AX element tree."""
    if depth > _MAX_DEPTH:
        return

    role = _get_attr(element, kAXRoleAttribute) or ""

    if role in _TEXT_ROLES or depth <= 1:
        for attr in (kAXValueAttribute, kAXTitleAttribute, kAXDescriptionAttribute):
            text = _get_attr(element, attr)
            if text and text.strip():
                yield text.strip()
    elif role not in _CONTAINER_ROLES:
        # Non-container, non-text roles: still grab value/title if meaningful
        for attr in (kAXValueAttribute, kAXTitleAttribute):
            text = _get_attr(element, attr)
            if text and text.strip() and len(text.strip()) > 1:
                yield text.strip()

    # Recurse into children for ALL roles (containers and text roles can have children)
    err, children = AXUIElementCopyAttributeValue(element, kAXChildrenAttribute, None)
    if err != 0 or not children:
        return
    for child in children:
        yield from _walk(child, depth + 1)


def _get_windows(root) -> list:
    """Return all available windows for this app element."""
    windows = []
    for attr in (kAXWindowsAttribute, kAXMainWindowAttribute, kAXFocusedWindowAttribute):
        err, val = AXUIElementCopyAttributeValue(root, attr, None)
        if err == 0 and val is not None:
            if isinstance(val, (list, tuple)):
                for w in val:
                    if w not in windows:
                        windows.append(w)
            else:
                if val not in windows:
                    windows.append(val)
    return windows


def snapshot(pid: int) -> list[str]:
    """Return a deduplicated list of visible text strings for the given PID."""
    root = AXUIElementCreateApplication(pid)

    # Enable enhanced UI mode so Chrome exposes full web-content AX tree
    from ApplicationServices import AXUIElementSetAttributeValue  # type: ignore[import]
    AXUIElementSetAttributeValue(root, "AXEnhancedUserInterface", True)

    seen: set[str] = set()
    result: list[str] = []

    windows = _get_windows(root)
    sources = windows if windows else [root]

    for source in sources:
        for text in _walk(source):
            if text not in seen:
                seen.add(text)
                result.append(text)
    return result


def snapshot_text(pid: int) -> str:
    """Return all visible text joined as a single string."""
    return "\n".join(snapshot(pid))


def hybrid_snapshot(pid: int) -> dict:
    """
    Combines AX metadata (URL, tab title) with OCR page content.
    Returns dict with keys: 'url', 'title', 'ax_text', 'ocr_text', 'full_text'.
    """
    from opp_server.ocr_reader import ocr_snapshot

    ax_texts = snapshot(pid)
    ocr_texts = ocr_snapshot(pid)

    # Extract URL and title from AX texts (URL-like strings)
    url = next((t for t in ax_texts if t.startswith(("http", "localhost", "file://"))), "")
    title = ax_texts[0] if ax_texts else ""

    ax_content = "\n".join(ax_texts)
    ocr_content = "\n".join(ocr_texts)

    # Merge: prefer OCR for page content, AX for metadata
    full = f"[URL] {url}\n[TITLE] {title}\n\n[PAGE CONTENT]\n{ocr_content}"

    return {
        "url": url,
        "title": title,
        "ax_text": ax_content,
        "ocr_text": ocr_content,
        "full_text": full,
    }



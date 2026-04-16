"""
event_monitor.py — global mouse/keyboard event listener using CGEventTap.

Fires callbacks when the user clicks anywhere (mousedown) or scrolls.
Requires: Accessibility permission (already needed for ax_reader).
"""
from __future__ import annotations

import threading
from typing import Callable

import Quartz  # type: ignore[import]


# Events we care about: left click, right click, scroll
_MASK = (
    Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
    | Quartz.CGEventMaskBit(Quartz.kCGEventRightMouseDown)
    | Quartz.CGEventMaskBit(Quartz.kCGEventScrollWheel)
)


class GlobalEventMonitor:
    """
    Runs a CGEventTap in a background thread.
    Calls *on_click()* on every left/right mouse down event.
    Calls *on_scroll()* on scroll events (throttled — max once per second).
    """

    def __init__(
        self,
        on_click: Callable[[], None] | None = None,
        on_scroll: Callable[[], None] | None = None,
        scroll_throttle: float = 1.0,
    ) -> None:
        self._on_click = on_click or (lambda: None)
        self._on_scroll = on_scroll or (lambda: None)
        self._scroll_throttle = scroll_throttle
        self._last_scroll = 0.0
        self._tap = None
        self._thread: threading.Thread | None = None
        self._loop = None

    def _callback(self, proxy, event_type, event, refcon):
        import time
        if event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown):
            threading.Thread(target=self._on_click, daemon=True).start()
        elif event_type == Quartz.kCGEventScrollWheel:
            now = time.monotonic()
            if now - self._last_scroll >= self._scroll_throttle:
                self._last_scroll = now
                threading.Thread(target=self._on_scroll, daemon=True).start()
        return event

    def start(self) -> None:
        """Start the event tap in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import CoreFoundation  # type: ignore[import]

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,  # passive — does NOT block events
            _MASK,
            self._callback,
            None,
        )
        if tap is None:
            raise RuntimeError(
                "CGEventTapCreate failed — ensure Accessibility permission is granted."
            )
        self._tap = tap
        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        self._loop = CoreFoundation.CFRunLoopGetCurrent()
        CoreFoundation.CFRunLoopAddSource(
            self._loop, source, CoreFoundation.kCFRunLoopDefaultMode
        )
        Quartz.CGEventTapEnable(tap, True)
        CoreFoundation.CFRunLoopRun()

    def stop(self) -> None:
        import CoreFoundation  # type: ignore[import]
        if self._loop:
            CoreFoundation.CFRunLoopStop(self._loop)


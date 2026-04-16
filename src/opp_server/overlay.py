"""
overlay.py — always-on-top floating window using native macOS NSPanel (PyObjC).

Call overlay.build() on the main thread, then run NSRunLoop.
Worker threads call .append() / .set_header() safely via a queue.
"""
from __future__ import annotations

import queue

import AppKit  # type: ignore[import]
import objc  # type: ignore[import]
from Foundation import NSObject, NSMakeRect  # type: ignore[import]


class _Delegate(NSObject):
    """Drains the OverlayWindow queue on the main run loop every 50ms."""

    def initWithOverlay_(self, overlay: "OverlayWindow"):
        self = objc.super(_Delegate, self).init()
        if self is not None:
            self._ov = overlay
        return self

    def tick_(self, _timer):
        ov = self._ov
        try:
            while True:
                cmd, data = ov._queue.get_nowait()
                if cmd == "clear":
                    ov._do_clear()
                elif cmd == "header":
                    ov._do_set_header(data)
                elif cmd == "append":
                    ov._do_append(data)
        except queue.Empty:
            pass


class OverlayWindow:
    """
    Native macOS NSPanel floating above all windows.
    Call build() on main thread once; then use set_header/append from any thread.
    """

    def __init__(
        self,
        width: float = 440,
        height: float = 240,
        alpha: float = 0.90,
        font_size: float = 13.0,
        x_offset: float = 40,
        y_offset: float = 60,
    ) -> None:
        self._width = width
        self._height = height
        self._alpha = alpha
        self._font_size = font_size
        self._x_offset = x_offset
        self._y_offset = y_offset
        self._queue: queue.Queue = queue.Queue()
        self._text_view = None

    def build(self) -> None:
        """Create NSPanel. MUST be called on the main thread."""
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        screen = AppKit.NSScreen.mainScreen()
        sw = screen.frame().size.width
        x = sw - self._width - self._x_offset
        y = self._y_offset

        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, self._width, self._height),
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskResizable
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskUtilityWindow,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("🤖 AI Assistant")
        panel.setLevel_(AppKit.NSFloatingWindowLevel + 1)
        panel.setAlphaValue_(self._alpha)
        panel.setHasShadow_(True)
        panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setMovableByWindowBackground_(True)

        bg = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.118, 0.118, 0.18, 1.0)
        panel.setBackgroundColor_(bg)

        content = panel.contentView()
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(content.bounds())
        scroll.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        scroll.setHasVerticalScroller_(True)
        scroll.setDrawsBackground_(False)

        tv = AppKit.NSTextView.alloc().initWithFrame_(content.bounds())
        tv.setEditable_(False)
        tv.setSelectable_(True)
        tv.setRichText_(True)
        tv.setBackgroundColor_(bg)
        tv.setTextColor_(AppKit.NSColor.colorWithRed_green_blue_alpha_(0.804, 0.839, 0.957, 1.0))
        tv.setFont_(
            AppKit.NSFont.fontWithName_size_("SF Mono", self._font_size)
            or AppKit.NSFont.monospacedSystemFontOfSize_weight_(self._font_size, AppKit.NSFontWeightRegular)
        )
        tv.setAutomaticSpellingCorrectionEnabled_(False)
        tv.setTextContainerInset_(AppKit.NSSize(10, 10))

        scroll.setDocumentView_(tv)
        content.addSubview_(scroll)
        self._text_view = tv
        self._font_size_val = self._font_size

        panel.orderFrontRegardless()

        delegate = _Delegate.alloc().initWithOverlay_(self)
        timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, delegate, "tick:", None, True
        )
        AppKit.NSRunLoop.mainRunLoop().addTimer_forMode_(timer, AppKit.NSRunLoopCommonModes)

    # ── internal (main thread only) ─────────────────────────────────────────

    def _do_clear(self) -> None:
        if self._text_view:
            self._text_view.setString_("")

    def _do_set_header(self, text: str) -> None:
        tv = self._text_view
        if not tv:
            return
        tv.setString_("")
        tv.textStorage().appendAttributedString_(
            AppKit.NSAttributedString.alloc().initWithString_attributes_(
                text + "\n",
                {
                    AppKit.NSForegroundColorAttributeName: AppKit.NSColor.grayColor(),
                    AppKit.NSFontAttributeName: AppKit.NSFont.monospacedSystemFontOfSize_weight_(
                        10, AppKit.NSFontWeightRegular
                    ),
                },
            )
        )

    def _do_append(self, text: str) -> None:
        tv = self._text_view
        if not tv:
            return
        tv.textStorage().appendAttributedString_(
            AppKit.NSAttributedString.alloc().initWithString_attributes_(
                text,
                {
                    AppKit.NSForegroundColorAttributeName: AppKit.NSColor.colorWithRed_green_blue_alpha_(
                        0.804, 0.839, 0.957, 1.0
                    ),
                    AppKit.NSFontAttributeName: AppKit.NSFont.fontWithName_size_(
                        "SF Mono", self._font_size
                    ) or AppKit.NSFont.monospacedSystemFontOfSize_weight_(
                        self._font_size, AppKit.NSFontWeightRegular
                    ),
                },
            )
        )
        tv.scrollRangeToVisible_(AppKit.NSMakeRange(tv.string().length(), 0))

    # ── Public API (thread-safe) ────────────────────────────────────────────

    def set_header(self, text: str) -> None:
        self._queue.put(("header", text))

    def append(self, token: str) -> None:
        self._queue.put(("append", token))

    def clear(self) -> None:
        self._queue.put(("clear", None))


    def __init__(
        self,
        width: float = 440,
        height: float = 240,
        alpha: float = 0.90,
        font_size: float = 13.0,
        x_offset: float = 40,
        y_offset: float = 60,
    ) -> None:
        self._width = width
        self._height = height
        self._alpha = alpha
        self._font_size = font_size
        self._x_offset = x_offset
        self._y_offset = y_offset
        self._queue: queue.Queue = queue.Queue()
        self._panel = None
        self._text_view = None

    def build(self) -> None:
        """Create the NSPanel. MUST be called on the main thread."""
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        screen = AppKit.NSScreen.mainScreen()
        sw = screen.frame().size.width
        sh = screen.frame().size.height
        x = sw - self._width - self._x_offset
        y = self._y_offset

        rect = NSMakeRect(x, y, self._width, self._height)
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            AppKit.NSWindowStyleMaskTitled
            | AppKit.NSWindowStyleMaskResizable
            | AppKit.NSWindowStyleMaskClosable
            | AppKit.NSWindowStyleMaskUtilityWindow,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("🤖 AI Assistant")
        panel.setLevel_(AppKit.NSFloatingWindowLevel + 1)
        panel.setAlphaValue_(self._alpha)
        panel.setHasShadow_(True)
        panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setMovableByWindowBackground_(True)

        bg = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.118, 0.118, 0.18, 1.0)
        panel.setBackgroundColor_(bg)

        content = panel.contentView()
        scroll = AppKit.NSScrollView.alloc().initWithFrame_(content.bounds())
        scroll.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        scroll.setHasVerticalScroller_(True)
        scroll.setDrawsBackground_(False)

        text_view = AppKit.NSTextView.alloc().initWithFrame_(content.bounds())
        text_view.setEditable_(False)
        text_view.setSelectable_(True)
        text_view.setRichText_(True)
        text_view.setBackgroundColor_(bg)
        fg = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.804, 0.839, 0.957, 1.0)
        text_view.setTextColor_(fg)
        font = AppKit.NSFont.fontWithName_size_("SF Mono", self._font_size) or \
               AppKit.NSFont.monospacedSystemFontOfSize_weight_(self._font_size, AppKit.NSFontWeightRegular)
        text_view.setFont_(font)
        text_view.setAutomaticSpellingCorrectionEnabled_(False)
        text_view.setTextContainerInset_(AppKit.NSSize(10, 10))

        scroll.setDocumentView_(text_view)
        content.addSubview_(scroll)

        self._panel = panel
        self._text_view = text_view
        panel.orderFrontRegardless()

        # Drain queue every 50ms via NSTimer on main run loop
        delegate = _Delegate.alloc().initWithOverlay_(self)
        timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, delegate, "tick:", None, True
        )
        AppKit.NSRunLoop.mainRunLoop().addTimer_forMode_(timer, AppKit.NSRunLoopCommonModes)

    # ── internal (main thread only) ─────────────────────────────────────────

    def _do_clear(self) -> None:
        if self._text_view:
            self._text_view.setString_("")

    def _do_set_header(self, text: str) -> None:
        if not self._text_view:
            return
        self._text_view.setString_("")
        attrs = {
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.grayColor(),
            AppKit.NSFontAttributeName: AppKit.NSFont.monospacedSystemFontOfSize_weight_(
                10, AppKit.NSFontWeightRegular
            ),
        }
        astr = AppKit.NSAttributedString.alloc().initWithString_attributes_(text + "\n", attrs)
        self._text_view.textStorage().appendAttributedString_(astr)

    def _do_append(self, text: str) -> None:
        if not self._text_view:
            return
        fg = AppKit.NSColor.colorWithRed_green_blue_alpha_(0.804, 0.839, 0.957, 1.0)
        font = AppKit.NSFont.fontWithName_size_("SF Mono", self._font_size) or \
               AppKit.NSFont.monospacedSystemFontOfSize_weight_(self._font_size, AppKit.NSFontWeightRegular)
        astr = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            text,
            {AppKit.NSForegroundColorAttributeName: fg, AppKit.NSFontAttributeName: font},
        )
        self._text_view.textStorage().appendAttributedString_(astr)
        length = self._text_view.string().length()
        self._text_view.scrollRangeToVisible_(AppKit.NSMakeRange(length, 0))

    # ── Public API (thread-safe) ────────────────────────────────────────────

    def set_header(self, text: str) -> None:
        self._queue.put(("header", text))

    def append(self, token: str) -> None:
        self._queue.put(("append", token))

    def clear(self) -> None:
        self._queue.put(("clear", None))



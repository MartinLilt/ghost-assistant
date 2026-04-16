"""
pipeline.py — autonomous screen watcher + Ollama AI assistant.

Triggers automatically on:
  - mouse click when target browser is the frontmost app
  - browser tab/URL change (detected via AX polling)
  - scroll pause (only when browser is focused)

Usage:
    python -m opp_server.pipeline --browser "Google Chrome" --model qwen2.5-coder:7b
    python -m opp_server.pipeline --browser "Google Chrome" --no-overlay
    python -m opp_server.pipeline --list-models
"""
from __future__ import annotations

import argparse
import sys
import time
import threading
from datetime import datetime, timezone

import AppKit  # type: ignore[import]  — part of pyobjc-framework-Cocoa

from opp_server.ax_reader import get_pid_by_name, hybrid_snapshot
from opp_server.ai_assistant import ask, list_models, DEFAULT_MODEL
from opp_server.event_monitor import GlobalEventMonitor
from opp_server.overlay import OverlayWindow
from opp_server.output_stream import MultiOutput, TCPBroadcast, BluetoothSerial


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _frontmost_pid() -> int | None:
    """Return PID of the currently focused (frontmost) application."""
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.processIdentifier() if app else None


class AutonomousPipeline:
    def __init__(
        self,
        pid: int,
        app_name: str,
        model: str,
        question: str,
        debounce: float = 1.5,
        tab_poll_interval: float = 1.0,
        use_overlay: bool = True,
        output: MultiOutput | None = None,
    ) -> None:
        self._pid = pid
        self._app_name = app_name
        self._model = model
        self._question = question
        self._debounce = debounce
        self._tab_poll_interval = tab_poll_interval
        self._output = output  # MultiOutput for TCP/BT

        self._pending_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._busy = False
        self._last_url = ""
        self._last_title = ""

        self._overlay = OverlayWindow() if use_overlay else None

    # ── focus check ────────────────────────────────────────────────────────

    def _browser_is_focused(self) -> bool:
        return _frontmost_pid() == self._pid

    # ── debounce ───────────────────────────────────────────────────────────

    def _schedule_analysis(self, reason: str) -> None:
        with self._lock:
            if self._pending_timer:
                self._pending_timer.cancel()
            self._pending_timer = threading.Timer(
                self._debounce, self._run_analysis, args=(reason,)
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _on_click(self) -> None:
        if self._browser_is_focused():
            self._schedule_analysis("click")

    def _on_scroll(self) -> None:
        if self._browser_is_focused():
            self._schedule_analysis("scroll-pause")

    # ── analysis ───────────────────────────────────────────────────────────

    def _run_analysis(self, reason: str) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
        try:
            data = hybrid_snapshot(self._pid)
            url = data.get("url", "")
            screen = data["full_text"]

            header = f"[{_now()}] {reason}" + (f" · {url}" if url else "")
            print(f"\n{'─'*60}")
            print(header)
            print("🤖 ", end="", flush=True)

            if self._overlay:
                self._overlay.set_header(header)

            ask(screen, question=self._question, model=self._model,
                stream=True, overlay=self._overlay, output=self._output)

        except Exception as exc:
            print(f"\n[pipeline] error: {exc}", file=sys.stderr)
        finally:
            with self._lock:
                self._busy = False

    # ── tab watcher ────────────────────────────────────────────────────────

    def _tab_watcher(self) -> None:
        while True:
            try:
                data = hybrid_snapshot(self._pid)
                url = data.get("url", "")
                title = data.get("title", "")
                if url != self._last_url or title != self._last_title:
                    if self._last_url or self._last_title:
                        self._schedule_analysis("tab-change")
                    self._last_url = url
                    self._last_title = title
            except Exception:
                pass
            time.sleep(self._tab_poll_interval)

    # ── run ────────────────────────────────────────────────────────────────

    def run(self) -> None:
        threading.Thread(target=self._tab_watcher, daemon=True).start()

        monitor = GlobalEventMonitor(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        monitor.start()

        print(f"[pipeline] Autonomous mode active. Ctrl-C to stop.", file=sys.stderr)
        print(f"[pipeline] Triggers: click/scroll (Chrome focused) + tab change", file=sys.stderr)
        print(f"[pipeline] Model: {self._model} | Debounce: {self._debounce}s", file=sys.stderr)

        if self._overlay:
            print(f"[pipeline] Overlay: enabled (bottom-right)", file=sys.stderr)
            self._overlay.build()  # must be called on main thread
            print(file=sys.stderr)
            # Run macOS event loop on main thread (keeps overlay alive + processes NSTimer)
            try:
                AppKit.NSRunLoop.mainRunLoop().runUntilDate_(
                    AppKit.NSDate.distantFuture()
                )
            except KeyboardInterrupt:
                pass
        else:
            print(file=sys.stderr)
            try:
                while True:
                    import time as _time
                    _time.sleep(1)
            except KeyboardInterrupt:
                pass

        monitor.stop()
        print("\n[pipeline] Stopped.", file=sys.stderr)


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous screen watcher + Ollama AI")
    parser.add_argument("--browser", default="Google Chrome")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--question", default="What is shown on screen? If it is a task or question, explain and suggest an answer.")
    parser.add_argument("--debounce", type=float, default=1.5)
    parser.add_argument("--tab-poll", type=float, default=1.0)
    parser.add_argument("--no-overlay", action="store_true", help="Disable floating window")
    parser.add_argument("--tcp", type=int, metavar="PORT", help="Broadcast AI output via TCP (e.g. --tcp 9999)")
    parser.add_argument("--bt", metavar="DEVICE", help="Send AI output via Bluetooth Serial (e.g. --bt HC-05)")
    parser.add_argument("--baud", type=int, default=9600, help="Bluetooth baud rate (default: 9600)")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    if args.list_models:
        models = list_models()
        print("Available Ollama models:")
        for m in models:
            print(f"  • {m}")
        return

    print(f"[pipeline] Looking for '{args.browser}'…", file=sys.stderr)
    pid = get_pid_by_name(args.browser)
    if pid is None:
        print(f"[pipeline] ERROR: '{args.browser}' not running.", file=sys.stderr)
        sys.exit(1)

    models = list_models()
    if not models:
        print("[pipeline] ERROR: Ollama not running. Run: ollama serve", file=sys.stderr)
        sys.exit(1)
    if args.model not in models:
        print(f"[pipeline] Model '{args.model}' not found. Available: {models}", file=sys.stderr)
        sys.exit(1)

    # Build output channels
    output = MultiOutput()
    if args.tcp:
        tcp = TCPBroadcast(port=args.tcp)
        tcp.start()
        output.add(tcp)
    if args.bt:
        bt = BluetoothSerial(device_name=args.bt, baud=args.baud)
        try:
            bt.start()
            output.add(bt)
        except RuntimeError as e:
            print(f"[pipeline] Bluetooth error: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[pipeline] PID={pid} | model={args.model}", file=sys.stderr)
    print(f"[pipeline] Question: {args.question}\n", file=sys.stderr)

    AutonomousPipeline(
        pid=pid,
        app_name=args.browser,
        model=args.model,
        question=args.question,
        debounce=args.debounce,
        tab_poll_interval=args.tab_poll,
        use_overlay=not args.no_overlay,
        output=output if (args.tcp or args.bt) else None,
    ).run()


if __name__ == "__main__":
    main()

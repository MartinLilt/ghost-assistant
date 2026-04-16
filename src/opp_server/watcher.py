"""
watcher.py — polls an app's visible text on a fixed interval and emits changes.

Usage:
    python -m opp_server.watcher --browser "Google Chrome" --interval 2
    python -m opp_server.watcher --browser "Google Chrome" --interval 2 --json
    python -m opp_server.watcher --browser "Google Chrome" --ocr-only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from difflib import unified_diff

from opp_server.ax_reader import get_pid_by_name, hybrid_snapshot, snapshot_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def watch(
    app_name: str,
    interval: float = 2.0,
    output_json: bool = False,
    diff_only: bool = True,
    ocr_only: bool = False,
) -> None:
    """Main polling loop. Ctrl-C to stop."""
    print(f"[opp-watcher] Looking for '{app_name}'…", file=sys.stderr)
    pid = get_pid_by_name(app_name)
    if pid is None:
        print(f"[opp-watcher] ERROR: '{app_name}' not found. Is it running?", file=sys.stderr)
        sys.exit(1)
    print(f"[opp-watcher] Found PID {pid}. Watching every {interval}s. Ctrl-C to stop.", file=sys.stderr)

    prev_text = ""
    while True:
        try:
            if ocr_only:
                from opp_server.ocr_reader import ocr_snapshot_text
                current_text = ocr_snapshot_text(pid)
                record_extra = {}
            else:
                data = hybrid_snapshot(pid)
                current_text = data["full_text"]
                record_extra = {"url": data["url"], "title": data["title"]}
        except Exception as exc:  # noqa: BLE001
            print(f"[opp-watcher] Read error: {exc}", file=sys.stderr)
            time.sleep(interval)
            continue

        if current_text != prev_text:
            ts = _now()
            if diff_only and prev_text:
                lines_prev = prev_text.splitlines(keepends=True)
                lines_curr = current_text.splitlines(keepends=True)
                diff = list(unified_diff(lines_prev, lines_curr, lineterm=""))
                changed_text = "".join(l for l in diff if l.startswith("+") and not l.startswith("+++"))
            else:
                changed_text = current_text

            if changed_text.strip():
                if output_json:
                    record = {
                        "timestamp": ts,
                        "app": app_name,
                        "pid": pid,
                        "text": changed_text,
                        **record_extra,
                    }
                    print(json.dumps(record, ensure_ascii=False), flush=True)
                else:
                    print(f"\n── {ts} ──────────────────────────", flush=True)
                    if record_extra.get("url"):
                        print(f"URL: {record_extra['url']}", flush=True)
                    print(changed_text, flush=True)

            prev_text = current_text

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch visible text in a macOS app via AX API + OCR")
    parser.add_argument("--browser", default="Google Chrome", help="App name to watch")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--json", action="store_true", help="Emit newline-delimited JSON")
    parser.add_argument("--full", action="store_true", help="Full snapshot on every change")
    parser.add_argument("--ocr-only", action="store_true", help="Use OCR only (no AX metadata)")
    args = parser.parse_args()
    watch(
        app_name=args.browser,
        interval=args.interval,
        output_json=args.json,
        diff_only=not args.full,
        ocr_only=args.ocr_only,
    )


if __name__ == "__main__":
    main()


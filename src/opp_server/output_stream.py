"""
output_stream.py — broadcasts AI responses to external clients.

Supported channels:
  1. TCP socket server  — any device on LAN connects with netcat / terminal app
  2. Bluetooth Serial   — classic BT RFCOMM via paired /dev/tty.* device
  3. stdout             — always active (fallback)

Usage (standalone test):
    python -m opp_server.output_stream --tcp 9999
    python -m opp_server.output_stream --bt "MyDevice"
"""
from __future__ import annotations

import socket
import threading
import sys
import time
from typing import Protocol


class OutputChannel(Protocol):
    def write(self, text: str) -> None: ...
    def close(self) -> None: ...


# ── TCP Server ──────────────────────────────────────────────────────────────

class TCPBroadcast:
    """
    Listens on a TCP port. All connected clients receive every token in real time.
    Connect from phone:  nc <mac-ip> 9999
    iOS app:             "TCP Socket" / "Terminal" apps on App Store
    Android:             JuiceSSH / Serial Bluetooth Terminal in TCP mode
    """

    def __init__(self, port: int = 9999, host: str = "0.0.0.0") -> None:
        self._port = port
        self._host = host
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._server: socket.socket | None = None

    def start(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self._host, self._port))
        self._server.listen(5)
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        # Print local IP for easy connection
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"[tcp] Listening on {local_ip}:{self._port}", file=sys.stderr)
        print(f"[tcp] Connect from phone:  nc {local_ip} {self._port}", file=sys.stderr)

    def _accept_loop(self) -> None:
        while True:
            try:
                conn, addr = self._server.accept()
                with self._lock:
                    self._clients.append(conn)
                print(f"[tcp] Client connected: {addr}", file=sys.stderr)
            except Exception:
                break

    def write(self, text: str) -> None:
        dead = []
        with self._lock:
            for c in self._clients:
                try:
                    c.sendall(text.encode("utf-8"))
                except Exception:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    def close(self) -> None:
        if self._server:
            self._server.close()


# ── Bluetooth Serial (RFCOMM) ───────────────────────────────────────────────

class BluetoothSerial:
    """
    Writes to a paired Bluetooth device via its /dev/tty.* serial port.

    How to find your device name on macOS:
        ls /dev/tty.* | grep -v Bluetooth
    Or pair the device in System Settings → Bluetooth, then check ls /dev/tty.*

    Works with:
        - HC-05 / HC-06 Bluetooth modules (Arduino, ESP32)
        - Bluetooth serial adapters
        - Phones with "Serial Bluetooth Terminal" app (Android)
        - Smart glasses / earpiece modules
    """

    def __init__(self, device_name: str | None = None, baud: int = 9600) -> None:
        """
        device_name: partial name match, e.g. "HC-05" or full "/dev/tty.HC-05"
        """
        self._device_name = device_name
        self._baud = baud
        self._port = None
        self._path: str | None = None

    def start(self) -> None:
        import glob
        import serial  # type: ignore[import]  — pip install pyserial

        if self._device_name:
            if self._device_name.startswith("/dev/"):
                candidates = [self._device_name]
            else:
                candidates = glob.glob(f"/dev/tty.*{self._device_name}*")
        else:
            candidates = glob.glob("/dev/tty.*")
            candidates = [c for c in candidates if "Bluetooth" not in c]

        if not candidates:
            raise RuntimeError(
                f"No Bluetooth serial device found matching '{self._device_name}'. "
                f"Pair device first, then check: ls /dev/tty.*"
            )
        self._path = candidates[0]
        self._port = serial.Serial(self._path, self._baud, timeout=1)
        print(f"[bluetooth] Connected to {self._path} @ {self._baud} baud", file=sys.stderr)

    def write(self, text: str) -> None:
        if self._port and self._port.is_open:
            try:
                self._port.write(text.encode("utf-8"))
            except Exception as e:
                print(f"[bluetooth] Write error: {e}", file=sys.stderr)

    def close(self) -> None:
        if self._port:
            self._port.close()


# ── MultiOutput — writes to all active channels simultaneously ──────────────

class MultiOutput:
    """Fans out to stdout + all registered channels."""

    def __init__(self) -> None:
        self._channels: list[OutputChannel] = []

    def add(self, channel: OutputChannel) -> None:
        self._channels.append(channel)

    def write(self, text: str) -> None:
        print(text, end="", flush=True)  # always stdout
        for ch in self._channels:
            try:
                ch.write(text)
            except Exception:
                pass

    def close(self) -> None:
        for ch in self._channels:
            ch.close()


# ── CLI test ────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Test output stream channels")
    parser.add_argument("--tcp", type=int, metavar="PORT", help="Enable TCP broadcast on PORT (e.g. 9999)")
    parser.add_argument("--bt", metavar="DEVICE", help="Bluetooth serial device name (e.g. HC-05)")
    args = parser.parse_args()

    out = MultiOutput()

    if args.tcp:
        tcp = TCPBroadcast(port=args.tcp)
        tcp.start()
        out.add(tcp)

    if args.bt:
        bt = BluetoothSerial(device_name=args.bt)
        bt.start()
        out.add(bt)

    print("[output_stream] Sending test message every 2 seconds. Ctrl-C to stop.", file=sys.stderr)
    try:
        i = 0
        while True:
            msg = f"[{time.strftime('%H:%M:%S')}] AI response token {i}\n"
            out.write(msg)
            i += 1
            time.sleep(2)
    except KeyboardInterrupt:
        out.close()


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Headless daemon that applies simulated iOS GPS coordinates via tunneld."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

# Default Target Coordinates (Chicago, IL - CST)
# Override via environment variables or /etc/default/auto-spoof
DEFAULT_LAT: str = "41.8781"
DEFAULT_LON: str = "-87.6298"
DEFAULT_PYTHON_BIN: str = "/opt/ios-spoofer/bin/python"
DEFAULT_TUNNELD_URL: str = "http://127.0.0.1:49151"
DEFAULT_POLL_INTERVAL_SEC: float = 3.0

TARGET_LAT: str = os.getenv("TARGET_LAT", DEFAULT_LAT)
TARGET_LON: str = os.getenv("TARGET_LON", DEFAULT_LON)
PYTHON_BIN: str = os.getenv("PYTHON_BIN", DEFAULT_PYTHON_BIN)
TUNNELD_URL: str = os.getenv("TUNNELD_URL", DEFAULT_TUNNELD_URL)
POLL_INTERVAL_SEC: float = float(
    os.getenv("POLL_INTERVAL_SEC", str(DEFAULT_POLL_INTERVAL_SEC))
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("auto_spoof")


def get_active_tunnel() -> Optional[Tuple[str, str, int]]:
    """Polls the local tunneld REST API for an active device tunnel.

    Returns:
        A tuple of (udid, ipv6_address, port) if a tunnel is active, else None.
    """
    try:
        with urllib.request.urlopen(TUNNELD_URL, timeout=2) as response:
            payload: dict[str, list[dict[str, Any]]] = json.loads(
                response.read().decode("utf-8")
            )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    for udid, tunnels in payload.items():
        if not tunnels:
            continue
        tunnel = tunnels[0]
        address = tunnel.get("tunnel-address")
        port = tunnel.get("tunnel-port")
        if address and port is not None:
            return udid, str(address), int(port)

    return None


def mount_developer_image(address: str, port: int) -> None:
    """Mounts the Developer Disk Image through the active RSD tunnel.

    Args:
        address: Tunnel IPv6 address.
        port: Tunnel RSD port.
    """
    cmd = [
        PYTHON_BIN,
        "-m",
        "pymobiledevice3",
        "mounter",
        "auto-mount",
        "--rsd",
        address,
        str(port),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        logger.info("Developer Disk Image mounted or already present.")
    else:
        logger.warning(
            "mounter auto-mount exited with %d: %s",
            result.returncode,
            (result.stderr or result.stdout).strip(),
        )


def start_location_simulation(address: str, port: int) -> subprocess.Popen[str]:
    """Launches the DVT location simulation process over the RSD tunnel.

    Args:
        address: Tunnel IPv6 address.
        port: Tunnel RSD port.

    Returns:
        Running subprocess holding the simulated location session.
    """
    cmd = [
        PYTHON_BIN,
        "-m",
        "pymobiledevice3",
        "developer",
        "dvt",
        "simulate-location",
        "set",
        "--rsd",
        address,
        str(port),
        "--",
        TARGET_LAT,
        TARGET_LON,
    ]
    logger.info(
        "Applying coordinates (%s, %s) via %s:%d",
        TARGET_LAT,
        TARGET_LON,
        address,
        port,
    )
    return subprocess.Popen(cmd, text=True)


def stop_process(proc: Optional[subprocess.Popen[str]]) -> None:
    """Terminates a child subprocess cleanly if it is still running.

    Args:
        proc: Subprocess instance to stop, or None.
    """
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main() -> None:
    """Runs the continuous tunnel polling and spoofing loop."""
    active_key: Optional[Tuple[str, str, int]] = None
    dvt_proc: Optional[subprocess.Popen[str]] = None
    running = True

    def handle_shutdown(signum: int, _frame: Any) -> None:
        nonlocal running
        logger.info("Received signal %d; shutting down.", signum)
        running = False

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    logger.info("Watching %s for paired iOS tunnels...", TUNNELD_URL)

    try:
        while running:
            tunnel_info = get_active_tunnel()

            if tunnel_info is not None:
                needs_apply = (
                    tunnel_info != active_key
                    or dvt_proc is None
                    or dvt_proc.poll() is not None
                )
                if needs_apply:
                    udid, address, port = tunnel_info
                    logger.info("Active tunnel detected for device %s.", udid)
                    stop_process(dvt_proc)
                    mount_developer_image(address, port)
                    dvt_proc = start_location_simulation(address, port)
                    active_key = tunnel_info
            elif active_key is not None:
                logger.info("Tunnel lost; resetting watcher state.")
                stop_process(dvt_proc)
                dvt_proc = None
                active_key = None

            time.sleep(POLL_INTERVAL_SEC)
    finally:
        stop_process(dvt_proc)


if __name__ == "__main__":
    main()

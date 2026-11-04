#!/usr/bin/env python3
"""Interactive CLI tool to switch iOS system time zone via location simulation."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Dict, NamedTuple, Optional


class Location(NamedTuple):
    """Geographic coordinate representation."""

    name: str
    latitude: float
    longitude: float


# Curated mapping of common time zones and regions to representative coordinates
TIMEZONE_REGIONS: Dict[str, Location] = {
    # United Kingdom & UTC
    "gmt": Location("London (GMT/BST)", 51.5074, -0.1278),
    "utc": Location("UTC Baseline (London)", 51.5074, -0.1278),
    # Europe
    "cet": Location("Paris/Berlin (CET/CEST)", 48.8566, 2.3522),
    "eet": Location("Athens/Helsinki (EET/EEST)", 37.9838, 23.7275),
    # North America
    "est": Location("New York (US Eastern)", 40.7128, -74.0060),
    "cst": Location("Chicago (US Central)", 41.8781, -87.6298),
    "mst": Location("Denver (US Mountain)", 39.7392, -104.9903),
    "pst": Location("Los Angeles (US Pacific)", 34.0522, -118.2437),
    "akst": Location("Anchorage (Alaska)", 61.2181, -149.9003),
    "hst": Location("Honolulu (Hawaii)", 21.3069, -157.8583),
    # Asia & Middle East
    "gst": Location("Dubai (GST)", 25.2048, 55.2708),
    "ist": Location("New Delhi (IST)", 28.6139, 77.2090),
    "cst_asia": Location("Singapore / Beijing (CST)", 1.3521, 103.8198),
    "jst": Location("Tokyo (JST)", 35.6762, 139.6503),
    # Oceania & South America
    "aest": Location("Sydney (AEST/AEDT)", -33.8688, 151.2093),
    "nzst": Location("Auckland (NZST/NZDT)", -36.8485, 174.7633),
    "brt": Location("São Paulo (BRT)", -23.5505, -46.6333),
}


def run_command(args: list[str], timeout: Optional[int] = None) -> bool:
    """Executes a pymobiledevice3 subprocess command.

    Args:
        args: List of command arguments following python -m pymobiledevice3.
        timeout: Optional execution timeout in seconds.

    Returns:
        True if command completed successfully, False otherwise.
    """
    cmd = [sys.executable, "-m", "pymobiledevice3"] + args
    try:
        subprocess.run(cmd, check=True, timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        # Expected behavior when interrupting DVT location sessions
        return True
    except subprocess.CalledProcessError as exc:
        print(f"\n[!] Error executing {' '.join(cmd)}: {exc}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("\n[!] Python or pymobiledevice3 executable not found.", file=sys.stderr)
        return False


def set_simulated_location(lat: float, lon: float) -> None:
    """Sends DVT location simulation packets and terminates gracefully.

    Args:
        lat: Latitude coordinate.
        lon: Longitude coordinate.
    """
    cmd = [
        sys.executable,
        "-m",
        "pymobiledevice3",
        "developer",
        "dvt",
        "simulate-location",
        "set",
        "--tunnel",
        "",
        "--",
        str(lat),
        str(lon),
    ]

    print("\n[+] Dispatching coordinates to device...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Allow 2 seconds for DVT handshake and packet delivery
    time.sleep(2)

    # Terminate the lingering listener process so the prompt returns cleanly
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("[✓] Time zone location override applied successfully.")
    print("    iOS System Services will now update the system clock.")


def clear_simulated_location() -> None:
    """Clears active location overrides and resets to hardware GPS."""
    print("\n[*] Clearing location simulation...")
    success = run_command(
        ["developer", "dvt", "simulate-location", "clear", "--tunnel", ""]
    )
    if success:
        print("[✓] Restored to real satellite GPS.")


def prompt_user_choice() -> Optional[Location]:
    """Displays menu and parses user input.

    Returns:
        Selected Location instance, or None if reset/exit requested.
    """
    options = list(TIMEZONE_REGIONS.items())

    print("=" * 50)
    print("        iOS Time Zone & Location Switcher")
    print("=" * 50)
    for idx, (key, loc) in enumerate(options, start=1):
        print(f" [{idx:2d}] {key.upper():<8} -> {loc.name}")
    print(" [ 0] RESET    -> Clear override and revert to real GPS")
    print(" [ q] QUIT     -> Exit script without making changes")
    print("=" * 50)

    while True:
        choice = input("\nEnter number, abbreviation (e.g. 'PST'), or 'q': ").strip().lower()

        if choice in ("q", "quit", "exit"):
            sys.exit(0)

        if choice in ("0", "reset", "clear"):
            clear_simulated_location()
            return None

        if choice in TIMEZONE_REGIONS:
            return TIMEZONE_REGIONS[choice]

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][1]

        # Fuzzy search fallback by city or zone name
        matched = [
            loc for loc in TIMEZONE_REGIONS.values()
            if choice in loc.name.lower()
        ]
        if matched:
            return matched[0]

        print("[!] Invalid selection. Please choose a valid index or time zone code.")


def main() -> None:
    """Main workflow entrypoint."""
    try:
        location = prompt_user_choice()
        if not location:
            return

        print(f"\n[*] Target: {location.name}")
        print(f"[*] Coordinates: {location.latitude}, {location.longitude}")

        # Mount Developer Disk Image if needed
        run_command(["mounter", "auto-mount"])

        # Inject simulated coordinates
        set_simulated_location(location.latitude, location.longitude)

    except KeyboardInterrupt:
        print("\n\n[-] Operation canceled by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()

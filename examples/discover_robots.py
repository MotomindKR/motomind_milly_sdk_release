#!/usr/bin/env python3
"""List connected Milly robots by their engraved product ID ("모델명 받아오기").

Run this FIRST on a new setup: it finds the ID stamped on your arm (e.g.
MILLY_ABCD) that every other example passes to create_arm(). It probes the CAN
buses for the LED/button board and reads the product ID off it — no motors are
touched, so it is always safe to run.

  .venv/bin/python examples/discover_robots.py
  .venv/bin/python examples/discover_robots.py --interface can0

Equivalent CLI: `.venv/bin/motomind-milly-robots`. Bring the bus up first:
  sudo ip link set can0 up type can bitrate 1000000
"""

from __future__ import annotations

import argparse

import motomind_milly as mm


def main() -> int:
    ap = argparse.ArgumentParser(description="discover Milly robots by product ID")
    ap.add_argument("--interface", action="append", default=None, metavar="canX",
                    help="probe only this interface (repeatable; default: can0)")
    args = ap.parse_args()
    mm.enable_logging()

    robots = mm.list_robots(args.interface or ["can0"])   # can0 by default; --interface to override
    if not robots:
        print("no robots found — is the bus up (sudo ip link set can0 up type can "
              "bitrate 1000000) and the LED board powered?")
        return 1
    for r in robots:
        led = "fault" if r.led_fault else "normal"
        print(f"  {r.name or '(no product id programmed)'}  on {r.interface}   "
              f"button={r.button_state}  led={led}")
    # use the name with create_arm:  arm = mm.create_arm(robots[0].name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

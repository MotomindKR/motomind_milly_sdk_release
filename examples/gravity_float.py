#!/usr/bin/env python3
"""Gravity compensation — FLOAT (drag / hand-guide) demo.

Enable the arm and put it straight into FLOAT through ``arm.float_mode()``:
gravity compensation is ON, so the arm holds itself up and is back-drivable —
push it and it moves freely, staying where you leave it. ``set_robot_model()``
automatically applies the locked factory ``milly_cal.yaml`` mass/COM values;
raw URDF inertials are never used by this public FLOAT path.

  .venv/bin/python examples/gravity_float.py --product-id MILLY_ABCD
  .venv/bin/python examples/gravity_float.py --product-id MILLY_ABCD --gui=false

Ctrl-C exits via the damping latch — the arm settles, it does NOT drop.

NOTE: FLOAT-only for now. The OFF/HOLD transition (and the physical-button
toggle) are held back until the FLOAT->HOLD settling behaviour is finalised.
"""

from __future__ import annotations

import argparse
import time

import motomind_milly as mm


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gravity compensation FLOAT demo")
    ap.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    ap.add_argument("--gui", type=_parse_bool, default=True,
                    metavar="{true,false}",
                    help="open the motor-state monitor (default: true)")
    args = ap.parse_args()
    mm.enable_logging()

    from motomind_robot_model import RobotModel

    arm = mm.create_arm(args.product_id)                # discover + verify + connect
    # Attaching the model also loads the locked factory milly_cal.yaml values.
    arm.set_robot_model(RobotModel(mm.milly_urdf()))
    if args.gui:
        # GIL rule: heavy Tk init BEFORE enable() starts the control loop
        from motomind_milly.monitor import MotorMonitor
        MotorMonitor(arm.manager, arm._config, poll_ms=250).start()
        time.sleep(1.0)
    if not arm.enable().ok:                             # control loop + supervisor (HOLD)
        print("! enable failed"); return 1

    arm.float_mode()  # public API -> FLOAT (factory-calibrated gravity comp ON)
    print("\nFLOAT (gravity comp ON) — drag the arm; it holds itself against "
          "gravity. Ctrl-C to quit.")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        arm.shutdown()          # exit reaction: damping latch (arm does NOT drop)
        print("\n[done] damping latch engaged (exit reaction)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

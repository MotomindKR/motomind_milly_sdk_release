#!/usr/bin/env python3
"""Gravity compensation — FLOAT (drag / hand-guide) demo.

Enable the arm and put it straight into FLOAT through ``arm.float_mode()``:
gravity compensation is ON, so the arm holds itself up and is back-drivable —
push it and it moves freely, staying where you leave it. ``set_robot_model()``
automatically applies the locked factory ``milly_cal.yaml`` mass/COM values;
raw URDF inertials are never used by this public FLOAT path.

  .venv/bin/python examples/python/gravity_float.py --product-id MILLY_ABCD
  .venv/bin/python examples/python/gravity_float.py --product-id MILLY_ABCD --gui=false

Ctrl-C exits via the damping latch — the arm settles, it does NOT drop.

This example stays in FLOAT until exit.
"""

from __future__ import annotations

import argparse
import time
import signal

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
    window = None
    enable_attempted = False
    try:
        arm.set_robot_model(RobotModel(mm.milly_urdf()))
        if args.gui:
            from motomind_milly._position_gui_process import PositionProcessMonitor, motor_feedback_snapshot
            # Tk stays in its own process, as in ROS2; no control buttons or CAN queries.
            window = PositionProcessMonitor(
                arm.manager, arm._config, poll_ms=100,
                title=f"{args.product_id} — motor feedback",
                feedback_snapshot=lambda: motor_feedback_snapshot(arm.manager, 0.5),
            )
            window.start(wait=True)
        enable_attempted = True
        if not arm.enable().ok:
            print("! enable failed")
            return 1
        arm.float_mode()  # public API -> FLOAT (factory-calibrated gravity comp ON)
        print("\nFLOAT (gravity comp ON) — drag the arm; it holds itself against "
              "gravity. Ctrl-C to quit.")
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[interrupt] stopping safely", flush=True)
        return 0
    finally:
        # Repeated Ctrl+C must not interrupt shutdown or leave the GUI child behind.
        previous_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if enable_attempted:
                result = arm.shutdown()  # canonical exit reaction; never disable()
                if not result.ok:
                    raise RuntimeError(f"SDK shutdown failed: {result.message}")
                print("[stop] SDK shutdown completed", flush=True)
            else:
                arm.disconnect()  # GUI/model initialization failed before enable
        finally:
            try:
                if window is not None:
                    window.close(wait=True)
            finally:
                signal.signal(signal.SIGINT, previous_sigint)


if __name__ == "__main__":
    raise SystemExit(main())

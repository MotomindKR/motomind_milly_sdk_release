#!/usr/bin/env python3
"""Planned joint-space move to Milly's zero posture.

  .venv/bin/python examples/python/move_j_test.py --product-id MILLY_ABCD
  .venv/bin/python examples/python/move_j_test.py --product-id MILLY_ABCD --gui=false
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
    parser = argparse.ArgumentParser(description="move_j to [0, 0, 0, 0, 0, 0]")
    parser.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    parser.add_argument("--max-vel", type=float, default=0.2, metavar="RAD_S",
                        help="peak joint velocity [rad/s] (default: 0.2)")
    parser.add_argument("--gui", type=_parse_bool, default=True,
                        metavar="{true,false}",
                        help="open the motor-state monitor (default: true)")
    args = parser.parse_args()

    mm.enable_logging()
    arm = mm.create_arm(args.product_id)
    window = None
    enable_attempted = False
    try:
        arm.set_max_vel(args.max_vel)
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
        grip = arm.init_effector()
        print("move_j target: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] rad")
        print("gripper target: 0.0 rad (closed)")
        input("Enter to move; keep clear of the arm... ")
        arm.move_j([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        grip.move(0.0)
        print("zero posture reached; gripper closed. Press Ctrl-C to stop safely.")
        while True:
            time.sleep(0.2)
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

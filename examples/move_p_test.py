#!/usr/bin/env python3
"""Planned Cartesian move to the flange pose of Milly's zero posture.

The target below is the calibrated URDF flange pose for joint angles
``[0, 0, 0, 0, 0, 0]``. It is passed directly to ``move_p``.

  .venv/bin/python examples/move_p_test.py --product-id MILLY_ABCD
  .venv/bin/python examples/move_p_test.py --product-id MILLY_ABCD --gui=false
"""

from __future__ import annotations

import argparse
import time

import motomind_milly as mm

ZERO_POSE = [-0.000020196, -0.000923829, 0.240114373,
             -1.570796418, -0.091183350, 3.141592626]


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="move_p to the flange pose of [0, 0, 0, 0, 0, 0]")
    parser.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    parser.add_argument("--max-vel", type=float, default=0.2, metavar="RAD_S",
                        help="peak joint velocity [rad/s] (default: 0.2)")
    parser.add_argument("--gui", type=_parse_bool, default=True,
                        metavar="{true,false}",
                        help="open the motor-state monitor (default: true)")
    args = parser.parse_args()

    mm.enable_logging()
    from motomind_robot_model import RobotModel

    arm = mm.create_arm(args.product_id)
    arm.set_robot_model(RobotModel(mm.milly_urdf()))
    arm.set_max_vel(args.max_vel)
    if args.gui:
        from motomind_milly.monitor import MotorMonitor
        MotorMonitor(arm.manager, arm._config, poll_ms=250).start()
        time.sleep(1.0)

    if not arm.enable().ok:
        print("! enable failed")
        return 1
    try:
        grip = arm.init_effector()
        print(f"move_p target: {ZERO_POSE} (flange pose of zero joints)")
        print("gripper target: 0.0 rad (closed)")
        input("Enter to move; keep clear of the arm... ")
        arm.move_p(ZERO_POSE)
        grip.move(0.0)
        print("zero posture reached; gripper closed. Press Ctrl-C to stop safely.")
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[interrupt] engaging damping latch")
        return 0
    finally:
        arm.shutdown()  # damping latch — does NOT drop the arm
        print("[done] damping latch engaged (exit reaction)")


if __name__ == "__main__":
    raise SystemExit(main())

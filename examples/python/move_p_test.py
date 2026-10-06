#!/usr/bin/env python3
"""Planned Cartesian move to the flange pose of Milly's zero posture.

The target below is the calibrated URDF flange pose for joint angles
``[0, 0, 0, 0, 0, 0]``. It is passed directly to ``move_p``.

  .venv/bin/python examples/python/move_p_test.py --product-id MILLY_ABCD
  .venv/bin/python examples/python/move_p_test.py --product-id MILLY_ABCD --gui=false
"""

from __future__ import annotations

import argparse
import time
import signal

import motomind_milly as mm
from motomind_robot_model import RobotModel

# RAW-coordinate URDF: FK from base_link to link_6 at all-zero joints.
ZERO_POSE = [0.00005187, -0.10934281, 0.23828490,
             1.5707963267948966, 0.0, 0.0]


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
    arm = mm.create_arm(args.product_id)
    window = None
    enable_attempted = False
    try:
        arm.set_robot_model(RobotModel(mm.milly_urdf()))
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
        print(f"move_p target: {ZERO_POSE} (flange pose of zero joints)")
        print("gripper target: 0.0 rad (closed)")
        input("Enter to move; keep clear of the arm... ")
        # 관절각(rad) → flange pose(m/rad)는 FK입니다. 위에서 robot model을 설정한 뒤 사용합니다.
        # target_pose = arm.fk([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # [x, y, z, roll, pitch, yaw]
        # arm.move_p(target_pose)  # ZERO_POSE 대신 사용 가능. 내부 IK로 관절 목표를 구해 PTP 이동
        # current_pose = arm.get_flange_pose()  # 현재 실측 관절각의 FK 조회; 이동하지 않음
        arm.move_p(ZERO_POSE)
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

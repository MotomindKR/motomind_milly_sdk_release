#!/usr/bin/env python3
"""MIT warm-start demo: move all six arm joints to zero, then wait for Ctrl-C.

The target is the explicit zero posture ``[0, 0, 0, 0, 0, 0]``. Because
``move_mit`` updates one motor at a time, this example updates all six arm
motors at 30 Hz along one 3-second cosine ramp. The gripper is included and
also moves to 0 rad (closed). Ctrl-C exits through the canonical damping latch;
it never torque-disables a loaded arm.

  .venv/bin/python examples/move_mit_test.py --product-id MILLY_ABCD
"""

from __future__ import annotations

import argparse
import math
import time

import motomind_milly as mm

WARMUP_SECONDS = 3.0
COMMAND_RATE_HZ = 30.0


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def _motors(arm: mm.Arm):
    if arm._config is None:
        raise RuntimeError("move_mit_test needs the create_arm product path")
    motors = list(arm._config.motors)
    if len(motors) != 7:
        raise RuntimeError(f"expected six arm motors plus gripper, found {[motor.id for motor in motors]}")
    return motors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MIT warm-start to [0, 0, 0, 0, 0, 0], then damping latch")
    parser.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    parser.add_argument("--gui", type=_parse_bool, default=True,
                        metavar="{true,false}",
                        help="open the motor-state monitor (default: true)")
    args = parser.parse_args()

    mm.enable_logging()
    arm = mm.create_arm(args.product_id)
    if args.gui:
        from motomind_milly.monitor import MotorMonitor
        MotorMonitor(arm.manager, arm._config, poll_ms=250).start()
        time.sleep(1.0)
    enabled = False
    try:
        if not arm.enable().ok:  # product path starts control loop + supervisor
            print("! enable failed")
            return 1
        enabled = True

        motors = _motors(arm)
        states = {state.id: state for state in arm.states()}
        missing = [motor.id for motor in motors if motor.id not in states]
        if missing:
            print(f"! no feedback from motor(s) {missing}; refusing to move")
            return 1
        start = {motor.id: states[motor.id].position for motor in motors}

        print("MIT target: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] rad (joint_1 -> joint_6)")
        print("gripper target: 0.0 rad (closed)")
        print("warm start: current posture -> zero over 3.0 s")
        input("Enter to start; keep clear of the arm... ")

        start_time = time.monotonic()
        period = 1.0 / COMMAND_RATE_HZ
        while True:
            elapsed = min(time.monotonic() - start_time, WARMUP_SECONDS)
            phase = math.pi * elapsed / WARMUP_SECONDS
            alpha = 0.5 * (1.0 - math.cos(phase))
            alpha_dot = 0.5 * math.pi * math.sin(phase) / WARMUP_SECONDS
            for motor in motors:
                initial = start[motor.id]
                arm.move_mit(
                    motor.id,
                    position=(1.0 - alpha) * initial,
                    velocity=-alpha_dot * initial,
                    torque_feedforward=0.0,
                )
            if elapsed >= WARMUP_SECONDS:
                break
            time.sleep(period)

        print("zero posture reached. Press Ctrl-C to stop safely.")
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[interrupt] engaging damping latch")
        return 0
    finally:
        if enabled:
            arm.shutdown()  # canonical exit reaction: damping latch, never disable()
            print("[done] damping latch engaged")


if __name__ == "__main__":
    raise SystemExit(main())

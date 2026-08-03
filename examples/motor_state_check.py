#!/usr/bin/env python3
"""Simple real-motor smoke test for the motomind_milly SDK.

Tests every motor listed in the config (or a subset via --motor-ids). Default run
is READ-ONLY and safe: open the CAN bus, enable, print live feedback for a few
seconds, then shut down (damping latch — the arm settles, it does NOT drop).
Motion only happens with --move (a small, low-gain sine
around each motor's current position, with a per-motor phase offset).

Prereqs (bring up the CAN interface; bitrate must match the motors):
  sudo ip link set can0 up type can bitrate 1000000

Usage:
  python examples/motor_state_check.py --product-id MILLY_A1B2             # read-only
  python examples/motor_state_check.py --product-id MILLY_A1B2 --duration 10
  python examples/motor_state_check.py --product-id MILLY_A1B2 --motor-ids 1 3
  python examples/motor_state_check.py --product-id MILLY_A1B2 --move       # careful!
"""

from __future__ import annotations

import argparse
import math
import time
from typing import Dict, List

import motomind_milly as mm


def _fmt(fb) -> str:
    return (
        f"pos={fb.position:+.4f} rad  vel={fb.velocity:+.4f} rad/s  "
        f"tau={fb.torque:+.3f} Nm  temp={fb.temperature:5.1f}C  "
        f"mode={fb.mode_status}  fault=0x{fb.fault_bits:04x}"
    )


def feedback_map(arm: mm.Arm, ids: List[int]) -> Dict[int, object]:
    """Actively poll fresh feedback for the requested ids (falls back to states)."""
    fresh = arm.manager.refresh_feedback(timeout_ms=100, retries=2)
    out: Dict[int, object] = {i: fresh[i] for i in ids if i in fresh}
    if len(out) < len(ids):
        by_id = {s.id: s for s in arm.manager.states()}
        for i in ids:
            if i not in out and i in by_id:
                out[i] = by_id[i]
    return out


def run_read_only(arm: mm.Arm, ids: List[int], duration: float) -> None:
    print(f"\n[read] streaming feedback for {duration:.0f}s "
          f"(motors {ids}) — Ctrl-C to stop early")
    end = time.monotonic() + duration
    while time.monotonic() < end:
        fb = feedback_map(arm, ids)
        line = []
        for i in ids:
            if i in fb:
                line.append(f"[{i}] {_fmt(fb[i])}")
            else:
                line.append(f"[{i}] (no feedback)")
        print("  " + "\n  ".join(line))
        time.sleep(0.2)


def run_move(arm: mm.Arm, ids: List[int], *, amplitude: float, kp: float,
             kd: float, rate: float, duration: float) -> None:
    print("\n[move] GENTLE motion test")
    print(f"       amplitude=±{amplitude} rad  kp={kp}  kd={kd}  "
          f"freq=0.3Hz  duration={duration:.0f}s  motors={ids}")

    fb = feedback_map(arm, ids)
    start_pos: Dict[int, float] = {}
    for i in ids:
        if i not in fb:
            print(f"  ! no feedback for motor {i}; refusing to move without a "
                  "known start position.")
            return
        start_pos[i] = fb[i].position
    print("  start positions: " +
          ", ".join(f"[{i}]={start_pos[i]:+.4f}" for i in ids))

    started = arm.manager.start()  # Enabled -> Running
    if not started.ok:
        print(f"  ! start() failed: {started.message}")
        return
    loop = arm.manager.start_control_loop(rate)
    if not loop.ok:
        print(f"  ! start_control_loop() failed: {loop.message}")
        return

    print("  moving in 2s — keep clear of the motors... ", end="", flush=True)
    time.sleep(2.0)
    print("go")

    def send(targets: Dict[int, float]) -> None:
        arm.manager.set_commands(
            [mm.MotorCommand(id=i, position=targets[i], kp=kp, kd=kd) for i in ids]
        )

    t0 = time.monotonic()
    try:
        while True:
            t = time.monotonic() - t0
            if t >= duration:
                break
            targets = {}
            for k, i in enumerate(ids):
                phase = k * (math.pi / max(len(ids), 1))  # stagger the motors
                targets[i] = start_pos[i] + amplitude * math.sin(
                    2.0 * math.pi * 0.3 * t + phase)
            send(targets)
            time.sleep(0.02)  # ~50 Hz Python; C++ loop streams at `rate`
    finally:
        send(start_pos)  # ease back to the starting posture
        time.sleep(0.5)
        arm.stop_control_loop()
        print("  motion done; control loop stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-motor smoke test")
    parser.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    parser.add_argument("--motor-ids", type=int, nargs="+", default=None,
                        help="motor ids to test (default: all motors on the arm)")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="read-only streaming duration (s)")
    parser.add_argument("--move", action="store_true",
                        help="perform a small low-gain motion (default: read-only)")
    parser.add_argument("--amplitude", type=float, default=0.5, help="rad")
    parser.add_argument("--kp", type=float, default=5.0)
    parser.add_argument("--kd", type=float, default=0.5)
    parser.add_argument("--rate", type=float, default=500.0, help="control loop Hz")
    parser.add_argument("--move-duration", type=float, default=4.0)
    args = parser.parse_args()
    mm.enable_logging()
    print(f"motomind_milly {mm.__version__}")

    arm = mm.create_arm(args.product_id)          # discover + verify + connect (finds the bus)
    arm._supervisor_auto = False                  # raw low-level test — drive arm.manager directly
    ids = args.motor_ids or [s.id for s in arm.manager.states()]
    print(f"motors under test: {ids}")

    enabled = False
    try:
        print(f"[enable] motors {ids}...")
        res = arm.enable()
        if not res.ok:
            print(f"  ! enable failed: {res.message}\n"
                  "    check power, motor ids, and CAN bitrate.")
            return 1
        enabled = True
        print(f"  enabled (state={arm.state()})")

        run_read_only(arm, ids, args.duration)
        if args.move:
            run_move(arm, ids, amplitude=args.amplitude, kp=args.kp, kd=args.kd,
                     rate=args.rate, duration=args.move_duration)
        return 0
    except KeyboardInterrupt:
        print("\n[interrupt] stopping...")
        return 0
    finally:
        # SAFE exit: shutdown() runs the yaml exit reaction (damping latch) so the
        # arm settles gently under damping and does NOT drop. A raw disable() here
        # would cut torque and let the arm fall (and after shutdown the FSM is in
        # Shutdown, where disable() is invalid anyway — shutdown() is the exit).
        try:
            if arm.manager.control_loop_running():
                arm.stop_control_loop()
        except Exception:
            pass
        try:
            if enabled:
                arm.shutdown()
        except Exception:
            pass
        try:
            arm.disconnect()
        except Exception:
            pass
        print("[done] damping latch engaged; disconnected.")


if __name__ == "__main__":
    raise SystemExit(main())

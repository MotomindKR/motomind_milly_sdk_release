#!/usr/bin/env python3
"""Simple real-motor smoke test for the motomind_milly SDK.

Tests every motor listed in the config (or a subset via --motor-ids). Default run
enables the motors: open the CAN bus, enable, print live feedback for a few
seconds, then shut down (damping latch — the arm settles, it does NOT drop).

Prereqs (bring up the CAN interface; bitrate must match the motors):
  sudo ip link set can0 up type can bitrate 1000000

Usage:
  python examples/python/motor_state_check.py --product-id MILLY_A1B2             # enables motors; feedback display
  python examples/python/motor_state_check.py --product-id MILLY_A1B2 --duration 10
  python examples/python/motor_state_check.py --product-id MILLY_A1B2 --motor-ids 1 3
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-motor smoke test")
    parser.add_argument("--product-id", required=True,
                        help="robot ID engraved on the arm")
    parser.add_argument("--motor-ids", type=int, nargs="+", default=None,
                        help="motor ids to test (default: all motors on the arm)")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="read-only streaming duration (s)")
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

#!/usr/bin/env python3
"""Real-arm gripper test — position (impedance) control via init_effector.

Goes through the SAME user path a program would: create_arm -> enable()
(auto-starts the supervisor) -> init_effector() -> open/close/move. The
gripper rides the supervisor's command stream, so it holds its target between
commands without a dead-man latch. Ctrl-C / q exits via the damping latch
(shutdown()), NOT a drop.

Milly gripper: close = 0.0 rad, open = -2.3 rad (config range).

  .venv/bin/python examples/gripper_test.py --product-id MILLY_ABCD

Keys (press Enter after the letter):
  o        open   (-2.3 rad)
  c        close  ( 0.0 rad)
  <number> move to that position [rad] (clamped to range), e.g. -1.2
  k        set hold gains for the next move   (prompts kp kd)
  s        status (target / measured position)
  q        quit   (Ctrl-C also works — exits via the damping latch)
"""

from __future__ import annotations

import argparse
import threading
import time

import motomind_milly as mm


def main() -> int:
    ap = argparse.ArgumentParser(description="Real-arm gripper test")
    ap.add_argument("--product-id", required=True,
                    help="robot ID engraved on the arm")
    ap.add_argument("--joint", default="gripper",
                    help="config joint/name of the effector motor")
    args = ap.parse_args()
    mm.enable_logging()

    # enable() auto-starts the control loop + supervisor, so the gripper's
    # held target is streamed every tick.
    arm = mm.create_arm(args.product_id)   # discover + verify + connect
    print(f"[arm] {args.product_id} connected")

    if not arm.enable().ok:                     # auto-starts control loop + supervisor
        print("! enable failed"); return 1

    grip = arm.init_effector(args.joint)
    lo, hi = grip.range
    print(f"[gripper] motor id={grip.motor_id}  range=[{lo:.2f}, {hi:.2f}] rad  "
          f"(close={hi:.2f}, open={lo:.2f})")

    stop = threading.Event()
    gains = {"kp": None, "kd": None}

    def status() -> None:
        pos = grip.position
        tgt = arm._supervisor.hold_targets().get(grip.motor_id)
        pos_s = f"{pos:+.3f}" if pos is not None else "  n/a"
        tgt_s = f"{tgt:+.3f}" if tgt is not None else "  n/a"
        print(f"  target={tgt_s} rad   measured={pos_s} rad   state={arm.state()}")

    def set_gains() -> None:
        try:
            raw = input("  kp kd (blank = default): ").strip()
        except (EOFError, KeyboardInterrupt):
            stop.set(); return
        if not raw:
            gains["kp"] = gains["kd"] = None
            print("  gains -> default")
            return
        kp, kd = (float(x) for x in raw.split()[:2])
        gains["kp"], gains["kd"] = kp, kd
        print(f"  gains -> kp={kp} kd={kd}")

    def move_to(pos: float) -> None:
        grip.move(pos, kp=gains["kp"], kd=gains["kd"])

    def reader() -> None:
        print("keys: o=open  c=close  <number>=move[rad]  k=gains  s=status  q=quit")
        while not stop.is_set():
            try:
                key = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                stop.set(); return
            if key == "q":
                stop.set(); return
            try:
                if key == "o":
                    grip.open(kp=gains["kp"], kd=gains["kd"])
                elif key == "c":
                    grip.close(kp=gains["kp"], kd=gains["kd"])
                elif key == "k":
                    set_gains()
                elif key == "s":
                    status()
                elif key == "":
                    continue
                else:
                    move_to(float(key))          # a bare number = target position
            except ValueError:
                print(f"  unknown key {key!r} — o c <number> k s q")
            except Exception as exc:
                print(f"  refused: {exc}")

    th = threading.Thread(target=reader, name="console", daemon=True)
    th.start()
    try:
        while not stop.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        arm.shutdown()      # exit reaction: damping latch (does NOT drop)
        print("\n[done] damping latch engaged (exit reaction)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

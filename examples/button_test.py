#!/usr/bin/env python3
"""Button/LED board test — poll the STM LED/button board over CAN and report
toggles + link reliability (how often a poll gets no response).

The board shares the motor CAN line. Each poll sends ONE feedback request and
waits up to ~0.3 s for the board's reply (``identity.read_button``). A poll is a
MISS ("no response") when no matching feedback frame arrives in that window —
i.e. the request or the reply was dropped, or the board answered too late.
``--retries`` lets read_button re-send within a poll before giving up (0 =
single-shot, exactly what the supervisor's button monitor does).

  # standalone soak — leave it running and watch the miss rate:
  .venv/bin/python examples/button_test.py --interface can0

  # while the arm is enabled (poll on a 2nd socket while the core drives motors):
  .venv/bin/python examples/button_test.py --with-arm --product-id MILLY_ABCD

Press the button to see TOGGLE lines. A running summary prints every
``--stats-sec`` and a full summary prints on Ctrl-C. With --with-arm, also
confirm the arm keeps holding (no motor fault) while polling.

Toggle detection is edge-based vs a start baseline: the first read is the
baseline (a button already 'on' at startup is NOT a toggle); after that every
button_state change is a TOGGLE.
"""

from __future__ import annotations

import argparse
import time

import motomind_milly as mm
from motomind_milly import identity


def main() -> int:
    ap = argparse.ArgumentParser(description="Button/LED board test + reliability")
    ap.add_argument("--interface", default="can0",
                    help="CAN interface the button board is on (standalone mode)")
    ap.add_argument("--poll-ms", type=int, default=200, metavar="MS",
                    help="polling period (50..1000 typical)")
    ap.add_argument("--retries", type=int, default=0, metavar="N",
                    help="read_button re-sends per poll before a MISS (default 0 "
                         "= single-shot, matches the supervisor's button monitor)")
    ap.add_argument("--stats-sec", type=float, default=5.0, metavar="S",
                    help="print a running reliability summary every S seconds")
    ap.add_argument("--with-arm", action="store_true",
                    help="enable the arm first, then poll the button on a 2nd "
                         "socket (verifies concurrent read while motors run)")
    ap.add_argument("--product-id", default=None,
                    help="robot ID (only used with --with-arm)")
    args = ap.parse_args()
    if args.with_arm and not args.product_id:
        ap.error("--with-arm requires --product-id MILLY_XXXX")
    mm.enable_logging()

    arm = None
    iface = args.interface
    if args.with_arm:
        arm = mm.create_arm(args.product_id)          # discover + verify + connect
        iface = arm._config.buses[0].config.interface_name
        if not arm.enable().ok:                       # control loop + supervisor
            print("! enable failed"); return 1
        print(f"[arm] {args.product_id} enabled on {iface} (holding)")

    period = max(0.02, args.poll_ms / 1000.0)
    print(f"[button] polling {iface} every {args.poll_ms} ms (retries={args.retries}) "
          f"— press the button; Ctrl-C for the summary")

    polls = hits = misses = 0
    streak = max_streak = 0          # consecutive-miss streaks
    led_faults = 0
    tmin = tmax = None
    baseline = prev = None
    next_stats = time.monotonic() + args.stats_sec

    def summary(tag: str) -> None:
        rate = (misses / polls * 100.0) if polls else 0.0
        temp = f"{tmin:.1f}..{tmax:.1f}C" if tmin is not None else "n/a"
        print(f"  [{tag}] polls={polls} hits={hits} miss={misses} "
              f"({rate:.2f}%)  max_miss_streak={max_streak}  "
              f"led_faults={led_faults}  temp={temp}")

    try:
        while True:
            st = identity.read_button(iface, retries=args.retries)
            polls += 1
            if st is None:                            # no matching reply within the timeout
                misses += 1
                streak += 1
                max_streak = max(max_streak, streak)
                if streak in (1, 10, 50, 200):
                    print(f"  (no response x{streak} — dropped/late reply on {iface})")
            else:
                hits += 1
                streak = 0
                b = st["button_state"]
                if st["led_fault"]:
                    led_faults += 1
                t = st["temperature_deci_c"] / 10.0
                tmin = t if tmin is None else min(tmin, t)
                tmax = t if tmax is None else max(tmax, t)
                if baseline is None:
                    baseline = prev = b
                    print(f"  baseline button_state={b}  led_fault={st['led_fault']}  "
                          f"temp={t:.1f}C  (start state is NOT a toggle)")
                elif b != prev:
                    rel = "== baseline" if b == baseline else "!= baseline"
                    print(f"  TOGGLE  button_state {prev} -> {b}   ({rel})")
                    prev = b
            time.sleep(period)
            if time.monotonic() >= next_stats:
                summary("stats")
                next_stats = time.monotonic() + args.stats_sec
    except KeyboardInterrupt:
        print("\n[interrupt] stopping")
    finally:
        summary("TOTAL")
        if arm is not None:
            arm.shutdown()          # exit reaction: damping latch
            print("[done] arm damping latch engaged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

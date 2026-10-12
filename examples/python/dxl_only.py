#!/usr/bin/env python3
"""Teaching device only: selected torque ON, mapped positions, then torque OFF."""
import time

from _teaching import parser, session, setup


def run_device(dev, controller, *, rate_hz=30., duration=None, confirm=input):
    with session(dev):
        print('Models:', dev.models)
        print('Torque axes:', controller.ids)
        confirm('Support the teaching device. Enter to enable DXL torque; Ctrl+C to cancel: ')
        controller.enable()
        started = time.monotonic()
        while duration is None or time.monotonic() - started < duration:
            tick = time.monotonic()
            print(controller.step(), flush=True)
            time.sleep(max(0., 1 / rate_hz - (time.monotonic() - tick)))
    print('DXL torque OFF; port closed.')


def main():
    p = parser(__doc__)
    p.add_argument('--fake', action='store_true', help='no hardware; sample transport')
    p.add_argument('--auto-start', action='store_true', help='fake tests only')
    args = p.parse_args()
    if args.auto_start and not args.fake:
        p.error('--auto-start requires --fake')
    try:
        dev, controller, _ = setup(args, fake=args.fake)
        run_device(dev, controller, rate_hz=args.rate_hz, duration=args.duration,
                   confirm=(lambda _: None) if args.auto_start else input)
        return 0
    except (KeyboardInterrupt, EOFError):
        print('Stopped by operator.')
        return 0
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

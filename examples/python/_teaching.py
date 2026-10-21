"""Shared teaching example setup; no Milly, ROS, or CAN imports."""
import argparse
from contextlib import contextmanager
import math
from pathlib import Path
import select
import signal
import sys
import time

from motomind_teaching import TeachingDevice
from motomind_teaching.feedback import TeachingFeedback
from motomind_teaching._profiles import load_profile
from motomind_teaching.serial_access import DEFAULT_PORT


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('expected a finite positive value')
    return value


def parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--port', default=DEFAULT_PORT)
    nearby = Path(__file__).parent / 'configs/dxl_right_example.json'
    default_profile = nearby
    if not nearby.is_file():
        for ancestor in Path(__file__).resolve().parents:
            candidate = ancestor/'configs/teaching_devices/dxl_right_example.json'
            if candidate.is_file():
                default_profile = candidate
                break
    parser.add_argument('--profile', type=Path, default=default_profile)
    parser.add_argument('--rate-hz', type=positive, default=30.)
    parser.add_argument('--duration', type=positive, help='stop after N seconds; default: Ctrl+C')
    return parser


def setup(args, *, fake=False):
    if not 0 < args.rate_hz <= 100:
        raise ValueError('rate-hz must be in (0, 100]')
    profile = load_profile(args.profile)
    transport = None
    if fake:
        from motomind_teaching.device import MODELS
        from motomind_teaching.testing import FakeTransport
        numbers = {name: number for number, name in MODELS.items()}
        transport = FakeTransport(profile['ids'])
        transport.model = {mid: numbers[name] for mid, name in zip(profile['ids'], profile['models'])}
        print('FAKE: no serial device or robot is opened.')
    dev = TeachingDevice.from_profile(args.port, args.profile, transport=transport)
    controller = TeachingFeedback(dev, profile)
    gripper = profile['joint_names'].index('gripper')
    print(f"DXL gripper settings: P={controller.p_gain[gripper]}, "
          f"restoring target={profile['teleop_feedback']['gripper_target_rad']:g} rad, "
          f"output max={controller.policy.limits[gripper][1]:g} rad", flush=True)
    return dev, controller, profile


@contextmanager
def ignore_signals():
    previous = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextmanager
def session(dev):
    previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    def interrupt(*_):
        raise KeyboardInterrupt()
    try:
        for sig in previous:
            signal.signal(sig, interrupt)
        dev.open()
        yield dev
    finally:
        try:
            with ignore_signals():
                dev.close()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def wait_for_enter(controller, rate_hz):
    """Keep fresh DXL reads/force updates while waiting; disconnect cancels start."""
    print('DXL ready. Support both devices and compare their poses. Enter to start Milly; Ctrl+C to cancel.', flush=True)
    print('Teaching positions (rad):', controller.step(), flush=True)
    while True:
        start = time.monotonic()
        controller.step()
        if select.select([sys.stdin], [], [], 0)[0]:
            if not sys.stdin.readline():
                raise EOFError('input closed; start cancelled')
            return
        time.sleep(max(0., 1 / rate_hz - (time.monotonic() - start)))

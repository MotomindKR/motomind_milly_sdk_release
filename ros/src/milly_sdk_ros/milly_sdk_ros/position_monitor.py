"""Position queries only: no enable, mode changes, command stream or damping.

This does NOT make an already enabled robot torque-free. It only reads the
mechanical-position register via the SDK and closes its own socket on exit.
"""
import math
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class GripperDisplayMap:
    """Uncalibrated RViz interpolation, never a motor command or SDK model input.

    The current CAD fingers move inward as their prismatic coordinates increase.
    Endpoints describe each finger, not the total distance between the jaws.
    """

    motor_closed: float = 0.0
    motor_open: float = 2.11
    finger_closed: float = 0.05
    finger_open: float = 0.0

    def __post_init__(self):
        if not all(math.isfinite(value) for value in (
                self.motor_closed, self.motor_open, self.finger_closed, self.finger_open)):
            raise ValueError("gripper display endpoints must be finite")
        if self.motor_open <= self.motor_closed:
            raise ValueError("gripper_motor_open must exceed gripper_motor_closed (RAW coordinates)")
        if not 0.0 <= self.finger_open < self.finger_closed <= 0.05:
            raise ValueError("gripper display requires 0 <= finger_open < finger_closed <= 0.05 m")

    def position(self, raw):
        if not math.isfinite(raw):
            raise ValueError("gripper raw position must be finite")
        fraction = (raw - self.motor_closed) / (self.motor_open - self.motor_closed)
        fraction = min(1.0, max(0.0, fraction))
        return self.finger_closed + fraction * (self.finger_open - self.finger_closed)


class PositionMonitor:
    def __init__(self, arm, *, stale_after_s=0.5, clock=time.monotonic):
        self.arm = arm
        self.stale_after_s = stale_after_s
        self.clock = clock
        self._cache = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self.last_error = ""

    def poll_once(self):
        # The core reads mechPos (0x7019). Unlike enable/active-report setup,
        # refresh_feedback writes no motor parameter or control command.
        started = self.clock()
        try:
            feedback = self.arm.manager.refresh_feedback(timeout_ms=10, retries=1)
            with self._lock:
                for mid, item in feedback.items():
                    if math.isfinite(item.position):
                        self._cache[mid] = (float(item.position), started)
                self.last_error = ""
        except Exception as exc:
            with self._lock:
                self.last_error = str(exc)

    def snapshot(self):
        now = self.clock()
        with self._lock:
            return {mid: {"position": pos, "age_s": max(0.0, now - stamp),
                          "fresh": 0 <= now - stamp <= self.stale_after_s}
                    for mid, (pos, stamp) in self._cache.items()}

    def start(self):
        if self._thread is not None or self._closed:
            raise RuntimeError("monitor already started/closed")
        def run():
            while not self._stop.is_set():
                self.poll_once()
                self._stop.wait(0.05)
        self._thread = threading.Thread(target=run, name="milly-position-query", daemon=True)
        self._thread.start()

    def close(self):
        if self._closed:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join()  # bounded per-register timeout, no socket race
        self.arm.disconnect()  # NEVER shutdown(): shutdown would send damping
        self._closed = True

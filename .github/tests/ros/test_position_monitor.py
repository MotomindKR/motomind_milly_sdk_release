"""Passive monitor must never change the motor's enabled state or torque."""
from types import SimpleNamespace as NS
import math
import pytest

from milly_sdk_ros.position_monitor import GripperDisplayMap, PositionMonitor


@pytest.mark.parametrize("raw, expected", [
    (0.0, 0.05), (1.055, 0.025), (2.11, 0.0), (-0.1, 0.05), (2.21, 0.0)])
def test_gripper_display_closing_direction_and_limits(raw, expected):
    assert GripperDisplayMap().position(raw) == pytest.approx(expected)


def test_gripper_display_adjustable_endpoints():
    mapping = GripperDisplayMap(motor_closed=0.1, motor_open=2.1,
                               finger_closed=0.045, finger_open=0.005)
    assert mapping.position(0.1) == pytest.approx(0.045)
    assert mapping.position(1.1) == pytest.approx(0.025)
    assert mapping.position(2.1) == pytest.approx(0.005)


@pytest.mark.parametrize("overrides", [
    {"motor_open": 0.0}, {"motor_open": -2.11}, {"motor_closed": math.nan},
    {"finger_open": math.inf}, {"finger_closed": 0.051}, {"finger_open": -0.01},
    {"finger_open": 0.05}])
def test_invalid_gripper_display_endpoints_rejected(overrides):
    with pytest.raises(ValueError):
        GripperDisplayMap(**overrides)


@pytest.mark.parametrize("raw", [math.nan, math.inf, -math.inf])
def test_nonfinite_gripper_feedback_rejected(raw):
    with pytest.raises(ValueError):
        GripperDisplayMap().position(raw)


def test_position_queries_freshness_and_disconnect_only():
    calls = []
    now = [10.0]
    feedback = {1: NS(position=0.4), 2: NS(position=-1.2), 7: NS(position=1.5)}
    def query(**kw):
        calls.append(("query", kw))
        return feedback
    arm = NS(manager=NS(refresh_feedback=query), disconnect=lambda: calls.append("disconnect"))
    monitor = PositionMonitor(arm, clock=lambda: now[0])
    assert monitor.snapshot() == {}  # do not publish zero for missing feedback
    monitor.poll_once()
    rows = monitor.snapshot()
    assert rows[2]["position"] == -1.2  # no second sign multiplication
    assert rows[7]["position"] == 1.5
    assert all(row["fresh"] for row in rows.values())
    assert 3 not in rows
    now[0] += 1
    feedback.clear()
    monitor.poll_once()
    assert not monitor.snapshot()[1]["fresh"]
    feedback[1] = NS(position=math.nan)
    monitor.poll_once()
    assert monitor.snapshot()[1]["position"] == 0.4
    monitor.close()
    monitor.close()
    assert calls.count("disconnect") == 1
    assert all(c == "disconnect" or c == ("query", {"timeout_ms": 10, "retries": 1}) for c in calls)


def test_query_error_still_disconnects():
    calls = []
    def query(**kw):
        raise OSError("CAN unavailable")
    arm = NS(manager=NS(refresh_feedback=query), disconnect=lambda: calls.append("disconnect"))
    monitor = PositionMonitor(arm)
    monitor.poll_once()
    assert "CAN unavailable" in monitor.last_error
    assert monitor.snapshot() == {}
    monitor.close()
    assert calls == ["disconnect"]

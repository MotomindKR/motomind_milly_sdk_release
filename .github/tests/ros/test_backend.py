"""No ROS, no native extension, no CAN: service adapter behavior contract."""
import math
import threading
import unittest
from types import SimpleNamespace as NS

from milly_sdk_ros.backend import Backend, optional
from milly_sdk_ros.telemetry import joint_values, quaternion


class FakeArm:
    def __init__(self):
        self.calls = []
        self.mode = "Idle"
        self.manager = NS(fault_reason=lambda: "test fault" if self.mode == "Fault" else "")
        self._max_vel = 0.5
        self.rows = [NS(id=i, joint_name=f"joint_{i}" if i < 7 else "gripper",
                        position=0., velocity=0., torque=0., temperature=25.,
                        fault_bits=0, mode_status=0, feedback_age_s=-1.) for i in range(1, 8)]
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block_move = False
        self.raise_motion = None
        self.gripper = NS(range=(0., 2.11), move=lambda p, **k: max(0., min(2.11, p)),
                          open=lambda **k: 2.11, close=lambda **k: 0.)

    def init_effector(self): return self.gripper
    def state(self): return self.mode
    def states(self): return self.rows
    def _default_gains_for_motor(self, mid): return (10., 1.)
    def enable(self):
        self.calls.append(("enable", {}))
        if self.mode != "Idle": return NS(ok=False, message="enable only from Idle")
        self.mode = "Running"
        return NS(ok=True, message="enabled")
    def recover(self):
        self.calls.append(("recover", {}))
        if self.mode != "Fault": return NS(ok=False, message="recover only from Fault")
        self.mode = "Idle"
        return NS(ok=True, message="recovered")
    def electronic_emergency_stop(self):
        self.mode = "Fault"
        self.calls.append(("estop", {}))
        self.release.set()
        return NS(ok=True, message="damping")
    def shutdown(self):
        self.calls.append(("shutdown", {}))
        self.mode = "Shutdown"
        self.release.set()
        return NS(ok=True, message="shutdown")
    def disable(self):
        self.mode = "Idle"
        self.release.set()
        return NS(ok=True, message="disabled")
    def move_j(self, values, **kw):
        if self.mode != "Running": raise RuntimeError("requires Running")
        self.calls.append(("move_j", dict(values=values, **kw)))
        self.entered.set()
        if self.block_move: self.release.wait(2)
        if self.raise_motion: raise RuntimeError(self.raise_motion)
        return 1.5  # intentionally returns success even on fault; adapter must catch it
    move_p = move_j
    def move_mit(self, mid, **kw):
        if self.mode != "Running": raise RuntimeError("requires Running")
        self.calls.append(("move_mit", dict(mid=mid, **kw)))
        return True
    def hold_mode(self): self.calls.append(("hold", {}))
    def float_mode(self): self.calls.append(("float", {}))
    def set_max_vel(self, max_vel): self._max_vel = max_vel
    def set_default_gains(self, kp, kd): self.calls.append(("gains", dict(kp=kp, kd=kd)))
    def set_gripper_gains(self, kp, kd): self.calls.append(("gripper_gains", dict(kp=kp, kd=kd)))


def make_backend():
    arm = FakeArm()
    limits = NS(position_min=-3., position_max=3., kp_min=0., kp_max=200., kd_min=0., kd_max=20.)
    cfg = NS(motors=[NS(id=i, joint_name=f"joint_{i}" if i < 7 else "gripper",
                        limits=limits) for i in range(1, 8)],
             buses=[NS(config=NS(interface_name="can0"))])
    return Backend(arm, "MILLY_TEST", cfg, fk_solver=lambda q: list(q)), arm


class BackendTest(unittest.TestCase):
    def test_no_automatic_enable(self):
        b, arm = make_backend()
        self.assertEqual(arm.calls, [])
        self.assertEqual(b.status()["manager_state"], "Idle")

    def test_optional_scalar_and_nonfinite(self):
        self.assertIsNone(optional([]))
        self.assertEqual(optional([0.]), 0.)
        for v in ([1., 2.], [math.nan], [math.inf]):
            with self.assertRaises(ValueError): optional(v)

    def test_enable_and_api_defaults(self):
        b, arm = make_backend()
        self.assertFalse(b.execute("move_j", positions=[0.]*6).success)
        self.assertTrue(b.execute("enable").success)
        self.assertFalse(b.execute("enable").success)
        r = b.execute("move_j", positions=[0.]*6, max_vel=None, kp=None, kd=None)
        self.assertTrue(r.success)
        self.assertEqual(r.duration_s, 1.5)
        self.assertIsNone(arm.calls[-1][1]["kp"])
        self.assertTrue(b.execute("move_p", pose=[0.]*6, max_vel=0.2).success)
        self.assertTrue(b.execute("move_mit", motor_id=2, position=0., kp=None, kd=None).success)
        self.assertTrue(b.execute("float_mode").success)
        self.assertEqual(arm.calls[-1], ("float", {}))
        self.assertTrue(b.execute("hold_mode").success)

    def test_gripper_and_gain_validation(self):
        b, arm = make_backend()
        self.assertTrue(b.execute("set_gains", group="arm", kp=[10.]*6, kd=[1.]*6).success)
        self.assertFalse(b.execute("set_gains", group="arm", kp=[10.], kd=[1.]).success)
        self.assertFalse(b.execute("set_gains", group="gripper", kp=[201.], kd=[1.]).success)
        self.assertFalse(b.execute("set_max_vel", max_vel=math.nan).success)
        b.execute("enable")
        self.assertFalse(b.execute("set_gains", group="arm", kp=[10.]*6, kd=[1.]*6).success)
        self.assertEqual(b.execute("gripper", action="open").target, 2.11)
        self.assertEqual(b.execute("gripper", action="close").target, 0.)
        self.assertEqual(b.execute("gripper", action="move", position=-9.).target, 0.)

    def test_rejected_ik_and_collision_are_failures(self):
        b, arm = make_backend()
        b.execute("enable")
        for message in ("IK did not converge", "self-collision preflight rejected"):
            arm.raise_motion = message
            self.assertFalse(b.execute("move_p", pose=[0.]*6).success)
            self.assertIn(message, b.last_error)
            self.assertEqual(arm.mode, "Running")

    def test_estop_not_blocked_by_motion_and_no_false_success(self):
        b, arm = make_backend()
        b.execute("enable")
        arm.block_move = True
        results = []
        worker = threading.Thread(target=lambda: results.append(
            b.execute("move_j", positions=[0.]*6)))
        worker.start()
        self.assertTrue(arm.entered.wait(1))
        self.assertTrue(b.status()["moving"])
        self.assertFalse(b.execute("move_p", pose=[0.]*6).success)
        self.assertFalse(b.execute("move_mit", motor_id=1, position=0.).success)
        self.assertTrue(b.stop().success)
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertFalse(results[0].success)
        self.assertFalse(b.execute("enable").success)
        self.assertTrue(b.execute("recover").success)
        self.assertEqual(arm.mode, "Idle")
        self.assertTrue(b.execute("enable").success)

    def test_fault_without_explicit_stop_is_not_success(self):
        b, arm = make_backend()
        b.execute("enable")
        def fault(*a, **k):
            arm.mode = "Fault"
            return 3.
        arm.move_j = fault
        self.assertFalse(b.execute("move_j", positions=[0.]*6).success)

    def test_shutdown_interrupts_and_is_idempotent(self):
        b, arm = make_backend()
        b.execute("enable")
        arm.block_move = True
        results = []
        worker = threading.Thread(target=lambda: results.append(b.execute("move_j", positions=[0.]*6)))
        worker.start()
        self.assertTrue(arm.entered.wait(1))
        self.assertTrue(b.stop("shutdown").success)
        worker.join(1)
        self.assertFalse(results[0].success)
        self.assertTrue(b.stop("shutdown").success)
        self.assertFalse(b.status()["connected"])
        self.assertFalse(b.execute("enable").success)
        self.assertEqual(sum(name == "shutdown" for name, kw in arm.calls), 1)

    def test_freshness_never_based_on_position_changes(self):
        b, arm = make_backend()
        self.assertFalse(b.status()["feedback_valid"])
        self.assertEqual(joint_values(b.snapshots(), (0., 2.11))[0], [])
        for row in arm.rows: row.feedback_age_s = 0.01
        self.assertTrue(b.status()["feedback_valid"])
        self.assertTrue(b.fk([]).success)
        self.assertTrue(b.status()["feedback_valid"])  # stationary, but fresh
        arm.rows[0].feedback_age_s = 1.
        self.assertIn(1, b.status()["stale_motor_ids"])
        self.assertFalse(b.fk([]).success)
        self.assertNotIn("joint_1", joint_values(b.snapshots(), (0., 2.11))[0])
        self.assertTrue(b.fk([0.]*6).success)

    def test_visual_gripper_and_quaternion(self):
        b, arm = make_backend()
        arm.rows[-1].feedback_age_s = 0.01
        names, p, v = joint_values(b.snapshots(), (0., 2.11))
        self.assertEqual(names, [])  # no uncalibrated finger measurements
        self.assertEqual(p, [])
        arm.rows[-1].position = 0.
        self.assertEqual(joint_values(b.snapshots(), (0., 2.11))[1], [])
        self.assertEqual(quaternion(0., 0., 0.), (0., 0., 0., 1.))

    def test_unknown_or_nonfinite_motion(self):
        b, arm = make_backend()
        b.execute("enable")
        self.assertFalse(b.execute("move_j", positions=[math.nan]*6).success)
        self.assertFalse(b.execute("move_mit", motor_id=8, position=0.).success)
        self.assertFalse(b.execute("move_mit", motor_id=1, position=math.inf).success)


if __name__ == "__main__":
    unittest.main()


def test_float_rejects_tuning_without_calling_sdk():
    backend, arm = make_backend()
    for key in ('scale', 'kp', 'kd', 'gains'):
        assert not backend.execute('float_mode', **{key: 0.5}).success
    assert not arm.calls


def test_shutdown_cannot_report_a_noop_disable_as_success():
    backend, arm = make_backend()
    assert backend.execute('enable').success
    assert backend.stop('shutdown').success
    calls = list(arm.calls)
    assert backend.stop('shutdown').success
    assert not backend.execute('enable').success
    for operation in ('disable', 'electronic_emergency_stop'):
        result = backend.stop(operation)
        assert not result.success
        assert 'no motor command sent' in result.message
    assert arm.calls == calls
    fresh, fresh_arm = make_backend()
    assert fresh.execute('enable').success
    assert fresh.stop('disable').success
    assert fresh_arm.state() == 'Idle'

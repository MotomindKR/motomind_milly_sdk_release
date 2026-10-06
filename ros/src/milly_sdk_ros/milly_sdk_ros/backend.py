"""SDK adapter without ROS imports, so concurrency/error handling is unit-testable.

No CAN ownership mechanism: the locks below serialize callbacks in THIS driver
only. A second SDK process can still interfere with the robot.
"""
from dataclasses import dataclass, field
import math
import threading


@dataclass
class Result:
    success: bool
    message: str = ""
    duration_s: float = 0.0
    target: float = 0.0
    values: list = field(default_factory=list)


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("values must be finite")
    return value


def optional(values):
    """ROS optional scalar: [] -> None, [x] -> x; never a magic zero."""
    if len(values) > 1:
        raise ValueError("optional scalars accept [] or [value]")
    return finite(values[0]) if values else None


def state_name(value):
    return getattr(value, "name", str(value).rsplit(".", 1)[-1])


class Backend:
    def __init__(self, arm, product_id, config, *, fk_solver, sdk_version="",
                 supervisor_rate_hz=100.0, stale_after_s=0.5):
        self.arm = arm
        self.product_id = product_id
        self.config = config
        self.sdk_version = sdk_version
        self.supervisor_rate_hz = supervisor_rate_hz
        self.stale_after_s = stale_after_s
        self.gripper = arm.init_effector()
        self._fk_solver = fk_solver
        self._fk_lock = threading.Lock()
        self._operation = threading.Lock()
        self._lifecycle = threading.Lock()
        self._meta = threading.Lock()
        self._epoch = 0
        self._blocked = False
        self._closed = False
        self._moving = False
        self.last_error = ""

    @classmethod
    def connect(cls, product_id, urdf_path, *, supervisor_rate_hz=100.0,
                stale_after_s=0.5):
        import motomind_milly as mm
        from motomind_robot_model import RobotModel
        if not hasattr(mm.MotorState(), "feedback_age_s"):
            raise RuntimeError("SDK wheel needs feedback_age_s; rebuild/install this release")
        # Validate/load model BEFORE connecting, with no motor operation.
        model = RobotModel(urdf_path)
        query_model = RobotModel(urdf_path)  # do not share mutable Pinocchio Data with supervisor
        names = [f"joint_{i}" for i in range(1, 7)]
        if any(name not in query_model.joint_names for name in names):
            raise ValueError("URDF must contain joint_1..joint_6")
        query_model.frame_id("link_6")
        arm = mm.create_arm(product_id, supervisor_rate_hz=supervisor_rate_hz)
        try:
            arm.set_robot_model(model)  # FK/IK and gravity only; no collision preflight
            def solve(angles):
                q = query_model.q_from_joints(dict(zip(names, angles)))
                xyz, rpy = query_model.frame_pose(q, "link_6")
                return list(xyz) + list(rpy)
            return cls(arm, product_id, arm._config, fk_solver=solve,
                       sdk_version=mm.__version__, supervisor_rate_hz=supervisor_rate_hz,
                       stale_after_s=stale_after_s)
        except BaseException:
            # No enable has been attempted: only close our own socket.
            arm.disconnect()
            raise

    def fail(self, message):
        self.last_error = str(message)
        return Result(False, self.last_error)

    def snapshots(self):
        rows = []
        for s in self.arm.states():
            age = float(s.feedback_age_s)
            received = math.isfinite(age) and age >= 0.0
            numeric = all(math.isfinite(float(getattr(s, k)))
                          for k in ("position", "velocity", "torque", "temperature"))
            rows.append(dict(
                id=s.id, joint_name=s.joint_name, position=s.position,
                velocity=s.velocity, torque=s.torque, temperature=s.temperature,
                fault_bits=s.fault_bits, mode_status=s.mode_status,
                feedback_age_s=age, received=received,
                fresh=received and age <= self.stale_after_s and numeric))
        return rows

    def status(self):
        rows = self.snapshots()
        by_id = {r["id"]: r for r in rows}
        missing = [m.id for m in self.config.motors
                   if m.id not in by_id or not by_id[m.id]["received"]]
        stale = [r["id"] for r in rows if r["received"] and not r["fresh"]]
        return dict(
            product_id=self.product_id, manager_state=state_name(self.arm.state()),
            connected=not self._closed, moving=self._moving,
            feedback_valid=not missing and not stale and not self._closed,
            missing_motor_ids=missing, stale_motor_ids=stale,
            fault_reason=self.arm.manager.fault_reason(),
            last_error=self.last_error)

    def info(self):
        motors = self.config.motors
        gains = [self.arm._default_gains_for_motor(m.id) for m in motors]
        return dict(
            product_id=self.product_id, sdk_version=self.sdk_version,
            can_interface=self.config.buses[0].config.interface_name,
            base_frame="base_link", flange_frame="link_6",
            motor_ids=[m.id for m in motors], joint_names=[m.joint_name for m in motors],
            position_min=[m.limits.position_min for m in motors],
            position_max=[m.limits.position_max for m in motors],
            kp_max=[m.limits.kp_max for m in motors], kd_max=[m.limits.kd_max for m in motors],
            default_kp=[x[0] for x in gains], default_kd=[x[1] for x in gains],
            max_vel=self.arm._max_vel, supervisor_rate_hz=self.supervisor_rate_hz)

    def fk(self, joints):
        try:
            angles = list(joints)
            if not angles:
                by_name = {r["joint_name"]: r for r in self.snapshots()}
                names = [f"joint_{i}" for i in range(1, 7)]
                if any(n not in by_name or not by_name[n]["fresh"] for n in names):
                    raise ValueError("FK requires fresh feedback from all six arm joints")
                angles = [by_name[n]["position"] for n in names]
            if len(angles) != 6:
                raise ValueError("FK expects six angles or [] for measured joints")
            with self._fk_lock:
                values = [float(x) for x in self._fk_solver([finite(x) for x in angles])]
            return Result(True, values=values)
        except Exception as exc:
            return self.fail(exc)

    def execute(self, operation, **kw):
        # No queue of future motions, and no teleop/VLA source arbitration.
        if not self._operation.acquire(blocking=False):
            return self.fail("busy: another command is executing")
        try:
            with self._meta:
                epoch = self._epoch
                if self._closed:
                    return self.fail("driver is shut down; restart it to reconnect")
                if self._blocked and operation != "recover":
                    return self.fail("stop requested; inspect the robot, recover, then enable")
                self._moving = operation in ("move_j", "move_p")
            if operation in ("enable", "recover"):
                with self._lifecycle:
                    with self._meta:
                        if epoch != self._epoch:
                            return self.fail("interrupted by stop")
                    result = getattr(self.arm, operation)()
                    if not result.ok:
                        return self.fail(result.message)
                    if operation == "recover":
                        with self._meta:
                            if epoch == self._epoch:
                                self._blocked = False
                    output = Result(True, result.message)
            elif operation in ("move_j", "move_p"):
                key = "positions" if operation == "move_j" else "pose"
                vector = [finite(x) for x in kw.pop(key)]
                if len(vector) != 6:
                    raise ValueError("planned move requires exactly six values")
                output = Result(True, "SDK trajectory completed (not measured arrival)",
                                duration_s=float(getattr(self.arm, operation)(vector, **kw)))
            elif operation == "move_mit":
                motor_id = kw.pop("motor_id")
                if not any(m.id == motor_id for m in self.config.motors):
                    raise ValueError("unknown motor_id")
                args = {k: finite(v) if v is not None else None for k, v in kw.items()}
                ok = self.arm.move_mit(motor_id, **args)
                output = Result(bool(ok), "MIT target accepted" if ok else "MIT rejected")
            elif operation == "gripper":
                action = kw.pop("action")
                if action not in ("move", "open", "close"):
                    raise ValueError("gripper operation must be move/open/close")
                position = finite(kw.pop("position", 0.0))
                fn = getattr(self.gripper, action)
                target = fn(position, **kw) if action == "move" else fn(**kw)
                output = Result(True, "gripper target accepted (not measured arrival)",
                                target=float(target))
            elif operation == "float_mode":
                if kw:
                    raise ValueError("FLOAT accepts no tuning parameters")
                self.arm.float_mode()
                output = Result(True, "accepted")
            elif operation in ("hold_mode", "set_max_vel"):
                if operation == "set_max_vel":
                    value = finite(kw["max_vel"])
                    if not 0.0 < value <= 2.0:
                        raise ValueError("max_vel must be within (0, 2.0] rad/s")
                    kw["max_vel"] = value
                getattr(self.arm, operation)(**kw)
                output = Result(True, "accepted")
            elif operation == "set_gains":
                # SDK defaults take full effect on next supervisor start.
                if state_name(self.arm.state()) != "Idle":
                    raise ValueError("set_gains requires Idle; it applies on next enable")
                group = kw["group"]
                motors = [m for m in self.config.motors
                          if (m.joint_name == "gripper") == (group == "gripper")]
                count = 1 if group == "gripper" else 6
                if group not in ("arm", "gripper") or len(motors) != count:
                    raise ValueError("gain group must be arm or gripper")
                kp, kd = [finite(x) for x in kw["kp"]], [finite(x) for x in kw["kd"]]
                if len(kp) != count or len(kd) != count:
                    raise ValueError(f"{group} gains require {count} kp and kd values")
                for m, p, d in zip(motors, kp, kd):
                    if not (m.limits.kp_min <= p <= m.limits.kp_max and
                            m.limits.kd_min <= d <= m.limits.kd_max):
                        raise ValueError(f"gains outside canonical limits for motor {m.id}")
                if group == "arm":
                    self.arm.set_default_gains(kp, kd)
                else:
                    self.arm.set_gripper_gains(kp[0], kd[0])
                output = Result(True, "defaults updated; applies on next enable")
            else:
                raise ValueError(f"unsupported operation: {operation}")
            with self._meta:
                interrupted = epoch != self._epoch
            if interrupted or (operation in ("move_j", "move_p", "enable") and
                               state_name(self.arm.state()) != "Running"):
                return self.fail("interrupted: stop/fault occurred during execution")
            if not output.success:
                return self.fail(output.message)
            return output
        except Exception as exc:
            return self.fail(exc)
        finally:
            self._moving = False
            self._operation.release()

    def stop(self, operation="electronic_emergency_stop"):
        if operation not in ("electronic_emergency_stop", "disable", "shutdown"):
            return self.fail("invalid stop operation")
        # Do not wait for the long move service's operation lock.
        with self._meta:
            self._epoch += 1
            epoch = self._epoch
            self._blocked = True
        with self._lifecycle:
            if self._closed:
                if operation == "shutdown":
                    return Result(True, "already shut down")
                return self.fail("driver is shut down; no motor command sent; restart it before enable/disable")
            try:
                result = getattr(self.arm, operation)()
                if not result.ok:
                    return self.fail(result.message)
                with self._meta:
                    if operation == "shutdown":
                        self._closed = True
                    elif operation == "disable" and epoch == self._epoch:
                        self._blocked = False  # explicit enable allowed from Idle
                return Result(True, result.message)
            except Exception as exc:
                return self.fail(exc)

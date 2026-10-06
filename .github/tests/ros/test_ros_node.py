"""Humble middleware tests with a fake SDK facade: NEVER opens CAN."""
import threading
import time

import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from std_srvs.srv import Trigger
from sensor_msgs.msg import JointState
from milly_sdk_interfaces.srv import MoveJ, MoveP, GetRobotInfo
from milly_sdk_interfaces.msg import DriverStatus
from milly_sdk_ros.node import Driver
from test_backend import make_backend


def wait_for(predicate, timeout=5):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("ROS operation timed out")


@pytest.fixture
def runtime():
    rclpy.init()
    b, arm = make_backend()
    overrides = [Parameter("product_id", value="MILLY_TEST"),
                 Parameter("urdf_path", value="/unused-in-fake.urdf")]
    node = Driver(backend_factory=lambda *a, **k: b, namespace="/milly/MILLY_TEST",
                  parameter_overrides=overrides)
    client = rclpy.create_node("sdk_test_client")
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(client)
    thread = threading.Thread(target=executor.spin)
    thread.start()
    def call(service, kind, req=None):
        c = client.create_client(kind, "/milly/MILLY_TEST/" + service)
        assert c.wait_for_service(timeout_sec=5)
        return c.call_async(req or kind.Request())
    yield node, client, b, arm, call
    b.stop("shutdown")
    executor.shutdown()
    thread.join(5)
    node.destroy_node()
    client.destroy_node()
    rclpy.shutdown()


def test_explicit_enable_and_namespace(runtime):
    node, client, b, arm, call = runtime
    assert not arm.calls
    assert node.get_namespace() == "/milly/MILLY_TEST"
    future = call("get_robot_info", GetRobotInfo)
    wait_for(future.done)
    assert future.result().product_id == "MILLY_TEST"
    assert future.result().success
    future = call("enable", Trigger)
    wait_for(future.done)
    assert future.result().success
    assert arm.mode == "Running"


def test_move_stop_and_telemetry_are_independent(runtime):
    node, client, b, arm, call = runtime
    statuses = []
    subscription = client.create_subscription(
        DriverStatus, "/milly/MILLY_TEST/status", statuses.append, 1)
    enabled = call("enable", Trigger)
    wait_for(enabled.done)
    arm.block_move = True
    request = MoveJ.Request()
    request.positions = [0.] * 6
    move = call("move_j", MoveJ, request)
    assert arm.entered.wait(5)
    wait_for(lambda: any(s.moving for s in statuses))
    second = call("move_p", MoveP)
    wait_for(second.done)
    assert not second.result().success
    stop = call("emergency_stop", Trigger)
    wait_for(stop.done)
    wait_for(move.done)
    assert stop.result().success
    assert not move.result().success
    assert arm.mode == "Fault"
    assert subscription is not None


def test_no_fabricated_or_stale_joint_states(runtime):
    node, client, b, arm, call = runtime
    samples, statuses = [], []
    joints = client.create_subscription(JointState, "/milly/MILLY_TEST/joint_states",
                                        samples.append, qos_profile_sensor_data)
    state = client.create_subscription(DriverStatus, "/milly/MILLY_TEST/status",
                                       statuses.append, 1)
    wait_for(lambda: len(statuses) >= 3)
    assert not samples
    assert not statuses[-1].feedback_valid
    for row in arm.rows:
        row.feedback_age_s = 0.01
    wait_for(lambda: samples and statuses[-1].feedback_valid)
    assert "joint_1" in samples[-1].name
    arm.rows[0].feedback_age_s = 2.0
    wait_for(lambda: 1 in statuses[-1].stale_motor_ids)
    wait_for(lambda: "joint_1" not in samples[-1].name)
    assert joints is not None and state is not None


def test_control_display_gripper_uses_fresh_feedback_only(runtime):
    from milly_sdk_interfaces.msg import MotorStates

    node, client, b, arm, call = runtime
    display, measured, motors, statuses = [], [], [], []
    for topic, kind, samples in (
        ("display_joint_states", JointState, display),
        ("joint_states", JointState, measured),
        ("motor_states", MotorStates, motors),
        ("status", DriverStatus, statuses),
    ):
        client.create_subscription(kind, "/milly/MILLY_TEST/" + topic,
                                   samples.append, qos_profile_sensor_data)
    wait_for(lambda: len(statuses) >= 3)
    assert not display and not measured
    for row in arm.rows[:6]:
        row.feedback_age_s = 0.01
    wait_for(lambda: display and measured)
    assert list(display[-1].name) == [f"joint_{i}" for i in range(1, 7)]
    gripper = arm.rows[6]
    for raw, finger in ((0.0, 0.05), (1.055, 0.025), (2.11, 0.0)):
        gripper.position = raw
        gripper.feedback_age_s = 0.01
        wait_for(lambda: "finger_2_joint" in display[-1].name
                 and display[-1].position[-1] == pytest.approx(finger))
        assert list(display[-1].position[-2:]) == pytest.approx([finger, finger])
        assert list(display[-1].velocity) == list(display[-1].effort) == []
        assert list(measured[-1].name) == [f"joint_{i}" for i in range(1, 7)]
        wait_for(lambda: motors[-1].motors[6].position == pytest.approx(raw))
    gripper.feedback_age_s = 2.0
    wait_for(lambda: 7 in statuses[-1].stale_motor_ids)
    wait_for(lambda: "finger_2_joint" not in display[-1].name)
    assert list(display[-1].name) == [f"joint_{i}" for i in range(1, 7)]
    assert not arm.calls


def test_display_feedback_reaches_finger_tf(runtime, tmp_path):
    import subprocess
    from pathlib import Path
    import yaml
    import motomind_milly as mm
    from ament_index_python.packages import get_package_prefix
    from tf2_msgs.msg import TFMessage

    node, client, b, arm, call = runtime
    transforms = {}
    def record(message):
        transforms.update({tf.child_frame_id: tf for tf in message.transforms})
    client.create_subscription(TFMessage, "/milly/MILLY_TEST/tf", record,
                               qos_profile_sensor_data)
    params = tmp_path / "rsp.yaml"
    params.write_text(yaml.safe_dump({"/**": {"ros__parameters": {
        "robot_description": Path(mm.milly_urdf()).read_text(),
        "frame_prefix": "MILLY_TEST/",
    }}}))
    binary = Path(get_package_prefix("robot_state_publisher")) / "lib/robot_state_publisher/robot_state_publisher"
    with (tmp_path / "rsp.log").open("w") as log:
        process = subprocess.Popen([
            str(binary), "--ros-args", "--params-file", str(params),
            "-r", "__ns:=/milly/MILLY_TEST", "-r", "joint_states:=display_joint_states",
            "-r", "/tf:=tf", "-r", "/tf_static:=tf_static",
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            for row in arm.rows:
                row.feedback_age_s = 0.01
            # Compare the two endpoint TFs, not only the outgoing JointState.
            finger_links = ("MILLY_TEST/finger_1", "MILLY_TEST/finger_2")
            wait_for(lambda: all(link in transforms for link in finger_links))
            closed = {link: transforms[link] for link in finger_links}
            arm.rows[6].position = 2.11
            def moved():
                for link in finger_links:
                    a, z = closed[link].transform.translation, transforms[link].transform.translation
                    distance = ((a.x-z.x)**2 + (a.y-z.y)**2 + (a.z-z.z)**2)**0.5
                    if abs(distance - 0.05) > 1e-5:
                        return False
                return True
            wait_for(moved)
            assert not arm.calls
        finally:
            process.terminate()
            process.wait(timeout=5)


def test_optional_scalar_error_is_service_failure(runtime):
    node, client, b, arm, call = runtime
    req = MoveJ.Request()
    req.positions = [0.] * 6
    req.max_vel = [0.2, 0.3]
    future = call("move_j", MoveJ, req)
    wait_for(future.done)
    assert not future.result().success
    assert "optional" in future.result().message
    assert not arm.calls


def test_passive_description_queries_only(monkeypatch):
    import json
    from types import SimpleNamespace as NS
    import motomind_milly as mm
    from std_msgs.msg import String
    from milly_sdk_ros.description_monitor import DescriptionMonitor

    calls = []
    feedback = {1: NS(position=0.25), 2: NS(position=-0.4)}
    def refresh(**kwargs):
        calls.append("position_query")
        return dict(feedback)
    fake = NS(manager=NS(refresh_feedback=refresh), disconnect=lambda: calls.append("disconnect"))
    monkeypatch.setattr(mm, "create_arm", lambda *a, **k: fake)
    rclpy.init()
    node = client = executor = thread = None
    try:
        node = DescriptionMonitor(namespace="/milly/MILLY_TEST/description_check",
                                  parameter_overrides=[Parameter("product_id", value="MILLY_TEST")])
        client = rclpy.create_node("passive_check_client")
        samples, status = [], []
        client.create_subscription(JointState, node.get_namespace() + "/joint_states", samples.append, 10)
        client.create_subscription(String, node.get_namespace() + "/description_status",
                                   lambda msg: status.append(json.loads(msg.data)), 10)
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        executor.add_node(client)
        thread = threading.Thread(target=executor.spin)
        thread.start()
        wait_for(lambda: samples and status)
        assert list(samples[-1].name) == ["joint_1", "joint_2"]
        assert status[-1]["finger_position_m"] is None
        assert not status[-1]["finger_feedback_valid"]
        feedback[7] = NS(position=1.5)
        wait_for(lambda: status[-1]["finger_feedback_valid"])
        wait_for(lambda: "finger_2_joint" in samples[-1].name)
        assert list(samples[-1].name) == ["joint_1", "joint_2", "finger_1_joint", "finger_2_joint"]
        expected_finger = 0.05 * (1.0 - 1.5 / 2.11)
        assert list(samples[-1].position) == pytest.approx([0.25, -0.4, expected_finger, expected_finger])
        assert list(samples[-1].velocity) == []
        assert list(samples[-1].effort) == []
        assert status[-1]["motors"]["7"]["position"] == 1.5
        assert status[-1]["finger_display"] == "linear_estimate_from_motor_7"
        assert status[-1]["finger_feedback_valid"]
        assert status[-1]["finger_position_m"] == pytest.approx(expected_finger)
        assert not status[-1]["feedback_valid"]
        services = [name.rsplit("/", 1)[-1] for name, _ in node.get_service_names_and_types()]
        assert not {"enable", "disable", "move_j", "move_p", "shutdown", "emergency_stop"} & set(services)
        feedback.clear()
        wait_for(lambda: 1 in status[-1]["stale_motor_ids"])
        wait_for(lambda: not status[-1]["finger_feedback_valid"])
        assert status[-1]["finger_position_m"] is None
        feedback[1] = NS(position=0.3)
        wait_for(lambda: list(samples[-1].name) == ["joint_1"])
        feedback[7] = NS(position=2.11)
        wait_for(lambda: status[-1]["finger_feedback_valid"])
        wait_for(lambda: list(samples[-1].name) == ["joint_1", "finger_1_joint", "finger_2_joint"]
                 and samples[-1].position[-1] == 0.0)
    finally:
        if executor:
            executor.shutdown()
        if thread:
            thread.join(5)
        if node:
            node.monitor.close()
            node.destroy_node()
        if client:
            client.destroy_node()
        rclpy.shutdown()
    assert calls[-1] == "disconnect"
    assert all(c in ("position_query", "disconnect") for c in calls)


def test_motor_gui_shares_arm_and_closes_before_disconnect(monkeypatch):
    from types import SimpleNamespace as NS
    import motomind_milly as mm
    import motomind_milly.monitor as gui_module
    from milly_sdk_ros.description_monitor import DescriptionMonitor
    events, windows = [], []
    manager = NS(refresh_feedback=lambda **kw: {})
    arm = NS(manager=manager, disconnect=lambda: events.append("disconnect"))
    def create(*a, **kw):
        events.append("create_arm")
        return arm
    class Window:
        def __init__(self, supplied_manager, cfg, **kw):
            assert supplied_manager is manager
            assert kw["owns_arm"] is False
            assert callable(kw["position_snapshot"])
            windows.append(self)
        def start(self, **kw): events.append("gui_start")
        def close(self, **kw): events.append("gui_close")
    monkeypatch.setattr(mm, "create_arm", create)
    monkeypatch.setattr(gui_module, "MotorMonitor", Window)
    rclpy.init()
    node = None
    try:
        node = DescriptionMonitor(parameter_overrides=[Parameter("product_id", value="MILLY_TEST"),
                                                       Parameter("motor_gui", value=True)])
        assert len(windows) == 1
        assert events == ["create_arm", "gui_start"]
    finally:
        if node: node.destroy_node()
        rclpy.shutdown()
    assert events == ["create_arm", "gui_start", "gui_close", "disconnect"]


def test_float_request_has_no_tuning_fields(runtime):
    from milly_sdk_interfaces.srv import FloatMode
    assert FloatMode.Request.get_fields_and_field_types() == {}
    with pytest.raises(AttributeError):
        FloatMode.Request().scale = [0.5]
    node, client, b, arm, call = runtime
    enabled = call('enable', Trigger)
    wait_for(enabled.done)
    future = call('float_mode', FloatMode)
    wait_for(future.done)
    assert future.result().success
    assert arm.calls[-1] == ('float', {})


def test_motor_gui_shares_feedback_without_control(monkeypatch):
    from types import SimpleNamespace as NS
    import motomind_milly._position_gui_process as gui
    b, arm = make_backend()
    events, windows = [], []
    arm.manager.states = lambda: arm.rows
    class Window:
        def __init__(self, manager, config, **kw):
            assert manager is arm.manager and config is b.config
            self.snapshot = kw['feedback_snapshot']
            windows.append(self)
        def start(self, **kw): events.append('gui_start')
        def close(self, **kw): events.append('gui_close')
    monkeypatch.setattr(gui, 'PositionProcessMonitor', Window)
    rclpy.init()
    node = None
    try:
        node = Driver(backend_factory=lambda *a, **kw: b,
                      parameter_overrides=[Parameter('product_id', value='MILLY_TEST'),
                          Parameter('urdf_path', value='/unused'), Parameter('motor_gui', value=True)])
        assert not arm.calls
        assert windows[0].snapshot() == {}
        arm.rows[0].feedback_age_s = .01
        assert windows[0].snapshot()[1]['fresh']
        windows[0].close()
        assert not arm.calls  # closing the window never disables/shuts down the arm
    finally:
        if node: node.destroy_node()
        rclpy.shutdown()
    assert events == ['gui_start', 'gui_close', 'gui_close']


def test_motor_gui_startup_failure_disconnects_before_enable(monkeypatch):
    import motomind_milly._position_gui_process as gui
    b, arm = make_backend()
    events = []
    arm.disconnect = lambda: events.append('disconnect')
    class Window:
        def __init__(self, *a, **kw): pass
        def start(self, **kw): raise RuntimeError('no display')
        def close(self, **kw): events.append('gui_close')
    monkeypatch.setattr(gui, 'PositionProcessMonitor', Window)
    rclpy.init()
    try:
        with pytest.raises(RuntimeError, match='no display'):
            Driver(backend_factory=lambda *a, **kw: b,
                   parameter_overrides=[Parameter('product_id', value='MILLY_TEST'),
                       Parameter('urdf_path', value='/unused'), Parameter('motor_gui', value=True)])
        assert not arm.calls
        assert events == ['gui_close', 'disconnect']
    finally:
        rclpy.shutdown()


def test_parameter_services_survive_driver_setup(runtime):
    from rcl_interfaces.srv import GetParameters, ListParameters, DescribeParameters, SetParameters
    node, client, b, arm, call = runtime
    get = call('milly_driver/get_parameters', GetParameters,
               GetParameters.Request(names=['publish_rate_hz']))
    wait_for(get.done)
    assert get.result().values[0].double_value == 30.0
    listing = call('milly_driver/list_parameters', ListParameters)
    wait_for(listing.done)
    assert 'publish_rate_hz' in listing.result().result.names
    describe = call('milly_driver/describe_parameters', DescribeParameters,
                    DescribeParameters.Request(names=['publish_rate_hz']))
    wait_for(describe.done)
    assert describe.result().descriptors[0].read_only
    change = call('milly_driver/set_parameters', SetParameters, SetParameters.Request(
        parameters=[Parameter('publish_rate_hz', value=20.).to_parameter_msg()]))
    wait_for(change.done)
    assert not change.result().results[0].successful
    names = [service.srv_name for service in node.services]
    assert len(names) == len(set(names))  # create_service already registers each service
    assert not arm.calls  # parameter queries must not enable or command the robot


def test_ros_param_cli_reads_driver_parameter(runtime):
    import subprocess
    import sys
    node, client, b, arm, call = runtime
    result = subprocess.run(
        [sys.executable, '/opt/ros/humble/bin/ros2', 'param', 'get',
         '/milly/MILLY_TEST/milly_driver', 'publish_rate_hz'],
        capture_output=True, text=True, timeout=15.)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '30.0' in result.stdout
    assert not arm.calls

"""Optional teaching SDK + Humble integration. Fake DXL only; never opens USB/CAN."""
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import time

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, DurabilityPolicy
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from visualization_msgs.msg import Marker
from tf2_msgs.msg import TFMessage
from ament_index_python.packages import get_package_prefix
from launch import LaunchContext
import yaml
import motomind_milly as mm
from motomind_teaching._profiles import load_profile

from milly_sdk_ros.teaching_preview import TeachingPreview, make_device, PREFIX

SDK = next(p for p in Path(__file__).resolve().parents if (p / "ros/src").is_dir())
PROFILE = SDK / "examples/python/configs/teleoperation_tool_setting_example.json"
if not PROFILE.is_file():
    ROOT = next(p for p in SDK.parents if (p / "configs/teaching_devices/teleoperation_tool_setting_example.json").is_file())
    PROFILE = ROOT / "configs/teaching_devices/teleoperation_tool_setting_example.json"


def overrides(**kwargs):
    return [Parameter(k, value=v) for k, v in {"profile": str(PROFILE), "fake": True, **kwargs}.items()]


@pytest.fixture
def runtime():
    rclpy.init()
    created = []
    def factory(*args, **kwargs):
        device = make_device(*args, **kwargs)
        created.append(device)
        return device
    node = TeachingPreview(device_factory=factory, parameter_overrides=overrides())
    client = rclpy.create_node("preview_test_client")
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(client)
    messages = {name: [] for name in ("joint_states", "mapped_positions", "status", "status_marker", "tf")}
    retained = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    for topic, kind in (("joint_states", JointState), ("mapped_positions", JointState),
                        ("status", String), ("status_marker", Marker), ("tf", TFMessage)):
        client.create_subscription(kind, "/milly/teaching_preview/" + topic,
                                   messages[topic].append, retained if topic.startswith("status") else 10)
    def until(predicate, timeout=5):
        end = time.monotonic() + timeout
        while not predicate():
            assert time.monotonic() < end, "preview ROS operation timed out"
            executor.spin_once(timeout_sec=0.02)
    yield node, client, created, messages, until
    executor.shutdown()
    node.destroy_node()
    client.destroy_node()
    rclpy.shutdown()
    assert all(d._io.writes == [] for d in created)
    assert all(not d._io.opened for d in created)


def test_mapped_pose_and_disconnect_latches_without_writes(runtime):
    node, _, devices, messages, until = runtime
    until(lambda: messages["joint_states"] and messages["mapped_positions"])
    assert list(messages["mapped_positions"][-1].position) == [0.] * 7
    assert list(messages["joint_states"][-1].position) == [0.] * 6 + [0.05, 0.05]
    io = devices[0]._io
    io.positions_raw = [2178, 1918, 1918, 2178, 2178, 2178, 2211]
    until(lambda: 0.1 < messages["mapped_positions"][-1].position[0] < 0.3)
    mapped = messages["mapped_positions"][-1]
    expected = devices[0].mapping.apply(tuple(t * 2 * math.pi / 4096 for t in io.positions_raw))
    assert mapped.position == pytest.approx(expected)
    assert list(mapped.velocity) == list(mapped.effort) == []
    assert not io.writes
    io.fail_after = io.read_count
    until(lambda: messages["status_marker"] and "FAULT" in messages["status_marker"][-1].text)
    assert not io.opened
    assert messages["status_marker"][-1].color.r == 1.0
    # Drain in-flight middleware messages; then prove no replay and no reconnect.
    until(lambda: messages["status"] and "FAULT" in messages["status"][-1].data)
    node.poll()
    read_count = io.read_count
    deadline = time.monotonic() + 0.1
    until(lambda: time.monotonic() >= deadline)
    counts = [len(messages[topic]) for topic in ("joint_states", "mapped_positions")]
    deadline = time.monotonic() + 0.2
    until(lambda: time.monotonic() >= deadline)
    assert [len(messages[topic]) for topic in ("joint_states", "mapped_positions")] == counts
    for _ in range(10):
        node.poll()
    assert io.read_count == read_count
    assert len(devices) == 1
    assert "injected cable disconnect" in node.fault


def test_initial_failure_publishes_fault_without_zero_pose(runtime):
    node, _, _, messages, until = runtime
    def fail():
        raise OSError("initial connection missing")
    node._factory = fail
    until(lambda: messages["status"] and "FAULT" in messages["status"][-1].data)
    assert not messages["joint_states"] and not messages["mapped_positions"]
    assert "initial connection missing" in node.fault


def test_teaching_pose_reaches_real_robot_state_publisher(runtime, tmp_path):
    _, _, devices, messages, until = runtime
    params = tmp_path / "rsp.yaml"
    params.write_text(yaml.safe_dump({"/**": {"ros__parameters": {
        "robot_description": Path(mm.milly_urdf()).read_text(),
        "frame_prefix": PREFIX + "/",
    }}}))
    binary = Path(get_package_prefix("robot_state_publisher")) / "lib/robot_state_publisher/robot_state_publisher"
    with (tmp_path / "rsp.log").open("w") as log:
        proc = subprocess.Popen([str(binary), "--ros-args", "--params-file", str(params),
                                 "-r", "__ns:=/milly/teaching_preview",
                                 "-r", "/tf:=tf", "-r", "/tf_static:=tf_static"],
                                stdout=log, stderr=subprocess.STDOUT)
        try:
            def frames():
                return {tf.child_frame_id: tf for msg in messages["tf"] for tf in msg.transforms}
            until(lambda: PREFIX + "/finger_2" in frames())
            start = frames()
            devices[0]._io.positions_raw = [2178, 1918, 1918, 2178, 2178, 2178, 2211]
            until(lambda: frames()[PREFIX + "/link_1"].transform.rotation !=
                  start[PREFIX + "/link_1"].transform.rotation)
            until(lambda: frames()[PREFIX + "/finger_2"].transform.translation !=
                  start[PREFIX + "/finger_2"].transform.translation)
            assert proc.poll() is None
        finally:
            proc.terminate()
            proc.wait(timeout=5)


@pytest.mark.parametrize("params", [
    {"port": "/dev/never-open"}, {"rate_hz": 0.0},
    {"rate_hz": float("nan")}, {"read_timeout_s": -1.0}, {"profile": ""},
])
def test_invalid_configuration_never_creates_device(params):
    rclpy.init()
    def forbidden(*args, **kwargs):
        pytest.fail("device creation before configuration validation")
    try:
        with pytest.raises(ValueError):
            TeachingPreview(device_factory=forbidden, parameter_overrides=overrides(**params))
    finally:
        rclpy.shutdown()


def test_reordered_profile_rejected_before_device_creation(tmp_path):
    data = load_profile(PROFILE)
    data["joint_names"].reverse()
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    rclpy.init()
    try:
        with pytest.raises(ValueError, match="joint_names"):
            TeachingPreview(parameter_overrides=overrides(profile=str(path)))
    finally:
        rclpy.shutdown()


def test_three_key_user_settings_publish_clamped_positions_without_writes(tmp_path):
    data = json.loads(PROFILE.read_text())
    path = tmp_path / 'user.json'
    path.write_text(json.dumps({key: data[key] for key in ('torque_enable', 'current_limit', 'p_gain')}))
    rclpy.init()
    node = TeachingPreview(parameter_overrides=overrides(profile=str(path)))
    try:
        node.poll()
        assert node.fault == ''
        assert node.device.read_positions() == (0.,) * 7
        assert not hasattr(node.device, 'read_raw_positions')
        node.device._io.positions_raw[6] = 4096
        node.poll()
        assert node.fault == ''
        assert node.device.read_positions()[6] == 2.11
        assert node.device._io.writes == []
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_default_real_port_is_ttyacm0_without_opening_it():
    seen = []
    rclpy.init()
    def factory(port, profile, **kwargs):
        seen.append(port)
        # Real selection is checked, but all communication stays fake in this test.
        return make_device('', profile, fake=True, read_timeout_s=kwargs['read_timeout_s'])
    node = TeachingPreview(device_factory=factory, parameter_overrides=overrides(fake=False))
    try:
        node.poll()
        assert seen == ['/dev/ttyACM0']
        assert not node.fault
        assert node.device._io.writes == []
    finally:
        node.destroy_node()
        rclpy.shutdown()


@pytest.mark.parametrize('port', ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1'])
def test_explicit_usb_and_acm_ports_reach_device_factory_without_hardware(port):
    seen = []
    rclpy.init()
    def factory(selected, profile, **kwargs):
        seen.append(selected)
        return make_device('', profile, fake=True, read_timeout_s=kwargs['read_timeout_s'])
    node = TeachingPreview(device_factory=factory, parameter_overrides=overrides(fake=False, port=port))
    try:
        node.poll()
        assert seen == [port] and not node.fault
        assert node.device._io.writes == []
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_launch_has_only_preview_and_visualization(monkeypatch, tmp_path):
    from types import SimpleNamespace as NS
    launch_path = SDK / "ros/src/milly_sdk_description/launch/teaching_preview.launch.py"
    spec = importlib.util.spec_from_file_location("preview_launch", launch_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    share = tmp_path / "share"
    (share / "milly_description/urdf").mkdir(parents=True)
    (share / "milly_description/urdf/MILLY.urdf").write_text(
        Path(mm.milly_urdf()).read_text())
    (share / "rviz").mkdir()
    (share / "rviz/milly.rviz").write_text((SDK / "ros/src/milly_sdk_description/rviz/milly.rviz").read_text())
    monkeypatch.setattr(module, "get_package_share_directory", lambda _: str(share))
    nodes = []
    def node(**kwargs):
        nodes.append(kwargs)
        return NS(**kwargs)
    monkeypatch.setattr(module, "Node", node)
    actions = module.setup(LaunchContext())
    assert [n["executable"] for n in nodes] == ["teaching_preview", "robot_state_publisher", "rviz2"]
    assert all(n["namespace"] == "milly/teaching_preview" for n in nodes)
    config = yaml.safe_load(Path(nodes[-1]["arguments"][-1]).read_text())
    assert config["Visualization Manager"]["Global Options"]["Fixed Frame"] == PREFIX + "/base_link"
    assert config["Visualization Manager"]["Displays"][-1]["Marker Topic"]["Value"] == "status_marker"
    assert actions

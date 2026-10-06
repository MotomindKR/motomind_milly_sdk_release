"""Inspect real launch plans without executing a driver or opening CAN."""
import importlib.util
from pathlib import Path
import shutil
from types import SimpleNamespace as NS

from launch import LaunchContext
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.utilities import perform_substitutions
import motomind_milly as mm

SDK = next(parent for parent in Path(__file__).resolve().parents if (parent/'ros/src').is_dir())


def load(package, name):
    path = SDK / 'ros/src' / package / 'launch' / (name + '.launch.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bringup_owns_one_driver_and_display_is_optional(monkeypatch):
    launch = load('milly_sdk_bringup', 'bringup')
    monkeypatch.setattr(launch, 'get_package_share_directory', lambda _: '/model/share')
    nodes = []
    def node(**kw):
        nodes.append(kw)
        return NS(**kw)
    monkeypatch.setattr(launch, 'Node', node)
    context = LaunchContext()
    context.launch_configurations.update(product_id='MILLY_TEST', gui='false')
    actions = launch.setup(context)
    assert [(n['package'], n['executable']) for n in nodes] == [('milly_sdk_ros', 'driver')]
    assert nodes[0]['namespace'] == 'milly/MILLY_TEST'
    display, = [a for a in actions if isinstance(a, IncludeLaunchDescription)]
    assert not display.condition.evaluate(context)
    context.launch_configurations['gui'] = 'true'
    assert display.condition.evaluate(context)
    defaults = {a.name: perform_substitutions(context, a.default_value)
                for a in launch.generate_launch_description().entities
                if isinstance(a, DeclareLaunchArgument) and a.default_value is not None}
    assert defaults['gui'] == 'false'
    assert defaults['motor_gui'] == 'true'
    assert defaults['supervisor_rate_hz'] == '100.0'


def test_display_launch_subscribes_without_driver_or_monitor(monkeypatch, tmp_path):
    launch = load('milly_sdk_description', 'display')
    share = tmp_path/'share'
    (share/'milly_description/urdf').mkdir(parents=True)
    shutil.copy2(mm.milly_urdf(), share/'milly_description/urdf/MILLY.urdf')
    monkeypatch.setattr(launch, 'get_package_share_directory', lambda _: str(share))
    monkeypatch.setattr(launch, 'make_rviz_config', lambda *a: (NS(cleanup=lambda: None), '/tmp/test.rviz'))
    nodes = []
    def node(**kw):
        nodes.append(kw)
        return NS(**kw)
    monkeypatch.setattr(launch, 'Node', node)
    context = LaunchContext()
    context.launch_configurations.update(product_id='MILLY_TEST', gui='true')
    launch.setup(context)
    assert [n['executable'] for n in nodes] == ['robot_state_publisher', 'rviz2']
    assert ('joint_states', 'display_joint_states') in nodes[0]['remappings']
    assert all(n['namespace'] == 'milly/MILLY_TEST' for n in nodes)
    assert nodes[0]['parameters'][0]['frame_prefix'] == 'MILLY_TEST/'

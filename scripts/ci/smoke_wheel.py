#!/usr/bin/env python3
"""Run inside a clean wheel-installed environment. Fake CAN only."""
from importlib.metadata import version
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import time
import subprocess
import sys

import motomind_milly as mm
from motomind_milly import _core, profile
from motomind_robot_model import RobotModel, __version__ as robot_model_version

root = Path(__file__).resolve().parents[2]
manifest = json.loads((root/'.github/release_manifest.json').read_text())
assert mm.__version__ == version('motomind-milly-sdk') == manifest['sdk_version']
assert robot_model_version == version('motomind-robot-model') == manifest['robot_model_version']
assert mm.MotorState().feedback_age_s == -1.0
for module in ('identity', 'monitor'):
    subprocess.run([sys.executable, '-m', 'motomind_milly.'+module, '--help'],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
for module in ('_isolated_model', '_position_gui_process'):
    subprocess.run([sys.executable, '-m', 'motomind_milly.'+module], input='', text=True,
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
assert not any(hasattr(mm.Arm, name) for name in (
    'set_gravity_gains', 'set_float_kd', 'set_float_kp'))
try:
    mm.Arm.float_mode(None, scale=0.5)
except TypeError:
    pass
else:
    raise AssertionError('public FLOAT must reject scale overrides')
cfg, tuning = profile.load_robot_profile('MILLY_CI')
assert {motor.id: motor.safety.damping_kd for motor in cfg.motors} == {
    1: 10.0, 2: 10.0, 3: 10.0, 4: 5.0, 5: 5.0, 6: 5.0, 7: 5.0}
expected_positions = {1: (-2.8, 2.8), 2: (-3.2, 0.), 3: (-2.75, 0.),
                      4: (-2.42, 2.42), 5: (-1.84, 1.7), 6: (-1.55, 1.55), 7: (0., 2.11)}
assert cfg.buses[0].command_rate_hz == 100.0
for motor in cfg.motors:
    lo, hi = expected_positions[motor.id]
    assert (motor.limits.position_min, motor.limits.position_max) == (lo, hi)
    assert abs(motor.safety.safe_position_min - (lo - .05)) < 1e-9
    assert abs(motor.safety.safe_position_max - (hi + .05)) < 1e-9
rig = _core.build_fake_rig(cfg.motors)
arm = mm.Arm(rig.manager, cfg)
arm._supervisor_auto = True
arm._supervisor_rate_hz = 100
arm.set_robot_model(RobotModel(mm.milly_urdf()))
urdf = ET.parse(mm.milly_urdf())
for motor in cfg.motors[:6]:
    limit = urdf.find(f"joint[@name='{motor.joint_name}']/limit")
    assert (float(limit.get('lower')), float(limit.get('upper'))) == expected_positions[motor.id]
arm.set_default_gains(tuning.kp, tuning.kd)
arm.set_gripper_gains(tuning.gripper_kp, tuning.gripper_kd)
scale, gains, kd, kp = profile.canonical_gravity_tuning(cfg)
assert gains == {1: 0., 2: 1., 3: .9, 4: 1., 5: 1., 6: 1.}
assert kd == {1: 0., 2: .3, 3: .3, 4: .15, 5: .15, 6: .15, 7: 0.}
arm._set_gravity_gains(gains)
arm._set_float_kd(kd)
arm._set_float_kp(kp)
assert rig.manager.open()
for motor in cfg.motors:
    rig.push_feedback_on_send(motor.id)
try:
    assert arm.enable().ok
    # Synthetic feedback: exercise the real command watchdog independently.
    cfg.safety.plugins = [p for p in cfg.safety.plugins if p.id == 'command_update_timeout']
    assert len(cfg.safety.plugins) == 1
    _core.apply_safety_config(rig.manager, cfg.safety)
    arm.move_j([0.0] * 6, max_vel=0.2)
    arm.move_p(arm.fk([0.0] * 6), max_vel=0.2)
    assert arm.move_mit(1, kp=0.0, kd=0.3)
    time.sleep(.2)
    assert arm._rm.geom_model is None, 'motion APIs must not load collision meshes'
    assert arm.state() == mm.MotorManagerState.Running
    assert arm._supervisor.running()
    assert not rig.manager.fault_reason()
    arm.float_mode()
    time.sleep(.1)
    commands = {c.id: c for c in rig.manager.commands()}
    assert set(commands) == set(range(1, 8))
    assert all(commands[i].kp == 0 for i in range(1, 7))
    assert commands[1].kp == commands[1].kd == commands[1].torque_feedforward == 0.
    assert commands[7].kp == commands[7].kd == commands[7].torque_feedforward == 0.
    for mid in range(1, 8):
        assert abs(commands[mid].kd - kd[mid]) < 1e-6
    arm.hold_mode()
finally:
    assert arm.shutdown().ok
    arm.disconnect()
print(f'Installed SDK {mm.__version__}: imports, factory fit, motion without collision geometry, watchdog and FakeCanBus lifecycle OK')

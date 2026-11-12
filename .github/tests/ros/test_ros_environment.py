"""Source the public Bash entry point in disposable bundles; no ROS or hardware."""
from pathlib import Path
import os
import subprocess

import pytest


SDK = next(p for p in Path(__file__).resolve().parents
           if (p/'scripts/ros_env.sh').is_file())


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path/'release with spaces'
    scripts = root/'scripts'
    scripts.mkdir(parents=True)
    underlay = tmp_path/'humble'
    underlay.mkdir()
    # Humble's setup scripts read optional variables without nounset guards.
    (underlay/'setup.bash').write_text(': "$AMENT_TRACE_SETUP_FILES"\nexport MILLY_TEST_ROS=loaded\n')
    script = scripts/'ros_env.sh'
    script.write_text((SDK/'scripts/ros_env.sh').read_text().replace(
        '/opt/ros/humble', str(underlay)))
    venv = root/'.venv_ros/bin'
    venv.mkdir(parents=True)
    (venv/'activate').write_text('export VIRTUAL_ENV="' + str(venv.parent) + '"\n')
    python = venv/'python'
    python.write_text('#!/bin/sh\nexit 0\n')
    python.chmod(0o755)
    install = root/'install'
    install.mkdir()
    (install/'local_setup.bash').write_text(': "$COLCON_TRACE"\nexport MILLY_TEST_OVERLAY=loaded\n')
    return root, script, underlay


def shell(script, commands):
    env = dict(os.environ)
    for name in ('ROS_DISTRO', 'AMENT_TRACE_SETUP_FILES', 'COLCON_TRACE'):
        env.pop(name, None)
    return subprocess.run(['bash', '--noprofile', '--norc', '-c', commands, '_', str(script)],
                          env=env, text=True, capture_output=True, timeout=10)


@pytest.mark.parametrize('strict', [False, True])
def test_source_accepts_optional_unset_ros_variables_and_preserves_shell_options(bundle, strict):
    root, script, _ = bundle
    commands = ('set -euo pipefail\n' if strict else 'set -e\n') + '''
source "$1"
source "$1"
[[ "$MILLY_TEST_ROS" == loaded && "$MILLY_TEST_OVERLAY" == loaded ]]
[[ "$MOTOMIND_CONFIG_DIR" == "${VIRTUAL_ENV%/.venv_ros}/profiles" ]]
'''
    commands += '[[ $- == *u* ]]' if strict else '[[ $- != *u* ]]'
    result = shell(script, commands)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count('environment ready') == 2


@pytest.mark.parametrize('stage', ['activation', 'underlay', 'overlay'])
@pytest.mark.parametrize('strict', [False, True])
def test_source_failure_propagates_and_restores_nounset(bundle, stage, strict):
    root, script, underlay = bundle
    path = {'activation': root/'.venv_ros/bin/activate',
            'underlay': underlay/'setup.bash',
            'overlay': root/'install/local_setup.bash'}[stage]
    path.write_text('return 23\n')
    commands = ('set -eu\n' if strict else 'set -e\n') + '''
if source "$1"; then exit 90; else result=$?; fi
[[ $result -eq 23 ]]
'''
    commands += '[[ $- == *u* ]]' if strict else '[[ $- != *u* ]]'
    result = shell(script, commands)
    assert result.returncode == 0, result.stderr
    assert 'environment ready' not in result.stdout


def test_other_ros_distribution_rejected_before_activation(bundle):
    _, script, _ = bundle
    result = shell(script, 'export ROS_DISTRO=jazzy; source "$1"')
    assert result.returncode == 1
    assert 'fresh terminal' in result.stderr
    assert 'environment ready' not in result.stdout


@pytest.mark.parametrize('missing, message', [
    ('underlay', 'ROS2 Humble is missing'),
    ('activation', 'Run bash scripts/setup_ros_humble.sh first'),
    ('overlay', 'Milly ROS build is missing'),
])
def test_incomplete_install_has_an_actionable_error(bundle, missing, message):
    root, script, underlay = bundle
    path = {'underlay': underlay/'setup.bash',
            'activation': root/'.venv_ros/bin/activate',
            'overlay': root/'install/local_setup.bash'}[missing]
    path.unlink()
    result = shell(script, 'set -eu; source "$1"')
    assert result.returncode == 1
    assert message in result.stderr
    assert 'environment ready' not in result.stdout


def test_script_must_be_sourced(bundle):
    _, script, _ = bundle
    result = subprocess.run(['bash', str(script)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'Use: source scripts/ros_env.sh' in result.stderr


def test_non_bash_shell_has_an_actionable_error(bundle):
    _, script, _ = bundle
    env = {name: value for name, value in os.environ.items() if name != 'BASH_VERSION'}
    result = subprocess.run(['sh', '-c', '. "$1"', '_', str(script)],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert 'Open Bash first' in result.stderr

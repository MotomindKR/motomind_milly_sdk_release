#!/usr/bin/env python3
"""Validate a generated release bundle without importing SDK code or opening CAN."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from email.parser import BytesParser

import yaml

LOCAL_ONLY_NAMES = {'.milly-sdk-examples-generated', '.milly-sdk-ros-generated', 'RELEASE_REVIEW.md'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_compiled_wheel(names, prefix):
    launchers = {'identity', 'monitor', '_isolated_model', '_position_gui_process'}
    allowed = {'__init__.py'} if prefix == 'motomind_milly/' else set()
    if prefix == 'motomind_milly/':
        allowed.update(name+'.py' for name in launchers)
    sources = {n[len(prefix):] for n in names if n.startswith(prefix) and n.endswith('.py')}
    assert sources == allowed, f'implementation source leaked or facade missing: {sources}'
    assert not any(n.endswith(('.c', '.cpp', '.h', '.hpp', '.a', '.pyc', '.pyx')) for n in names), 'build source/artifact leaked'
    modules = ('_core', '_sdk', 'gravity_comp', 'mode_supervisor', 'motion', 'profile',
               '_worker_rpc', *('_compiled_'+n for n in launchers)) if prefix == 'motomind_milly/' else ('__init__', 'calibration')
    for name in modules:
        assert any(n.startswith(prefix+name+'.') and n.endswith('.so') for n in names), f'missing compiled module: {name}'


def inspect(root, version):
    assert not (root/'ros/tests').exists(), 'development/CI tests must live under .github/tests/ros'
    assert not (root/'examples/ros').exists(), 'ROS examples are development-only'
    assert not (root/'ros/README.md').exists(), 'ROS documentation belongs in SDK_ROS2_guide.md'
    for name in ('test_examples.py', 'test_example_launch.py'):
        assert not (root/'.github/tests/ros'/name).exists(), 'development example tests must not be exported'
    tools = root/'tests/tools'
    assert not tools.exists() and not tools.is_symlink(), 'development-only tests/tools in release'
    artifacts, versions, models = {}, set(), set()
    profile_hashes = set()
    urdf = (root / 'milly_description/urdf/MILLY.urdf').read_bytes()
    model = json.loads((root / 'milly_description/model_manifest.json').read_text())
    assert model['sdk_urdf_sha256'] == sha(urdf), 'description URDF hash mismatch'
    for name, digest in model['mesh_sha256'].items():
        path = root / 'milly_description/meshes' / name
        assert sha(path.read_bytes()) == digest, f'mesh mismatch: {name}'
    for mesh in ET.fromstring(urdf).iter('mesh'):
        uri = mesh.attrib['filename']
        assert uri.startswith('package://milly_description/'), uri
        assert (root / 'milly_description' / uri.removeprefix('package://milly_description/')).is_file(), uri
    calibration_hashes = set()
    profiles = {'MILLY_DEFAULT.yaml', 'MILLY_SAMPLE.yaml', 'milly_canonical.yaml', 'milly_cal.yaml'}
    for py in ('3.10', '3.11', '3.12'):
        folder = root / 'dist/linux_x86_64' / ('python' + py)
        sdks = list(folder.glob(f'motomind_milly_sdk-{version}-*.whl'))
        abi = 'cp' + py.replace('.', '')
        rms = list(folder.glob(f'motomind_robot_model-*-{abi}-{abi}-linux_x86_64.whl'))
        assert len(sdks) == len(rms) == 1, f'expected one wheel of each package: {folder}'
        for wheel in (sdks[0], rms[0]):
            artifacts[wheel.relative_to(root).as_posix()] = sha(wheel.read_bytes())
            with ZipFile(wheel) as z:
                metadata = [n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
                assert len(metadata) == 1
                info = BytesParser().parsebytes(z.read(metadata[0]))
                abi = 'cp' + py.replace('.', '')
                assert f'-{abi}-{abi}-linux_x86_64.whl' in wheel.name, wheel.name
                if wheel == rms[0]:
                    models.add(info['Version'])
                    verify_compiled_wheel(set(z.namelist()), 'motomind_robot_model/')
                    continue
                versions.add(info['Version'])
                abi = 'cp' + py.replace('.', '')
                assert f'-{abi}-{abi}-linux_x86_64.whl' in wheel.name, wheel.name
                prefix = 'motomind_milly/'
                names = set(z.namelist())
                assert any(n.startswith(prefix + '_core.') and n.endswith('.so') for n in names)
                assert prefix + 'button.py' not in names, 'development button module leaked'
                verify_compiled_wheel(names, prefix)
                found = {Path(n).name for n in names if n.startswith(prefix+'profiles/') and n.endswith('.yaml')}
                assert found == profiles, f'profile allowlist violation: {found}'
                profile_hashes.add(tuple((n, sha(z.read(prefix+'profiles/'+n))) for n in sorted(profiles)))
                assert z.read(prefix+'robot/MILLY.urdf') == urdf, 'wheel/ROS URDF mismatch'
                data = z.read(prefix+'profiles/milly_cal.yaml')
                calibration_hashes.add(sha(data))
                cal = yaml.safe_load(data)
                assert cal['model_compatibility'] == {'status': 'validated', 'coordinates': 'motor_raw', 'urdf_sha256': sha(urdf)}
                assert cal['use_calibrated_params'] is True
                assert cal['provenance']['operator_accepted'] is True
                assert all(p['mass'] > 0 for p in cal['inertia_params'].values())
    assert len(versions) == len(models) == len(profile_hashes) == len(calibration_hashes) == 1
    assert versions == {version}, 'SDK metadata version differs from requested release'
    assert re.fullmatch(r'\d+\.\d+\.\d+', version)
    packages = {}
    for path in sorted((root/'ros/src').glob('*/package.xml')):
        doc = ET.parse(path)
        packages[doc.findtext('name')] = doc.findtext('version')
    assert set(packages) == {'milly_sdk_interfaces', 'milly_sdk_ros', 'milly_sdk_description', 'milly_sdk_bringup'}
    return {'sdk_version': version, 'robot_model_version': models.pop(), 'ros_packages': packages,
            'urdf_sha256': sha(urdf), 'calibration_sha256': calibration_hashes.pop(),
            'profile_sha256': dict(profile_hashes.pop()), 'wheels': artifacts}


def verify_inventory(root, inventory):
    assert inventory, 'empty release inventory'
    for name, digest in inventory.items():
        path = root/name
        assert not Path(name).is_absolute() and '..' not in Path(name).parts, name
        assert path.resolve().is_relative_to(root.resolve()), name
        assert not path.is_symlink(), f'symlinked release file: {name}'
        assert sha(path.read_bytes()) == digest, f'release file hash mismatch: {name}'


def verify_manifest(root, saved):
    result = inspect(root, saved['sdk_version'])
    assert not any(Path(name).name in LOCAL_ONLY_NAMES for name in saved['files']), 'local-only marker in release inventory'
    verify_inventory(root, saved['files'])
    required = {
        *result['wheels'], 'LICENSE', 'INSTALL.md', 'README.md',
        'scripts/set_can_interface.sh', 'milly_description/model_manifest.json',
        'milly_description/urdf/MILLY.urdf',
        'SDK_python_guide.md', 'SDK_ROS2_guide.md',
        *(f'ros/src/{name}/package.xml' for name in result['ros_packages']),
        'scripts/setup_ros_humble.sh', 'scripts/ros_env.sh', 'scripts/check_ros_install.py',
        *(f'.github/tests/ros/{name}' for name in (
            'test_backend.py', 'test_ros_node.py', 'test_motor_gui.py',
            'test_position_monitor.py', 'test_rviz_config.py', 'test_launch_layout.py')),
        *(f'scripts/ci/{name}.py' for name in ('verify_release', 'install_wheels', 'smoke_wheel', 'package_release')),
        '.github/workflows/release-ci.yml', '.github/workflows/release-publish.yml',
    }
    # A hash list alone must not let omitted ROS/runtime/docs files pass packaging.
    for folder in ('ros/src', '.github/tests/ros', 'examples/python', 'milly_description'):
        required.update(p.relative_to(root).as_posix() for p in (root/folder).rglob('*')
            if p.is_file() and not ({'__pycache__', '.pytest_cache'} & set(p.parts))
            and p.suffix != '.pyc' and p.name not in LOCAL_ONLY_NAMES)
    assert required <= saved['files'].keys(), f'missing inventory entries: {sorted(required - saved["files"].keys())}'
    assert {k:v for k,v in saved.items() if k != 'files'} == result, 'manifest differs from bundle'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--write-manifest', action='store_true')
    p.add_argument('--version', help='required when generating the manifest')
    a = p.parse_args()
    manifest = a.root/'.github/release_manifest.json'
    legacy_manifest = a.root/'release_manifest.json'
    expected = a.version if a.write_manifest else json.loads(manifest.read_text())['sdk_version']
    if not expected or not re.fullmatch(r'\d+\.\d+\.\d+', expected):
        p.error('a MAJOR.MINOR.PATCH version is required')
    result = inspect(a.root, expected)
    if a.write_manifest:
        excluded = {'.git', '.venv', '.venv_ci', '.venv_ros', 'build', 'install', 'log', '__pycache__', '.pytest_cache'}
        result['files'] = {p.relative_to(a.root).as_posix(): sha(p.read_bytes())
            for p in sorted(a.root.rglob('*')) if p.is_file() and p not in (manifest, legacy_manifest)
            and not (set(p.relative_to(a.root).parts) & excluded)
            and p.suffix != '.pyc' and p.name not in LOCAL_ONLY_NAMES}
        verify_manifest(a.root, result)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
        legacy_manifest.unlink(missing_ok=True)
    else:
        saved = json.loads(manifest.read_text())
        verify_manifest(a.root, saved)
    print(f"Release {result['sdk_version']}: all 3 wheel pairs, profiles, calibration and meshes verified")


if __name__ == '__main__':
    main()

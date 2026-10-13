"""Upgrade regression using temporary metadata; no ROS nodes or hardware."""
import importlib.util
from importlib.metadata import distribution
from pathlib import Path

import pytest

SDK = next(p for p in Path(__file__).resolve().parents
           if (p/'scripts/clean_ros_metadata.py').is_file())
spec = importlib.util.spec_from_file_location('clean_ros_metadata', SDK/'scripts/clean_ros_metadata.py')
cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleaner)


def metadata(site, version, *, preview=True, name='milly-sdk-ros', kind='egg-info'):
    path = site/f'milly_sdk_ros-{version}-py3.10.{kind}'
    path.mkdir(parents=True)
    (path/('PKG-INFO' if kind == 'egg-info' else 'METADATA')).write_text(
        f'Name: {name}\nVersion: {version}\n')
    names = sorted(cleaner.ENTRY_POINTS - (set() if preview else {'teaching_preview'}))
    (path/'entry_points.txt').write_text('[console_scripts]\n' +
        ''.join(f'{name} = milly_sdk_ros.{name}:main\n' for name in names))
    return path


@pytest.fixture
def installation(tmp_path):
    package = tmp_path/'ros/src/milly_sdk_ros/package.xml'
    package.parent.mkdir(parents=True)
    package.write_text('<package><name>milly_sdk_ros</name><version>1.0.0</version></package>')
    site = tmp_path/'install/milly_sdk_ros/lib/python3.10/site-packages'
    old = metadata(site, '0.1.0', preview=False)
    return tmp_path, site, old


def test_upgrade_removes_old_metadata_and_resolves_preview(installation, monkeypatch):
    root, site, old = installation
    current = metadata(site, '1.0.0')
    other = site/'another_package-0.1.0.egg-info'
    other.mkdir()
    module = site/'milly_sdk_ros'
    module.mkdir()
    (module/'user.txt').write_text('keep')
    monkeypatch.syspath_prepend(str(site))
    assert cleaner.clean(root) == [old.name]
    assert not old.exists() and current.exists() and other.exists()
    assert (module/'user.txt').read_text() == 'keep'
    selected = distribution('milly-sdk-ros')
    assert selected.version == '1.0.0'
    assert cleaner.ENTRY_POINTS <= {e.name for e in selected.entry_points}
    assert cleaner.clean(root) == []


@pytest.mark.parametrize('failure', ['missing', 'no_preview', 'duplicate'])
def test_incomplete_current_install_does_not_remove_old_metadata(installation, failure):
    root, site, old = installation
    if failure != 'missing':
        metadata(site, '1.0.0', preview=failure != 'no_preview')
    if failure == 'duplicate':
        metadata(site, '1.0.0', kind='dist-info')
    with pytest.raises(ValueError, match='Current ROS metadata'):
        cleaner.clean(root)
    assert old.exists()


def test_symlinked_metadata_is_never_followed(installation):
    root, site, old = installation
    metadata(site, '1.0.0')
    linked = site/'milly_sdk_ros-0.2.0-py3.10.egg-info'
    linked.symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError, match='non-directory ROS metadata'):
        cleaner.clean(root)
    assert old.exists() and linked.is_symlink()


def test_symlinked_install_parent_is_never_followed(installation):
    root, site, old = installation
    metadata(site, '1.0.0')
    installed = root/'install/milly_sdk_ros'
    saved = root/'preserved_install'
    installed.rename(saved)
    installed.symlink_to(saved, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinked ROS install path'):
        cleaner.clean(root)
    assert (saved/'lib/python3.10/site-packages'/old.name).exists()


def test_unrecognized_metadata_prevents_cleanup(installation):
    root, site, old = installation
    metadata(site, '1.0.0')
    metadata(site, '0.2.0', name='another-package')
    with pytest.raises(ValueError, match='Unrecognized ROS metadata'):
        cleaner.clean(root)
    assert old.exists()

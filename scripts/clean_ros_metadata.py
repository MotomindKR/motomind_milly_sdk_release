#!/usr/bin/env python3
"""Remove obsolete metadata from this bundle's isolated ROS install only."""
import argparse
from importlib.metadata import PathDistribution
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ENTRY_POINTS = {'driver', 'discover', 'description_monitor', 'teaching_preview'}


def clean(root):
    root = Path(root).resolve()
    package = ET.parse(root/'ros/src/milly_sdk_ros/package.xml')
    version = package.findtext('version')
    if package.findtext('name') != 'milly_sdk_ros' or not version:
        raise ValueError('Invalid milly_sdk_ros package metadata.')
    site = root/'install/milly_sdk_ros/lib/python3.10/site-packages'
    for path in (site, *site.parents):
        if path == root:
            break
        if path.is_symlink():
            raise ValueError(f'Refusing symlinked ROS install path: {path}')
    candidates = []
    for path in site.glob('milly_sdk_ros-*'):
        if path.suffix not in ('.egg-info', '.dist-info'):
            continue
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f'Refusing non-directory ROS metadata: {path}')
        distribution = PathDistribution(path)
        if (distribution.metadata.get('Name', '').replace('-', '_') != 'milly_sdk_ros'
                or not distribution.version):
            raise ValueError(f'Unrecognized ROS metadata: {path}')
        candidates.append((path, distribution))
    current = [(path, dist) for path, dist in candidates if dist.version == version]
    if len(current) != 1 or not ENTRY_POINTS <= {
            entry.name for entry in current[0][1].entry_points if entry.group == 'console_scripts'}:
        raise ValueError('Current ROS metadata is missing or incomplete. Build ROS sources first.')
    removed = []
    for path, dist in candidates:
        if dist.version != version:
            shutil.rmtree(path)
            removed.append(path.name)
    return removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    for name in clean(args.root):
        print(f'Removed obsolete ROS package metadata: {name}')


if __name__ == '__main__':
    main()

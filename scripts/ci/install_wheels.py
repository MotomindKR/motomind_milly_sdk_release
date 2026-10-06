#!/usr/bin/env python3
"""Install only wheels named by the release manifest for this interpreter."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
os.environ['PYTHONNOUSERSITE'] = '1'
manifest = json.loads((root/'.github/release_manifest.json').read_text())
folder = f'dist/linux_x86_64/python{sys.version_info.major}.{sys.version_info.minor}/'
wheels = [root/name for name in manifest['wheels'] if name.startswith(folder)]
assert len(wheels) == 2, f'unsupported interpreter or incomplete manifest: {folder}'
subprocess.run([sys.executable, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', *map(str, wheels)], check=True)
# Resolve dependencies separately so updating our same-version review wheels
# does not force reinstalling every shared third-party dependency.
subprocess.run([sys.executable, '-m', 'pip', 'install', *map(str, wheels)], check=True)

#!/usr/bin/env python3
"""Package only the reviewed manifest inventory, excluding retained legacy files."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from verify_release import verify_manifest

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
manifest = json.loads((root/'.github/release_manifest.json').read_text())
verify_manifest(root, manifest)
a.out.mkdir(parents=True, exist_ok=True)
name = f"motomind-milly-sdk-{manifest['sdk_version']}-linux-x86_64"
archive = a.out/(name+'.tar.gz')
with tarfile.open(archive, 'x:gz') as tar:
    for path in sorted([*manifest['files'], '.github/release_manifest.json']):
        tar.add(root/path, arcname=name+'/'+path, recursive=False)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
(a.out/'SHA256SUMS').write_text(f'{checksum}  {archive.name}\n')
print(archive)

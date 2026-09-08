"""Build recorder data/source packages without executing code from the source tree."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import zipfile


@dataclass(frozen=True)
class ModulePackage:
    path: Path
    version: str
    sha256: str


def build_module(source: Path, destination: Path) -> ModulePackage:
    source = source.resolve()
    definition_path = source / 'definition.yml'
    if definition_path.is_symlink() or not definition_path.resolve().is_relative_to(source):
        raise ValueError('Module definition is outside the source tree')
    definition = definition_path.read_text(encoding='utf-8')
    if not re.search(r'^name: recorder\s*$', definition, re.M):
        raise ValueError('Unexpected module identity')
    match = re.search(r'^version: (\d+\.\d+\.\d+)\s*$', definition, re.M)
    if not match:
        raise ValueError('Invalid recorder version')
    version = match.group(1)
    files = [source / name for name in ('definition.yml', 'options.yml', 'init.lua', 'README.md', 'CHANGELOG.md')]
    for folder, pattern in (('code', '*.lua'), ('docs', '*.md'), ('locale', '*.yml'), ('locale', '*.md')):
        files.extend(sorted((source / folder).rglob(pattern)))
    for name in ('compare_multiplayer.py', 'inspect_replay.py'):
        tool = source / 'tools' / name
        if tool.exists():
            files.append(tool)
    # Validate the complete member list before creating an archive. This also
    # rejects directory links that resolve outside the trusted source root.
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError('Package member is missing or outside the source tree: ' + str(path))
    destination.mkdir(parents=True, exist_ok=True)
    asset = destination / f'recorder-{version}.zip'
    with zipfile.ZipFile(asset, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())
    with zipfile.ZipFile(asset) as archive:
        if archive.testzip() is not None:
            raise ValueError('Recorder package CRC mismatch')
    return ModulePackage(asset, version, hashlib.sha256(asset.read_bytes()).hexdigest())

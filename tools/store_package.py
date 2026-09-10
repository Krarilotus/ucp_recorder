"""Prepare the shared recorder package for UCP's native store signing pipeline."""
import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile
from module_package import build_module


def stage_store(source: Path, configuration: str) -> Path:
    if configuration not in ('Release', 'Debug'):
        raise ValueError('Unknown UCP build configuration')
    source = source.resolve()
    destination = source / 'dist' / 'store'
    # The build may be repeated. Never follow a link when replacing staging data.
    if destination.resolve() != destination or destination.is_symlink():
        raise ValueError('Store staging directory must remain inside the source tree')
    with tempfile.TemporaryDirectory() as temporary:
        package = build_module(source, Path(temporary),
                               profile='release' if configuration == 'Release' else 'diagnostic')
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        # This archive was just produced by our allowlisted shared packager.
        with zipfile.ZipFile(package.path) as archive:
            archive.extractall(destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', choices=('Release', 'Debug'), required=True)
    args = parser.parse_args()
    print(stage_store(Path(__file__).resolve().parents[1], args.configuration))

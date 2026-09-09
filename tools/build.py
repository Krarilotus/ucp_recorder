"""Build a correctly named UCP module ZIP using only the Python standard library."""
from pathlib import Path
import argparse
from module_package import build_module, build_diagnostic_bundle

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--profile', choices=('release','diagnostic','both'), default='both')
profile = parser.parse_args().profile
if profile in ('release','both'):
    print(build_module(root, root / 'dist', profile='release').path)
if profile in ('diagnostic','both'):
    print(build_diagnostic_bundle(root, root / 'dist').path)

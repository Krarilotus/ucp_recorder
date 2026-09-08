"""Build a correctly named UCP module ZIP using only the Python standard library."""
from pathlib import Path
from module_package import build_module

root = Path(__file__).resolve().parents[1]
print(build_module(root, root / 'dist').path)

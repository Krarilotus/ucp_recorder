"""Build a correctly named UCP module ZIP using only the Python standard library."""
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parents[1]
definition = (root/'definition.yml').read_text()
name = re.search(r'^name: (.+)$', definition, re.M).group(1)
version = re.search(r'^version: (.+)$', definition, re.M).group(1)
destination = root/'dist'/f'{name}-{version}.zip'
destination.parent.mkdir(exist_ok=True)
files = [root/p for p in ('definition.yml', 'options.yml', 'init.lua', 'README.md', 'CHANGELOG.md')]
files.extend(sorted((root/'code').rglob('*.lua')))
files.extend(sorted((root/'docs').rglob('*.md')))
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None
    assert 'definition.yml' in archive.namelist()
print(destination)

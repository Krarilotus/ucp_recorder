"""Publish immutable PR packages, without executing PR build code."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True, encoding='utf-8')


def output(**values):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        for key, value in values.items():
            stream.write(f'{key}={json.dumps(value, separators=(",", ":"))}\n')


def discover():
    source = os.environ['SOURCE_REPO']
    publisher = os.environ['GITHUB_REPOSITORY']
    requested = os.environ.get('REQUESTED_PR', '')
    if requested:
        assert requested.isdecimal(), 'PR must be a number'
        pulls = [json.loads(gh('api', f'repos/{source}/pulls/{requested}'))]
    else:
        pages = json.loads(gh('api', f'repos/{source}/pulls?state=open&per_page=100', '--paginate', '--slurp'))
        pulls = [pr for page in pages for pr in page]
    pages = json.loads(gh('api', f'repos/{publisher}/releases?per_page=100', '--paginate', '--slurp'))
    existing = {release['tag_name'] for page in pages for release in page if not release['draft']}
    builds = []
    for pr in pulls:
        head = pr['head']
        if pr['draft'] or not head['repo'] or head['repo']['full_name'] not in {
            publisher, source, 'Krarilotus/ucp_recorder'
        }:
            continue
        sha = head['sha']
        assert re.fullmatch('[0-9a-f]{40}', sha)
        tag = f'pr-{pr["number"]}-{sha[:12]}'
        if tag not in existing:
            builds.append(dict(pr=pr['number'], sha=sha, repo=head['repo']['full_name'], tag=tag))
    tests = [dict(build, os=runner) for build in builds for runner in ('ubuntu-latest', 'windows-latest')]
    output(builds={'include': builds}, tests={'include': tests}, count=len(builds))
    print(f'{len(builds)} PR releases need publication')


def package():
    build = json.loads(os.environ['PR_BUILD'])
    source = Path('source').resolve()
    destination = Path('out')
    destination.mkdir(exist_ok=True)
    definition = (source / 'definition.yml').read_text(encoding='utf-8')
    assert re.search(r'^name: recorder\s*$', definition, re.M), 'Unexpected module identity'
    version = re.search(r'^version: (\d+\.\d+\.\d+)\s*$', definition, re.M).group(1)
    asset = destination / f'recorder-{version}.zip'
    files = [source / name for name in ('definition.yml', 'options.yml', 'init.lua', 'README.md', 'CHANGELOG.md')]
    files += sorted((source / 'code').rglob('*.lua'))
    files += sorted((source / 'docs').rglob('*.md'))
    comparator = source / 'tools/compare_multiplayer.py'
    if comparator.exists():
        files.append(comparator)
    with zipfile.ZipFile(asset, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(source)
            archive.write(path, path.relative_to(source).as_posix())
    checksum = hashlib.sha256(asset.read_bytes()).hexdigest()
    asset.with_suffix('.zip.sha256').write_text(f'{checksum}  {asset.name}\n', encoding='utf-8')
    (destination / 'build.json').write_text(json.dumps(dict(build, version=version, sha256=checksum)), encoding='utf-8')


def publish():
    build = json.loads(os.environ['PR_BUILD'])
    metadata = json.loads(Path('out/build.json').read_text(encoding='utf-8'))
    assert all(metadata[key] == value for key, value in build.items()), 'Artifact belongs to another PR/commit'
    version = metadata['version']
    assert re.fullmatch(r'\d+\.\d+\.\d+', version)
    asset = Path('out') / f'recorder-{version}.zip'
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    assert digest == metadata['sha256'], 'Artifact checksum differs'
    with zipfile.ZipFile(asset) as archive:
        assert archive.testzip() is None
        definition = archive.read('definition.yml').decode('utf-8')
        assert re.search(rf'^version: {re.escape(version)}\s*$', definition, re.M)
        changelog = archive.read('CHANGELOG.md').decode('utf-8')
    asset.with_suffix('.zip.sha256').write_text(f'{digest}  {asset.name}\n', encoding='utf-8')
    section = re.search(rf'^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    source = os.environ['SOURCE_REPO']
    notes = f'''Experimental test build for [{source} PR #{build['pr']}](https://github.com/{source}/pull/{build['pr']}).

**Exact commit:** `{build['sha']}`. **Module version:** `{version}`.

Download **{asset.name}** below. GitHub's source archives are not installable modules. This PR includes preceding stacked changes; test the PR stages in order. Later updates produce a separate release for the new commit.

Use a separate UCP3 developer-mode installation. Preserve Graphics API Replacer and its dependencies if required. Consult the packaged README for the features and installation instructions of this exact stage. Later stages require recorder after protocol in extension order.

Automated tests passed on Windows and Linux. No live game is launched by this workflow. These builds are not certified for complete replay or multiplayer playback; earlier stages deliberately have fewer features and safeguards. Publishing a fork prerelease does not merge or approve its upstream PR.

## Changelog for this stage

{section.group(1).strip() if section else 'See CHANGELOG.md in the module archive.'}
'''
    body = Path('out/release-notes.md')
    body.write_text(notes, encoding='utf-8')
    print(gh('release', 'create', build['tag'], str(asset), str(asset.with_suffix('.zip.sha256')),
             '--repo', os.environ['GITHUB_REPOSITORY'], '--target', build['sha'], '--prerelease',
             '--title', f'PR #{build["pr"]} - Recorder {version} - {build["sha"][:12]}', '--notes-file', str(body)))


if __name__ == '__main__':
    {'discover': discover, 'package': package, 'publish': publish}[sys.argv[1]]()

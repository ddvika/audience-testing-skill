#!/usr/bin/env python3
"""Export an auditable public source tree; never copy private study artifacts."""
from pathlib import Path
import argparse
import shutil

SOURCE_ENTRIES = ('SKILL.md', '.gitignore', 'agents', 'references', 'scripts', 'assets')
PUBLIC_ENTRIES = ('README.md', 'LICENSE', 'pyproject.toml', '.gitignore', '.github',
                  'CONTRIBUTING.md', 'SECURITY.md', 'docs', 'examples')
SKIP_NAMES = {'__pycache__', '.git', '.venv', 'runs', 'reports', 'audience-run',
              'browser-state', 'node_modules', 'build', 'dist'}


def ignored(path):
    return (path.name in SKIP_NAMES or path.name.startswith('.env') or
            path.suffix in {'.pyc', '.pyo', '.pem', '.key'} or
            path.name.endswith('.egg-info'))


def copy_entry(source, destination, *, skill_assets=False):
    if source.is_symlink():
        raise ValueError('Public exports do not follow symlinks: ' + source.name)
    if ignored(source):
        return
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            # Public-facing docs belong at the repository root, not inside the skill.
            if skill_assets and child.name == 'repository':
                continue
            copy_entry(child, destination / child.name)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def template_root(source):
    bundled = source / 'assets' / 'repository'
    if bundled.is_dir():
        return bundled
    # An exported source checkout stores its public docs at the root.
    public = source.parent.parent
    if (public / 'pyproject.toml').is_file() and (public / 'README.md').is_file():
        return public
    raise ValueError('Export templates are unavailable; use the complete source checkout.')


def export(destination):
    source = Path(__file__).resolve().parents[1]
    dest = Path(destination).resolve()
    templates = template_root(source)
    if dest == source or source in dest.parents or dest == templates or templates in dest.parents:
        raise ValueError('Export to a directory outside the skill and source repository.')
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise ValueError('Destination must be new or empty.')
    target = dest / 'skills' / 'audience'
    target.mkdir(parents=True, exist_ok=True)
    for name in SOURCE_ENTRIES:
        entry = source / name
        if entry.exists():
            copy_entry(entry, target / name, skill_assets=name == 'assets')
    for name in PUBLIC_ENTRIES:
        entry = templates / name
        if entry.exists():
            copy_entry(entry, dest / name)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    print(export(parser.parse_args().destination))

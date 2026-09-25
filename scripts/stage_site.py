#!/usr/bin/env python3
"""Stage only public deliverables. Never serve .git, environments, raw features or secrets."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def stage(destination):
    requested = Path(destination)
    build_root = ROOT / 'build'
    if build_root.resolve() != build_root or requested.is_symlink():
        raise ValueError('Refusing symlinked staging roots')
    destination = requested.resolve()
    if destination.parent != build_root:
        raise ValueError('Staging must be an immediate child of repository build/, never root/.git/docs')
    destination.mkdir(parents=True, exist_ok=True)
    allowed = ['docs', 'research', 'evidence', 'provenance', 'legacy/docs', 'legacy/data/evidence']
    for relative in allowed:
        source, target = ROOT / relative, destination / relative
        if destination not in target.resolve().parents or target.is_symlink():
            raise ValueError(f'Staging target escapes its public directory: {relative}')
        if source.exists():
            # Remove only our fixed generated subtree, never an arbitrary caller path.
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target,
                            ignore=shutil.ignore_patterns('__pycache__', 'cache', '*.tmp', '.git', '.env'))
    for relative in ['index.html', '.nojekyll', 'README.md', 'NEXT_STEPS.md', 'REVIEW.md',
                     'THIRD_PARTY.md', 'legacy/data/dem_links.json']:
        source, target = ROOT / relative, destination / relative
        if destination not in target.resolve().parents or target.is_symlink():
            raise ValueError(f'Staging file escapes its public directory: {relative}')
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    print(f'Staged public site in {destination}; .git and raw training data are excluded')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/site')
    stage(parser.parse_args().out)

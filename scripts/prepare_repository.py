"""Build a reviewable source-only repository preview; never remove or publish files."""
from pathlib import Path
import argparse
import hashlib
import json
import os
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = {'_backup', '_backups', '.git', 'dist', '__pycache__', '.pytest_cache', '.venv', 'venv'}
PUBLIC_DOCS = ('INSTALLATION.md', 'DATA_AND_MODELS.md', 'RESULTS.md', 'DELIVERY.md')


def safe_file(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or any(x.casefold() in PRIVATE for x in p.parts):
        raise ValueError('Private or external publication path')
    target = root/p
    for part in (target, *target.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Link in publication path')
        if part == root:
            break
    return target


def source_files(root):
    names = {'.env.example', '.gitignore', '.gitattributes', 'README.md', 'pytest.ini'}
    names.update(p.name for p in root.glob('requirements*.txt'))
    names.update('docs/'+name for name in PUBLIC_DOCS)
    for prefix, suffixes in [('src', {'.py'}), ('tests', {'.py'}),
                             ('scripts', {'.py', '.ps1'}), ('specs', {'.json', '.md', '.txt', '.csv'}),
                             ('configs', {'.json'}), ('data/manifests', {'.json'})]:
        start = root/prefix
        for directory, dirs, files in os.walk(start, followlinks=False):
            dirs[:] = [d for d in dirs if d.casefold() not in PRIVATE
                       and not (Path(directory)/d).is_symlink()
                       and not (Path(directory)/d).is_junction()]
            for name in files:
                p = Path(directory)/name
                if prefix == 'data/manifests' and p.name not in {'day07_rgb_assets.json','day07_video_environment.json','day13_whisper_assets.json'}:
                    continue
                if p.suffix.lower() in suffixes and not p.is_symlink():
                    names.add(p.relative_to(root).as_posix())
    # Small frozen text/metadata are dependencies of offline plan regression.
    for name in ('configs/day16_text_evaluation_v3_final.json',
                 'configs/day16_text_evaluation_v3_prompt_v2.json',
                 'configs/sentiment_contrast_evaluation_v1.json'):
        plan = json.loads(safe_file(root, name).read_bytes())
        names.update(plan['frozen_hashes'])
    for name in sorted(names):
        p = safe_file(root, name)
        if not p.is_file() or p.stat().st_size > 2*1024*1024:
            raise ValueError(f'Missing or oversized public file: {name}')
        if p.suffix.lower() in {'.mp4', '.mp3', '.m4a', '.wav', '.zip', '.sqlite3', '.bin'}:
            raise ValueError('Binary/private asset in public selection')
    return sorted(names)


def build_preview(root=ROOT):
    root = Path(root).absolute()
    names = source_files(root)
    target = root/'dist'/('repository-preview-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in names:
        p = safe_file(root, name)
        raw = p.read_bytes()
        destination = target/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(raw)
        rows.append(dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    manifest = dict(repository='https://github.com/dharmasistemas/MedAssistMultimodal',
        preview=target.relative_to(root).as_posix(), file_count=len(rows),
        total_bytes=sum(r['bytes'] for r in rows), files=rows,
        deleted_files=0, pushed=False, review_required=True)
    output = root/'reports/REPOSITORY_PUBLICATION_MANIFEST_2026-11-16.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = build_preview()
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False, indent=2))

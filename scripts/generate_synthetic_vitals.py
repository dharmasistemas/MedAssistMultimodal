"""Generate the day 11 synthetic corpus using only the standard library."""
import argparse
from pathlib import Path

from medassistmultimodal.demo.synthetic_vitals import SEED, write_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/synthetic/vitals_v1'))
    parser.add_argument('--seed', type=int, default=SEED)
    args = parser.parse_args()
    target = args.output.resolve()
    allowed = (Path(__file__).resolve().parents[1] / 'data/synthetic').resolve()
    if not target.is_relative_to(allowed) or target == allowed:
        parser.error('output must be a new directory under data/synthetic')
    try:
        manifest = write_bundle(target, args.seed)
    except FileExistsError:
        parser.error('output already exists; previous artifacts were preserved')
    print(f'{manifest["scenario_count"]} scenarios; {manifest["sample_count"]} samples; {target}')


if __name__ == '__main__':
    main()

"""Run the offline pipeline.

    python -m src.pipeline --phase 1   # run one phase
    python -m src.pipeline --all       # run every implemented phase in order

New phases are added to PHASES as they are built.
"""

import argparse

from src import clean, eda, features, ingest


def run_phase_1() -> None:
    """Ingest the workbook, apply the cleaning rules, draw the EDA figures."""
    ingest.run()
    clean.run()
    eda.run()


def run_phase_2() -> None:
    """Build customers, customer_features (S1, S2, S3) and outcomes (S1, S2)."""
    features.run()


PHASES = {
    1: run_phase_1,
    2: run_phase_2,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Probably High-Value? pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phase", type=int, choices=sorted(PHASES), help="run one phase")
    group.add_argument("--all", action="store_true", help="run every phase in order")
    args = parser.parse_args()

    if args.all:
        for number in sorted(PHASES):
            print(f"=== Phase {number} ===")
            PHASES[number]()
    else:
        PHASES[args.phase]()


if __name__ == "__main__":
    main()

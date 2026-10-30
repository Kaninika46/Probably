"""Run the offline pipeline.

    python -m src.pipeline --phase 1   # run one phase
    python -m src.pipeline --all       # run every implemented phase in order

New phases are added to PHASES as they are built.
"""

import argparse

from src import (
    clean,
    eda,
    evaluate,
    export_app_db,
    features,
    ingest,
    lapse,
    membership,
    prob_queries,
    report_tables,
    rules,
    segment,
    worlds,
)


def run_phase_1() -> None:
    """Ingest the workbook, apply the cleaning rules, draw the EDA figures."""
    ingest.run()
    clean.run()
    eda.run()


def run_phase_2() -> None:
    """Build customers, customer_features (S1, S2, S3) and outcomes (S1, S2)."""
    features.run()


def run_phase_3() -> None:
    """Run K-Means and GMM grids on S3 and export candidate segment profiles."""
    segment.run()


def run_phase_4() -> None:
    """Build BID segment_membership (gmm + bootstrap), gate report and tree rules."""
    membership.run()
    rules.run()


def run_phase_5() -> None:
    """Train calibrated S1 lapse model, evaluate on S2, score S3 into lapse_risk."""
    lapse.run()


def run_phase_6() -> None:
    """Run probabilistic query templates Q1-Q6, possible-worlds check and export app.duckdb."""
    prob_queries.run()
    worlds.run()
    export_app_db.run()


def run_phase_7() -> None:
    """Evaluate the spaCy NL engine on dev questions and populate eval_results."""
    evaluate.run()


def run_phase_9() -> None:
    """Generate Markdown results tables from reports/tables/ and sync README.md."""
    report_tables.run()


PHASES = {
    1: run_phase_1,
    2: run_phase_2,
    3: run_phase_3,
    4: run_phase_4,
    5: run_phase_5,
    6: run_phase_6,
    7: run_phase_7,
    9: run_phase_9,
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

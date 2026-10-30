# Probably High-Value?

Customer segmentation and lapse risk stored as a probabilistic database, queried in plain English.
Course project for Data Management and AI Integration (ABAI2009L), Bennett University, 2026.

The full spec is in [CLAUDE.md](CLAUDE.md), and progress is tracked in [docs/PROGRESS.md](docs/PROGRESS.md).

## Setup

Requires Python 3.12.

```
py -3.12 -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
python data/download.py            # fetches UCI Online Retail II into data/raw/
pytest
```

## Running the pipeline

```
python -m src.pipeline --phase 1   # one phase
python -m src.pipeline --all       # every implemented phase
```

## Data

UCI Online Retail II (dataset 502), DOI 10.24432/C5CG6D, licence CC BY 4.0.
Raw data is downloaded locally and is never committed.

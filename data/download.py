"""Download the UCI Online Retail II dataset into data/raw/.

Run from the project root:  python data/download.py

If the download fails, the script says so and tells you how to get the file by
hand. It never invents or fakes data.
"""

import sys
import urllib.request
import zipfile
from pathlib import Path

# Make "from src import config" work when this file is run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402


def download_zip(url: str, target: Path) -> None:
    """Save the file at `url` to `target`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, target)
    print(f"Saved {target} ({target.stat().st_size:,} bytes)")


def extract_xlsx(zip_path: Path, target_xlsx: Path) -> None:
    """Pull the .xlsx out of the zip and save it under the expected name.

    We look for the .xlsx by extension instead of trusting a file name, because
    the name inside the zip is decided by UCI, not by us.
    """
    with zipfile.ZipFile(zip_path) as zf:
        xlsx_names = [name for name in zf.namelist() if name.lower().endswith(".xlsx")]
        if len(xlsx_names) != 1:
            raise RuntimeError(f"Expected exactly one .xlsx in the zip, found: {xlsx_names}")
        with zf.open(xlsx_names[0]) as src, open(target_xlsx, "wb") as dst:
            dst.write(src.read())
    print(f"Extracted {xlsx_names[0]} -> {target_xlsx}")


def main() -> None:
    if config.RAW_XLSX.exists():
        print(f"{config.RAW_XLSX} already exists, nothing to do.")
        return
    try:
        download_zip(config.DATASET_URL, config.RAW_ZIP)
        extract_xlsx(config.RAW_ZIP, config.RAW_XLSX)
    except Exception as error:
        print(f"Download failed: {error}")
        print("Please download the dataset by hand from")
        print("  https://archive.ics.uci.edu/dataset/502/online+retail+ii")
        print(f"and save the workbook as {config.RAW_XLSX}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Load the attributed seven-day real-data fixture into a new SQLite database."""

from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3
import pandas as pd
from src.utils.config import ROOT_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/sample.db"))
    args = parser.parse_args()
    if args.db.exists():
        parser.error("Destination already exists; choose a new database path.")
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        for path in sorted((ROOT_DIR / "data/sample").glob("raw_*.csv")):
            pd.read_csv(path).to_sql(path.stem, conn, index=False)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()

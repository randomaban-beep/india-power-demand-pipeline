"""Compare cleaner revisions on identical raw data; excludes download time."""

from __future__ import annotations
import argparse
import importlib.util
import json
import platform
import sqlite3
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from sqlalchemy import create_engine
from src.clean import clean_hourly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--baseline-ref", default="5e86c18")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmark.json"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    baseline_code = subprocess.check_output(["git", "show", f"{args.baseline_ref}:src/clean/clean_hourly.py"])
    report = {
        "baseline_ref": args.baseline_ref,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "method": "Alternating runs on SQLite backups of the same source; cleaner wall time includes reads, transformation and staging write; excludes copy/download; warm filesystem cache; outputs differ due to correctness fixes.",
        "runs": [],
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        old_file = root / "baseline.py"
        old_file.write_bytes(baseline_code)
        spec = importlib.util.spec_from_file_location("baseline_cleaner", old_file)
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        for repeat in range(args.repeats):
            for label, module in [("before", old), ("after", clean_hourly)]:
                path = root / f"{label}-{repeat}.db"
                src = sqlite3.connect(args.db)
                dst = sqlite3.connect(path)
                src.backup(dst)
                src.close()
                dst.close()
                engine = create_engine(f"sqlite:///{path.as_posix()}")
                module.get_engine = lambda: engine
                start = time.perf_counter()
                stats = module.clean_hourly_demand()
                elapsed = time.perf_counter() - start
                engine.dispose()
                report["runs"].append(
                    {
                        "revision": label,
                        "repeat": repeat + 1,
                        "seconds": elapsed,
                        **{k: v for k, v in stats.items() if k != "duration_s"},
                    }
                )
    for label in ["before", "after"]:
        report[f"{label}_median_seconds"] = statistics.median(
            r["seconds"] for r in report["runs"] if r["revision"] == label
        )
    report["speedup"] = report["before_median_seconds"] / report["after_median_seconds"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

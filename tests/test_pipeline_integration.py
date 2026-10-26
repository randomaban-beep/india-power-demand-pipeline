"""Offline integration test: real sample -> staging -> marts -> atomic snapshot."""

from contextlib import closing
import sqlite3
import pandas as pd
from src.utils.config import ROOT_DIR
from src.clean.run_all import run_all as clean
from src.model.run_all import run_all as model
from src.model.export_powerbi import export_powerbi_tables, export_slim_db, MARTS


def test_offline_pipeline_is_repeatable(tmp_path, monkeypatch):
    source = tmp_path / "raw.db"
    with closing(sqlite3.connect(source)) as conn:
        for path in (ROOT_DIR / "data/sample").glob("raw_*.csv"):
            pd.read_csv(path).to_sql(path.stem, conn, index=False)
    monkeypatch.setenv("ENERGY_DB_PATH", str(source))
    monkeypatch.setenv("ENERGY_WRITE_CLEANING_LOG", "0")
    snapshots = []
    for _ in range(2):
        clean()
        model()
        export_powerbi_tables(tmp_path / "processed")
        destination = export_slim_db(tmp_path / "snapshot.db")
        with closing(sqlite3.connect(destination)) as conn:
            snapshots.append(
                {table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall() for table in MARTS}
            )
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert (
                conn.execute("SELECT COUNT(*) FROM data_quality_checks WHERE status='FAIL'").fetchone()[0]
                == 0
            )
            assert (
                conn.execute("SELECT COUNT(*) FROM data_quality_checks WHERE status='SKIP'").fetchone()[0]
                >= 1
            )
        for table in MARTS:
            parquet = pd.read_parquet(tmp_path / "processed" / f"{table}.parquet")
            csv = pd.read_csv(
                tmp_path / "processed" / f"{table}.csv",
                dtype={c: str for c in parquet.select_dtypes(include="object").columns},
            )
            pd.testing.assert_frame_equal(
                csv.astype(object).where(csv.notna(), None),
                parquet.astype(object).where(parquet.notna(), None),
                check_dtype=False,
            )
    assert snapshots[0] == snapshots[1]
    assert len(snapshots[0]["mart_temp_vs_demand"]) == 168

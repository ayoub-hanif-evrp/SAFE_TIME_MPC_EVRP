from pathlib import Path

import pytest

from safe_time_evrp.data.arc_adapter import REQUIRED_COLUMNS, load_arc_table


def test_arc_adapter_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "not_the_dataset.csv"
    path.write_text("from,to\nA,B\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing ARC columns"):
        load_arc_table(path)


def test_arc_adapter_reads_a_declared_fixture(tmp_path: Path):
    header = ",".join(REQUIRED_COLUMNS)
    row = "A,B,1.5,0.2,1,4,0.01,0.02,residential"
    path = tmp_path / "synthetic_arc_fixture.csv"
    path.write_text(header + "\n" + row + "\n", encoding="utf-8")
    rows = load_arc_table(path)
    assert rows[0]["distance_km"] == "1.5"
    assert "kwh" not in rows[0]

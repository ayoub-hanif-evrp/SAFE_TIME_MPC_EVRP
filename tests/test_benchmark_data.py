from collections import Counter

from safe_time_evrp.data.checks import validate_instance
from safe_time_evrp.data.paths import manifest_path, schneider_dir
from safe_time_evrp.data.schneider import iter_instance_files, parse_schneider_file


def test_schneider_archive_matches_its_deposited_structure():
    assert manifest_path().exists(), "run python -m safe_time_evrp.data.download"
    files = iter_instance_files(schneider_dir() / "extracted")
    assert len(files) == 92
    sizes: Counter[str] = Counter()
    families: Counter[str] = Counter()
    for path in files:
        instance = parse_schneider_file(path)
        report = validate_instance(instance)
        assert report["ok"], report["errors"]
        assert report["customers"] == _expected_customers(path.stem)
        stem = path.stem
        if stem.startswith("rc"):
            families["rc"] += 1
        elif stem.startswith("r"):
            families["r"] += 1
        else:
            families["c"] += 1
        if stem.endswith("_21"):
            sizes["full"] += 1
            assert report["customers"] == 100
        elif "C15" in stem:
            sizes["15"] += 1
        elif "C10" in stem:
            sizes["10"] += 1
        elif "C5" in stem:
            sizes["5"] += 1
        source_customers = [
            line.split()[0] for line in path.read_text(encoding="utf-8").splitlines() if line.split()[1:2] == ["c"]
        ]
        assert source_customers == sorted(source_customers, key=source_customers.index)
        assert set(source_customers) == set(instance.customer_ids())
    assert sizes == Counter({"full": 56, "15": 12, "10": 12, "5": 12})
    assert sum(families.values()) == 92
    assert families["c"] and families["r"] and families["rc"]


def _expected_customers(stem: str) -> int:
    if "C5" in stem:
        return 5
    if "C10" in stem:
        return 10
    if "C15" in stem:
        return 15
    return 100

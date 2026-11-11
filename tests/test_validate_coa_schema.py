from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest

from validate_coa_schema import main, validate_coa_jsonld


ROOT = Path(__file__).resolve().parent.parent


def _load_example(filename: str) -> dict:
    return json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))


def _set_prop(doc: dict, prop_id: str, new_val: object) -> dict:
    mutated = copy.deepcopy(doc)
    for item in mutated["additionalProperty"]:
        if item["propertyID"] == prop_id:
            item["value"] = new_val
            return mutated
    raise KeyError(prop_id)


def test_hush_0_35mg_example_passes() -> None:
    doc = _load_example("hush_0_35mg_melatonin.jsonld")
    report = validate_coa_jsonld(doc)
    assert report.valid is True, report.errors
    assert report.sku == "HERM-HUSH-20G"
    assert report.computed_recovery_pct == pytest.approx(102.86, abs=0.02)
    assert any("EXAMPLE-" in w for w in report.warnings)


def test_meru_500mg_example_passes() -> None:
    doc = _load_example("meru_500mg_shilajit.jsonld")
    report = validate_coa_jsonld(doc)
    assert report.valid is True, report.errors
    assert report.sku == "HERM-MERU-50T"
    assert report.computed_recovery_pct == pytest.approx(101.20, abs=0.02)


def test_rejects_out_of_tolerance_overage() -> None:
    # e.g., 0.55 mg measured on a 0.35 mg label claim = 157.14% (> 115% upper limit)
    doc = _set_prop(_load_example("hush_0_35mg_melatonin.jsonld"), "coa:measuredAssayPerServing", 0.55)
    report = validate_coa_jsonld(doc)
    assert report.valid is False
    assert any("outside declared tolerance" in e for e in report.errors)


def test_rejects_heavy_metal_exceedance() -> None:
    doc = _set_prop(_load_example("meru_500mg_shilajit.jsonld"), "coa:leadPpm", 1.25)
    report = validate_coa_jsonld(doc)
    assert report.valid is False
    assert any("coa:leadPpm" in e for e in report.errors)


def test_rejects_unaccredited_lab_and_date_inversion() -> None:
    doc = _set_prop(_load_example("hush_0_35mg_melatonin.jsonld"), "coa:iso17025Accredited", False)
    doc = _set_prop(doc, "coa:expirationDate", "2025-01-01")
    report = validate_coa_jsonld(doc)
    assert report.valid is False
    assert any("coa:iso17025Accredited" in e for e in report.errors)
    assert any("coa:expirationDate" in e for e in report.errors)


def test_rejects_missing_required_vessel_property() -> None:
    doc = _load_example("meru_500mg_shilajit.jsonld")
    doc["additionalProperty"] = [
        p for p in doc["additionalProperty"] if p["propertyID"] != "vessel:architecture"
    ]
    report = validate_coa_jsonld(doc)
    assert report.valid is False
    assert any("vessel:architecture" in e for e in report.errors)


def test_cli_exit_codes(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    hush = str(ROOT / "examples" / "hush_0_35mg_melatonin.jsonld")
    meru = str(ROOT / "examples" / "meru_500mg_shilajit.jsonld")
    assert main([hush, meru]) == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out

    bad_file = tmp_path / "bad.jsonld"
    bad_doc = _set_prop(_load_example("hush_0_35mg_melatonin.jsonld"), "coa:microbialStatus", "FAIL")
    bad_file.write_text(json.dumps(bad_doc), encoding="utf-8")
    assert main([str(bad_file), "--json"]) == 1
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["valid"] is False

#!/usr/bin/env python3
"""
supplement-coa-jsonld validator (Python 3, zero external dependencies)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates Schema.org Product + PropertyValue JSON-LD payloads carrying:
  1. ISO/IEC 17025 Certificate of Analysis metadata (lot, dates, lab accreditation)
  2. Active-analyte label claim vs. measured assay recovery within declared tolerances
  3. Heavy-metal ICP-MS (As, Cd, Pb, Hg) and USP microbial pass gates
  4. Primary structural vessel & barrier specifications (`vessel:*`)

Author: Christian Gallo Delgado — Hermetica Superfoods (LifeForce Liquids Corp.)
License: MIT
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ALLOWED_ASSAY_UNITS = {"mg", "mcg", "ug", "g", "iu"}
HEAVY_METAL_SAFE_CEILINGS_PPM = {
    "coa:arsenicPpm": 1.5,
    "coa:cadmiumPpm": 0.5,
    "coa:leadPpm": 0.5,
    "coa:mercuryPpm": 0.2,
}

REQUIRED_COA_PROPERTIES = (
    "coa:batchLotNumber",
    "coa:iso17025Accredited",
    "coa:accreditationBody",
    "coa:testingLaboratory",
    "coa:testDate",
    "coa:expirationDate",
    "coa:activeAnalyteName",
    "coa:labelClaimPerServing",
    "coa:measuredAssayPerServing",
    "coa:assayUnit",
    "coa:toleranceMinPct",
    "coa:toleranceMaxPct",
    "coa:heavyMetalsStatus",
    "coa:arsenicPpm",
    "coa:cadmiumPpm",
    "coa:leadPpm",
    "coa:mercuryPpm",
    "coa:microbialStatus",
    "vessel:architecture",
    "vessel:reusableHardware",
    "vessel:moistureLightBarrier",
    "vessel:servingsPerVessel",
)


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    sku: Optional[str]
    product_name: Optional[str]
    batch_lot_number: Optional[str]
    computed_recovery_pct: Optional[float]
    errors: List[str]
    warnings: List[str]


def _parse_iso_date(raw: Any, field_label: str, errors: List[str]) -> Optional[dt.date]:
    if not isinstance(raw, str):
        errors.append(f"{field_label} must be an ISO-8601 YYYY-MM-DD string")
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        errors.append(f"{field_label} invalid ISO-8601 date: {raw!r}")
        return None


def _is_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def validate_coa_jsonld(doc: Dict[str, Any]) -> ValidationReport:
    """Validate structural Schema.org fields and quantitative COA / vessel invariants."""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(doc, dict):
        return ValidationReport(
            valid=False,
            sku=None,
            product_name=None,
            batch_lot_number=None,
            computed_recovery_pct=None,
            errors=["Root JSON-LD document must be an object"],
            warnings=[],
        )

    if doc.get("@context") != "https://schema.org":
        errors.append("@context must equal 'https://schema.org'")

    doc_type = doc.get("@type")
    if isinstance(doc_type, str):
        type_ok = doc_type == "Product"
    elif isinstance(doc_type, list):
        type_ok = "Product" in doc_type and all(isinstance(t, str) for t in doc_type)
    else:
        type_ok = False
    if not type_ok:
        errors.append("@type must be 'Product' or an array containing 'Product'")

    name = doc.get("name")
    if not isinstance(name, str) or len(name.strip()) < 2:
        errors.append("name must be a non-empty string")

    sku = doc.get("sku")
    if not isinstance(sku, str) or len(sku.strip()) < 2:
        errors.append("sku must be a non-empty string")

    brand = doc.get("brand")
    if not isinstance(brand, dict) or brand.get("@type") not in ("Brand", "Organization") or not brand.get("name"):
        errors.append("brand must be an object with @type in {'Brand', 'Organization'} and non-empty name")

    raw_props = doc.get("additionalProperty")
    if not isinstance(raw_props, list) or not raw_props:
        errors.append("additionalProperty must be a non-empty array of Schema.org PropertyValue objects")
        return ValidationReport(
            valid=False,
            sku=sku if isinstance(sku, str) else None,
            product_name=name if isinstance(name, str) else None,
            batch_lot_number=None,
            computed_recovery_pct=None,
            errors=errors,
            warnings=warnings,
        )

    props: Dict[str, Dict[str, Any]] = {}
    for idx, item in enumerate(raw_props):
        if not isinstance(item, dict):
            errors.append(f"additionalProperty[{idx}] must be an object")
            continue
        if item.get("@type") != "PropertyValue":
            errors.append(f"additionalProperty[{idx}].@type must be 'PropertyValue'")
        prop_id = item.get("propertyID")
        if not isinstance(prop_id, str) or ":" not in prop_id:
            errors.append(f"additionalProperty[{idx}].propertyID must be a namespaced string (e.g., 'coa:batchLotNumber')")
            continue
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            errors.append(f"additionalProperty[{idx}] ({prop_id}) must include a human-readable 'name'")
        if "value" not in item or item["value"] is None:
            errors.append(f"additionalProperty[{idx}] ({prop_id}) must include a non-null 'value'")
        if prop_id in props:
            errors.append(f"Duplicate propertyID {prop_id!r} in additionalProperty")
        props[prop_id] = item

    for req_key in REQUIRED_COA_PROPERTIES:
        if req_key not in props:
            errors.append(f"Missing required PropertyValue: {req_key}")

    def val(key: str) -> Any:
        return props[key].get("value") if key in props else None

    lot = val("coa:batchLotNumber")
    if lot is not None and (not isinstance(lot, str) or not lot.strip()):
        errors.append("coa:batchLotNumber must be a non-empty string")
    if isinstance(lot, str) and lot.upper().startswith("EXAMPLE-"):
        warnings.append("Document uses an illustrative EXAMPLE-* lot identifier (reference fixture, not a live production release).")

    iso_acc = val("coa:iso17025Accredited")
    if iso_acc is not True:
        errors.append("coa:iso17025Accredited must be boolean true for verified COA publication")

    for str_key in (
        "coa:accreditationBody",
        "coa:testingLaboratory",
        "coa:activeAnalyteName",
        "vessel:architecture",
        "vessel:moistureLightBarrier",
    ):
        v = val(str_key)
        if v is not None and (not isinstance(v, str) or not v.strip()):
            errors.append(f"{str_key} must be a non-empty string")

    test_date = _parse_iso_date(val("coa:testDate"), "coa:testDate", errors) if "coa:testDate" in props else None
    exp_date = _parse_iso_date(val("coa:expirationDate"), "coa:expirationDate", errors) if "coa:expirationDate" in props else None
    if test_date and exp_date and exp_date <= test_date:
        errors.append(f"coa:expirationDate ({exp_date}) must be strictly after coa:testDate ({test_date})")

    assay_unit = val("coa:assayUnit")
    if assay_unit is not None and (not isinstance(assay_unit, str) or assay_unit.lower() not in ALLOWED_ASSAY_UNITS):
        errors.append(f"coa:assayUnit must be one of {sorted(ALLOWED_ASSAY_UNITS)}, got {assay_unit!r}")

    label_claim = val("coa:labelClaimPerServing")
    measured = val("coa:measuredAssayPerServing")
    tol_min = val("coa:toleranceMinPct")
    tol_max = val("coa:toleranceMaxPct")
    computed_recovery: Optional[float] = None

    if label_claim is not None and (not _is_number(label_claim) or float(label_claim) <= 0):
        errors.append("coa:labelClaimPerServing must be a positive number")
    if measured is not None and (not _is_number(measured) or float(measured) < 0):
        errors.append("coa:measuredAssayPerServing must be a non-negative number")
    if tol_min is not None and (not _is_number(tol_min) or not (50.0 <= float(tol_min) <= 100.0)):
        errors.append("coa:toleranceMinPct must be a number between 50.0 and 100.0")
    if tol_max is not None and (not _is_number(tol_max) or not (100.0 <= float(tol_max) <= 150.0)):
        errors.append("coa:toleranceMaxPct must be a number between 100.0 and 150.0")

    if (
        _is_number(label_claim)
        and float(label_claim) > 0
        and _is_number(measured)
        and _is_number(tol_min)
        and _is_number(tol_max)
    ):
        computed_recovery = round((float(measured) / float(label_claim)) * 100.0, 2)
        if not (float(tol_min) <= computed_recovery <= float(tol_max)):
            errors.append(
                f"Active assay recovery {computed_recovery:.2f}% ({measured} vs {label_claim} label claim) "
                f"outside declared tolerance [{tol_min}%, {tol_max}%]"
            )
        if "coa:assayRecoveryPct" in props:
            declared_rec = val("coa:assayRecoveryPct")
            if not _is_number(declared_rec) or abs(float(declared_rec) - computed_recovery) > 0.25:
                errors.append(
                    f"Declared coa:assayRecoveryPct ({declared_rec}) diverges from computed recovery ({computed_recovery:.2f}%)"
                )

    for status_key in ("coa:heavyMetalsStatus", "coa:microbialStatus"):
        st = val(status_key)
        if st != "PASS":
            errors.append(f"{status_key} must equal 'PASS' for compliant release, got {st!r}")

    for hm_key, ceiling_ppm in HEAVY_METAL_SAFE_CEILINGS_PPM.items():
        hm_val = val(hm_key)
        if hm_val is not None:
            if not _is_number(hm_val) or float(hm_val) < 0:
                errors.append(f"{hm_key} must be a non-negative number in ppm")
            elif float(hm_val) > ceiling_ppm:
                errors.append(f"{hm_key} ({hm_val} ppm) exceeds USP/compendial ceiling ({ceiling_ppm} ppm)")

    reusable = val("vessel:reusableHardware")
    if reusable is not None and not isinstance(reusable, bool):
        errors.append("vessel:reusableHardware must be a boolean")

    servings = val("vessel:servingsPerVessel")
    if servings is not None and (not isinstance(servings, int) or isinstance(servings, bool) or servings <= 0):
        errors.append("vessel:servingsPerVessel must be a positive integer")

    return ValidationReport(
        valid=len(errors) == 0,
        sku=sku if isinstance(sku, str) else None,
        product_name=name if isinstance(name, str) else None,
        batch_lot_number=lot if isinstance(lot, str) else None,
        computed_recovery_pct=computed_recovery,
        errors=errors,
        warnings=warnings,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate-coa-jsonld",
        description="Validate dietary supplement COA + structural vessel JSON-LD documents.",
    )
    parser.add_argument("files", nargs="+", type=Path, help="One or more .json / .jsonld files to validate")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON validation report")
    args = parser.parse_args(argv)

    reports = []
    any_failed = False
    for path in args.files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        rep = validate_coa_jsonld(doc)
        if not rep.valid:
            any_failed = True
        reports.append({"file": str(path), **asdict(rep)})

    if args.as_json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2))
    else:
        for r in reports:
            badge = "PASS" if r["valid"] else "FAIL"
            rec_str = f"{r['computed_recovery_pct']:.2f}% of label claim" if r["computed_recovery_pct"] is not None else "n/a"
            print(f"[{badge}] {r['file']} — {r['product_name']} (lot={r['batch_lot_number']}, assay={rec_str})")
            for w in r["warnings"]:
                print(f"  WARN: {w}")
            for err in r["errors"]:
                print(f"  ERROR: {err}")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())

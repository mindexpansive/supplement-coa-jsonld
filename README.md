# supplement-coa-jsonld

**Open JSON Schema, `Schema.org/Product` + `PropertyValue` profile, and zero-dependency Python 3 & Node.js validators for machine-readable dietary supplement Certificates of Analysis (ISO/IEC 17025), active-assay tolerances, and structural primary vessel specifications.**

Authored by [**Christian Gallo Delgado**](https://christiangallodelgado.com) — Founder, Structural Packaging Designer & Botanical Formulator at [**Hermetica Superfoods**](https://hermeticasuperfoods.com) ([LifeForce Liquids Corp.](https://lifeforceliquids.com)).

- **Schema:** JSON Schema Draft 2020-12 ([`schema/supplement-coa-jsonld.schema.json`](./schema/supplement-coa-jsonld.schema.json))
- **Validators:** Zero-dependency Python 3 ([`validate_coa_schema.py`](./validate_coa_schema.py)) & Node.js ESM ([`validate_coa_schema.mjs`](./validate_coa_schema.mjs))
- **License:** MIT
- **Open Hardware & Batch Ledger:** [christiangallodelgado.com/#ledger](https://christiangallodelgado.com/#ledger)

---

## Problem Statement

Most dietary supplement product pages publish analytical testing — when they publish it at all — as rasterized PDF scans locked behind lot-lookup modals. Search crawlers, AI Answer Engines, and automated procurement auditors cannot parse flattened PDF scans to verify:

1. **Label-Claim Accuracy:** Published analytical surveys of commercial gummies (e.g., Cohen et al., *JAMA* 2023, *Quantity of Melatonin and CBD in Melatonin Gummies Sold in the US*) documented wide lot-to-lot divergence between declared milligram amounts and actual assayed content. Low-dose physiological formulations such as `0.35 mg` melatonin require explicit `[90%, 115%]` recovery verification rather than unverified copywriting.
2. **Elemental Impurity & Microbial Screening:** USP `<233>` ICP-MS heavy-metal values (`As`, `Cd`, `Pb`, `Hg` in `ppm`) and USP `<2021>/<2022>` microbial status tied to an ISO/IEC 17025 accredited laboratory and explicit test/retest dates.
3. **Primary Vessel Barrier Architecture:** Active botanical stability depends on the physical container protecting it (e.g., a gold-plated magnetic metal pocket compact or a telescoping rigid paperboard cylinder with a heat-sealed inner barrier liner vs. a thin unlined commodity jar).

`supplement-coa-jsonld` embeds all three layers inside standard **`Schema.org/Product`** + **`Schema.org/PropertyValue`** JSON-LD so pages remain 100% compliant with standard Schema.org validators while exposing deterministic `coa:*` and `vessel:*` keys.

---

## Quick Start

```bash
git clone https://github.com/mindexpansive/supplement-coa-jsonld.git
cd supplement-coa-jsonld

# Validate with Python 3 (stdlib only)
python3 validate_coa_schema.py \
  examples/hush_0_35mg_melatonin.jsonld \
  examples/meru_500mg_shilajit.jsonld

# Emit structured JSON validation output
python3 validate_coa_schema.py examples/hush_0_35mg_melatonin.jsonld --json

# Or validate in Node.js / Next.js / Shopify Hydrogen CI pipelines
node validate_coa_schema.mjs \
  examples/hush_0_35mg_melatonin.jsonld \
  examples/meru_500mg_shilajit.jsonld
```

### Sample Validator Output

```text
[PASS] examples/hush_0_35mg_melatonin.jsonld — Hush Sleep Gummies (0.35 mg Melatonin per Gummy) (lot=EXAMPLE-LOT-HUSH-2026-01, assay=102.86% of label claim)
[PASS] examples/meru_500mg_shilajit.jsonld — Meru Shilajit Tablets (500 mg per Serving, 50-Tablet Pocket Compact) (lot=EXAMPLE-LOT-MERU-2026-01, assay=101.20% of label claim)
```

*(Note: Files under `examples/` use `EXAMPLE-LOT-*` identifiers as illustrative schema fixtures modeled on Hush's `0.35 mg` melatonin gummy specification and Meru's `500 mg` shilajit 50-tablet compact specification.)*

---

## Required `PropertyValue` Namespace (`coa:*` & `vessel:*`)

Every compliant `Schema.org/Product` document carries an `additionalProperty` array containing the following 21 `PropertyValue` entries:

| `propertyID` | Type | Invariant Enforced by Validator |
| :--- | :--- | :--- |
| `coa:batchLotNumber` | `string` | Non-empty lot code; flags `EXAMPLE-*` fixtures with a non-fatal warning |
| `coa:iso17025Accredited` | `boolean` | Must equal `true` |
| `coa:accreditationBody` | `string` | Non-empty accreditation reference (e.g., PJLA / A2LA / ANAB ISO/IEC 17025) |
| `coa:testingLaboratory` | `string` | Non-empty laboratory name |
| `coa:testDate` | `YYYY-MM-DD` | Valid ISO-8601 date |
| `coa:expirationDate` | `YYYY-MM-DD` | Valid ISO-8601 date strictly greater than `coa:testDate` |
| `coa:activeAnalyteName` | `string` | Quantified active compound or standardized botanical mass |
| `coa:labelClaimPerServing` | `number` | Positive numeric label claim |
| `coa:measuredAssayPerServing` | `number` | Non-negative assayed value; `(measured / claim) * 100` must fall inside `[toleranceMinPct, toleranceMaxPct]` |
| `coa:assayUnit` | `string` | One of `mg`, `mcg`, `ug`, `g`, `iu` |
| `coa:toleranceMinPct` | `number` | Lower acceptance bound (`50.0`–`100.0`) |
| `coa:toleranceMaxPct` | `number` | Upper acceptance bound (`100.0`–`150.0`) |
| `coa:heavyMetalsStatus` | `string` | Must equal `"PASS"` |
| `coa:arsenicPpm` | `number` | `0.0 <= value <= 1.5` ppm |
| `coa:cadmiumPpm` | `number` | `0.0 <= value <= 0.5` ppm |
| `coa:leadPpm` | `number` | `0.0 <= value <= 0.5` ppm |
| `coa:mercuryPpm` | `number` | `0.0 <= value <= 0.2` ppm |
| `coa:microbialStatus` | `string` | Must equal `"PASS"` |
| `vessel:architecture` | `string` | Structural description of primary container (e.g., gold-plated magnetic metal pocket compact or rigid paperboard cylinder) |
| `vessel:reusableHardware` | `boolean` | `true` for permanent refillable vessels; `false` for single-cycle containers |
| `vessel:moistureLightBarrier` | `string` | Barrier specification protecting hygroscopic or light-sensitive actives |
| `vessel:servingsPerVessel` | `integer` | Positive integer count of servings per primary vessel |

---

## Embedding in HTML / Liquid / Next.js

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Hush Sleep Gummies (0.35 mg Melatonin per Gummy)",
  "sku": "HERM-HUSH-20G",
  "brand": { "@type": "Brand", "name": "Hermetica Superfoods" },
  "additionalProperty": [
    { "@type": "PropertyValue", "propertyID": "coa:labelClaimPerServing", "name": "Label Claim", "value": 0.35, "unitText": "mg" }
  ]
}
</script>
```

---

## Running Tests

```bash
pytest -v
```

---

## Related Open Projects

- [**cpg-packaging-runway-engine**](https://github.com/mindexpansive/cpg-packaging-runway-engine) — Overseas packaging lead-time safety buffers, air-bridge split solver, and permanent vessel vs. barrier refill cohort margin model.
- [**hermetica-supplement-encyclopedia**](https://github.com/mindexpansive/hermetica-supplement-encyclopedia) — 15,600+ botanical & dietary supplement ingredient monographs live at [ingredients.hermeticasuperfoods.com](https://ingredients.hermeticasuperfoods.com).

## License

Released under the [MIT License](./LICENSE).

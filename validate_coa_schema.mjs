#!/usr/bin/env node
/**
 * supplement-coa-jsonld validator (Node.js ESM, zero external dependencies)
 * Mirrors `validate_coa_schema.py` for TypeScript / Next.js / Shopify Hydrogen build pipelines.
 *
 * Author: Christian Gallo Delgado — Hermetica Superfoods (LifeForce Liquids Corp.)
 * License: MIT
 */

import fs from "node:fs";

const ALLOWED_ASSAY_UNITS = new Set(["mg", "mcg", "ug", "g", "iu"]);
const HEAVY_METAL_CEILINGS_PPM = {
  "coa:arsenicPpm": 1.5,
  "coa:cadmiumPpm": 0.5,
  "coa:leadPpm": 0.5,
  "coa:mercuryPpm": 0.2,
};

const REQUIRED_KEYS = [
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
];

export function validateCoaJsonLd(doc) {
  const errors = [];
  const warnings = [];

  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    return { valid: false, errors: ["Root JSON-LD document must be an object"], warnings };
  }

  if (doc["@context"] !== "https://schema.org") {
    errors.push("@context must equal 'https://schema.org'");
  }
  const t = doc["@type"];
  const typeOk = t === "Product" || (Array.isArray(t) && t.includes("Product"));
  if (!typeOk) {
    errors.push("@type must be 'Product' or an array containing 'Product'");
  }
  if (typeof doc.name !== "string" || doc.name.trim().length < 2) {
    errors.push("name must be a non-empty string");
  }
  if (typeof doc.sku !== "string" || doc.sku.trim().length < 2) {
    errors.push("sku must be a non-empty string");
  }
  if (
    !doc.brand ||
    typeof doc.brand !== "object" ||
    !["Brand", "Organization"].includes(doc.brand["@type"]) ||
    !doc.brand.name
  ) {
    errors.push("brand must be a Brand or Organization object with a name");
  }

  if (!Array.isArray(doc.additionalProperty) || doc.additionalProperty.length === 0) {
    errors.push("additionalProperty must be a non-empty array");
    return { valid: false, sku: doc.sku ?? null, product_name: doc.name ?? null, errors, warnings };
  }

  const props = new Map();
  doc.additionalProperty.forEach((item, idx) => {
    if (!item || typeof item !== "object") {
      errors.push(`additionalProperty[${idx}] must be an object`);
      return;
    }
    if (item["@type"] !== "PropertyValue") {
      errors.push(`additionalProperty[${idx}].@type must be 'PropertyValue'`);
    }
    if (typeof item.propertyID !== "string" || !item.propertyID.includes(":")) {
      errors.push(`additionalProperty[${idx}].propertyID must be namespaced`);
      return;
    }
    if (props.has(item.propertyID)) {
      errors.push(`Duplicate propertyID '${item.propertyID}'`);
    }
    props.set(item.propertyID, item);
  });

  for (const key of REQUIRED_KEYS) {
    if (!props.has(key)) errors.push(`Missing required PropertyValue: ${key}`);
  }

  const val = (k) => (props.has(k) ? props.get(k).value : undefined);

  const lot = val("coa:batchLotNumber");
  if (typeof lot === "string" && lot.toUpperCase().startsWith("EXAMPLE-")) {
    warnings.push("Document uses an illustrative EXAMPLE-* lot identifier (reference fixture).");
  }
  if (val("coa:iso17025Accredited") !== true) {
    errors.push("coa:iso17025Accredited must be boolean true");
  }

  const unit = val("coa:assayUnit");
  if (typeof unit !== "string" || !ALLOWED_ASSAY_UNITS.has(unit.toLowerCase())) {
    errors.push(`Invalid coa:assayUnit: ${unit}`);
  }

  const claim = val("coa:labelClaimPerServing");
  const measured = val("coa:measuredAssayPerServing");
  const tolMin = val("coa:toleranceMinPct");
  const tolMax = val("coa:toleranceMaxPct");
  let computedRecoveryPct = null;

  if (
    typeof claim === "number" &&
    claim > 0 &&
    typeof measured === "number" &&
    typeof tolMin === "number" &&
    typeof tolMax === "number"
  ) {
    computedRecoveryPct = Number(((measured / claim) * 100).toFixed(2));
    if (computedRecoveryPct < tolMin || computedRecoveryPct > tolMax) {
      errors.push(
        `Active assay recovery ${computedRecoveryPct}% outside declared tolerance [${tolMin}%, ${tolMax}%]`
      );
    }
  } else {
    errors.push("Numeric assay fields must be valid numbers with positive label claim");
  }

  for (const stKey of ["coa:heavyMetalsStatus", "coa:microbialStatus"]) {
    if (val(stKey) !== "PASS") errors.push(`${stKey} must equal 'PASS'`);
  }
  for (const [hmKey, ceiling] of Object.entries(HEAVY_METAL_CEILINGS_PPM)) {
    const v = val(hmKey);
    if (typeof v !== "number" || v < 0 || v > ceiling) {
      errors.push(`${hmKey} (${v} ppm) invalid or above ceiling (${ceiling} ppm)`);
    }
  }
  if (typeof val("vessel:reusableHardware") !== "boolean") {
    errors.push("vessel:reusableHardware must be boolean");
  }
  const servings = val("vessel:servingsPerVessel");
  if (!Number.isInteger(servings) || servings <= 0) {
    errors.push("vessel:servingsPerVessel must be a positive integer");
  }

  return {
    valid: errors.length === 0,
    sku: doc.sku ?? null,
    product_name: doc.name ?? null,
    batch_lot_number: lot ?? null,
    computed_recovery_pct: computedRecoveryPct,
    errors,
    warnings,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    console.error("Usage: node validate_coa_schema.mjs <file.jsonld> [...]");
    process.exit(2);
  }
  let failed = false;
  for (const f of files) {
    const doc = JSON.parse(fs.readFileSync(f, "utf8"));
    const rep = validateCoaJsonLd(doc);
    if (!rep.valid) failed = true;
    console.log(
      `[${rep.valid ? "PASS" : "FAIL"}] ${f} — ${rep.product_name} (lot=${rep.batch_lot_number}, assay=${rep.computed_recovery_pct}% of label claim)`
    );
    for (const e of rep.errors) console.log(`  ERROR: ${e}`);
  }
  process.exit(failed ? 1 : 0);
}

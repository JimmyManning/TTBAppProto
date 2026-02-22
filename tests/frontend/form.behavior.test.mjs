import test from "node:test";
import assert from "node:assert/strict";

import {
  buildCountryOptions,
  collectAdditiveFlagValues,
  getFileSelectionStatus,
  sanitizeNumericWithDecimal,
} from "../../static/js/form.js";

test("numeric sanitization strips non-numeric chars and keeps one decimal", () => {
  assert.equal(sanitizeNumericWithDecimal("12a.3.4%"), "12.34");
  assert.equal(sanitizeNumericWithDecimal("abc"), "");
  assert.equal(sanitizeNumericWithDecimal("750"), "750");
});

test("50-image limit status messages are correct", () => {
  assert.equal(getFileSelectionStatus(0, 50), "");
  assert.equal(getFileSelectionStatus(50, 50), "50 image(s) selected.");
  assert.equal(getFileSelectionStatus(51, 50), "You selected 51 images. Maximum allowed is 50.");
});

test("country dropdown defaults to configured origin", () => {
  const options = buildCountryOptions(["Canada", "United States"], "United States");
  const selected = options.find((option) => option.selected);
  assert.equal(selected?.value, "United States");
});

test("additive checkbox mapping sets expected booleans", () => {
  const additiveFlags = [
    { key: "fdcYellow5", checkboxId: "flagFdcYellow5" },
    { key: "cochinealExtract", checkboxId: "flagCochinealExtract" },
  ];

  const values = collectAdditiveFlagValues(additiveFlags, (checkboxId) => checkboxId === "flagFdcYellow5");
  assert.deepEqual(values, {
    fdcYellow5: true,
    cochinealExtract: false,
  });
});

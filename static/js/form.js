export function sanitizeNumericWithDecimal(value) {
  const cleaned = String(value || "").replace(/[^0-9.]/g, "");
  const firstDotIndex = cleaned.indexOf(".");
  if (firstDotIndex < 0) return cleaned;
  return `${cleaned.slice(0, firstDotIndex + 1)}${cleaned.slice(firstDotIndex + 1).replace(/\./g, "")}`;
}

export function bindNumericOnlyInput(inputEl) {
  if (!inputEl) return;
  inputEl.addEventListener("input", () => {
    const sanitized = sanitizeNumericWithDecimal(inputEl.value);
    if (inputEl.value !== sanitized) {
      inputEl.value = sanitized;
    }
  });
}

export function getFileSelectionStatus(count, maxBatchImages) {
  if (!count) return "";
  if (count > maxBatchImages) {
    return `You selected ${count} images. Maximum allowed is ${maxBatchImages}.`;
  }
  return `${count} image(s) selected.`;
}

export function buildCountryOptions(countries, defaultOrigin) {
  return (countries || []).map((country) => ({
    value: country,
    label: country,
    selected: country === defaultOrigin,
  }));
}

export function initOriginSelect(originSelect, countries, defaultOrigin) {
  if (!originSelect) return;
  originSelect.innerHTML = "";
  buildCountryOptions(countries, defaultOrigin).forEach((country) => {
    const option = document.createElement("option");
    option.value = country.value;
    option.textContent = country.label;
    option.selected = country.selected;
    originSelect.appendChild(option);
  });
}

export function collectAdditiveFlagValues(additiveFlags, getCheckboxValue) {
  const output = {};
  (additiveFlags || []).forEach((flag) => {
    output[flag.key] = Boolean(getCheckboxValue(flag.checkboxId));
  });
  return output;
}

export function getExpected(config) {
  const {
    requiredFieldKeys,
    additiveFlags,
    ageYearsInput,
    netContentsInput,
    netContentsUnitInput,
    getElementById,
  } = config;

  const expected = Object.fromEntries(
    requiredFieldKeys.map((key) => {
      const el = getElementById(key);
      return [key, el ? String(el.value || "").trim() : ""];
    })
  );

  const alcoholRaw = expected.alcoholContent;
  const alcoholValue = Number.parseFloat(alcoholRaw);
  expected.alcoholContent = Number.isFinite(alcoholValue) ? alcoholValue : alcoholRaw;

  const netAmountRaw = String(netContentsInput?.value || "").trim();
  const netUnit = String(netContentsUnitInput?.value || "").trim();
  if (netAmountRaw && netUnit) {
    expected.netContents = `${netAmountRaw} ${netUnit}`;
  }

  const ageRaw = String(ageYearsInput?.value || "").trim();
  if (ageRaw) {
    const ageValue = Number.parseFloat(ageRaw);
    expected.ageYears = Number.isFinite(ageValue) ? ageValue : ageRaw;
  }

  const additiveValues = collectAdditiveFlagValues(additiveFlags, (checkboxId) => {
    const checkbox = getElementById(checkboxId);
    return checkbox?.checked;
  });

  return { ...expected, ...additiveValues };
}

export function getMissingExpectedFields(config) {
  const {
    expected,
    fieldLabels,
    requiredFieldKeys,
    netContentsInput,
    requiresAgeForClassCode,
  } = config;
  const issues = [];

  requiredFieldKeys.forEach((key) => {
    if (key === "alcoholContent") {
      if (!(typeof expected.alcoholContent === "number" && expected.alcoholContent > 0 && expected.alcoholContent <= 100)) {
        issues.push("Alcohol Content must be a number between 0 and 100.");
      }
      return;
    }

    if (!expected[key]) {
      issues.push(`${fieldLabels[key] || key} is required.`);
    }
  });

  const netAmountRaw = String(netContentsInput?.value || "").trim();
  if (!netAmountRaw || !/^\d+(?:\.\d+)?$/.test(netAmountRaw)) {
    issues.push("Net Contents amount must be a number.");
  }

  if (requiresAgeForClassCode(expected.classTypeCode) && !(typeof expected.ageYears === "number" && expected.ageYears > 0)) {
    issues.push("Age Statement (Years) is required for the selected class/type code.");
  }

  return issues;
}

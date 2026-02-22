let fields = {
  brandName: "Brand Name",
  classTypeCode: "Class/Type Code",
  alcoholContent: "Alcohol Content (%)",
  netContents: "Net Contents",
  bottler: "Bottler/Producer",
  bottlerAddress: "Bottler/Producer Address",
  origin: "Country of Origin",
};

const statusEl = document.getElementById("status");
const summaryEl = document.getElementById("summary");
const resultsEl = document.getElementById("results");
const resultTemplate = document.getElementById("resultTemplate");
const classTypeCodeInput = document.getElementById("classTypeCode");
const classCodeCategorySelect = document.getElementById("classCodeCategory");
const classCodeTypeSelect = document.getElementById("classCodeType");
const originSelect = document.getElementById("origin");
const ageYearsInput = document.getElementById("ageYears");
const ageYearsHint = document.getElementById("ageYearsHint");
const alcoholContentInput = document.getElementById("alcoholContent");
const netContentsInput = document.getElementById("netContents");
const labelFilesInput = document.getElementById("labelFiles");
let MAX_BATCH_IMAGES = 50;

const COUNTRIES = [
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia",
  "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium",
  "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
  "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad",
  "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica", "Côte d’Ivoire", "Croatia", "Cuba", "Cyprus",
  "Czechia", "Democratic People’s Republic of Korea", "Democratic Republic of the Congo", "Denmark", "Djibouti",
  "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia",
  "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana",
  "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary",
  "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan",
  "Kazakhstan", "Kenya", "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia",
  "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali",
  "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia",
  "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand",
  "Nicaragua", "Niger", "Nigeria", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Panama",
  "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Republic of Korea",
  "Romania", "Russian Federation", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
  "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal",
  "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia",
  "South Africa", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
  "Tajikistan", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Türkiye",
  "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United Republic of Tanzania",
  "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
  "Holy See", "State of Palestine"
];

let classCodeEntries = [];
let requiredFieldKeys = Object.keys(fields);

async function initFieldConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return;
    const config = await response.json();
    if (config && typeof config === "object") {
      if (config.fieldLabels && typeof config.fieldLabels === "object") {
        fields = { ...fields, ...config.fieldLabels };
      }
      if (Array.isArray(config.requiredFields) && config.requiredFields.length) {
        requiredFieldKeys = config.requiredFields.filter((key) => typeof key === "string" && key.trim());
      }
      if (typeof config.maxBatchImages === "number" && Number.isFinite(config.maxBatchImages)) {
        MAX_BATCH_IMAGES = config.maxBatchImages;
      }
    }
  } catch {
    // fallback to local defaults
  }
}

function sanitizeNumericWithDecimal(value) {
  const cleaned = String(value || "").replace(/[^0-9.]/g, "");
  const firstDotIndex = cleaned.indexOf(".");
  if (firstDotIndex < 0) return cleaned;
  return `${cleaned.slice(0, firstDotIndex + 1)}${cleaned.slice(firstDotIndex + 1).replace(/\./g, "")}`;
}

function bindNumericOnlyInput(inputEl) {
  if (!inputEl) return;
  inputEl.addEventListener("input", () => {
    const sanitized = sanitizeNumericWithDecimal(inputEl.value);
    if (inputEl.value !== sanitized) {
      inputEl.value = sanitized;
    }
  });
}

function initOriginSelect() {
  if (!originSelect) return;
  originSelect.innerHTML = "";
  COUNTRIES.forEach((country) => {
    const option = document.createElement("option");
    option.value = country;
    option.textContent = country;
    option.selected = country === "United States";
    originSelect.appendChild(option);
  });
}

function parseClassCodeTsv(tsvText) {
  return tsvText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const tabIndex = line.indexOf("\t");
      if (tabIndex < 0) return null;
      return {
        code: line.slice(0, tabIndex).trim(),
        label: line.slice(tabIndex + 1).trim(),
      };
    })
    .filter(Boolean);
}

function tokenizeLabel(label) {
  const stopWords = new Set([
    "OTHER",
    "AND",
    "OR",
    "OF",
    "THE",
    "UP",
    "UNDER",
    "WITH",
    "IN",
    "FB",
    "USB",
    "BIB",
  ]);

  return String(label || "")
    .toUpperCase()
    .replace(/[^A-Z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((token) => token.length >= 3 && !stopWords.has(token));
}

function getCategoryKey(code) {
  const match = String(code || "").match(/^(\d+)/);
  if (!match) return "misc";
  const firstDigit = match[1][0];
  return String(Number(firstDigit) * 100);
}

function getRangeLabelFromKey(categoryKey) {
  if (categoryKey === "misc") return "Misc";
  const start = Number(categoryKey);
  const end = start + 99;
  return `${String(start).padStart(3, "0")}-${String(end).padStart(3, "0")}`;
}

function getMostRecurringWords(entries) {
  const groupedEntries = entries.reduce((acc, entry) => {
    const key = getCategoryKey(entry.code);
    if (!acc[key]) acc[key] = [];
    acc[key].push(entry);
    return acc;
  }, {});

  const groupKeys = Object.keys(groupedEntries).sort((a, b) => {
    if (a === "misc") return 1;
    if (b === "misc") return -1;
    return Number(a) - Number(b);
  });

  const output = [];

  groupKeys.forEach((groupKey) => {
    const firstEntry = groupedEntries[groupKey].slice().sort(sortByCode)[0];
    if (!firstEntry) return;
    output.push({
      groupKey,
      rangeLabel: getRangeLabelFromKey(groupKey),
      name: firstEntry.label,
      value: groupKey,
    });
  });

  return output;
}

function sortByCode(a, b) {
  const aCode = a.code;
  const bCode = b.code;
  const aMatch = aCode.match(/^(\d+)/);
  const bMatch = bCode.match(/^(\d+)/);
  const aNum = aMatch ? Number(aMatch[1]) : Number.MAX_SAFE_INTEGER;
  const bNum = bMatch ? Number(bMatch[1]) : Number.MAX_SAFE_INTEGER;
  if (aNum !== bNum) return aNum - bNum;
  return aCode.localeCompare(bCode);
}

function requiresAgeForClassCode(code) {
  const normalizedCode = String(code || "").trim();
  if (!normalizedCode) return false;
  const entry = classCodeEntries.find((item) => item.code === normalizedCode);
  if (!entry) return false;
  const label = String(entry.label || "").toUpperCase();
  if (label.includes("UNBLENDED")) return false;
  return label.includes("SPIRIT WHISKY") || label.includes("BLENDED");
}

function updateAgeRequirementUi() {
  const requiresAge = requiresAgeForClassCode(classTypeCodeInput.value);
  ageYearsInput.required = requiresAge;
  ageYearsHint.textContent = requiresAge
    ? "Required for selected class/type code per Chapter 8."
    : "Optional unless class/type requires an age statement.";
}

function buildGuidedClassCodeSelectors(entries) {
  const recurringWords = getMostRecurringWords(entries);

  classCodeCategorySelect.innerHTML = `<option value="">Select common keyword</option>`;
  recurringWords.forEach(({ value, name, rangeLabel }) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${rangeLabel} — ${name}`;
    classCodeCategorySelect.appendChild(option);
  });

  function populateTypes(selectionValue) {
    const groupKey = String(selectionValue || "");
    const list = entries
      .filter((entry) => {
        if (!groupKey) return false;
        return getCategoryKey(entry.code) === groupKey;
      })
      .slice()
      .sort(sortByCode);

    classCodeTypeSelect.innerHTML = `<option value="">Select specific type/code</option>`;
    list.forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.code;
      option.textContent = `${entry.code} — ${entry.label}`;
      classCodeTypeSelect.appendChild(option);
    });
  }

  classCodeCategorySelect.addEventListener("change", () => {
    populateTypes(classCodeCategorySelect.value);
    classCodeTypeSelect.value = "";
  });

  classCodeTypeSelect.addEventListener("change", () => {
    if (classCodeTypeSelect.value) {
      classTypeCodeInput.value = classCodeTypeSelect.value;
      updateAgeRequirementUi();
    }
  });

  classTypeCodeInput.addEventListener("change", syncGuidedSelectionFromCode);
  classTypeCodeInput.addEventListener("input", syncGuidedSelectionFromCode);
  classTypeCodeInput.addEventListener("change", updateAgeRequirementUi);
  classTypeCodeInput.addEventListener("input", updateAgeRequirementUi);

  function syncLocal() {
    const code = classTypeCodeInput.value.trim();
    if (!code) return;

    const matchedEntry = entries.find((entry) => entry.code === code);
    if (!matchedEntry) return;

    const selectionValue = getCategoryKey(code);

    if (classCodeCategorySelect.value !== selectionValue) {
      classCodeCategorySelect.value = selectionValue;
      populateTypes(selectionValue);
    }

    const exists = [...classCodeTypeSelect.options].some((opt) => opt.value === code);
    if (exists) {
      classCodeTypeSelect.value = code;
    }
  }

  window.__syncGuidedClassCodeSelection = syncLocal;
}

function syncGuidedSelectionFromCode() {
  if (typeof window.__syncGuidedClassCodeSelection === "function") {
    window.__syncGuidedClassCodeSelection();
  }
}

async function initGuidedClassCodeSelection() {
  try {
    const response = await fetch("/static/class_type_codes.tsv");
    const tsv = await response.text();
    classCodeEntries = parseClassCodeTsv(tsv);
    buildGuidedClassCodeSelectors(classCodeEntries);
    syncGuidedSelectionFromCode();
  } catch {
    // optional helper UI only
  }
}

initFieldConfig();
initGuidedClassCodeSelection();
updateAgeRequirementUi();
bindNumericOnlyInput(alcoholContentInput);
bindNumericOnlyInput(netContentsInput);
initOriginSelect();

function getExpected() {
  const expected = Object.fromEntries(
    requiredFieldKeys.map((k) => {
      const el = document.getElementById(k);
      return [k, el ? el.value.trim() : ""];
    })
  );
  const alcoholRaw = expected.alcoholContent;
  const alcoholValue = Number.parseFloat(alcoholRaw);
  expected.alcoholContent = Number.isFinite(alcoholValue) ? alcoholValue : alcoholRaw;

  const netAmountRaw = document.getElementById("netContents").value.trim();
  const netUnit = document.getElementById("netContentsUnit").value.trim();
  if (netAmountRaw && netUnit) {
    expected.netContents = `${netAmountRaw} ${netUnit}`;
  }

  const ageRaw = ageYearsInput.value.trim();
  if (ageRaw) {
    const ageValue = Number.parseFloat(ageRaw);
    expected.ageYears = Number.isFinite(ageValue) ? ageValue : ageRaw;
  }

  expected.fdcYellow5 = document.getElementById("flagFdcYellow5").checked;
  expected.cochinealExtract = document.getElementById("flagCochinealExtract").checked;
  expected.carmine = document.getElementById("flagCarmine").checked;

  return expected;
}

function getMissingExpectedFields(expected) {
  const issues = [];

  requiredFieldKeys.forEach((key) => {
    if (key === "alcoholContent") {
      if (!(typeof expected.alcoholContent === "number" && expected.alcoholContent > 0 && expected.alcoholContent <= 100)) {
        issues.push("Alcohol Content must be a number between 0 and 100.");
      }
      return;
    }

    if (!expected[key]) {
      issues.push(`${fields[key]} is required.`);
    }
  });

  const netAmountRaw = netContentsInput.value.trim();
  if (!netAmountRaw || !/^\d+(?:\.\d+)?$/.test(netAmountRaw)) {
    issues.push("Net Contents amount must be a number.");
  }

  if (requiresAgeForClassCode(expected.classTypeCode) && !(typeof expected.ageYears === "number" && expected.ageYears > 0)) {
    issues.push("Age Statement (Years) is required for the selected class/type code.");
  }

  return issues;
}

async function validateViaBackend(files, expected) {
  const formData = new FormData();
  files.forEach((file) => formData.append("images", file));
  formData.append("expected", JSON.stringify(expected));

  const response = await fetch("/api/validate/batch", {
    method: "POST",
    body: formData,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Validation failed (${response.status})`);
  }

  return body;
}

function renderResultCard(filename, confidence, rawText, comparisons) {
  const clone = resultTemplate.content.cloneNode(true);
  clone.querySelector("h3").textContent = filename;
  clone.querySelector(".confidence").textContent = confidence;

  const tbody = clone.querySelector("tbody");
  comparisons.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.label}</td>
      <td>${row.expected || "—"}</td>
      <td>${row.detected || "—"}</td>
      <td><span class="badge ${row.pass ? "pass" : "fail"}">${row.pass ? "PASS" : "REVIEW"}</span></td>
    `;
    tbody.appendChild(tr);
  });

  clone.querySelector("pre").textContent = rawText || "No text detected.";
  resultsEl.appendChild(clone);
}

function renderSummary(total, autoPass, needsReview, elapsedMs) {
  summaryEl.innerHTML = `
    <div><strong>Total labels:</strong> ${total}</div>
    <div><strong>Auto-pass:</strong> ${autoPass}</div>
    <div><strong>Needs review:</strong> ${needsReview}</div>
    <div><strong>Elapsed:</strong> ${(elapsedMs / 1000).toFixed(2)}s</div>
  `;
}

labelFilesInput.addEventListener("change", () => {
  const count = labelFilesInput.files?.length || 0;
  if (!count) {
    statusEl.textContent = "";
    return;
  }
  if (count > MAX_BATCH_IMAGES) {
    statusEl.textContent = `You selected ${count} images. Maximum allowed is ${MAX_BATCH_IMAGES}.`;
  } else {
    statusEl.textContent = `${count} image(s) selected.`;
  }
});

document.getElementById("verifyBtn").addEventListener("click", async () => {
  const files = [...labelFilesInput.files];
  if (!files.length) {
    statusEl.textContent = "Select one or more label images.";
    return;
  }

  if (files.length > MAX_BATCH_IMAGES) {
    statusEl.textContent = `You can upload up to ${MAX_BATCH_IMAGES} images at a time.`;
    return;
  }

  const expected = getExpected();
  const issues = getMissingExpectedFields(expected);
  if (issues.length) {
    statusEl.textContent = `Please fix input issues: ${issues.join(" ")}`;
    return;
  }

  resultsEl.innerHTML = "";
  summaryEl.innerHTML = "";

  const started = performance.now();
  let autoPass = 0;

  statusEl.textContent = `Processing ${files.length} label(s)...`;

  try {
    const result = await validateViaBackend(files, expected);
    autoPass = result.autoPass || 0;

    (result.results || []).forEach((item) => {
      renderResultCard(
        item.filename || "label",
        "OCR source: backend",
        item.extractedText || "",
        item.comparisons || []
      );
    });

    const elapsed = performance.now() - started;
    renderSummary(result.total || files.length, autoPass, result.needsReview || 0, elapsed);
    statusEl.textContent = "Done.";
  } catch (error) {
    const elapsed = performance.now() - started;
    renderSummary(files.length, 0, files.length, elapsed);
    statusEl.textContent = `Error: ${error.message}`;
  }
});

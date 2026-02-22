const fields = {
  brandName: "Brand Name",
  classTypeCode: "Class/Type Code",
  alcoholContent: "Alcohol Content (%)",
  netContents: "Net Contents",
  bottler: "Bottler/Producer",
  origin: "Country of Origin",
};

const statusEl = document.getElementById("status");
const summaryEl = document.getElementById("summary");
const resultsEl = document.getElementById("results");
const resultTemplate = document.getElementById("resultTemplate");
const classTypeCodeInput = document.getElementById("classTypeCode");
const classCodeCategorySelect = document.getElementById("classCodeCategory");
const classCodeTypeSelect = document.getElementById("classCodeType");
const ageYearsInput = document.getElementById("ageYears");
const ageYearsHint = document.getElementById("ageYearsHint");
const MAX_BATCH_IMAGES = 50;

let classCodeEntries = [];

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

initGuidedClassCodeSelection();
updateAgeRequirementUi();

function getExpected() {
  const expected = Object.fromEntries(Object.keys(fields).map((k) => [k, document.getElementById(k).value.trim()]));
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

  return expected;
}

function getMissingExpectedFields(expected) {
  return Object.keys(fields).filter((key) => {
    if (key === "alcoholContent") {
      return !(typeof expected.alcoholContent === "number" && expected.alcoholContent > 0 && expected.alcoholContent <= 100);
    }
    return !expected[key];
  }).concat(
    requiresAgeForClassCode(expected.classTypeCode) && !(typeof expected.ageYears === "number" && expected.ageYears > 0)
      ? ["ageYears"]
      : []
  );
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

document.getElementById("verifyBtn").addEventListener("click", async () => {
  const files = [...document.getElementById("labelFiles").files];
  if (!files.length) {
    statusEl.textContent = "Select one or more label images.";
    return;
  }

  if (files.length > MAX_BATCH_IMAGES) {
    statusEl.textContent = `You can upload up to ${MAX_BATCH_IMAGES} images at a time.`;
    return;
  }

  const expected = getExpected();
  const missing = getMissingExpectedFields(expected);
  if (missing.length) {
    statusEl.textContent = `Fill all required fields before verification (missing: ${missing.join(", ")}).`;
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

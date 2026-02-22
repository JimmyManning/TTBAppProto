import { validateBatchLabels } from "./api-client.js";
import {
  bindNumericOnlyInput,
  getExpected,
  getFileSelectionStatus,
  getMissingExpectedFields,
  initOriginSelect,
} from "./form.js";
import {
  createAgeRequirementChecker,
  initGuidedClassCodeSelection,
} from "./guided-selection.js";
import { renderResultCard, renderSummary } from "./render.js";

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
const netContentsUnitInput = document.getElementById("netContentsUnit");
const labelFilesInput = document.getElementById("labelFiles");
const verifyBtn = document.getElementById("verifyBtn");

let fieldLabels = {
  brandName: "Brand Name",
  classTypeCode: "Class/Type Code",
  alcoholContent: "Alcohol Content (%)",
  netContents: "Net Contents",
  bottler: "Bottler/Producer",
  bottlerAddress: "Bottler/Producer Address",
  origin: "Country of Origin",
};
let requiredFieldKeys = Object.keys(fieldLabels);
let maxBatchImages = 50;
let countries = [];
let defaultOrigin = "United States";
let additiveFlags = [
  { key: "fdcYellow5", checkboxId: "flagFdcYellow5" },
  { key: "cochinealExtract", checkboxId: "flagCochinealExtract" },
  { key: "carmine", checkboxId: "flagCarmine" },
];
let requiresAgeForClassCode = () => false;

function updateAgeRequirementUi() {
  const requiresAge = requiresAgeForClassCode(classTypeCodeInput.value);
  ageYearsInput.required = requiresAge;
  ageYearsHint.textContent = requiresAge
    ? "Required for selected class/type code per Chapter 8."
    : "Optional unless class/type requires an age statement.";
}

async function initConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return;
    const config = await response.json();

    if (config.fieldLabels && typeof config.fieldLabels === "object") {
      fieldLabels = { ...fieldLabels, ...config.fieldLabels };
    }
    if (Array.isArray(config.requiredFields) && config.requiredFields.length) {
      requiredFieldKeys = config.requiredFields.filter((key) => typeof key === "string" && key.trim());
    }
    if (typeof config.maxBatchImages === "number" && Number.isFinite(config.maxBatchImages)) {
      maxBatchImages = config.maxBatchImages;
    }
    if (Array.isArray(config.countries)) {
      countries = config.countries;
    }
    if (typeof config.defaultOrigin === "string" && config.defaultOrigin.trim()) {
      defaultOrigin = config.defaultOrigin;
    }
    if (Array.isArray(config.additiveFlags) && config.additiveFlags.length) {
      additiveFlags = config.additiveFlags;
    }
  } catch {
    // use defaults
  }
}

function bindFileSelectionStatus() {
  labelFilesInput.addEventListener("change", () => {
    const count = labelFilesInput.files?.length || 0;
    statusEl.textContent = getFileSelectionStatus(count, maxBatchImages);
  });
}

async function init() {
  await initConfig();
  initOriginSelect(originSelect, countries, defaultOrigin);

  bindNumericOnlyInput(alcoholContentInput);
  bindNumericOnlyInput(netContentsInput);
  bindFileSelectionStatus();

  const classEntries = await initGuidedClassCodeSelection({
    classTypeCodeInput,
    classCodeCategorySelect,
    classCodeTypeSelect,
    updateAgeRequirementUi,
  });
  requiresAgeForClassCode = createAgeRequirementChecker(classEntries);
  updateAgeRequirementUi();

  verifyBtn.addEventListener("click", async () => {
    const files = [...(labelFilesInput.files || [])];
    if (!files.length) {
      statusEl.textContent = "Select one or more label images.";
      return;
    }
    if (files.length > maxBatchImages) {
      statusEl.textContent = `You can upload up to ${maxBatchImages} images at a time.`;
      return;
    }

    const expected = getExpected({
      requiredFieldKeys,
      additiveFlags,
      ageYearsInput,
      netContentsInput,
      netContentsUnitInput,
      getElementById: (id) => document.getElementById(id),
    });

    const issues = getMissingExpectedFields({
      expected,
      fieldLabels,
      requiredFieldKeys,
      netContentsInput,
      requiresAgeForClassCode,
    });
    if (issues.length) {
      statusEl.textContent = `Please fix input issues: ${issues.join(" ")}`;
      return;
    }

    resultsEl.innerHTML = "";
    summaryEl.innerHTML = "";

    const started = performance.now();
    statusEl.textContent = `Processing ${files.length} label(s)...`;

    try {
      const result = await validateBatchLabels(files, expected);
      (result.results || []).forEach((item) => {
        renderResultCard(
          resultTemplate,
          resultsEl,
          item.filename || "label",
          "OCR source: backend",
          item.extractedText || "",
          item.comparisons || []
        );
      });

      const elapsed = performance.now() - started;
      renderSummary(summaryEl, result.total || files.length, result.autoPass || 0, result.needsReview || 0, elapsed);
      statusEl.textContent = "Done.";
    } catch (error) {
      const elapsed = performance.now() - started;
      renderSummary(summaryEl, files.length, 0, files.length, elapsed);
      statusEl.textContent = `Error: ${error.message || "Unexpected error"}`;
    }
  });
}

init();

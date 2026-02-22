export function parseClassCodeTsv(tsvText) {
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

function getGroupChoices(entries) {
  const grouped = entries.reduce((acc, entry) => {
    const key = getCategoryKey(entry.code);
    if (!acc[key]) acc[key] = [];
    acc[key].push(entry);
    return acc;
  }, {});

  const groupKeys = Object.keys(grouped).sort((a, b) => {
    if (a === "misc") return 1;
    if (b === "misc") return -1;
    return Number(a) - Number(b);
  });

  return groupKeys
    .map((groupKey) => {
      const firstEntry = grouped[groupKey].slice().sort(sortByCode)[0];
      if (!firstEntry) return null;
      return {
        groupKey,
        rangeLabel: getRangeLabelFromKey(groupKey),
        name: firstEntry.label,
        value: groupKey,
      };
    })
    .filter(Boolean);
}

export function createAgeRequirementChecker(entries) {
  return (code) => {
    const normalizedCode = String(code || "").trim();
    if (!normalizedCode) return false;
    const entry = entries.find((item) => item.code === normalizedCode);
    if (!entry) return false;
    const label = String(entry.label || "").toUpperCase();
    if (label.includes("UNBLENDED")) return false;
    return label.includes("SPIRIT WHISKY") || label.includes("BLENDED");
  };
}

export async function initGuidedClassCodeSelection(elements) {
  const {
    classTypeCodeInput,
    classCodeCategorySelect,
    classCodeTypeSelect,
    updateAgeRequirementUi,
  } = elements;

  try {
    const response = await fetch("/static/class_type_codes.tsv");
    const tsv = await response.text();
    const entries = parseClassCodeTsv(tsv);

    const recurring = getGroupChoices(entries);
    classCodeCategorySelect.innerHTML = `<option value="">Select common keyword</option>`;
    recurring.forEach(({ value, name, rangeLabel }) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = `${rangeLabel} — ${name}`;
      classCodeCategorySelect.appendChild(option);
    });

    function populateTypes(selectionValue) {
      const groupKey = String(selectionValue || "");
      const list = entries
        .filter((entry) => groupKey && getCategoryKey(entry.code) === groupKey)
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

    function syncGuidedSelectionFromCode() {
      const code = classTypeCodeInput.value.trim();
      if (!code) return;
      const matched = entries.find((entry) => entry.code === code);
      if (!matched) return;

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

    syncGuidedSelectionFromCode();
    return entries;
  } catch {
    return [];
  }
}

export function renderResultCard(resultTemplate, resultsEl, filename, confidence, rawText, comparisons) {
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

export function renderSummary(summaryEl, total, autoPass, needsReview, elapsedMs) {
  summaryEl.innerHTML = `
    <div><strong>Total labels:</strong> ${total}</div>
    <div><strong>Auto-pass:</strong> ${autoPass}</div>
    <div><strong>Needs review:</strong> ${needsReview}</div>
    <div><strong>Elapsed:</strong> ${(elapsedMs / 1000).toFixed(2)}s</div>
  `;
}

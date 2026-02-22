export async function validateBatchLabels(files, expected) {
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

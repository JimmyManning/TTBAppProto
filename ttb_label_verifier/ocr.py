"""OCR helper functions for uploaded label images."""

import importlib
import time
from io import BytesIO

from ttb_label_verifier.validators.text import similarity

try:
    pytesseract = importlib.import_module("pytesseract")
except Exception:  # pragma: no cover
    pytesseract = None

try:
    Image = importlib.import_module("PIL.Image")
    ImageEnhance = importlib.import_module("PIL.ImageEnhance")
    ImageFilter = importlib.import_module("PIL.ImageFilter")
    ImageOps = importlib.import_module("PIL.ImageOps")
    UnidentifiedImageError = importlib.import_module("PIL").UnidentifiedImageError
except Exception:  # pragma: no cover
    Image = None
    ImageEnhance = None
    ImageFilter = None
    ImageOps = None
    UnidentifiedImageError = Exception

_TESSERACT_READY: bool | None = None
_MAX_DIMENSION = 1800
_OCR_CALL_TIMEOUT_SECONDS = 8
_OCR_QUICK_TIMEOUT_SECONDS = 4
_OCR_TOTAL_BUDGET_SECONDS = 20
_FAST_FIRST_PASS_MIN_ALNUM = 90


def ocr_token_is_close(expected_token: str, observed_tokens: list[str]) -> bool:
    """Return True when an OCR token reasonably matches the expected token.

    This helper is designed for OCR noise tolerance (e.g. 0/O, 1/l, rn/m).
    """
    expected = (expected_token or "").strip().lower()
    if not expected:
        return True

    tokens = [token.strip().lower() for token in (observed_tokens or []) if token and token.strip()]
    token_set = set(tokens)

    if expected in token_set:
        return True

    for token in tokens:
        if token.startswith(expected) or expected.startswith(token):
            if abs(len(token) - len(expected)) <= 2:
                return True

    threshold = 0.84 if len(expected) >= 6 else 0.9
    for token in tokens:
        if similarity(expected, token) >= threshold:
            return True

    return False


def _score_ocr_text(text: str) -> int:
    """Score OCR output quality by amount of useful alphanumeric content."""
    cleaned = "".join(ch for ch in (text or "") if ch.isalnum())
    return len(cleaned)


def _trim_borders(image: Image.Image) -> Image.Image:
    """Trim empty borders to focus OCR on label content."""
    try:
        gray = image.convert("L")
        inverted = ImageOps.invert(gray)
        bbox = inverted.getbbox()
    except Exception:
        return image

    if not bbox:
        return image
    cropped = image.crop(bbox)
    width, height = cropped.size
    if width < 40 or height < 40:
        return image
    return cropped


def _exif_transpose_safe(image: Image.Image) -> Image.Image:
    """Apply EXIF transpose when available; otherwise return original."""
    transpose = getattr(ImageOps, "exif_transpose", None)
    if callable(transpose):
        try:
            return transpose(image)
        except Exception:
            return image
    return image


def _resample_filter(name: str):
    """Return a Pillow resampling constant compatible across versions."""
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None and hasattr(resampling, name):
        return getattr(resampling, name)
    fallback = getattr(Image, name, None)
    if fallback is not None:
        return fallback
    if name == "LANCZOS":
        return getattr(Image, "BICUBIC", 3)
    if name == "NEAREST":
        return getattr(Image, "BILINEAR", 2)
    return getattr(Image, "BILINEAR", 2)


def _should_try_invert(gray_image: Image.Image) -> bool:
    """Return True when image appears dark with light text-like regions."""
    try:
        histogram = gray_image.histogram()
        total = sum(histogram)
        if total <= 0:
            return False

        mean_luma = sum(index * count for index, count in enumerate(histogram)) / float(total)
        dark_ratio = sum(histogram[:86]) / float(total)
        bright_ratio = sum(histogram[170:]) / float(total)

        # Favor inversion for predominantly dark images that still contain bright strokes.
        return mean_luma < 110 and dark_ratio >= 0.45 and bright_ratio >= 0.08
    except Exception:
        return False


def _preprocess_variants(image: Image.Image) -> list[Image.Image]:
    """Build image variants to improve OCR recall across varied label photos."""
    base = _trim_borders(_exif_transpose_safe(image)).convert("RGB")
    max_side = max(base.width, base.height)
    if max_side > _MAX_DIMENSION:
        scale = _MAX_DIMENSION / float(max_side)
        lanczos = _resample_filter("LANCZOS")
        base = base.resize((max(1, int(base.width * scale)), max(1, int(base.height * scale))), lanczos)

    base_gray = base.convert("L")
    denoised = base_gray.filter(ImageFilter.MedianFilter(size=3))
    auto = ImageOps.autocontrast(denoised)
    enhanced = ImageEnhance.Contrast(auto).enhance(2.4)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    thresholded_150 = sharpened.point(lambda p: 255 if p > 150 else 0)
    thresholded_175 = sharpened.point(lambda p: 255 if p > 175 else 0)

    lanczos = _resample_filter("LANCZOS")
    nearest = _resample_filter("NEAREST")
    resized_gray = enhanced.resize((max(1, int(enhanced.width * 1.5)), max(1, int(enhanced.height * 1.5))), lanczos)
    resized_bw = thresholded_150.resize((max(1, int(thresholded_150.width * 1.5)), max(1, int(thresholded_150.height * 1.5))), nearest)

    inverted_variants: list[Image.Image] = []
    if _should_try_invert(base_gray):
        inv_gray = ImageOps.invert(base_gray)
        inv_auto = ImageOps.autocontrast(inv_gray)
        inv_enhanced = ImageEnhance.Contrast(inv_auto).enhance(2.0)
        inv_thresholded = inv_enhanced.point(lambda p: 255 if p > 150 else 0)
        inverted_variants = [inv_gray, inv_enhanced, inv_thresholded]

    # Order strongest/most useful variants first for faster early exits.
    variants = [
        base,
        enhanced,
        thresholded_150,
        *inverted_variants,
        resized_gray,
        base_gray,
        denoised,
        auto,
        sharpened,
        thresholded_175,
        resized_bw,
    ]

    for angle in (90, 180, 270):
        variants.append(base.rotate(angle, expand=True))

    return variants


def _safe_conf_to_int(value: str) -> int:
    """Convert tesseract confidence strings to int safely."""
    try:
        return int(float(value))
    except Exception:
        return -1


def _ocr_candidate(variant: Image.Image, config: str) -> tuple[str, float, int, float]:
    """Return OCR text, score, alnum count, and avg confidence for one run."""
    output = getattr(pytesseract, "Output", None)
    if output is None:
        text = pytesseract.image_to_string(variant, lang="eng", config=config, timeout=_OCR_CALL_TIMEOUT_SECONDS) or ""
        alnum = _score_ocr_text(text)
        return text, float(alnum), alnum, 0.0

    try:
        data = pytesseract.image_to_data(
            variant,
            lang="eng",
            config=config,
            output_type=output.DICT,
            timeout=_OCR_CALL_TIMEOUT_SECONDS,
        )
    except Exception:
        return "", 0.0, 0, 0.0

    words = []
    conf_values = []
    for item_text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        token = (item_text or "").strip()
        if token:
            words.append(token)
        conf_i = _safe_conf_to_int(conf)
        if conf_i >= 0:
            conf_values.append(conf_i)

    text = "\n".join(words)

    avg_conf = (sum(conf_values) / len(conf_values)) if conf_values else 0.0
    alnum = _score_ocr_text(text)
    weighted_score = float(alnum) + avg_conf * 4.0
    return text, weighted_score, alnum, avg_conf


def _quick_ocr_candidate(variant: Image.Image, config: str) -> tuple[str, int]:
    """Run a faster OCR attempt without confidence extraction."""
    try:
        text = pytesseract.image_to_string(
            variant,
            lang="eng",
            config=config,
            timeout=_OCR_QUICK_TIMEOUT_SECONDS,
        ) or ""
    except Exception:
        return "", 0
    return text, _score_ocr_text(text)


def _extract_best_text(image: Image.Image) -> str:
    """Run OCR with multiple variants/configs and return best-scoring text."""
    core_configs = [
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
        "--oem 3 --psm 4",
    ]
    extended_configs = ["--oem 3 --psm 3"]

    variants = _preprocess_variants(image)
    rotated_variants = variants[-3:] if len(variants) >= 3 else []
    non_rotated_variants = variants[:-3] if len(variants) >= 3 else variants
    core_variants = non_rotated_variants[:4]
    extended_variants = non_rotated_variants[4:10]
    started_at = time.monotonic()

    # Fast first pass: quick string extraction on strongest variants.
    fast_variants = core_variants[:2]
    fast_configs = ["--oem 3 --psm 6", "--oem 3 --psm 11"]
    fast_best_text = ""
    fast_best_alnum = 0
    for variant in fast_variants:
        for config in fast_configs:
            text, alnum = _quick_ocr_candidate(variant, config)
            if alnum > fast_best_alnum:
                fast_best_alnum = alnum
                fast_best_text = text
    if fast_best_alnum >= _FAST_FIRST_PASS_MIN_ALNUM:
        return fast_best_text

    best_text = ""
    best_score = -1.0
    best_alnum = 0
    best_avg_conf = 0.0

    for variant in core_variants:
        for config in core_configs:
            if time.monotonic() - started_at > _OCR_TOTAL_BUDGET_SECONDS:
                return best_text
            text, score, alnum, avg_conf = _ocr_candidate(variant, config)
            if score > best_score:
                best_score = score
                best_text = text
                best_alnum = alnum
                best_avg_conf = avg_conf

    # Early-exit when we already have high-confidence, sufficiently rich text.
    if best_avg_conf >= 60.0 and best_alnum >= 120:
        return best_text

    for variant in core_variants:
        for config in extended_configs:
            if time.monotonic() - started_at > _OCR_TOTAL_BUDGET_SECONDS:
                return best_text
            text, score, alnum, avg_conf = _ocr_candidate(variant, config)
            if score > best_score:
                best_score = score
                best_text = text
                best_alnum = alnum
                best_avg_conf = avg_conf

    if best_avg_conf >= 55.0 and best_alnum >= 100:
        return best_text

    for variant in extended_variants:
        for config in core_configs:
            if time.monotonic() - started_at > _OCR_TOTAL_BUDGET_SECONDS:
                return best_text
            text, score, _alnum, _avg_conf = _ocr_candidate(variant, config)
            if score > best_score:
                best_score = score
                best_text = text

    # Rotated passes are very expensive; only run when text quality is still weak.
    if best_avg_conf < 45.0 and best_alnum < 80:
        for variant in rotated_variants:
            for config in extended_configs:
                if time.monotonic() - started_at > _OCR_TOTAL_BUDGET_SECONDS:
                    return best_text
                text, score, _alnum, _avg_conf = _ocr_candidate(variant, config)
                if score > best_score:
                    best_score = score
                    best_text = text

    return best_text


def ocr_image_file(file_storage) -> tuple[str | None, str | None]:
    """Extract text from an uploaded image file.

    Args:
        file_storage: Werkzeug file storage object.

    Returns:
        Tuple of (extracted_text, error_message). One value is `None`.
    """
    if pytesseract is None or Image is None or ImageEnhance is None or ImageFilter is None or ImageOps is None:
        return None, "OCR dependencies not installed. Install pillow and pytesseract."

    global _TESSERACT_READY
    if _TESSERACT_READY is None:
        try:
            _ = pytesseract.get_tesseract_version()
            _TESSERACT_READY = True
        except Exception:
            _TESSERACT_READY = False
    if not _TESSERACT_READY:
        return None, "Tesseract binary not found. Install Tesseract OCR on the host."

    if not file_storage:
        return None, "No image file provided"

    try:
        raw_bytes = file_storage.read()
        image = Image.open(BytesIO(raw_bytes))
        text = _extract_best_text(image)
        return text or "", None
    except UnidentifiedImageError:
        return None, "Uploaded file is not a valid image"
    except Exception as exc:  # pragma: no cover
        return None, f"OCR failed: {exc}"

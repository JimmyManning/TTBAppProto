"""Generate 100 synthetic label images + metadata for app testing.

This creates a deterministic mix of designed PASS/FAIL samples.
FAIL samples include a declared failure reason so expected outcome is known beforehand.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tests" / "synthetic_dataset"
IMG_DIR = OUT_DIR / "images"
TSV_PATH = ROOT / "static" / "class_type_codes.tsv"

TOTAL = 100
PASS_COUNT = 60
SEED = 20260221


def get_required_warning() -> str:
    """Return backend-required government warning text."""
    from ttb_label_verifier.validation import REQUIRED_GOV_WARNING

    return REQUIRED_GOV_WARNING


def load_class_codes(path: Path) -> list[tuple[str, str]]:
    """Load class/type code rows from TSV as `(code, label)` pairs."""
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "\t" not in line:
            continue
        code, label = line.split("\t", 1)
        code = code.strip()
        label = label.strip()
        if code and label:
            rows.append((code, label))
    return rows


def pick_font(size: int) -> ImageFont.ImageFont:
    """Pick a readable font at the requested size, with fallback."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def pick_fonts() -> dict[str, ImageFont.ImageFont]:
    """Build a small font set for label rendering."""
    return {
        "title": pick_font(54),
        "subtitle": pick_font(34),
        "body": pick_font(28),
        "small": pick_font(22),
    }


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Wrap text to fit pixel width constraints."""
    wrapped: list[str] = []
    for paragraph in text.split("\n"):
        para = paragraph.strip()
        if not para:
            wrapped.append("")
            continue
        words = para.split()
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                wrapped.append(current)
                current = word
        wrapped.append(current)
    return wrapped


def choose_product_style(label_name: str, idx: int) -> str:
    """Choose visual bottle style (beer/wine/spirits) from label hints and index."""
    upper = label_name.upper()
    if any(token in upper for token in ["ALE", "LAGER", "STOUT", "PILSNER", "BEER"]):
        return "beer"
    if any(token in upper for token in ["WINE", "PORT", "SHERRY", "CHAMPAGNE"]):
        return "wine"
    # Distribute a mixed visual set for testing variety even with spirits-centric labels.
    cycle = ["spirits", "wine", "beer", "spirits", "spirits"]
    return cycle[idx % len(cycle)]


def draw_text_image(text: str, dest: Path, fonts: dict[str, ImageFont.ImageFont], product_style: str) -> None:
    """Render synthetic labels as stylized bottle mockups (beer/wine/spirits)."""
    width, height = 2200, 3000
    palette = {
        "beer": {"bg": "#efe8db", "glass": "#8f5a2a", "label": "#f4e6bf", "ink": "#1b140d", "foil": "#d8b56a"},
        "wine": {"bg": "#f3f0f4", "glass": "#3b4f3d", "label": "#f8f3e6", "ink": "#211e1a", "foil": "#6e2a3c"},
        "spirits": {"bg": "#edf2f8", "glass": "#566f86", "label": "#f9f6ef", "ink": "#102032", "foil": "#c7a453"},
    }[product_style]

    image = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(image)

    bottle_left, bottle_top = 640, 220
    bottle_right, bottle_bottom = 1560, 2780

    if product_style == "beer":
        neck_left, neck_top = 900, 120
        neck_right, neck_bottom = 1300, 520
    elif product_style == "wine":
        neck_left, neck_top = 980, 80
        neck_right, neck_bottom = 1220, 680
    else:
        neck_left, neck_top = 920, 100
        neck_right, neck_bottom = 1280, 580

    draw.ellipse((760, 2720, 1440, 2870), fill="#00000022")
    draw.rounded_rectangle((bottle_left, bottle_top, bottle_right, bottle_bottom), radius=90, fill=palette["glass"])
    draw.rounded_rectangle((neck_left, neck_top, neck_right, neck_bottom), radius=45, fill=palette["glass"])
    draw.rectangle((neck_left - 20, neck_top - 35, neck_right + 20, neck_top + 35), fill=palette["foil"])

    front_label = (760, 760, 1440, 1840)
    back_label = (770, 1920, 1430, 2630)
    draw.rounded_rectangle(front_label, radius=24, fill=palette["label"], outline="#00000033", width=4)
    draw.rounded_rectangle(back_label, radius=20, fill=palette["label"], outline="#00000022", width=3)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    brand = lines[0] if lines else "SYNTHETIC LABEL"
    class_type = lines[1] if len(lines) > 1 else "CLASS TYPE"
    core_fields = lines[2:7] if len(lines) > 2 else []
    warning_text = "\n".join(lines[7:]) if len(lines) > 7 else ""

    x1, y1, x2, y2 = front_label
    content_w = x2 - x1 - 70
    y = y1 + 35
    for line in _wrap_text(draw, brand, fonts["title"], content_w)[:2]:
        draw.text((x1 + 35, y), line, fill=palette["ink"], font=fonts["title"])
        y = draw.textbbox((x1 + 35, y), line, font=fonts["title"])[3] + 8

    for line in _wrap_text(draw, class_type, fonts["subtitle"], content_w)[:3]:
        draw.text((x1 + 35, y), line, fill=palette["ink"], font=fonts["subtitle"])
        y = draw.textbbox((x1 + 35, y), line, font=fonts["subtitle"])[3] + 6

    y += 10
    for field in core_fields:
        for line in _wrap_text(draw, field, fonts["body"], content_w):
            draw.text((x1 + 35, y), line, fill=palette["ink"], font=fonts["body"])
            y = draw.textbbox((x1 + 35, y), line, font=fonts["body"])[3] + 4

    bx1, by1, bx2, by2 = back_label
    back_w = bx2 - bx1 - 50
    y = by1 + 20
    draw.text((bx1 + 25, y), "GOVERNMENT WARNING", fill=palette["ink"], font=fonts["subtitle"])
    y = draw.textbbox((bx1 + 25, y), "GOVERNMENT WARNING", font=fonts["subtitle"])[3] + 8
    warning_lines = _wrap_text(draw, warning_text or "No warning text", fonts["small"], back_w)
    for line in warning_lines:
        if y > by2 - 40:
            break
        draw.text((bx1 + 25, y), line, fill=palette["ink"], font=fonts["small"])
        y = draw.textbbox((bx1 + 25, y), line, font=fonts["small"])[3] + 2

    image.save(dest, format="PNG")


def build_expected(code: str, abv_percent: float, idx: int) -> dict[str, object]:
    """Build expected metadata payload for one synthetic sample."""
    brand = f"COPILOT TEST DISTILLERY {idx:03d}"
    return {
        "brandName": brand,
        "classTypeCode": code,
        "alcoholContent": abv_percent,
        "netContents": "750 mL",
        "bottler": f"Bottled by {brand}, Frankfort, KY",
        "origin": "Product of USA",
    }


def build_pass_text(expected: dict[str, object], label_name: str) -> str:
    """Build OCR text body designed to pass validation."""
    abv = float(expected["alcoholContent"])
    proof = int(round(abv * 2))
    required_warning = get_required_warning()
    parts = [
        str(expected["brandName"]),
        f"{label_name}",
        f"Class Type {expected['classTypeCode']}",
        f"{abv:g}% Alc./Vol. ({proof} Proof)",
        str(expected["netContents"]),
        str(expected["bottler"]),
        str(expected["origin"]),
        required_warning,
    ]
    return "\n".join(parts)


def build_fail_text(expected: dict[str, object], label_name: str, reason: str) -> str:
    """Build OCR text body designed to fail for a known reason."""
    abv = float(expected["alcoholContent"])
    proof = int(round(abv * 2))
    required_warning = get_required_warning()
    base_parts = [
        str(expected["brandName"]),
        f"{label_name}",
        f"Class Type {expected['classTypeCode']}",
        str(expected["netContents"]),
        str(expected["bottler"]),
        str(expected["origin"]),
    ]

    if reason == "abv_not_allowed":
        base_parts.insert(3, f"{abv:g}% ABV")
        base_parts.append(required_warning)
    elif reason == "proof_mismatch":
        base_parts.insert(3, f"{abv:g}% Alc./Vol. ({proof - 10} Proof)")
        base_parts.append(required_warning)
    elif reason == "missing_warning":
        base_parts.insert(3, f"{abv:g}% Alc./Vol. ({proof} Proof)")
    elif reason == "wrong_origin":
        base_parts[5] = "Imported from Mars"
        base_parts.insert(3, f"{abv:g}% Alc./Vol. ({proof} Proof)")
        base_parts.append(required_warning)
    elif reason == "wrong_class_code":
        wrong_code = "999" if str(expected["classTypeCode"]) != "999" else "100"
        base_parts[2] = f"Class Type {wrong_code}"
        base_parts.insert(3, f"{abv:g}% Alc./Vol. ({proof} Proof)")
        base_parts.append(required_warning)
    else:
        raise ValueError(f"Unsupported fail reason: {reason}")

    return "\n".join(base_parts)


def main() -> None:
    """Generate synthetic image set and metadata manifests."""
    random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    class_codes = load_class_codes(TSV_PATH)
    if not class_codes:
        raise RuntimeError("No class codes found in static/class_type_codes.tsv")

    fonts = pick_fonts()
    fail_reasons = [
        "abv_not_allowed",
        "proof_mismatch",
        "missing_warning",
        "wrong_origin",
        "wrong_class_code",
    ]

    rows: list[dict[str, object]] = []
    for i in range(1, TOTAL + 1):
        code, label = random.choice(class_codes)
        abv = random.choice([35.0, 40.0, 42.5, 45.0, 46.5, 50.0])
        expected = build_expected(code=code, abv_percent=abv, idx=i)

        designed_pass = i <= PASS_COUNT
        fail_reason = "" if designed_pass else random.choice(fail_reasons)

        if designed_pass:
            image_text = build_pass_text(expected, label)
        else:
            image_text = build_fail_text(expected, label, fail_reason)

        filename = f"label_{i:03d}.png"
        image_path = IMG_DIR / filename
        product_style = choose_product_style(label, i)
        draw_text_image(image_text, image_path, fonts, product_style)

        rows.append(
            {
                "id": i,
                "image": f"images/{filename}",
                "designedOutcome": "pass" if designed_pass else "fail",
                "designedFailureReason": fail_reason,
                "expected": expected,
                "style": product_style,
                "notes": "Designed expectation before OCR runtime.",
            }
        )

    manifest_json = OUT_DIR / "metadata.json"
    manifest_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    manifest_jsonl = OUT_DIR / "metadata.jsonl"
    with manifest_jsonl.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    manifest_csv = OUT_DIR / "metadata.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "id",
                "image",
                "designedOutcome",
                "designedFailureReason",
                "brandName",
                "classTypeCode",
                "alcoholContent",
                "netContents",
                "bottler",
                "origin",
            ]
        )
        for row in rows:
            expected = row["expected"]
            writer.writerow(
                [
                    row["id"],
                    row["image"],
                    row["designedOutcome"],
                    row["designedFailureReason"],
                    expected["brandName"],
                    expected["classTypeCode"],
                    expected["alcoholContent"],
                    expected["netContents"],
                    expected["bottler"],
                    expected["origin"],
                ]
            )

    summary = {
        "total": TOTAL,
        "designedPass": PASS_COUNT,
        "designedFail": TOTAL - PASS_COUNT,
        "output": str(OUT_DIR.relative_to(ROOT)),
    }
    (OUT_DIR / "README.md").write_text(
        "\n".join(
            [
                "# Synthetic Label Test Dataset",
                "",
                "Generated by scripts/generate_synthetic_test_dataset.py.",
                "",
                f"- Total images: {summary['total']}",
                f"- Designed pass: {summary['designedPass']}",
                f"- Designed fail: {summary['designedFail']}",
                "- Visual styles: beer, wine, spirits bottle mockups",
                "",
                "Use metadata.json (or metadata.csv/jsonl) for expected payloads and pre-declared pass/fail intent.",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

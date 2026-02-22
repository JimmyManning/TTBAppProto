import json
import unittest
from io import BytesIO
from unittest.mock import patch

from ttb_label_verifier import create_app, routes, validation


class ValidationHelperTests(unittest.TestCase):
    @patch("ttb_label_verifier.validators.policy.load_class_type_code_labels")
    def test_class_code_requires_age_table_driven(self, mock_labels):
        mock_labels.return_value = {
            "200": "SPIRIT WHISKY",
            "201": "BLENDED WHISKY",
            "202": "SOUR MASH WHISKY",
            "203": "RUM",
            "204": "RUM CORDIAL",
            "205": "STRAIGHT BOURBON WHISKY",
            "206": "WINE",
        }

        cases = [
            ("200", True),
            ("201", True),
            ("202", False),
            ("203", True),
            ("204", False),
            ("205", True),
            ("206", False),
            ("", False),
            ("999", False),
        ]

        for code, expected in cases:
            with self.subTest(code=code):
                self.assertEqual(validation.class_code_requires_age(code), expected)

    def test_normalize_loose_ignores_case_and_punctuation(self):
        self.assertEqual(validation.normalize_loose("STONE'S THROW"), "stone s throw")
        self.assertEqual(validation.normalize_loose("Stone’s Throw"), "stone s throw")

    def test_validate_label_fuzzy_brand_match_passes(self):
        result = validation.validate_label(
            extracted_text="Stone's Throw",
            expected={"brandName": "STONE'S THROW"},
            filename="label.png",
        )

        brand_row = next(item for item in result["comparisons"] if item["key"] == "brandName")
        self.assertTrue(brand_row["pass"])

    def test_warning_requires_uppercase_header(self):
        warning = validation.REQUIRED_GOV_WARNING

        result = validation.validate_label(
            extracted_text=warning.replace("GOVERNMENT WARNING:", "Government Warning:"),
            expected={},
            filename="label.png",
        )

        warning_row = next(item for item in result["comparisons"] if item["key"] == "govWarning")
        self.assertFalse(warning_row["pass"])
        self.assertIn("Closest:", warning_row["detected"])
        self.assertIn("Reason:", warning_row["detected"])
        self.assertIn("missing exact uppercase header", warning_row["detected"])
        self.assertFalse(result["autoPass"])

    def test_class_type_code_passes_when_label_text_is_present(self):
        detected, passed, score = validation.verify_class_type_code(
            raw_text="This label identifies STRAIGHT BOURBON WHISKY and details.",
            class_type_code="101",
        )

        self.assertTrue(passed)
        self.assertEqual(detected, "STRAIGHT BOURBON WHISKY")
        self.assertGreaterEqual(score, 0.82)

    def test_alcohol_content_requires_allowed_phrase_and_rejects_abv(self):
        detected, passed, score = validation.verify_alcohol_content(
            raw_text="45% ABV",
            expected_value=45,
        )

        self.assertFalse(passed)
        self.assertEqual(detected, "ABV not allowed")
        self.assertEqual(score, 0.0)

    def test_alcohol_content_passes_with_alc_by_vol(self):
        detected, passed, score = validation.verify_alcohol_content(
            raw_text="This spirit is 45% alc/by vol.",
            expected_value=45,
        )

        self.assertTrue(passed)
        self.assertIn("45%", detected)
        self.assertGreater(score, 0.9)

    def test_alcohol_content_with_proof_must_match_abv(self):
        detected, passed, score = validation.verify_alcohol_content(
            raw_text="45% Alc./Vol. 90 Proof",
            expected_value=45,
        )

        self.assertTrue(passed)
        self.assertIn("90 Proof", detected)
        self.assertGreater(score, 0.9)

    def test_alcohol_content_with_mismatched_proof_fails(self):
        detected, passed, score = validation.verify_alcohol_content(
            raw_text="45% Alc./Vol. 80 Proof",
            expected_value=45,
        )

        self.assertFalse(passed)
        self.assertIn("80 Proof", detected)
        self.assertLess(score, 0.95)

    def test_origin_skips_validation_for_usa(self):
        detected, passed, score = validation.detect_field(
            raw_text="Random OCR text without origin",
            expected_value="Product of USA",
            field_key="origin",
        )

        self.assertTrue(passed)
        self.assertEqual(detected, "Product of USA")
        self.assertEqual(score, 1.0)

    def test_origin_skips_validation_for_us_state(self):
        detected, passed, score = validation.detect_field(
            raw_text="No matching origin line",
            expected_value="Kentucky",
            field_key="origin",
        )

        self.assertTrue(passed)
        self.assertEqual(detected, "Kentucky")
        self.assertEqual(score, 1.0)

    def test_origin_still_validates_for_non_us_country(self):
        detected, passed, score = validation.detect_field(
            raw_text="Product of USA",
            expected_value="Product of France",
            field_key="origin",
        )

        self.assertFalse(passed)
        self.assertNotEqual(detected, "Product of France")
        self.assertLess(score, 0.82)

    def test_age_statement_is_added_when_class_requires_age(self):
        expected = {
            "brandName": "OLD TOM DISTILLERY",
            "classTypeCode": "131",
            "alcoholContent": 45,
            "netContents": "750 mL",
            "bottler": "Bottled by Old Tom Distillery, Frankfort, KY",
            "bottlerAddress": "123 Main St, Frankfort, KY",
            "origin": "Product of USA",
            "ageYears": 4,
        }
        text = "\n".join(
            [
                "OLD TOM DISTILLERY",
                "BLENDED BOURBON WHISKY",
                "45% Alc./Vol. (90 Proof)",
                "AGED 4 YEARS",
                "750 mL",
                "Bottled by Old Tom Distillery, Frankfort, KY",
                "123 Main St, Frankfort, KY",
                "Product of USA",
                validation.REQUIRED_GOV_WARNING,
            ]
        )

        result = validation.validate_label(text, expected)
        age_row = next(item for item in result["comparisons"] if item["key"] == "ageYears")
        self.assertTrue(age_row["pass"])

    def test_age_required_class_without_age_fails(self):
        expected = {
            "brandName": "OLD TOM DISTILLERY",
            "classTypeCode": "131",
            "alcoholContent": 45,
            "netContents": "750 mL",
            "bottler": "Bottled by Old Tom Distillery, Frankfort, KY",
            "bottlerAddress": "123 Main St, Frankfort, KY",
            "origin": "Product of USA",
        }
        result = validation.validate_label("OLD TOM DISTILLERY", expected)
        age_row = next(item for item in result["comparisons"] if item["key"] == "ageYears")
        self.assertFalse(age_row["pass"])

    def test_additive_flag_passes_with_contains_phrase(self):
        expected = {
            "fdcYellow5": True,
        }
        result = validation.validate_label("Contains FD&C Yellow No. 5", expected)
        row = next(item for item in result["comparisons"] if item["key"] == "fdcYellow5")
        self.assertTrue(row["pass"])

    def test_additive_flag_fails_without_contains_phrase(self):
        expected = {
            "carmine": True,
        }
        result = validation.validate_label("Carmine added for color", expected)
        row = next(item for item in result["comparisons"] if item["key"] == "carmine")
        self.assertFalse(row["pass"])


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.required_expected = {
            "brandName": "OLD TOM DISTILLERY",
            "classTypeCode": "101",
            "alcoholContent": 45,
            "netContents": "750 mL",
            "bottler": "Bottled by Old Tom Distillery, Frankfort, KY",
            "bottlerAddress": "123 Main St, Frankfort, KY",
            "origin": "Product of USA",
            "ageYears": 4,
        }

    def test_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"status": "ok"})

    def test_config_returns_backend_owned_field_definitions(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("fieldLabels", body)
        self.assertIn("requiredFields", body)
        self.assertIn("maxBatchImages", body)
        self.assertIn("countries", body)
        self.assertIn("defaultOrigin", body)
        self.assertIn("additiveFlags", body)
        self.assertIn("numericSanitization", body)
        self.assertIn(body["defaultOrigin"], body["countries"])
        self.assertEqual(body["maxBatchImages"], 50)

    def test_openapi_schema_is_published(self):
        resp = self.client.get("/api/openapi.yaml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("openapi:", resp.get_data(as_text=True))

    def test_single_validate_rejects_json_content_type(self):
        resp = self.client.post("/api/validate", json={"foo": "bar"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("multipart/form-data", resp.get_json()["error"])

    def test_batch_validate_rejects_json_content_type(self):
        resp = self.client.post("/api/validate/batch", json={"foo": "bar"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("multipart/form-data", resp.get_json()["error"])

    @patch.object(routes, "ocr_image_file")
    def test_single_validate_multipart_image_success(self, mock_ocr):
        mock_ocr.return_value = ("OLD TOM DISTILLERY", None)

        resp = self.client.post(
            "/api/validate",
            data={
                "image": (BytesIO(b"fake-image"), "label.png"),
                "expected": json.dumps(self.required_expected),
            },
            content_type="multipart/form-data",
        )

        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["extractedText"], "OLD TOM DISTILLERY")

    @patch.object(routes, "ocr_image_file")
    def test_single_validate_with_additive_flags_includes_result_row(self, mock_ocr):
        mock_ocr.return_value = ("Contains Cochineal Extract", None)

        resp = self.client.post(
            "/api/validate",
            data={
                "image": (BytesIO(b"fake-image"), "label.png"),
                "expected": json.dumps({
                    **self.required_expected,
                    "cochinealExtract": True,
                }),
            },
            content_type="multipart/form-data",
        )

        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        additive_row = next(item for item in body["comparisons"] if item["key"] == "cochinealExtract")
        self.assertTrue(additive_row["pass"])

    @patch.object(routes, "ocr_image_file")
    def test_single_validate_rejects_missing_required_fields(self, mock_ocr):
        mock_ocr.return_value = ("OLD TOM DISTILLERY", None)

        resp = self.client.post(
            "/api/validate",
            data={
                "image": (BytesIO(b"fake-image"), "label.png"),
                "expected": '{"brandName":"OLD TOM DISTILLERY"}',
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("expected.classTypeCode is required", resp.get_json()["error"])

    @patch.object(routes, "ocr_image_file")
    def test_batch_validate_multipart_image_success(self, mock_ocr):
        expected_lines = [str(value) for value in self.required_expected.values()]
        expected_lines.append("45% Alc./Vol.")
        expected_lines.append("AGED 4 YEARS")
        full_match_text = "\n".join(expected_lines) + "\n" + validation.REQUIRED_GOV_WARNING
        mock_ocr.side_effect = [
            (full_match_text, None),
            (full_match_text.replace("45% Alc./Vol.", "45% ABV"), None),
        ]

        resp = self.client.post(
            "/api/validate/batch",
            data={
                "images": [
                    (BytesIO(b"fake-1"), "label1.png"),
                    (BytesIO(b"fake-2"), "label2.png"),
                ],
                "expected": json.dumps(self.required_expected),
            },
            content_type="multipart/form-data",
        )

        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["autoPass"], 1)
        self.assertEqual(body["needsReview"], 1)

    def test_batch_validate_rejects_missing_required_shared_expected(self):
        resp = self.client.post(
            "/api/validate/batch",
            data={
                "images": [(BytesIO(b"fake-1"), "label1.png")],
                "expected": '{"brandName":"OLD TOM DISTILLERY"}',
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("expected.classTypeCode is required", resp.get_json()["error"])

    def test_batch_validate_multipart_expected_list_size_mismatch(self):
        resp = self.client.post(
            "/api/validate/batch",
            data={
                "images": [(BytesIO(b"fake-1"), "label1.png")],
                "expectedList": '[{"brandName":"A"},{"brandName":"B"}]',
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("expectedList length", resp.get_json()["error"])

    def test_batch_validate_rejects_more_than_50_images(self):
        images = [(BytesIO(f"fake-{i}".encode()), f"label{i}.png") for i in range(51)]
        resp = self.client.post(
            "/api/validate/batch",
            data={
                "images": images,
                "expected": json.dumps(self.required_expected),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("Maximum 50 images", resp.get_json()["error"])

    def test_single_validate_requires_age_for_age_required_class_code(self):
        expected_without_age = {k: v for k, v in self.required_expected.items() if k != "ageYears"}
        resp = self.client.post(
            "/api/validate",
            data={
                "image": (BytesIO(b"fake-image"), "label.png"),
                "expected": json.dumps({
                    **expected_without_age,
                    "classTypeCode": "131",
                }),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("expected.ageYears is required", resp.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
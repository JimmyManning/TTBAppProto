"""Shared validation field definitions and constants."""

FIELD_LABELS = {
    "brandName": "Brand Name",
    "classTypeCode": "Class/Type Code",
    "alcoholContent": "Alcohol Content (%)",
    "netContents": "Net Contents",
    "bottler": "Bottler/Producer",
    "bottlerAddress": "Bottler/Producer Address",
    "origin": "Country of Origin",
    "govWarning": "Government Warning",
}

OPTIONAL_FIELD_LABELS = {
    "ageYears": "Age Statement (Years)",
    "fdcYellow5": "Contains FD&C Yellow No. 5",
    "cochinealExtract": "Contains Cochineal Extract",
    "carmine": "Contains Carmine",
}

OPTIONAL_ADDITIVE_FLAGS = {
    "fdcYellow5": "FD&C Yellow No. 5",
    "cochinealExtract": "Cochineal Extract",
    "carmine": "Carmine",
}

REQUIRED_GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects.\n\n"
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

EXPECTED_INPUT_FIELDS = (
    "brandName",
    "classTypeCode",
    "alcoholContent",
    "netContents",
    "bottler",
    "bottlerAddress",
    "origin",
)

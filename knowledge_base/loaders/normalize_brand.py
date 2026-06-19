"""
Brand name normalization for Tunisian pharmacy data.

Extracts canonical INNs from brand names by stripping dosages, manufacturers, and forms.
Supports multiple resolution strategies: hardcoded dictionary, CSV mapping, normalization rules.
"""

import csv
import os
import re
from typing import Optional

# Common manufacturer suffixes in Tunisia
MANUFACTURER_SUFFIXES = [
    "ADWYA", "OPALIA", "NEAPOLIS", "ZENTIVA", "SANOFI", "PANPHARMA",
    "MEDIS", "TEVA", "MYLAN", "SANDOZ", "PFIZER", "NOVARTIS", "ROCHE",
    "BAYER", "GSK", "ASTRAZENECA", "MERCK", "BOEHRINGER", "LILLY",
    "BRISTOL", "JANSSEN", "NOVO", "NORDISK", "ABBOTT", "ABBVIE",
    "AGUETTANT", "INFOMED", "SAIPH", "WINTHROP", "SOPHARMA", "NATIVELLE",
    "LABESFAL",
]

# Common form indicators and packaging terms
FORM_INDICATORS = [
    "COMP", "COMPRIME", "COMPRIMÉ", "GEL", "GELULE", "GÉLULE",
    "SOLUTION", "SUSPENSION", "SIROP", "INJECTABLE", "INJ", "PDRE",
    "POUDRE", "CREME", "CRÈME", "POMMADE", "SUPPO", "SUPPOSITOIRE",
    "PATCH", "SPRAY", "AEROSOL", "AÉROSOL", "COLLYRE", "GOUTTE",
    "RETARD", "LP", "SR", "XR", "MR", "CR", "DR", "EC", "ENTERIC",
    "GTTES", "BUV", "EFFERV", "DISPERS", "DISP", "PELL", "SEQUESTRE",
    "GASTRO", "GASTRORESIS", "GASTROREZIST", "BT", "FL", "FL.", "FLACON",
    "BOITE", "BOX", "CARTON", "PACK", "BLISTER", "SACH", "SACHETS",
    "SERINGUE", "CARTOUCHE", "AMP", "AMPOULE",
]

# Strength pattern
STRENGTH_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|ug|ml|l|ui|iu|mui|%|mmol|mEq|gbq|kbq|mbq)"
    r"(?:\s*/\s*\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|ug|ml|l|ui|iu|mui|%))?",
    re.IGNORECASE,
)

# Common brand-to-INN dictionary for Tunisian market
BRAND_TO_INN = {
    "amlodipine": "amlodipine",
    "amlor": "amlodipine",
    "amoxicillin": "amoxicillin",
    "amoxicilline": "amoxicillin",
    "amoxil": "amoxicillin",
    "amoxiclav": "amoxicillin/clavulanate",
    "amoxicilline/acide clavulanique": "amoxicillin/clavulanate",
    "augmentin": "amoxicillin/clavulanate",
    "aspirin": "aspirin",
    "acetylsalicylate": "aspirin",
    "acetylsalicylate de lysine": "aspirin",
    "aspegic": "aspirin",
    "aspirine": "aspirin",
    "kardegic": "aspirin",
    "ator": "atorvastatin",
    "atorvastatin": "atorvastatin",
    "tahor": "atorvastatin",
    "carbamazepine": "carbamazepine",
    "tegretol": "carbamazepine",
    "clarithromycin": "clarithromycin",
    "clarithromycine": "clarithromycin",
    "zeclar": "clarithromycin",
    "clopidogrel": "clopidogrel",
    "plavix": "clopidogrel",
    "diclofenac": "diclofenac",
    "voltarene": "diclofenac",
    "digoxin": "digoxin",
    "digoxine": "digoxin",
    "furosemide": "furosemide",
    "lasilix": "furosemide",
    "glibenclamide": "glibenclamide",
    "daonil": "glibenclamide",
    "heparin": "heparin",
    "heparine": "heparin",
    "insulin glargine": "insulin glargine",
    "lantus": "insulin glargine",
    "metformin": "metformin",
    "metformine": "metformin",
    "glucophage": "metformin",
    "metforal": "metformin",
    "metronidazole": "metronidazole",
    "flagyl": "metronidazole",
    "naproxen": "naproxen",
    "apranax": "naproxen",
    "omeprazole": "omeprazole",
    "mopral": "omeprazole",
    "prednisolone": "prednisolone",
    "solupred": "prednisolone",
    "ramipril": "ramipril",
    "triatec": "ramipril",
    "sertraline": "sertraline",
    "zoloft": "sertraline",
    "simvastatin": "simvastatin",
    "simvastatine": "simvastatin",
    "spironolactone": "spironolactone",
    "aldactone": "spironolactone",
    "tramadol": "tramadol",
    "tramal": "tramadol",
    "valproate": "valproate",
    "depakine": "valproate",
}


def normalize_brand_name(raw: str) -> str:
    """
    Normalize a brand name by removing dosage, manufacturer, and form indicators.
    
    Args:
        raw: Raw brand name string
        
    Returns:
        Normalized brand name (lowercase, minimal)
        
    Examples:
        "AMLODIPINE ZENTIVA 10mg Comp" -> "amlodipine"
        "AMOXICILLINE SANOFI 1g Comp.Disp." -> "amoxicilline"
        "AUGMENTIN 500mg/50mg" -> "augmentin"
    """
    if not raw:
        return ""
    
    # Start with raw string
    normalized = raw.strip()
    
    # Remove strength (e.g., "10mg", "500mg/5ml")
    normalized = STRENGTH_RE.sub("", normalized)
    
    # Remove package counts (e.g., "Bt 28" becomes "Bt" then removed)
    # Pattern: optional whitespace, optional form indicator, then count number
    normalized = re.sub(r"\s+\d+\s*$", "", normalized)  # Remove trailing numbers
    
    # Remove manufacturer suffixes
    for suffix in MANUFACTURER_SUFFIXES:
        pattern = r"\b" + re.escape(suffix) + r"\b"
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    
    # Remove form indicators
    for form in FORM_INDICATORS:
        pattern = r"\b" + re.escape(form) + r"\b"
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)
    
    # Remove special characters and collapse whitespace
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    
    return normalized.lower()


def lookup_tunisian_inn(
    normalized_brand: str, 
    mapping_csv_path: Optional[str] = None
) -> Optional[str]:
    """
    Look up INN from Tunisian brand mapping CSV.
    
    Args:
        normalized_brand: Normalized brand name to look up
        mapping_csv_path: Path to tunisian_brand_mapping_clean.csv
        
    Returns:
        INN string or None if not found
    """
    if not mapping_csv_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mapping_csv_path = os.path.join(
            base_dir, "sources", "dataset", "tunisian_brand_mapping_clean.csv"
        )
    
    if not os.path.exists(mapping_csv_path):
        return None
    
    # Try exact and normalized matches
    try:
        with open(mapping_csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = row.get("brand_name", "").strip()
                inn = row.get("candidate_inn", "").strip().lower()
                
                if not inn:
                    continue
                
                # Try exact match
                if brand.lower() == normalized_brand:
                    return inn
                
                # Try normalized match
                normalized_csv = normalize_brand_name(brand)
                if normalized_csv == normalized_brand:
                    return inn
    except Exception as e:
        print(f"Warning: Could not read mapping CSV: {e}")
        return None
    
    return None


def common_brand_to_inn(brand: str) -> Optional[str]:
    """
    Look up INN from hardcoded dictionary of common Tunisian brands.
    
    Args:
        brand: Brand name (will be normalized)
        
    Returns:
        INN string or None if not found
    """
    normalized = normalize_brand_name(brand)
    return BRAND_TO_INN.get(normalized)


def resolve_brand_to_inn(
    raw_brand: str, 
    mapping_csv_path: Optional[str] = None
) -> Optional[str]:
    """
    Full resolution pipeline: dictionary lookup -> CSV mapping.
    
    Args:
        raw_brand: Raw brand name from PCT data
        mapping_csv_path: Optional path to mapping CSV
        
    Returns:
        INN string or None if unresolvable
    """
    if not raw_brand or not raw_brand.strip():
        return None
    
    # Step 1: Direct dictionary lookup
    inn = common_brand_to_inn(raw_brand)
    if inn:
        return inn
    
    # Step 2: Normalize then dictionary lookup
    normalized = normalize_brand_name(raw_brand)
    inn = BRAND_TO_INN.get(normalized)
    if inn:
        return inn
    
    # Step 3: CSV mapping lookup with normalized brand
    inn = lookup_tunisian_inn(normalized, mapping_csv_path)
    if inn:
        return inn
    
    # Step 4: Try raw brand in CSV
    inn = lookup_tunisian_inn(raw_brand.lower().strip(), mapping_csv_path)
    if inn:
        return inn
    
    return None


if __name__ == "__main__":
    # Test examples
    test_cases = [
        "AMLODIPINE ZENTIVA 10mg Comp Séc",
        "AMOXICILLINE SANOFI 1g Comp.Disp.",
        "AUGMENTIN 500mg/50mg Pdre.P.Prép.Inj.",
        "DAFALGAN 500mg",
        "BRUFEN 400mg",
        "TAHOR 10mg Comp.Pell.",
        "UNKNOWN_BRAND_XYZ",
        "VOLTARENE 50mg Suppo.",
    ]
    
    print("Brand name resolution test:")
    print(f"{'Brand Name':<50} {'INN':<30}")
    print("-" * 80)
    for brand in test_cases:
        inn = resolve_brand_to_inn(brand)
        print(f"{brand:<50} {inn or 'UNRESOLVED':<30}")

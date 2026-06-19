#!/usr/bin/env python3
"""Clean the raw data lake and generate reviewable candidate outputs.

This is a Linux-compatible replacement for knowledge_base/pipelines/clean_data_lake.ps1.
"""

from __future__ import annotations
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

SOURCE_DIR = Path(__file__).resolve().parent.parent / "sources"
RAW_PCT_PATH = SOURCE_DIR / "dataset" / "pct_human_medicines_raw.csv"
OUTPUT_DIR = SOURCE_DIR / "clean"

PRIORITY_DEFINITIONS = [
    {"inn": "warfarin", "reason": "high-risk anticoagulant interactions"},
    {"inn": "heparin", "reason": "high-risk anticoagulant interactions"},
    {"inn": "aspirin", "reason": "antiplatelet bleeding risk"},
    {"inn": "clopidogrel", "reason": "antiplatelet bleeding risk"},
    {"inn": "metformin", "reason": "renal contraindication trap"},
    {"inn": "glibenclamide", "reason": "hypoglycemia risk"},
    {"inn": "insulin glargine", "reason": "hypoglycemia risk"},
    {"inn": "enalapril", "reason": "ACE inhibitor renal/potassium risk"},
    {"inn": "ramipril", "reason": "ACE inhibitor renal/potassium risk"},
    {"inn": "amlodipine", "reason": "common cardiovascular drug"},
    {"inn": "furosemide", "reason": "electrolyte/renal risk"},
    {"inn": "spironolactone", "reason": "hyperkalemia risk"},
    {"inn": "digoxin", "reason": "narrow therapeutic index"},
    {"inn": "atorvastatin", "reason": "Tunisian brand duplication trap"},
    {"inn": "simvastatin", "reason": "CYP3A4 inhibitor trap"},
    {"inn": "ibuprofen", "reason": "NSAID bleeding/renal risk"},
    {"inn": "diclofenac", "reason": "NSAID bleeding/renal risk"},
    {"inn": "naproxen", "reason": "NSAID bleeding/renal risk"},
    {"inn": "prednisolone", "reason": "steroid interaction risk"},
    {"inn": "amoxicillin", "reason": "penicillin allergy trap"},
    {"inn": "ciprofloxacin", "reason": "QT/CYP/renal concerns"},
    {"inn": "metronidazole", "reason": "interaction-prone antimicrobial"},
    {"inn": "clarithromycin", "reason": "strong CYP3A4 inhibitor trap"},
    {"inn": "fluconazole", "reason": "CYP2C9 inhibitor trap"},
    {"inn": "carbamazepine", "reason": "CYP inducer and neurologic risk"},
    {"inn": "valproate", "reason": "neurologic and hepatic risk"},
    {"inn": "fluoxetine", "reason": "serotonin syndrome trap"},
    {"inn": "sertraline", "reason": "SSRI interaction risk"},
    {"inn": "omeprazole", "reason": "common gastric/CYP interaction drug"},
    {"inn": "tramadol", "reason": "serotonin syndrome trap"},
]

ALIAS_MAP = {
    "aspirin": ["aspirin", "aspirine", "acide acetylsalicylique", "acetylsalicylate", "acetylsalicylate de lysine"],
    "heparin": ["heparin", "heparine", "enoxaparine", "nadroparine"],
    "metformin": ["metformin", "metformine"],
    "glibenclamide": ["glibenclamide", "glyburide"],
    "insulin glargine": ["insulin glargine", "insuline glargine", "glargine"],
    "enalapril": ["enalapril"],
    "ramipril": ["ramipril"],
    "amlodipine": ["amlodipine"],
    "furosemide": ["furosemide", "furosémide"],
    "spironolactone": ["spironolactone", "spironolactone"],
    "digoxin": ["digoxin", "digoxine"],
    "atorvastatin": ["atorvastatin", "atorvastatine"],
    "simvastatin": ["simvastatin", "simvastatine"],
    "ibuprofen": ["ibuprofen", "ibuprofene", "ibuprofène"],
    "diclofenac": ["diclofenac", "diclofenac", "diclofénac"],
    "naproxen": ["naproxen", "naproxene", "naproxène"],
    "prednisolone": ["prednisolone"],
    "amoxicillin": ["amoxicillin", "amoxicilline"],
    "ciprofloxacin": ["ciprofloxacin", "ciprofloxacine"],
    "metronidazole": ["metronidazole", "metronidazole", "métronidazole"],
    "clarithromycin": ["clarithromycin", "clarithromycine"],
    "fluconazole": ["fluconazole"],
    "carbamazepine": ["carbamazepine", "carbamazépine"],
    "valproate": ["valproate", "valproique", "acide valproique", "valproate de sodium"],
    "fluoxetine": ["fluoxetine", "fluoxétine"],
    "sertraline": ["sertraline"],
    "omeprazole": ["omeprazole", "oméprazole"],
    "tramadol": ["tramadol"],
    "warfarin": ["warfarin"],
    "clopidogrel": ["clopidogrel"],
}

BRAND_SEED_MAP = {
    "TAHOR": "atorvastatin",
    "ATOR": "atorvastatin",
    "LIPITOR": "atorvastatin",
    "ZOCOR": "simvastatin",
    "GLUCOPHAGE": "metformin",
    "METFORAL": "metformin",
    "DAONIL": "glibenclamide",
    "LANTUS": "insulin glargine",
    "KARDEGIC": "aspirin",
    "ASPEGIC": "aspirin",
    "ASPIRINE": "aspirin",
    "PLAVIX": "clopidogrel",
    "LASILIX": "furosemide",
    "ALDACTONE": "spironolactone",
    "LANOXIN": "digoxin",
    "AMLOR": "amlodipine",
    "NORVASC": "amlodipine",
    "COVERSYL": "perindopril",
    "TRIATEC": "ramipril",
    "RENITEC": "enalapril",
    "AUGMENTIN": "amoxicillin",
    "AMOXIL": "amoxicillin",
    "CIFLOX": "ciprofloxacin",
    "FLAGYL": "metronidazole",
    "ZECLAR": "clarithromycin",
    "DIFLUCAN": "fluconazole",
    "TEGRETOL": "carbamazepine",
    "DEPAKINE": "valproate",
    "PROZAC": "fluoxetine",
    "ZOLOFT": "sertraline",
    "MOPRAL": "omeprazole",
    "TRAMAL": "tramadol",
    "VOLTARENE": "diclofenac",
    "BRUFEN": "ibuprofen",
    "APRANAX": "naproxen",
    "SOLUPRED": "prednisolone",
}

ALLERGY_GROUP_DEFINITIONS = [
    {
        "name": "Penicillins",
        "normalized_name": "penicillins",
        "description": "Penicillin-class beta-lactam antibiotics; includes amoxicillin and related aminopenicillins.",
        "clinical_note": "Use for documented penicillin allergy, especially immediate hypersensitivity or anaphylaxis.",
    },
    {
        "name": "Beta-lactams",
        "normalized_name": "beta_lactams",
        "description": "Broad beta-lactam antibiotic family including penicillins, cephalosporins, carbapenems, and monobactams.",
        "clinical_note": "Useful parent group for cross-reactivity review; do not treat all beta-lactam allergies as equal without reaction history.",
    },
    {
        "name": "Cephalosporins",
        "normalized_name": "cephalosporins",
        "description": "Cephalosporin beta-lactam antibiotics.",
        "clinical_note": "Cross-reactivity risk is higher with similar side chains and severe immediate penicillin reactions.",
    },
    {
        "name": "NSAIDs",
        "normalized_name": "nsaids",
        "description": "Non-steroidal anti-inflammatory drugs; includes ibuprofen, diclofenac, and naproxen.",
        "clinical_note": "Relevant for NSAID-exacerbated respiratory disease, urticaria/angioedema, and anaphylaxis.",
    },
    {
        "name": "Salicylates",
        "normalized_name": "salicylates",
        "description": "Aspirin and salicylate-containing medicines.",
        "clinical_note": "Aspirin sensitivity can cross-react clinically with many COX-1 NSAIDs.",
    },
    {
        "name": "Fluoroquinolones",
        "normalized_name": "fluoroquinolones",
        "description": "Fluoroquinolone antibiotics; includes ciprofloxacin.",
        "clinical_note": "Avoid same-class rechallenge after severe immediate hypersensitivity unless specialist-supervised.",
    },
    {
        "name": "Macrolides",
        "normalized_name": "macrolides",
        "description": "Macrolide antibiotics; includes clarithromycin.",
        "clinical_note": "Allergy is less common but same-class alternatives require review when reaction was severe.",
    },
    {
        "name": "Sulfonylureas",
        "normalized_name": "sulfonylureas",
        "description": "Sulfonylurea antidiabetics; includes glibenclamide.",
        "clinical_note": "Different from sulfonamide antibiotic allergy; keep distinct to avoid false positives.",
    },
    {
        "name": "Insulins",
        "normalized_name": "insulins",
        "description": "Insulin preparations and analogues; includes insulin glargine.",
        "clinical_note": "Can involve insulin molecule or excipients; reaction details matter.",
    },
    {
        "name": "Statins",
        "normalized_name": "statins",
        "description": "HMG-CoA reductase inhibitors; includes atorvastatin and simvastatin.",
        "clinical_note": "Distinguish allergy from intolerance such as myalgia.",
    },
    {
        "name": "SSRIs",
        "normalized_name": "ssris",
        "description": "Selective serotonin reuptake inhibitors; includes fluoxetine and sertraline.",
        "clinical_note": "True allergy is uncommon; document rash, angioedema, or severe reactions separately from side effects.",
    },
    {
        "name": "Opioids",
        "normalized_name": "opioids",
        "description": "Opioid analgesics and opioid-like medicines; includes tramadol.",
        "clinical_note": "Differentiate true allergy from histamine-mediated itching or nausea.",
    },
]

DRUG_ALLERGY_MAP = {
    "aspirin": ["Salicylates", "NSAIDs"],
    "ibuprofen": ["NSAIDs"],
    "diclofenac": ["NSAIDs"],
    "naproxen": ["NSAIDs"],
    "amoxicillin": ["Penicillins", "Beta-lactams"],
    "ciprofloxacin": ["Fluoroquinolones"],
    "clarithromycin": ["Macrolides"],
    "glibenclamide": ["Sulfonylureas"],
    "insulin glargine": ["Insulins"],
    "atorvastatin": ["Statins"],
    "simvastatin": ["Statins"],
    "fluoxetine": ["SSRIs"],
    "sertraline": ["SSRIs"],
    "tramadol": ["Opioids"],
}

CROSS_DEFINITIONS = [
    {
        "group_a": "Penicillins",
        "group_b": "Beta-lactams",
        "direction": "bidirectional",
        "clinical_note": "Penicillin allergy is part of the broader beta-lactam allergy review space.",
        "confidence": "high",
    },
    {
        "group_a": "Penicillins",
        "group_b": "Cephalosporins",
        "direction": "bidirectional",
        "clinical_note": "Cross-reactivity is possible, especially with immediate severe reactions or similar side chains; requires pharmacist review.",
        "confidence": "moderate",
    },
    {
        "group_a": "Salicylates",
        "group_b": "NSAIDs",
        "direction": "bidirectional",
        "clinical_note": "Aspirin/salicylate hypersensitivity can cross-react with non-selective NSAIDs.",
        "confidence": "high",
    },
]


def remove_diacritics(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_token(value: str) -> str:
    ascii_text = remove_diacritics(value)
    lower = ascii_text.lower()
    clean = re.sub(r"[^a-z0-9]+", " ", lower)
    return re.sub(r"\s+", " ", clean).strip()


def test_token_match(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    h = f" {normalize_token(haystack)} "
    n = re.escape(normalize_token(needle))
    return re.search(rf"(^| ){n}( |$)", h) is not None


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pct_path = RAW_PCT_PATH
    rxnorm_path = SOURCE_DIR / "rxnorm_mapping.json"
    if not pct_path.exists() or not rxnorm_path.exists():
        raise FileNotFoundError(
            "Required source files are missing: knowledge_base/sources/dataset/pct_human_medicines_raw.csv or knowledge_base/sources/rxnorm_mapping.json"
        )

    rxnorm_rows = load_json(rxnorm_path)
    rxnorm_by_inn = {row.get("inn_name", ""): row for row in rxnorm_rows}
    pct_rows = load_csv(pct_path)

    clean_brand_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    match_counts = {definition["inn"]: 0 for definition in PRIORITY_DEFINITIONS}
    priority_inns = {definition["inn"] for definition in PRIORITY_DEFINITIONS}

    for row in pct_rows:
        full_label = row.get("medicine_label", "")
        brand_guess = row.get("brand_guess", "")
        brand_token = normalize_token(brand_guess).upper()
        candidate_inn = ""
        confidence = ""
        rule = ""

        seed_inn = BRAND_SEED_MAP.get(brand_token)
        if seed_inn and seed_inn in priority_inns:
            candidate_inn = seed_inn
            confidence = "medium"
            rule = "brand_seed"

        if not candidate_inn:
            for definition in PRIORITY_DEFINITIONS:
                inn = definition["inn"]
                aliases = ALIAS_MAP.get(inn, [])
                if any(test_token_match(full_label, alias) for alias in aliases):
                    candidate_inn = inn
                    confidence = "high"
                    rule = f"label_alias:{aliases[0]}"
                    break

        if candidate_inn:
            rx = rxnorm_by_inn.get(candidate_inn, {})
            match_counts[candidate_inn] += 1
            clean_brand_rows.append(
                {
                    "brand_name": brand_guess,
                    "full_label": full_label,
                    "strength": row.get("strength_guess", ""),
                    "candidate_inn": candidate_inn,
                    "rxnorm_cui": rx.get("rxnorm_cui", ""),
                    "confidence": confidence,
                    "match_rule": rule,
                    "source": "PCT",
                    "needs_manual_review": "false",
                }
            )
        else:
            unresolved_rows.append(
                {
                    "brand_name": brand_guess,
                    "full_label": full_label,
                    "strength": row.get("strength_guess", ""),
                    "reason": "no_priority_inn_or_seed_match",
                    "source": "PCT",
                    "needs_manual_review": "true",
                }
            )

    molecule_rows: list[dict[str, Any]] = []
    priority_rows: list[dict[str, Any]] = []
    rxnorm_clean_rows: list[dict[str, Any]] = []
    allergy_group_rows: list[dict[str, Any]] = []
    drug_allergy_rows: list[dict[str, Any]] = []
    allergy_cross_rows: list[dict[str, Any]] = []

    for definition in PRIORITY_DEFINITIONS:
        inn = definition["inn"]
        rx = rxnorm_by_inn.get(inn, {})
        rxnorm_cui = rx.get("rxnorm_cui", "")
        synonyms = rx.get("all_synonyms", "")
        pct_count = match_counts[inn]

        molecule_rows.append(
            {
                "canonical_inn": inn,
                "rxnorm_cui": rxnorm_cui,
                "rxnorm_synonyms": synonyms,
                "pct_match_count": pct_count,
                "source": "RxNorm + PCT",
                "confidence": "high" if rxnorm_cui else "needs_review",
                "priority_phase": "week1_30",
            }
        )
        priority_rows.append(
            {
                "rank": len(priority_rows) + 1,
                "canonical_inn": inn,
                "rxnorm_cui": rxnorm_cui,
                "pct_match_count": pct_count,
                "selection_reason": definition["reason"],
                "selected_for_phase": "week1_30",
                "needs_manual_review": "true" if pct_count == 0 else "false",
            }
        )
        rxnorm_clean_rows.append(
            {
                "canonical_inn": inn,
                "rxnorm_cui": rxnorm_cui,
                "rxnorm_synonyms": synonyms,
                "status": rx.get("status", "missing"),
                "source": "RxNorm",
            }
        )

    for group in ALLERGY_GROUP_DEFINITIONS:
        allergy_group_rows.append(
            {
                "name": group["name"],
                "normalized_name": group["normalized_name"],
                "description": group["description"],
                "clinical_note": group["clinical_note"],
                "source": "MedFlow clinical seed",
                "confidence": "starter_reviewed",
            }
        )

    for inn, groups in DRUG_ALLERGY_MAP.items():
        rx = rxnorm_by_inn.get(inn, {})
        for group_name in groups:
            drug_allergy_rows.append(
                {
                    "canonical_inn": inn,
                    "rxnorm_cui": rx.get("rxnorm_cui", ""),
                    "allergy_group": group_name,
                    "relationship_type": "member",
                    "clinical_note": "Alert when patient has documented allergy to this group and this molecule is prescribed.",
                    "source": "MedFlow clinical seed",
                    "confidence": "starter_reviewed",
                }
            )

    for cross in CROSS_DEFINITIONS:
        allergy_cross_rows.append(
            {
                "group_a": cross["group_a"],
                "group_b": cross["group_b"],
                "direction": cross["direction"],
                "clinical_note": cross["clinical_note"],
                "source": "MedFlow clinical seed",
                "confidence": cross["confidence"],
            }
        )

    clean_brand_rows.sort(key=lambda row: (row["candidate_inn"], row["brand_name"], row["full_label"]))
    unresolved_rows.sort(key=lambda row: (row["brand_name"], row["full_label"]))
    drug_allergy_rows.sort(key=lambda row: (row["canonical_inn"], row["allergy_group"]))

    write_csv(OUTPUT_DIR / "tunisian_brand_mapping_clean.csv", clean_brand_rows, [
        "brand_name",
        "full_label",
        "strength",
        "candidate_inn",
        "rxnorm_cui",
        "confidence",
        "match_rule",
        "source",
        "needs_manual_review",
    ])
    write_csv(OUTPUT_DIR / "unresolved_review_queue.csv", unresolved_rows, [
        "brand_name",
        "full_label",
        "strength",
        "reason",
        "source",
        "needs_manual_review",
    ])
    write_csv(OUTPUT_DIR / "molecules_candidates.csv", molecule_rows, [
        "canonical_inn",
        "rxnorm_cui",
        "rxnorm_synonyms",
        "pct_match_count",
        "source",
        "confidence",
        "priority_phase",
    ])
    write_csv(OUTPUT_DIR / "priority_drugs_30_60.csv", priority_rows, [
        "rank",
        "canonical_inn",
        "rxnorm_cui",
        "pct_match_count",
        "selection_reason",
        "selected_for_phase",
        "needs_manual_review",
    ])
    write_csv(OUTPUT_DIR / "rxnorm_brand_mapping_clean.csv", rxnorm_clean_rows, [
        "canonical_inn",
        "rxnorm_cui",
        "rxnorm_synonyms",
        "status",
        "source",
    ])
    write_csv(OUTPUT_DIR / "allergy_groups_clean.csv", allergy_group_rows, [
        "name",
        "normalized_name",
        "description",
        "clinical_note",
        "source",
        "confidence",
    ])
    write_csv(OUTPUT_DIR / "drug_allergy_groups_clean.csv", drug_allergy_rows, [
        "canonical_inn",
        "rxnorm_cui",
        "allergy_group",
        "relationship_type",
        "clinical_note",
        "source",
        "confidence",
    ])
    write_csv(OUTPUT_DIR / "allergy_cross_reactivities_clean.csv", allergy_cross_rows, [
        "group_a",
        "group_b",
        "direction",
        "clinical_note",
        "source",
        "confidence",
    ])

    summary = {
        "pct_raw_rows": len(pct_rows),
        "matched_tunisian_brand_rows": len(clean_brand_rows),
        "unresolved_rows": len(unresolved_rows),
        "molecule_candidates": len(molecule_rows),
        "priority_drugs": len(priority_rows),
        "allergy_groups": len(allergy_group_rows),
        "drug_allergy_group_links": len(drug_allergy_rows),
        "allergy_cross_reactivities": len(allergy_cross_rows),
        "output_dir": str(OUTPUT_DIR.resolve()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

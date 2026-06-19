"""
Generate clinical knowledge blueprint from PostgreSQL.

Extracts all drugs, interactions, families, allergies, and CYP relationships
into a single JSON structure that serves as the in-memory knowledge graph.

This blueprint is loaded once by the agent and traversed for all validations.
No per-prescription database queries needed.
"""

import os
import json
import psycopg2
from datetime import datetime


def connect_db():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "medflow"),
        user=os.getenv("POSTGRES_USER", "medflow"),
        password=os.getenv("POSTGRES_PASSWORD", "medflow"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
    )


def generate_blueprint(output_path="blueprint.json"):
    """
    Generate complete clinical blueprint from database.

    Returns:
    {
        "metadata": { "generated_at": "...", "version": "..." },
        "drugs": {
            "warfarin": { "mol_id": 1, "families": [...], "cyp": [...], "doses": {...} },
            ...
        },
        "interactions": [
            { "drug_a": "warfarin", "drug_b": "aspirin", "severity": "...", "mechanism": "...", "management": "..." },
            ...
        ],
        "families": {
            "anticoagulants": { "drugs": ["warfarin", ...], "description": "...", "atc_prefix": "..." },
            ...
        },
        "allergies": {
            "penicillins": {
                "drugs": ["amoxicillin", ...],
                "description": "...",
                "cross_reactivities": ["cephalosporins"]
            },
            ...
        },
        "cyp": {
            "CYP2C9": {
                "substrates": ["warfarin", ...],
                "inhibitors": ["fluconazole", ...],
                "inducers": ["carbamazepine", ...]
            },
            ...
        }
    }
    """

    conn = connect_db()
    cur = conn.cursor()

    print("Generating clinical blueprint...")

    # ─────────────────────────────────────────────────────────────────────────

    # 1. Extract all drugs and molecules
    print("  Extracting drugs...")
    cur.execute("""
        SELECT m.inn, m.id, m.rxnorm_cui, d.id, d.brand_name, d.atc_code, 
               d.dose_adult, d.dose_elderly, d.dose_renal_impairment, d.dose_hepatic_impairment
        FROM molecules m
        LEFT JOIN drugs d ON d.molecule_id = m.id
        ORDER BY m.inn
    """)
    drugs_data = {}
    for row in cur.fetchall():
        inn, mol_id, rxnorm_cui, drug_id, brand, atc, dose_adult, dose_elderly, dose_renal, dose_hepatic = row
        if inn not in drugs_data:
            drugs_data[inn] = {
                "mol_id": mol_id,
                "rxnorm_cui": rxnorm_cui or "",
                "brands": [],
                "atc_codes": [],
                "doses": {
                    "adult": dose_adult or "",
                    "elderly": dose_elderly or "",
                    "renal_impairment": dose_renal or "",
                    "hepatic_impairment": dose_hepatic or "",
                },
                "families": [],
                "cyp": [],
                "allergies": [],
            }
        if brand:
            drugs_data[inn]["brands"].append(brand)
        if atc:
            drugs_data[inn]["atc_codes"].append(atc)

    # ─────────────────────────────────────────────────────────────────────────

    # 2. Extract drug families (from therapeutic_category/atc_code)
    print("  Extracting drug families...")
    families_data = {}
    cur.execute("""
        SELECT DISTINCT therapeutic_category, atc_code, d.id, m.inn
        FROM drugs d
        JOIN molecules m ON m.id = d.molecule_id
        WHERE therapeutic_category IS NOT NULL OR atc_code IS NOT NULL
    """)
    for row in cur.fetchall():
        category, atc, drug_id, inn = row
        family_name = category or atc or "unknown"
        if family_name not in families_data:
            families_data[family_name] = {
                "description": f"Category: {category or 'N/A'}, ATC: {atc or 'N/A'}",
                "atc_prefix": atc or "",
                "drugs": [],
            }
        if inn not in families_data[family_name]["drugs"]:
            families_data[family_name]["drugs"].append(inn)
        if inn in drugs_data:
            if family_name not in drugs_data[inn]["families"]:
                drugs_data[inn]["families"].append(family_name)

    # ─────────────────────────────────────────────────────────────────────────

    # 3. Extract drug-drug interactions
    print("  Extracting drug-drug interactions...")
    cur.execute("""
        SELECT m1.inn, m2.inn, di.severity_ansm, di.severity_active, 
               di.mechanism_type, di.clinical_effect, di.management
        FROM drug_interactions di
        JOIN molecules m1 ON m1.id = di.molecule_a_id
        JOIN molecules m2 ON m2.id = di.molecule_b_id
    """)
    interactions_data = []
    for row in cur.fetchall():
        inn_a, inn_b, severity_ansm, severity_active, mechanism, effect, management = row
        # Use most conservative severity
        severity = severity_ansm or severity_active or "a_prendre_en_compte"
        interactions_data.append({
            "drug_a": inn_a,
            "drug_b": inn_b,
            "severity": severity,
            "severity_ansm": severity_ansm or "",
            "severity_active": severity_active or "",
            "mechanism": mechanism or "",
            "clinical_effect": effect or "",
            "management": management or "",
        })

    # ─────────────────────────────────────────────────────────────────────────

    # 4. Extract allergy groups and cross-reactivities
    print("  Extracting allergies...")
    cur.execute("""
        SELECT ag.name, ag.description, m.inn
        FROM drug_allergy_groups dag
        JOIN allergy_groups ag ON ag.id = dag.allergy_group_id
        JOIN drugs d ON d.id = dag.drug_id
        JOIN molecules m ON m.id = d.molecule_id
    """)
    allergies_data = {}
    for row in cur.fetchall():
        allergy_name, description, inn = row
        if allergy_name not in allergies_data:
            allergies_data[allergy_name] = {
                "description": description or "",
                "drugs": [],
                "cross_reactivities": [],
            }
        if inn not in allergies_data[allergy_name]["drugs"]:
            allergies_data[allergy_name]["drugs"].append(inn)
        if inn in drugs_data:
            if allergy_name not in drugs_data[inn]["allergies"]:
                drugs_data[inn]["allergies"].append(allergy_name)

    # Get cross-reactivities
    cur.execute("""
        SELECT ag1.name, ag2.name
        FROM allergy_cross_reactivities acr
        JOIN allergy_groups ag1 ON ag1.id = acr.group_a_id
        JOIN allergy_groups ag2 ON ag2.id = acr.group_b_id
    """)
    for row in cur.fetchall():
        allergy_a, allergy_b = row
        if allergy_a in allergies_data:
            if allergy_b not in allergies_data[allergy_a]["cross_reactivities"]:
                allergies_data[allergy_a]["cross_reactivities"].append(allergy_b)

    # ─────────────────────────────────────────────────────────────────────────

    # 5. Extract CYP relationships
    print("  Extracting CYP relationships...")
    cur.execute("""
        SELECT m.inn, cr.enzyme, cr.relationship, cr.strength
        FROM cyp_relationships cr
        JOIN molecules m ON m.id = cr.molecule_id
    """)
    cyp_data = {}
    for row in cur.fetchall():
        inn, enzyme, relationship, strength = row
        if enzyme not in cyp_data:
            cyp_data[enzyme] = {
                "substrates": [],
                "inhibitors": [],
                "inducers": [],
            }
        if relationship == "substrate":
            cyp_data[enzyme]["substrates"].append(inn)
        elif relationship == "inhibitor":
            cyp_data[enzyme]["inhibitors"].append(inn)
        elif relationship == "inducer":
            cyp_data[enzyme]["inducers"].append(inn)

        # Store in drug record
        if inn in drugs_data:
            if enzyme not in drugs_data[inn]["cyp"]:
                drugs_data[inn]["cyp"].append(f"{enzyme}_{relationship}")

    # ─────────────────────────────────────────────────────────────────────────

    # 6. Build final blueprint
    print("  Building blueprint...")
    blueprint = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "version": "1.0",
            "source": "PostgreSQL medflow database",
        },
        "drugs": drugs_data,
        "interactions": interactions_data,
        "families": families_data,
        "allergies": allergies_data,
        "cyp": cyp_data,
    }

    # ─────────────────────────────────────────────────────────────────────────

    # 7. Write to file
    print(f"  Writing blueprint to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(blueprint, f, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────────────────────

    # Summary
    cur.execute("SELECT count(*) FROM molecules")
    num_drugs = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM drug_interactions")
    num_interactions = cur.fetchone()[0]
    num_families = len(families_data)
    cur.execute("SELECT count(*) FROM allergy_groups")
    num_allergies = cur.fetchone()[0]

    print("\n✓ Blueprint generated successfully!")
    print(f"  Drugs: {num_drugs}")
    print(f"  Interactions: {num_interactions}")
    print(f"  Families: {num_families}")
    print(f"  Allergy groups: {num_allergies}")
    print(f"  Output: {output_path}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    generate_blueprint()

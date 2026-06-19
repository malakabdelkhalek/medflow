"""
Load drug families and family-level interactions.

Groups drugs by therapeutic class and defines interaction rules between families.
"""

import os
import psycopg2

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "medflow"),
    user=os.getenv("POSTGRES_USER", "medflow"),
    password=os.getenv("POSTGRES_PASSWORD", "medflow"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
)
cur = conn.cursor()

# Drug family definitions
DRUG_FAMILIES = [
    {
        "name": "Anticoagulants",
        "atc_prefix": "B01A",
        "description": "Oral anticoagulants and antiplatelet agents",
        "drugs": ["warfarin", "aspirin", "clopidogrel", "heparin"],
        "indication": "stroke/thrombosis prevention",
    },
    {
        "name": "Statins",
        "atc_prefix": "C10A",
        "description": "HMG-CoA reductase inhibitors",
        "drugs": ["atorvastatin", "simvastatin"],
        "indication": "cholesterol reduction",
    },
    {
        "name": "ACE Inhibitors",
        "atc_prefix": "C09A",
        "description": "ACE inhibitors for hypertension and heart failure",
        "drugs": ["enalapril", "ramipril"],
        "indication": "hypertension/heart failure",
    },
    {
        "name": "NSAIDs",
        "atc_prefix": "M01A",
        "description": "Non-steroidal anti-inflammatory drugs",
        "drugs": ["aspirin", "ibuprofen", "diclofenac", "naproxen"],
        "indication": "pain/inflammation",
    },
    {
        "name": "SSRIs",
        "atc_prefix": "N06AB",
        "description": "Selective serotonin reuptake inhibitors",
        "drugs": ["fluoxetine", "sertraline"],
        "indication": "depression/anxiety",
    },
    {
        "name": "Antidiabetics",
        "atc_prefix": "A10",
        "description": "Antidiabetic drugs",
        "drugs": ["metformin", "glibenclamide"],
        "indication": "diabetes management",
    },
    {
        "name": "Antibiotics",
        "atc_prefix": "J01",
        "description": "Systemic antibacterial agents",
        "drugs": ["amoxicillin", "ciprofloxacin", "clarithromycin", "metronidazole"],
        "indication": "bacterial infection",
    },
]

# Family-level interactions
FAMILY_INTERACTIONS = [
    {
        "family_a": "Anticoagulants",
        "family_b": "NSAIDs",
        "type": "bleeding_risk",
        "severity": "deconseillee",
        "mechanism": "NSAIDs impair platelet function and damage gastric mucosa",
        "clinical_effect": "Significantly increased gastrointestinal bleeding risk",
        "management": "Avoid NSAIDs. Use acetaminophen instead.",
    },
    {
        "family_a": "Statins",
        "family_b": "Antibiotics",
        "type": "cyp_inhibition",
        "severity": "precaution_emploi",
        "mechanism": "Clarithromycin inhibits CYP3A4, increasing statin exposure",
        "clinical_effect": "Elevated statin levels, increased myopathy risk",
        "management": "Monitor for muscle pain. Reduce statin dose or switch antibiotic.",
    },
    {
        "family_a": "Anticoagulants",
        "family_b": "Antibiotics",
        "type": "warfarin_interaction",
        "severity": "precaution_emploi",
        "mechanism": "Antibiotics inhibit gut flora, increasing warfarin absorption",
        "clinical_effect": "Increased INR, bleeding risk",
        "management": "Monitor INR closely. May need warfarin dose adjustment.",
    },
    {
        "family_a": "SSRIs",
        "family_b": "NSAIDs",
        "type": "gi_bleeding",
        "severity": "precaution_emploi",
        "mechanism": "Both increase GI bleeding risk via different mechanisms",
        "clinical_effect": "Additive gastrointestinal bleeding risk",
        "management": "Use lowest NSAID dose. Consider PPI co-therapy.",
    },
]

# CYP relationships at family level
FAMILY_CYP = [
    {"family": "Statins", "enzyme": "CYP3A4", "relationship": "substrate", "strength": "moderate"},
    {
        "family": "Antibiotics",
        "enzyme": "CYP3A4",
        "relationship": "inhibitor",
        "strength": "strong",
    },
    {
        "family": "SSRIs",
        "enzyme": "CYP2D6",
        "relationship": "inhibitor",
        "strength": "moderate",
    },
    {
        "family": "Anticoagulants",
        "enzyme": "CYP2C9",
        "relationship": "substrate",
        "strength": "strong",
    },
]

# ─────────────────────────────────────────────────────────────────────────────

print("Loading drug families...")

# Insert families
for family in DRUG_FAMILIES:
    cur.execute(
        """
        INSERT INTO drug_families (name, description, atc_prefix, clinical_note)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
        RETURNING id
    """,
        (
            family["name"],
            family["description"],
            family["atc_prefix"],
            family["indication"],
        ),
    )
    family_id = cur.fetchone()[0]

    # Link drugs to family
    for drug_inn in family["drugs"]:
        cur.execute("SELECT d.id FROM drugs d JOIN molecules m ON m.id = d.molecule_id WHERE m.inn = %s", (drug_inn,))
        drug_row = cur.fetchone()
        if drug_row:
            cur.execute(
                """
                INSERT INTO drug_family_members (drug_id, family_id, indication)
                VALUES (%s, %s, %s)
                ON CONFLICT (drug_id, family_id) DO NOTHING
            """,
                (drug_row[0], family_id, family["indication"]),
            )

conn.commit()
print(f"✓ Inserted {len(DRUG_FAMILIES)} drug families")

# ─────────────────────────────────────────────────────────────────────────────

print("Loading family-level interactions...")

# Insert family interactions
for interaction in FAMILY_INTERACTIONS:
    # Get family IDs
    cur.execute("SELECT id FROM drug_families WHERE name = %s", (interaction["family_a"],))
    family_a_row = cur.fetchone()
    cur.execute("SELECT id FROM drug_families WHERE name = %s", (interaction["family_b"],))
    family_b_row = cur.fetchone()

    if family_a_row and family_b_row:
        family_a_id, family_b_id = family_a_row[0], family_b_row[0]
        cur.execute(
            """
            INSERT INTO family_interactions
                (family_a_id, family_b_id, interaction_type, severity, mechanism, clinical_effect, management)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (family_a_id, family_b_id) DO UPDATE SET
                interaction_type = EXCLUDED.interaction_type,
                severity = EXCLUDED.severity
        """,
            (
                family_a_id,
                family_b_id,
                interaction["type"],
                interaction["severity"],
                interaction["mechanism"],
                interaction["clinical_effect"],
                interaction["management"],
            ),
        )

conn.commit()
print(f"✓ Inserted {len(FAMILY_INTERACTIONS)} family interactions")

# ─────────────────────────────────────────────────────────────────────────────

print("Loading family CYP relationships...")

# Insert CYP relationships
for cyp in FAMILY_CYP:
    cur.execute("SELECT id FROM drug_families WHERE name = %s", (cyp["family"],))
    family_row = cur.fetchone()

    if family_row:
        family_id = family_row[0]
        cur.execute(
            """
            INSERT INTO family_cyp_relationships (family_id, enzyme, relationship, strength)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (family_id, enzyme, relationship) DO NOTHING
        """,
            (family_id, cyp["enzyme"], cyp["relationship"], cyp["strength"]),
        )

conn.commit()
print(f"✓ Inserted {len(FAMILY_CYP)} family CYP relationships")

# ─────────────────────────────────────────────────────────────────────────────

cur.execute("SELECT count(*) FROM drug_families")
print(f"\nSummary:")
print(f"  Families: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM drug_family_members")
print(f"  Family memberships: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM family_interactions")
print(f"  Family interactions: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM family_cyp_relationships")
print(f"  CYP relationships: {cur.fetchone()[0]}")

cur.close()
conn.close()
print("\n✓ Drug family loading complete!")

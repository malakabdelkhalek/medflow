"""
Load Tunisian PCT brand mappings into the database.

Reads tunisian_brand_mapping_clean.csv and populates:
1. molecules table (if INN not present)
2. drugs table (brand names linked to molecules)

Uses manual duplicate checking since drugs table has no unique constraint.
"""

import csv
import os
import psycopg2

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "medflow"),
    user=os.getenv("POSTGRES_USER", "medflow"),
    password=os.getenv("POSTGRES_PASSWORD", "medflow"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
)
cur = conn.cursor()

csv_path = os.path.join(
    os.path.dirname(__file__), "../sources/dataset/tunisian_brand_mapping_clean.csv"
)

print(f"Loading Tunisian brand mappings from {csv_path}...")

inserted_mol = 0
inserted_drug = 0
updated_drug = 0
skipped = 0
seen = set()  # Track (inn, brand) pairs to avoid duplicates

with open(csv_path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        brand = row.get("brand_name", "").strip()
        inn = row.get("candidate_inn", "").strip().lower()

        if not inn or not brand:
            skipped += 1
            continue

        # Skip duplicate (inn, brand) pairs
        key = (inn, brand)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)

        # ─────────────────────────────────────────────────────────────────────

        # Step 1: Ensure molecule exists for this INN
        cur.execute("SELECT id FROM molecules WHERE inn = %s", (inn,))
        mol = cur.fetchone()

        if not mol:
            # Molecule doesn't exist, try to insert
            cur.execute(
                """
                INSERT INTO molecules (inn)
                VALUES (%s)
                ON CONFLICT (inn) DO NOTHING
                RETURNING id
            """,
                (inn,),
            )
            mol = cur.fetchone()
            if mol:
                inserted_mol += 1

        # Re-fetch in case of race condition
        if not mol:
            cur.execute("SELECT id FROM molecules WHERE inn = %s", (inn,))
            mol = cur.fetchone()

        if not mol:
            skipped += 1
            continue

        mol_id = mol[0]

        # ─────────────────────────────────────────────────────────────────────

        # Step 2: Check if drug (brand) already exists for this molecule
        cur.execute(
            """
            SELECT id FROM drugs 
            WHERE molecule_id = %s AND (brand_name_tn = %s OR brand_name = %s)
        """,
            (mol_id, brand, brand),
        )

        existing = cur.fetchone()

        if existing:
            # Drug already exists, skip
            skipped += 1
            continue

        # ─────────────────────────────────────────────────────────────────────

        # Step 3: Insert new drug (brand name + Tunisian name)
        cur.execute(
            """
            INSERT INTO drugs (molecule_id, brand_name, brand_name_tn)
            VALUES (%s, %s, %s)
        """,
            (mol_id, brand, brand),
        )
        inserted_drug += 1

conn.commit()

# ─────────────────────────────────────────────────────────────────────────────

# Summary statistics
cur.execute("SELECT count(*) FROM molecules WHERE inn IN (SELECT distinct candidate_inn FROM (SELECT 'placeholder' as candidate_inn) t WHERE false)")
cur.execute("""
    SELECT COUNT(DISTINCT m.inn) 
    FROM drugs d 
    JOIN molecules m ON m.id = d.molecule_id
""")
drugs_loaded = cur.fetchone()[0]

cur.execute("SELECT count(*) FROM drugs")
total_drugs = cur.fetchone()[0]

print("\n✓ PCT brand loading complete!")
print(f"  New molecules: {inserted_mol}")
print(f"  New drugs (brands): {inserted_drug}")
print(f"  Skipped: {skipped}")
print(f"  Total drugs in DB: {total_drugs}")
print(f"  Molecules with drugs: {drugs_loaded}")

cur.close()
conn.close()

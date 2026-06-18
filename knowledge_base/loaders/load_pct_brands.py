import csv, os, psycopg2

# Maps PCT INN names to our canonical INN names
INN_MAP = {
    "acetylsalicylate": "aspirin", "aspirine": "aspirin", "aspirin": "aspirin",
    "amoxicillin": "amoxicillin", "amlodipine": "amlodipine",
    "atorvastatin": "atorvastatin", "carbamazepine": "carbamazepine",
    "ciprofloxacin": "ciprofloxacin", "clarithromycine": "clarithromycin", "clarithromycin": "clarithromycin",
    "clopidogrel": "clopidogrel", "diclofenac": "diclofenac",
    "digoxin": "digoxin", "digoxine": "digoxin",
    "enalapril": "enalapril", "fluconazole": "fluconazole",
    "fluoxetine": "fluoxetine", "furosemide": "furosemide",
    "glibenclamide": "glibenclamide", "heparin": "heparin", "insuline": "insulin glargine",
    "ibuprofen": "ibuprofen", "metformin": "metformin",
    "metronidazole": "metronidazole", "naproxen": "naproxen",
    "omeprazole": "omeprazole", "prednisolone": "prednisolone",
    "ramipril": "ramipril", "sertraline": "sertraline",
    "simvastatin": "simvastatin", "spironolactone": "spironolactone",
    "tramadol": "tramadol", "valproate": "valproate",
}

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "medflow"),
    user=os.getenv("POSTGRES_USER", "medflow"),
    password=os.getenv("POSTGRES_PASSWORD", "medflow"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
)
cur = conn.cursor()

csv_path = os.path.join(os.path.dirname(__file__), "../sources/clean/tunisian_brand_mapping_clean.csv")
updated, skipped = 0, 0
seen = set()  # keep first brand name per INN

with open(csv_path, newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        brand = row["brand_name"].strip()
        inn = row["candidate_inn"].strip().lower()
        if not inn or inn in seen or not brand:
            skipped += 1
            continue
        cur.execute("""
            UPDATE drugs SET brand_name_tn = %s
            FROM molecules WHERE drugs.molecule_id = molecules.id
              AND molecules.inn = %s
              AND drugs.brand_name_tn IS NULL
        """, (brand, inn))
        if cur.rowcount:
            seen.add(inn)
            updated += 1
        else:
            skipped += 1

conn.commit()
print(f"Updated: {updated}, Skipped: {skipped}")
cur.close()
conn.close()

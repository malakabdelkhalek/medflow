import os
import time
import urllib.request
import urllib.parse
import json
import psycopg2

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "medflow"),
    user=os.getenv("POSTGRES_USER", "medflow"),
    password=os.getenv("POSTGRES_PASSWORD", "medflow"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
)
cur = conn.cursor()

DRUGS = [
    "warfarin","heparin","aspirin","clopidogrel","metformin","glibenclamide",
    "insulin glargine","enalapril","ramipril","amlodipine","furosemide",
    "spironolactone","digoxin","atorvastatin","simvastatin","ibuprofen",
    "diclofenac","naproxen","prednisolone","amoxicillin","ciprofloxacin",
    "metronidazole","clarithromycin","fluconazole","carbamazepine","valproate",
    "fluoxetine","sertraline","omeprazole","tramadol"
]

def get_rxnorm_cui(name):
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={urllib.parse.quote(name)}"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
        ids = data.get("idGroup", {}).get("rxnormId", [])
        return ids[0] if ids else None

def get_chembl_id(name):
    url = f"https://www.ebi.ac.uk/chembl/api/data/molecule?pref_name__iexact={urllib.parse.quote(name)}&format=json"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
        mols = data.get("molecules", [])
        return mols[0]["molecule_chembl_id"] if mols else None

def get_chembl_cyp(chembl_id):
    url = f"https://www.ebi.ac.uk/chembl/api/data/metabolism?substrate_chembl_id={chembl_id}&format=json"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
        return data.get("metabolisms", [])

loaded, skipped = 0, 0

for drug in DRUGS:
    print(f"Processing {drug}...")
    try:
        rxnorm_cui = get_rxnorm_cui(drug)
        time.sleep(0.2)
        chembl_id = get_chembl_id(drug)
        time.sleep(0.2)

        # upsert molecule
        cur.execute("""
            INSERT INTO molecules (inn, rxnorm_cui, chembl_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (inn) DO UPDATE SET
                rxnorm_cui = EXCLUDED.rxnorm_cui,
                chembl_id  = EXCLUDED.chembl_id
            RETURNING id
        """, (drug, rxnorm_cui, chembl_id))
        mol_id = cur.fetchone()[0]

        # load CYP relationships
        if chembl_id:
            cyp_data = get_chembl_cyp(chembl_id)
            time.sleep(0.2)
            for entry in cyp_data:
                enzyme = entry.get("enzyme_name")
                if not enzyme:
                    continue
                cur.execute("""
                    INSERT INTO cyp_relationships (molecule_id, enzyme, relationship, strength)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (mol_id, enzyme, "metabolized_by", None))

        loaded += 1
        print(f"  OK — RxNorm: {rxnorm_cui}, ChEMBL: {chembl_id}")
    except Exception as e:
        print(f"  SKIP {drug}: {e}")
        skipped += 1

conn.commit()
cur.close()
conn.close()
print(f"\nDone. Loaded: {loaded}, Skipped: {skipped}")

import os, urllib.parse, json, psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

DB = dict(dbname=os.getenv("POSTGRES_DB","medflow"), user=os.getenv("POSTGRES_USER","medflow"),
          password=os.getenv("POSTGRES_PASSWORD","medflow"), host=os.getenv("POSTGRES_HOST","localhost"))

def fetch(mol_id, inn):
    try:
        url = f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{urllib.parse.quote(inn)}&limit=1"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.load(r)
        openfda = data["results"][0].get("openfda", {})
        atc    = (openfda.get("pharm_class_epc") or [None])[0]
        cat    = (openfda.get("pharm_class_cs") or openfda.get("pharm_class_epc") or [None])[0]
        route  = (openfda.get("route") or [None])[0]
        return mol_id, atc, cat, route
    except Exception:
        return mol_id, None, None, None

conn = psycopg2.connect(**DB)
cur  = conn.cursor()
cur.execute("""
    SELECT DISTINCT m.id, m.inn FROM molecules m JOIN drugs d ON d.molecule_id = m.id
    WHERE d.atc_code IS NULL AND m.inn IS NOT NULL ORDER BY m.inn
""")
molecules = cur.fetchall()
print(f"Molecules to enrich: {len(molecules)}")

updated = 0
with ThreadPoolExecutor(max_workers=20) as pool:
    futures = {pool.submit(fetch, mid, inn): inn for mid, inn in molecules}
    done = 0
    for f in as_completed(futures):
        mol_id, atc, cat, route = f.result()
        done += 1
        if done % 200 == 0:
            print(f"  {done}/{len(molecules)}...")
        if atc or cat:
            cur.execute("""
                UPDATE drugs SET atc_code=%s, therapeutic_category=%s, dosage_form=COALESCE(dosage_form,%s)
                FROM molecules WHERE drugs.molecule_id=molecules.id AND molecules.id=%s AND drugs.atc_code IS NULL
            """, (atc[:10] if atc else None, cat[:100] if cat else None, route[:50] if route else None, mol_id))
            updated += cur.rowcount

conn.commit()
print(f"Done. Updated: {updated} drug rows")
cur.close(); conn.close()

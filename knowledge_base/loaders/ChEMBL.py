import requests
import csv
import time
import os

DRUGS = [
    "warfarin", "heparin", "aspirin", "clopidogrel",
    "metformin", "glibenclamide", "insulin glargine",
    "enalapril", "ramipril", "amlodipine", "furosemide",
    "spironolactone", "digoxin", "atorvastatin", "simvastatin",
    "ibuprofen", "diclofenac", "naproxen", "prednisolone",
    "amoxicillin", "ciprofloxacin", "metronidazole",
    "clarithromycin", "fluconazole",
    "carbamazepine", "valproate", "fluoxetine",
    "sertraline", "omeprazole", "tramadol"
]

#CYP interactions
BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

def get_chembl_id(drug_name):
    url = f"{BASE_URL}/molecule.json?pref_name__iexact={drug_name}&limit=1"
    r = requests.get(url)
    if r.status_code != 200:
        return None, None
    data = r.json()
    molecules = data.get("molecules", [])
    if not molecules:
        return None, None
    mol = molecules[0]
    return mol.get("molecule_chembl_id"), mol.get("molecule_properties", {})

def get_cyp_data(chembl_id):
    # metabolism endpoint: shows which enzymes metabolize this drug
    url = f"{BASE_URL}/metabolism.json?substrate_chembl_id={chembl_id}&limit=20"
    r = requests.get(url)
    if r.status_code != 200:
        return []
    cyp_entries = []
    for m in r.json().get("metabolisms", []):
        enzyme = m.get("enzyme_name", "")
        if enzyme and "CYP" in enzyme.upper():
            cyp_entries.append(f"{enzyme}:metabolized_by")
    # inhibition/induction endpoint
    url2 = f"{BASE_URL}/mechanism.json?molecule_chembl_id={chembl_id}&limit=20"
    r2 = requests.get(url2)
    if r2.status_code == 200:
        for m in r2.json().get("mechanisms", []):
            target = m.get("target_name", "")
            if "CYP" in target.upper():
                cyp_entries.append(f"{target}:{m.get('action_type','?')}")
    return cyp_entries

results = []

for drug in DRUGS:
    print(f"Fetching: {drug}")
    chembl_id, props = get_chembl_id(drug)
    if chembl_id:
        cyp_data = get_cyp_data(chembl_id)
        results.append({
            "inn_name": drug,
            "chembl_id": chembl_id,
            "molecular_weight": props.get("mw_freebase", "") if props else "",
            "cyp_relationships": " | ".join(cyp_data) if cyp_data else "",
            "cyp_count": len(cyp_data),
            "status": "found"
        })
        print(f"  ✓ {chembl_id} — {len(cyp_data)} CYP relationships")
    else:
        results.append({
            "inn_name": drug,
            "chembl_id": "",
            "molecular_weight": "",
            "cyp_relationships": "",
            "cyp_count": 0,
            "status": "NOT FOUND"
        })
        print(f"  ✗ Not found")
    time.sleep(0.3)

output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../sources")
output_file = os.path.join(output_dir, "chembl_drug_data.csv")

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "inn_name", "chembl_id", "molecular_weight",
        "cyp_relationships", "cyp_count", "status"
    ])
    writer.writeheader()
    writer.writerows(results)

print(f"\nDone. {sum(1 for r in results if r['status'] == 'found')}/{len(results)} found.")
print(f"Fichier : {output_file}")
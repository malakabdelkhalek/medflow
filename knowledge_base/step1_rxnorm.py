import requests
import json
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
#CUI canoniques
BASE_URL = "https://rxnav.nlm.nih.gov/REST"

def get_rxcui(drug_name):
    url = f"{BASE_URL}/rxcui.json?name={drug_name}&search=1"
    r = requests.get(url)
    data = r.json()
    ids = data.get("idGroup", {}).get("rxnormId")
    if ids:
        return ids[0]
    return None

def get_all_names(rxcui):
    url = f"{BASE_URL}/rxcui/{rxcui}/allProperties.json?prop=names"
    r = requests.get(url)
    data = r.json()
    props = data.get("propConceptGroup", {}).get("propConcept", [])
    return [p["propValue"] for p in props]

results = []

for drug in DRUGS:
    print(f"Fetching: {drug}")
    cui = get_rxcui(drug)
    
    if cui:
        names = get_all_names(cui)
        results.append({
            "inn_name": drug,
            "rxnorm_cui": cui,
            "all_synonyms": " | ".join(names),
            "status": "found"
        })
        print(f"  ✓ CUI: {cui} — {len(names)} synonyms")
    else:
        results.append({
            "inn_name": drug,
            "rxnorm_cui": None,
            "all_synonyms": "",
            "status": "NOT FOUND"
        })
        print(f"  ✗ Not found")
    
    time.sleep(0.3)

# Les fichiers seront créés dans le même dossier que ce script
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(output_dir, "rxnorm_mapping.csv"), "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["inn_name", "rxnorm_cui", "all_synonyms", "status"])
    writer.writeheader()
    writer.writerows(results)

with open(os.path.join(output_dir, "rxnorm_mapping.json"), "w") as f:
    json.dump(results, f, indent=2)

print(f"\nDone. {sum(1 for r in results if r['status'] == 'found')}/{len(results)} found.")
print(f"Fichiers sauvegardés dans : {output_dir}")
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

#Interactions, warnings, contraindications
BASE_URL = "https://api.fda.gov/drug/label.json"

def get_drug_data(drug_name):
    url = f"{BASE_URL}?search=openfda.generic_name:{drug_name}&limit=1"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    results = data.get("results", [])
    if not results:
        return None
    label = results[0]
    return {
        "inn_name": drug_name,
        "brand_names": " | ".join(label.get("openfda", {}).get("brand_name", [])),
        "drug_interactions": label.get("drug_interactions", [""])[0][:1000] if label.get("drug_interactions") else "",
        "warnings": label.get("warnings", [""])[0][:1000] if label.get("warnings") else "",
        "contraindications": label.get("contraindications", [""])[0][:1000] if label.get("contraindications") else "",
        "status": "found"
    }

results = []

for drug in DRUGS:
    print(f"Fetching: {drug}")
    data = get_drug_data(drug)
    if data:
        results.append(data)
        print(f"  ✓ Found")
    else:
        results.append({
            "inn_name": drug,
            "brand_names": "",
            "drug_interactions": "",
            "warnings": "",
            "contraindications": "",
            "status": "NOT FOUND"
        })
        print(f"  ✗ Not found")
    time.sleep(0.3)

output_dir = os.path.dirname(os.path.abspath(__file__))
output_file = os.path.join(output_dir, "openfda_drug_data.csv")

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "inn_name", "brand_names", "drug_interactions",
        "warnings", "contraindications", "status"
    ])
    writer.writeheader()
    writer.writerows(results)

print(f"\nDone. {sum(1 for r in results if r['status'] == 'found')}/{len(results)} found.")
print(f"Fichier : {output_file}")
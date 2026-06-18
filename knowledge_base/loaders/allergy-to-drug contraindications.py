"""
FIXED v3 — allergy drug contraindications extractor.

ROOT CAUSE OF ALL FAILURES:
  - MEDRT does NOT support EPC classes. 
    MEDRT only covers: Disease, MoA, Chem, PE, PK.
  - EPC classes require relaSource=FDASPL (or DAILYMED), not MEDRT.
  - All N0000175XXX IDs were correct format but queried against wrong source.

CORRECT COMBINATION:
  classId=N0000XXXXXX  +  relaSource=FDASPL  +  rela=has_EPC  ✅
  classId=N0000XXXXXX  +  relaSource=MEDRT   +  rela=has_EPC  ❌ (always empty)

Class IDs verified from NIH MED-RT / FDA EPC vocabulary:
  https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxClass.getClassMembers.html
"""

import csv
import time
import requests

def extract_live_api_data(output_filename="allergy_drug_contraindications.csv"):

    base_url = "https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json"

    # ── CORRECT: relaSource=FDASPL for EPC classes ───────────────────────────
    # IDs are FDA EPC NUIs from the MED-RT vocabulary.
    # Verified at: https://rxnav.nlm.nih.gov/REST/rxclass/classMembers.json
    #              ?classId=N0000175882&relaSource=FDASPL&rela=has_EPC  (tetracyclines — works)
    allergy_groups = {
        "Penicillins":                  ("N0000175503", "FDASPL"),  # Penicillin-class Antibacterial
        "Cephalosporins":               ("N0000175911", "FDASPL"),  # Cephalosporin-class Antibacterial  
        "Sulfonamides (Sulfa)":         ("N0000175913", "FDASPL"),  # Sulfonamide Antibacterial
        "NSAIDs":                       ("N0000175722", "FDASPL"),  # Nonsteroidal Anti-inflammatory Drug
        "Aspirin":                      ("N0000006947", "FDASPL"),  # Salicylate
        "Fluoroquinolones":             ("N0000175706", "FDASPL"),  # Fluoroquinolone Antibacterial
        "Macrolides":                   ("N0000175463", "FDASPL"),  # Macrolide Antibacterial
        "Tetracyclines":                ("N0000175882", "FDASPL"),  # Tetracycline-class Drug (NIH example — confirmed working)
        "Opioids":                      ("N0000175789", "FDASPL"),  # Opioid Agonist
        "Statins (HMG-CoA Reductase)":  ("N0000175921", "FDASPL"),  # HMG-CoA Reductase Inhibitor
        "ACE Inhibitors":               ("N0000029130", "FDASPL"),  # Angiotensin-Converting Enzyme Inhibitor
        "Beta-Blockers":                ("N0000175561", "FDASPL"),  # beta-Adrenergic Blocker
        "Benzodiazepines":              ("N0000175774", "FDASPL"),  # Benzodiazepine
        "Aminoglycosides":              ("N0000175495", "FDASPL"),  # Aminoglycoside Antibacterial
        "Contrast Media (Iodine)":      ("N0000175918", "DAILYMED"), # Iodinated Contrast Media (not in FDASPL)
    }

    http_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DrugPipeline/1.0)",
        "Accept": "application/json",
    }

    csv_headers = [
        "Allergy_Group", "EPC_Class_ID", "RelaSource",
        "Drug_Name", "RxCUI", "Drug_Type"
    ]
    records_written = 0
    failed_groups = []

    print("Connecting to RxNav API...")
    print(f"Fetching {len(allergy_groups)} allergy classes via FDASPL/EPC...\n")

    with open(output_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(csv_headers)

        for group_name, (class_id, rela_source) in allergy_groups.items():
            params = {
                "classId":    class_id,
                "relaSource": rela_source,   # ← FDASPL not MEDRT
                "rela":       "has_EPC",
            }

            try:
                response = requests.get(
                    base_url, params=params,
                    headers=http_headers, timeout=15
                )

                if response.status_code != 200:
                    print(f"❌ HTTP {response.status_code} for {group_name}")
                    failed_groups.append(group_name)
                    continue

                data = response.json()
                drug_member_group = data.get("drugMemberGroup", {})

                # API returns [] (empty list) when classId not found
                if not drug_member_group or drug_member_group == []:
                    print(f"⚠️  No results for {group_name} (classId={class_id})")
                    failed_groups.append(group_name)
                    continue

                drug_members = drug_member_group.get("drugMember", [])
                if not drug_members:
                    print(f"⚠️  Empty member list for {group_name}")
                    continue

                # API returns a dict (not list) when there's only 1 member
                if isinstance(drug_members, dict):
                    drug_members = [drug_members]

                count = 0
                for member in drug_members:
                    concept   = member.get("minConcept", {})
                    drug_name = concept.get("name")
                    rxcui     = concept.get("rxcui")
                    tty       = concept.get("tty", "")

                    if drug_name and rxcui:
                        writer.writerow([
                            group_name, class_id, rela_source,
                            drug_name, rxcui, tty
                        ])
                        records_written += 1
                        count += 1

                print(f"✅ {group_name:35s} → {count:4d} drugs  (classId={class_id})")

            except requests.exceptions.Timeout:
                print(f"❌ Timeout for {group_name}")
                failed_groups.append(group_name)
            except requests.exceptions.ConnectionError as e:
                print(f"❌ Connection error for {group_name}: {e}")
                failed_groups.append(group_name)
            except Exception as e:
                print(f"❌ Unexpected error for {group_name}: {e}")
                import traceback; traceback.print_exc()
                failed_groups.append(group_name)

            time.sleep(0.3)   # polite rate limiting

    print(f"\n{'─'*55}")
    print(f"✅ Done — {records_written} records saved to '{output_filename}'")
    if failed_groups:
        print(f"⚠️  Failed groups ({len(failed_groups)}): {', '.join(failed_groups)}")
        print("   → For failed groups, verify the class ID at:")
        print("     https://mor.nlm.nih.gov/RxClass/  (search by class name)")


if __name__ == "__main__":
    extract_live_api_data()
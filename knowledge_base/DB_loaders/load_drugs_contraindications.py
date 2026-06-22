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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLEAN_DIR = os.path.join(BASE_DIR, "../sources/clean")

# ── drugs table (brand names + dose ranges) ──────────────────────────────────
DRUGS = [
    # (inn, brand_name, brand_name_tn, brand_name_fr, atc, category, form, dose_adult, dose_elderly, dose_renal, dose_hepatic)
    ("warfarin",        "Coumadin",     None,        "Coumadine",   "B01AA03", "Anticoagulant",      "tablet", "2-10mg/day titrated to INR", "Start low, monitor INR closely", "Contraindicated if CrCl<10", "Caution, monitor INR"),
    ("heparin",         "Heparin",      None,        "Héparine",    "B01AB01", "Anticoagulant",      "injection", "weight-based", "Reduce dose", "Reduce dose, monitor anti-Xa", "Use with caution"),
    ("aspirin",         "Aspégic",      "Aspégic",   "Aspégic",     "B01AC06", "Antiplatelet",       "tablet", "75-325mg/day", "75mg/day", "Avoid if CrCl<10", "Avoid in severe hepatic failure"),
    ("clopidogrel",     "Plavix",       "Plavix",    "Plavix",      "B01AC04", "Antiplatelet",       "tablet", "75mg/day", "75mg/day", "No dose adjustment", "Caution in severe hepatic impairment"),
    ("metformin",       "Glucophage",   "Glucophage","Glucophage",  "A10BA02", "Antidiabetic",       "tablet", "500-2000mg/day", "Start 500mg, titrate slowly", "Contraindicated if eGFR<30", "Contraindicated in hepatic failure"),
    ("glibenclamide",   "Daonil",       "Daonil",    "Daonil",      "A10BB01", "Antidiabetic",       "tablet", "2.5-15mg/day", "Start 2.5mg, risk of hypoglycemia", "Avoid if CrCl<30", "Avoid in hepatic failure"),
    ("insulin glargine","Lantus",       "Lantus",    "Lantus",      "A10AE04", "Antidiabetic",       "injection", "individualized", "Start low, titrate", "Monitor glucose closely", "Monitor glucose closely"),
    ("enalapril",       "Renitec",      None,        "Renitec",     "C09AA02", "ACE inhibitor",      "tablet", "5-40mg/day", "Start 2.5mg", "Start 2.5mg if CrCl<30", "Caution"),
    ("ramipril",        "Triatec",      "Triatec",   "Triatec",     "C09AA05", "ACE inhibitor",      "tablet", "2.5-10mg/day", "Start 1.25mg", "Start 1.25mg if CrCl<30", "Caution"),
    ("amlodipine",      "Amlor",        "Amlor",     "Amlor",       "C08CA01", "Calcium channel blocker","tablet","5-10mg/day","5mg/day","No dose adjustment","Start 5mg, titrate slowly"),
    ("furosemide",      "Lasilix",      "Lasilix",   "Lasilix",     "C03CA01", "Loop diuretic",      "tablet", "20-80mg/day", "Start low", "Higher doses may be needed", "Caution"),
    ("spironolactone",  "Aldactone",    "Aldactone", "Aldactone",   "C03DA01", "K-sparing diuretic", "tablet", "25-100mg/day", "Start 25mg", "Avoid if CrCl<30", "Caution in severe hepatic failure — monitor electrolytes"),
    ("digoxin",         "Digoxine",     None,        "Digoxine",    "C01AA05", "Cardiac glycoside",  "tablet", "0.125-0.25mg/day", "0.0625-0.125mg/day", "Reduce dose — renally cleared", "Caution"),
    ("atorvastatin",    "Tahor",        "Tahor",     "Tahor",       "C10AA05", "Statin",             "tablet", "10-80mg/day", "10-20mg/day", "No dose adjustment", "Contraindicated in active hepatic disease"),
    ("simvastatin",     "Zocor",        "Zocor",     "Zocor",       "C10AA01", "Statin",             "tablet", "10-40mg/day", "10-20mg/day", "Start 5mg if CrCl<30", "Contraindicated in active hepatic disease"),
    ("ibuprofen",       "Brufen",       "Brufen",    "Brufen",      "M01AE01", "NSAID",              "tablet", "400-800mg TID", "Use lowest effective dose", "Avoid if CrCl<30", "Avoid in hepatic failure"),
    ("diclofenac",      "Voltarène",    "Voltarène", "Voltarène",   "M01AB05", "NSAID",              "tablet", "50mg TID", "Use lowest effective dose", "Avoid if CrCl<30", "Avoid in hepatic failure"),
    ("naproxen",        "Naprosyne",    "Naprosyne", "Naprosyne",   "M01AE02", "NSAID",              "tablet", "250-500mg BID", "Use lowest effective dose", "Avoid if CrCl<30", "Avoid in hepatic failure"),
    ("prednisolone",    "Solupred",     "Solupred",  "Solupred",    "H02AB06", "Corticosteroid",     "tablet", "5-60mg/day", "5-10mg/day", "No dose adjustment", "Caution"),
    ("amoxicillin",     "Clamoxyl",     "Clamoxyl",  "Clamoxyl",    "J01CA04", "Penicillin antibiotic","capsule","500mg TID","500mg TID","Reduce dose if CrCl<30","No dose adjustment"),
    ("ciprofloxacin",   "Ciflox",       "Ciflox",    "Ciflox",      "J01MA02", "Fluoroquinolone",    "tablet", "500mg BID", "250-500mg BID", "250-500mg BID if CrCl<30", "Caution"),
    ("metronidazole",   "Flagyl",       "Flagyl",    "Flagyl",      "J01XD01", "Nitroimidazole",     "tablet", "400-500mg TID", "400mg TID", "No dose adjustment", "Reduce dose in severe hepatic failure"),
    ("clarithromycin",  "Zeclar",       "Zeclar",    "Zeclar",      "J01FA09", "Macrolide antibiotic","tablet","500mg BID","500mg BID","250mg BID if CrCl<30","Caution"),
    ("fluconazole",     "Triflucan",    "Triflucan", "Triflucan",   "J02AC01", "Antifungal",         "capsule","150-400mg/day","150mg","50% dose reduction if CrCl<50","Caution"),
    ("carbamazepine",   "Tégrétol",     "Tégrétol",  "Tégrétol",    "N03AF01", "Anticonvulsant",     "tablet", "400-1200mg/day", "Start low, titrate", "Use with caution", "Caution"),
    ("valproate",       "Dépakine",     "Dépakine",  "Dépakine",    "N03AG01", "Anticonvulsant",     "tablet", "500-2000mg/day", "Start low", "No dose adjustment", "Contraindicated in hepatic failure"),
    ("fluoxetine",      "Prozac",       "Prozac",    "Prozac",      "N06AB03", "SSRI",               "capsule","20-60mg/day","20mg/day","No dose adjustment","Reduce dose or increase interval"),
    ("sertraline",      "Zoloft",       "Zoloft",    "Zoloft",      "N06AB06", "SSRI",               "tablet", "50-200mg/day", "25-100mg/day", "No dose adjustment", "Start low, titrate slowly"),
    ("omeprazole",      "Mopral",       "Mopral",    "Mopral",      "A02BC01", "PPI",                "capsule","20-40mg/day","20mg/day","No dose adjustment","Max 20mg/day in severe hepatic failure"),
    ("tramadol",        "Topalgic",     "Topalgic",  "Topalgic",    "N02AX02", "Opioid analgesic",   "tablet", "50-100mg q4-6h, max 400mg/day", "Max 300mg/day", "Extend dosing interval if CrCl<30", "Reduce dose in hepatic failure"),
]

for (inn, brand, brand_tn, brand_fr, atc, category, form,
     dose_adult, dose_elderly, dose_renal, dose_hepatic) in DRUGS:
    cur.execute("SELECT id FROM molecules WHERE inn = %s", (inn,))
    mol = cur.fetchone()
    if not mol:
        continue
    cur.execute("""
        INSERT INTO drugs (molecule_id, brand_name, brand_name_tn, brand_name_fr,
            atc_code, therapeutic_category, dosage_form,
            dose_adult, dose_elderly, dose_renal_impairment, dose_hepatic_impairment)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
    """, (mol[0], brand, brand_tn, brand_fr, atc, category, form,
          dose_adult, dose_elderly, dose_renal, dose_hepatic))

# ── contraindications ─────────────────────────────────────────────────────────
CONTRAINDICATIONS = [
    ("metformin",       "5A11",  "Chronic kidney disease stage 4-5", "Risk of lactic acidosis — do not use if eGFR<30 or creatinine >135μmol/L (men) / >110μmol/L (women)", "ANSM/OpenFDA"),
    ("warfarin",        "JA00",  "Pregnancy",                        "Teratogenic — causes warfarin embryopathy and fetal hemorrhage", "OpenFDA"),
    ("warfarin",        "DB94",  "Active bleeding",                  "Anticoagulation worsens active hemorrhage", "OpenFDA"),
    ("spironolactone",  "5C77",  "Hyperkalemia",                     "Potassium-sparing effect worsens hyperkalemia", "OpenFDA"),
    ("valproate",       "DB93",  "Hepatic failure",                  "Hepatotoxic — contraindicated in severe hepatic impairment", "OpenFDA"),
    ("atorvastatin",    "DB93",  "Active hepatic disease",           "Statins are hepatotoxic in active liver disease", "OpenFDA"),
    ("simvastatin",     "DB93",  "Active hepatic disease",           "Statins are hepatotoxic in active liver disease", "OpenFDA"),
    ("ibuprofen",       "5A11",  "Chronic kidney disease stage 4-5", "NSAIDs reduce renal perfusion — risk of acute kidney injury", "OpenFDA"),
    ("diclofenac",      "5A11",  "Chronic kidney disease stage 4-5", "NSAIDs reduce renal perfusion — risk of acute kidney injury", "OpenFDA"),
    ("naproxen",        "5A11",  "Chronic kidney disease stage 4-5", "NSAIDs reduce renal perfusion — risk of acute kidney injury", "OpenFDA"),
    ("glibenclamide",   "5A11",  "Chronic kidney disease stage 4-5", "Risk of prolonged hypoglycemia — renally cleared active metabolites", "OpenFDA"),
]

for (inn, icd11, condition, reason, source) in CONTRAINDICATIONS:
    cur.execute("""
        SELECT d.id FROM drugs d
        JOIN molecules m ON m.id = d.molecule_id
        WHERE m.inn = %s LIMIT 1
    """, (inn,))
    drug = cur.fetchone()
    if not drug:
        continue
    cur.execute("""
        INSERT INTO contraindications (drug_id, condition_icd11, condition_name, reason, source)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
    """, (drug[0], icd11, condition, reason, source))

# allergy groups
allergy_groups_path = os.path.join(CLEAN_DIR, "allergy_groups_clean.csv")
if os.path.exists(allergy_groups_path):
    with open(allergy_groups_path, newline="", encoding="utf-8-sig") as f:
        allergy_groups = [
            (row["name"], row.get("description", ""))
            for row in csv.DictReader(f)
        ]
else:
    allergy_groups = [
        ("Penicillins", "Penicillin beta-lactam antibiotics"),
        ("NSAIDs", "Non-steroidal anti-inflammatory drugs"),
        ("Statins", "HMG-CoA reductase inhibitors (statins)"),
    ]

for name, desc in allergy_groups:
    cur.execute("""
        INSERT INTO allergy_groups (name, description)
        VALUES (%s, %s)
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
    """, (name, desc))

# allergy cross-reactivity pairs
cross_path = os.path.join(CLEAN_DIR, "allergy_cross_reactivities_clean.csv")
if os.path.exists(cross_path):
    with open(cross_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cur.execute("SELECT id FROM allergy_groups WHERE name = %s", (row["group_a"],))
            group_a = cur.fetchone()
            cur.execute("SELECT id FROM allergy_groups WHERE name = %s", (row["group_b"],))
            group_b = cur.fetchone()
            if not group_a or not group_b:
                continue

            cur.execute("""
                INSERT INTO allergy_cross_reactivities (group_a_id, group_b_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (group_a[0], group_b[0]))

            if row.get("direction") == "bidirectional":
                cur.execute("""
                    INSERT INTO allergy_cross_reactivities (group_a_id, group_b_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (group_b[0], group_a[0]))

# drug allergy group links
drug_allergies_path = os.path.join(CLEAN_DIR, "drug_allergy_groups_clean.csv")
if os.path.exists(drug_allergies_path):
    with open(drug_allergies_path, newline="", encoding="utf-8-sig") as f:
        drug_allergies = [
            (row["canonical_inn"], row["allergy_group"])
            for row in csv.DictReader(f)
        ]
else:
    drug_allergies = [
        ("amoxicillin", "Penicillins"),
        ("aspirin", "NSAIDs"),
        ("ibuprofen", "NSAIDs"),
        ("diclofenac", "NSAIDs"),
        ("naproxen", "NSAIDs"),
        ("atorvastatin", "Statins"),
        ("simvastatin", "Statins"),
    ]

for inn, group_name in drug_allergies:
    cur.execute("SELECT id FROM allergy_groups WHERE name = %s", (group_name,))
    group_row = cur.fetchone()
    if not group_row:
        continue
    group_id = group_row[0]

    cur.execute("""
        SELECT d.id FROM drugs d
        JOIN molecules m ON m.id = d.molecule_id
        WHERE m.inn = %s
    """, (inn,))
    for drug_row in cur.fetchall():
        cur.execute("""
            INSERT INTO drug_allergy_groups (drug_id, allergy_group_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (drug_row[0], group_id))

conn.commit()
cur.execute("SELECT count(*) FROM drugs")
print(f"Drugs loaded: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM contraindications")
print(f"Contraindications loaded: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM allergy_groups")
print(f"Allergy groups loaded: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM drug_allergy_groups")
print(f"Drug allergy group links loaded: {cur.fetchone()[0]}")
cur.execute("SELECT count(*) FROM allergy_cross_reactivities")
print(f"Allergy cross-reactivities loaded: {cur.fetchone()[0]}")

cur.close()
conn.close()

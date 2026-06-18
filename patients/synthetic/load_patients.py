"""
MedFlow — Synthetic patient loader
Inserts: allergy_groups, allergy_cross_reactivities, drug_allergy_groups,
         8 trap patients + 22 regular patients with meds, labs, conditions, allergies.
"""

import psycopg2
from datetime import date, datetime

DB = dict(host="localhost", port=5432, dbname="medflow", user="medflow", password="medflow")

# ── IDs resolved from DB ─────────────────────────────────────────────────────
# molecules
M_WARFARIN       = 1
M_ASPIRIN        = 3
M_METFORMIN      = 5
M_ATORVASTATIN   = 14
M_SIMVASTATIN    = 15
M_AMOXICILLIN    = 20
M_CIPROFLOXACIN  = 21
M_CLARITHROMYCIN = 23
M_FLUCONAZOLE    = 24
M_FLUOXETINE     = 27
M_TRAMADOL       = 30

# drugs (prefer branded Tunisian entry)
D_WARFARIN       = 1    # Coumadin
D_ASPIRIN        = 3    # Aspégic
D_METFORMIN      = 5    # Glucophage
D_ATORVASTATIN   = 14   # Tahor
D_SIMVASTATIN    = 15   # Zocor
D_AMOXICILLIN    = 20   # Clamoxyl
D_CIPROFLOXACIN  = 21   # Ciflox
D_CLARITHROMYCIN = 23   # Zeclar
D_FLUCONAZOLE    = 24   # Triflucan
D_FLUOXETINE     = 27   # Prozac
D_TRAMADOL       = 30   # Topalgic

LOINC_CREATININE = "2160-0"

def run():
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    # ── 1. Allergy groups ────────────────────────────────────────────────────
    allergy_groups = [
        ("penicillin",    "Penicillin-class antibiotics"),
        ("cephalosporin", "Cephalosporin-class antibiotics"),
        ("sulfonamide",   "Sulfonamide antibiotics"),
        ("nsaid",         "Non-steroidal anti-inflammatory drugs"),
    ]
    ag_ids = {}
    for name, desc in allergy_groups:
        cur.execute(
            "INSERT INTO allergy_groups (name, description) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET description=EXCLUDED.description "
            "RETURNING id",
            (name, desc)
        )
        ag_ids[name] = cur.fetchone()[0]

    # penicillin <-> cephalosporin partial cross-reactivity
    pen_id  = ag_ids["penicillin"]
    ceph_id = ag_ids["cephalosporin"]
    cur.execute(
        "INSERT INTO allergy_cross_reactivities (group_a_id, group_b_id) "
        "VALUES (%s, %s), (%s, %s) ON CONFLICT DO NOTHING",
        (pen_id, ceph_id, ceph_id, pen_id)
    )

    # amoxicillin -> penicillin group
    cur.execute(
        "INSERT INTO drug_allergy_groups (drug_id, allergy_group_id) "
        "VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (D_AMOXICILLIN, pen_id)
    )
    conn.commit()
    print(f"Allergy groups: {ag_ids}")

    # ── helpers ──────────────────────────────────────────────────────────────
    def add_patient(name, dob, sex, weight_kg, is_trap=False, trap_scenario=None):
        cur.execute(
            "INSERT INTO patients (name, dob, sex, weight_kg, is_trap, trap_scenario) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (name, dob, sex, weight_kg, is_trap, trap_scenario)
        )
        return cur.fetchone()[0]

    def add_med(patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date):
        cur.execute(
            "INSERT INTO active_medications "
            "(patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (patient_id, drug_id, rxnorm_cui, dose_mg, frequency, start_date)
        )

    def add_lab(patient_id, loinc, name, value, unit, ts=None):
        cur.execute(
            "INSERT INTO lab_results (patient_id, loinc_code, test_name, value, unit, collected_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (patient_id, loinc, name, value, unit, ts or datetime(2026, 6, 1))
        )

    def add_condition(patient_id, icd11, name, onset=date(2023, 1, 1)):
        cur.execute(
            "INSERT INTO conditions (patient_id, icd11_code, condition_name, onset_date) "
            "VALUES (%s,%s,%s,%s)",
            (patient_id, icd11, name, onset)
        )

    def add_allergy(patient_id, group_name, reaction_type, documented_at=date(2022, 1, 1)):
        cur.execute(
            "INSERT INTO allergies (patient_id, allergy_group_id, reaction_type, documented_at) "
            "VALUES (%s,%s,%s,%s)",
            (patient_id, ag_ids[group_name], reaction_type, documented_at)
        )

    # ── 2. TRAP PATIENTS ────────────────────────────────────────────────────

    # Trap 1 — warfarin + aspirin
    p = add_patient("Karim Ben Salah", date(1958, 4, 12), "M", 74, True, "warfarin_aspirin")
    add_condition(p, "BA80", "Atrial fibrillation")
    add_med(p, D_WARFARIN, "11289", 5, "once daily", date(2025, 3, 1))
    add_lab(p, "6301-6", "INR", 2.4, "ratio")          # therapeutic range
    add_lab(p, LOINC_CREATININE, "Creatinine", 88, "umol/L")

    # Trap 2 — metformin + CKD stage 4
    p = add_patient("Fatma Trabelsi", date(1963, 9, 5), "F", 68, True, "metformin_ckd")
    add_condition(p, "5A10", "Type 2 diabetes mellitus")
    add_condition(p, "GB61", "Chronic kidney disease stage 4")
    add_med(p, D_METFORMIN, "6809", 1000, "twice daily", date(2024, 1, 10))
    add_lab(p, LOINC_CREATININE, "Creatinine", 180, "umol/L")

    # Trap 3 — simvastatin + clarithromycin
    p = add_patient("Nabil Chaabane", date(1970, 6, 20), "M", 82, True, "simvastatin_clarity")
    add_condition(p, "BA80.1", "Hyperlipidaemia")
    add_med(p, D_SIMVASTATIN, "36567", 40, "once daily at night", date(2024, 6, 1))
    add_lab(p, LOINC_CREATININE, "Creatinine", 78, "umol/L")

    # Trap 4 — penicillin allergy + amoxicillin trigger
    p = add_patient("Amira Khelifi", date(1990, 2, 14), "F", 58, True, "penicillin_allergy")
    add_allergy(p, "penicillin", "anaphylaxis", date(2015, 5, 20))
    add_lab(p, LOINC_CREATININE, "Creatinine", 72, "umol/L")

    # Trap 5 — fluoxetine + tramadol (serotonin syndrome)
    p = add_patient("Sonia Mansouri", date(1985, 11, 3), "F", 63, True, "serotonin_syndrome")
    add_condition(p, "6A70", "Depressive disorder")
    add_med(p, D_FLUOXETINE, "41493", 20, "once daily", date(2025, 1, 15))
    add_lab(p, LOINC_CREATININE, "Creatinine", 74, "umol/L")

    # Trap 6 — elderly dose (ciprofloxacin)
    p = add_patient("Hédi Boughanmi", date(1948, 3, 7), "M", 52, True, "elderly_dose")
    add_condition(p, "MG31", "Urinary tract infection")
    add_lab(p, LOINC_CREATININE, "Creatinine", 105, "umol/L")

    # Trap 7 — CYP2C9 overload (warfarin + fluconazole)
    p = add_patient("Mariem Ayari", date(1966, 7, 19), "F", 70, True, "cyp2c9_overload")
    add_condition(p, "BA80", "Atrial fibrillation")
    add_med(p, D_WARFARIN, "11289", 5, "once daily", date(2025, 2, 1))
    add_med(p, D_FLUCONAZOLE, "4450", 150, "once weekly", date(2026, 5, 10))
    add_lab(p, "6301-6", "INR", 2.1, "ratio")
    add_lab(p, LOINC_CREATININE, "Creatinine", 82, "umol/L")

    # Trap 8 — therapeutic duplication (Tahor already; new script says "atorvastatin 20mg")
    p = add_patient("Riadh Jebali", date(1972, 8, 25), "M", 88, True, "therapeutic_dup")
    add_condition(p, "BA80.1", "Hyperlipidaemia")
    add_med(p, D_ATORVASTATIN, "83367", 20, "once daily", date(2025, 9, 1))
    add_lab(p, LOINC_CREATININE, "Creatinine", 85, "umol/L")

    conn.commit()
    print("Trap patients inserted: 8")

    # ── 3. REGULAR PATIENTS (22) ────────────────────────────────────────────
    regular = [
        # (name, dob, sex, weight, conditions, meds, creatinine)
        # meds: list of (drug_id, rxnorm, dose, freq)
        ("Imen Baccar",      date(1995,3,15),  "F", 60,
         [("6A70","Depressive disorder")],
         [(D_FLUOXETINE,"41493",20,"once daily")], 70),

        ("Mohamed Ferchichi",date(1955,7,4),   "M", 78,
         [("BA00","Essential hypertension")],
         [], 90),

        ("Najet Bouzid",     date(1968,12,20), "F", 65,
         [("5A10","Type 2 diabetes"),("BA00","Hypertension")],
         [(D_METFORMIN,"6809",500,"twice daily")], 82),

        ("Tarek Hammami",    date(1980,5,10),  "M", 90,
         [("BA80.1","Hyperlipidaemia")],
         [(D_ATORVASTATIN,"83367",10,"once daily")], 88),

        ("Leila Saidani",    date(1943,1,28),  "F", 54,
         [("BA00","Hypertension"),("5A10","Type 2 diabetes")],
         [(D_METFORMIN,"6809",500,"once daily")], 98),

        ("Youssef Laabidi",  date(1988,9,9),   "M", 76,
         [],
         [], 76),

        ("Khaoula Meddeb",   date(1975,4,6),   "F", 67,
         [("CA22","Asthma")],
         [], 78),

        ("Slim Belhadj",     date(1960,11,14), "M", 83,
         [("BA00","Hypertension"),("BA80","Atrial fibrillation")],
         [(D_WARFARIN,"11289",3,"once daily"),
          (D_ASPIRIN,"3498",100,"once daily")], 92),  # intentional — no trap flag

        ("Asma Dridi",       date(1992,6,30),  "F", 55,
         [("6A70","Depressive disorder")],
         [], 68),

        ("Hassen Oueslati",  date(1950,2,17),  "M", 72,
         [("BA00","Hypertension"),("5A10","Diabetes"),("BA80.1","Hyperlipidaemia")],
         [(D_SIMVASTATIN,"36567",20,"once daily"),
          (D_METFORMIN,"6809",1000,"twice daily")], 102),

        ("Wafa Ben Romdhane",date(1983,8,22),  "F", 61,
         [("CA22","Asthma")],
         [], 73),

        ("Bilel Nouri",      date(1965,3,3),   "M", 80,
         [("BA00","Hypertension")],
         [], 86),

        ("Sihem Achour",     date(1970,10,11), "F", 69,
         [("5A10","Diabetes"),("BA80.1","Hyperlipidaemia")],
         [(D_ATORVASTATIN,"83367",20,"once daily"),
          (D_METFORMIN,"6809",500,"once daily")], 80),

        ("Mondher Ghazali",  date(1945,5,19),  "M", 68,
         [("BA00","Hypertension"),("5A10","Diabetes"),("CA22","Asthma")],
         [(D_METFORMIN,"6809",500,"twice daily"),
          (D_CIPROFLOXACIN,"2551",500,"twice daily")], 110),

        ("Rim Zaghbani",     date(1998,1,5),   "F", 57,
         [],
         [], 65),

        ("Fares Cherif",     date(1987,12,12), "M", 77,
         [("BA80.1","Hyperlipidaemia")],
         [(D_SIMVASTATIN,"36567",20,"once daily")], 79),

        ("Hana Khalfallah",  date(1955,9,25),  "F", 62,
         [("BA00","Hypertension"),("5A10","Diabetes"),("BA80","Atrial fibrillation")],
         [(D_WARFARIN,"11289",4,"once daily"),
          (D_METFORMIN,"6809",500,"once daily")], 95),

        ("Adel Ouerghi",     date(1978,7,7),   "M", 85,
         [("BA00","Hypertension")],
         [], 84),

        ("Salwa Benhassen",  date(1962,4,16),  "F", 73,
         [("5A10","Diabetes"),("BA80.1","Hyperlipidaemia"),("BA00","Hypertension")],
         [(D_ATORVASTATIN,"83367",40,"once daily"),
          (D_METFORMIN,"6809",1000,"twice daily")], 97),

        ("Ramzi Baccouche",  date(1940,6,8),   "M", 65,
         [("BA00","Hypertension"),("BA80","Atrial fibrillation")],
         [(D_WARFARIN,"11289",2.5,"once daily")], 112),

        ("Dorra Mejri",      date(2000,11,30), "F", 52,
         [],
         [], 66),

        ("Lotfi Brahmi",     date(1968,8,1),   "M", 79,
         [("5A10","Diabetes"),("BA80.1","Hyperlipidaemia"),("CA22","Asthma")],
         [(D_METFORMIN,"6809",850,"twice daily"),
          (D_SIMVASTATIN,"36567",40,"once daily"),
          (D_CIPROFLOXACIN,"2551",250,"once daily")], 91),
    ]

    for (name, dob, sex, weight, conds, meds, creat) in regular:
        p = add_patient(name, dob, sex, weight)
        for icd, cname in conds:
            add_condition(p, icd, cname)
        for drug_id, rxnorm, dose, freq in meds:
            add_med(p, drug_id, rxnorm, dose, freq, date(2025, 1, 1))
        add_lab(p, LOINC_CREATININE, "Creatinine", creat, "umol/L")

    conn.commit()
    print("Regular patients inserted: 22")
    print("Total patients: 30")

    cur.execute("SELECT COUNT(*) FROM patients")
    print(f"DB count: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run()
